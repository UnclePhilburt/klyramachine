"""Klyra Display — full-screen multi-app launcher.

iOS/Android-style home screen with app tiles. Tap an app to open it.
Run with: python klyra_display.py
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configure QtWebEngine BEFORE QApplication is constructed.
#  - widevine-path: required for Spotify Web Player to actually play audio.
#    Install Widevine with: ./download_widevine.sh
#  - disable-features=Vulkan: AMD GPUs (Navi 21 / RX 6800 etc.) trigger a
#    flood of "Trying to Produce a Skia representation from a non-existent
#    mailbox" errors with Chromium's Vulkan path. Forcing GL backend fixes it.
#  - disable-gpu-compositing: belt-and-braces for the same compositor issue.
#  - ignore-gpu-blocklist: Chromium blocks acceleration on some AMD/Linux
#    combos by default; we want hardware video decode for smooth playback.
_WV = "/opt/google/chrome/WidevineCdm/_platform_specific/linux_x64/libwidevinecdm.so"
_FLAGS = [
    "--disable-features=Vulkan",
    "--disable-gpu-compositing",
    "--ignore-gpu-blocklist",
]
if os.path.exists(_WV):
    _FLAGS.append(f"--widevine-path={_WV}")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", " ".join(_FLAGS))

from PyQt6.QtCore import Qt, QSize, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPalette, QImage, QPixmap, QCursor,
)
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout,
    QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

# Settings UI is reused as one of the apps.
from settings_app import (
    SettingsWindow, OnboardingWizard, needs_onboarding, apply_theme,
    ACCENT, ACCENT_DARK, BG, SURFACE, BORDER, TEXT, MUTED, SUBTLE,
)

CLIENT_DIR = Path(__file__).parent
WEB_DATA = CLIENT_DIR / "webengine_data"


# ============================================================================
# App tile definitions — the launcher's home grid
# ============================================================================
# Each tile: (id, label, emoji, gradient_top, gradient_bottom)
# id == "coming_soon" → tile is a placeholder, can't be opened
APPS = [
    ("settings", "Settings", "⚙",  "#FF6B47", "#FF9472"),
    ("music",    "Music",    "🎵", "#1DB954", "#1ED760"),  # Spotify green
    ("camera",   "Camera",   "📷", "#3B82F6", "#60A5FA"),
    ("weather",  "Weather",  "☀",  "#F59E0B", "#FBBF24"),  # placeholder
    ("news",     "News",     "📰", "#6366F1", "#818CF8"),  # placeholder
    ("calendar", "Calendar", "📅", "#EC4899", "#F472B6"),  # placeholder
    ("home_hub", "Home",     "🏡", "#14B8A6", "#2DD4BF"),  # placeholder for HA etc.
    ("about",    "About",    "ℹ",  "#8B5CF6", "#A78BFA"),
]

# Apps wired up in this build. Everything else is "coming soon".
ENABLED_APPS = {"settings", "music", "camera", "about"}


def add_shadow(widget: QWidget, blur=24, offset_y=4, color=QColor(0, 0, 0, 40)):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, offset_y)
    eff.setColor(color)
    widget.setGraphicsEffect(eff)


# ============================================================================
# App tile widget (clickable rounded squircle on the home grid)
# ============================================================================

class AppTile(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, app_id: str, label: str, emoji: str,
                 grad_top: str, grad_bottom: str, enabled: bool, parent=None):
        super().__init__(parent)
        self.app_id = app_id
        self._enabled_app = enabled
        self.setFixedSize(140, 170)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ForbiddenCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Icon square (gradient background, emoji centered)
        icon = QLabel(emoji)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(48)
        icon.setFont(f)
        icon.setFixedSize(120, 120)
        opacity = "1.0" if enabled else "0.45"
        icon.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {grad_top}, stop: 1 {grad_bottom}
                );
                border-radius: 28px;
                color: white;
            }}
        """)
        # iOS-y soft shadow under the icon
        if enabled:
            add_shadow(icon, blur=22, offset_y=6, color=QColor(0, 0, 0, 50))
        else:
            icon.setGraphicsEffect(None)
            # Subtle desaturate via outer opacity widget? Easiest: reduce shadow.
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)

        # Label below
        text = QLabel(label)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lf = QFont()
        lf.setPointSize(11)
        lf.setWeight(QFont.Weight.Medium)
        text.setFont(lf)
        text.setStyleSheet(
            f"color: {TEXT};" if enabled else f"color: {MUTED};"
        )
        layout.addWidget(text)

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._enabled_app
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit(self.app_id)
        super().mouseReleaseEvent(event)


# ============================================================================
# Home screen (the launcher itself)
# ============================================================================

class HomeScreen(QWidget):
    app_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 32, 48, 32)
        outer.setSpacing(20)

        # Greeting (will be updated on showEvent)
        self.greeting = QLabel("Hi there")
        gf = QFont()
        gf.setPointSize(36)
        gf.setWeight(QFont.Weight.Bold)
        self.greeting.setFont(gf)
        self.greeting.setStyleSheet(f"color: {TEXT};")
        outer.addWidget(self.greeting)

        sub = QLabel("Tap an app to get started.")
        sf = QFont()
        sf.setPointSize(13)
        sub.setFont(sf)
        sub.setStyleSheet(f"color: {MUTED};")
        outer.addWidget(sub)
        outer.addSpacing(16)

        # App grid: 4 columns
        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(28)
        grid.setContentsMargins(0, 0, 0, 0)
        cols = 4
        for i, (app_id, label, emoji, gt, gb) in enumerate(APPS):
            tile = AppTile(app_id, label, emoji, gt, gb,
                          enabled=app_id in ENABLED_APPS)
            tile.clicked.connect(self.app_requested.emit)
            grid.addWidget(tile, i // cols, i % cols)
        # Push tiles to the left
        grid.setColumnStretch(cols, 1)
        outer.addWidget(grid_wrap, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch()

    def update_greeting(self, name: str):
        self.greeting.setText(f"Hi, {name}" if name else "Hi there")


# ============================================================================
# Music app — launches Spotify in Chrome --app mode
# ============================================================================
# QtWebEngine ships without proprietary codecs (AAC etc.) so Spotify can't
# actually play audio when embedded. Workaround: spawn Google Chrome (which
# we already install for Widevine) in --app mode pointed at the Web Player.
# Chrome has every codec, so playback just works. Klyra still owns the
# launcher; Chrome runs as its own window. Killed when the user returns home.

CHROME_DATA = CLIENT_DIR / "chrome_data"  # persistent Spotify login
SPOTIFY_URL = "https://open.spotify.com"


def _find_chrome() -> str | None:
    """Locate a Chrome/Chromium binary. Returns absolute path or None."""
    for name in ("google-chrome-stable", "google-chrome", "chromium-browser",
                 "chromium", "/opt/google/chrome/chrome"):
        path = shutil.which(name) if "/" not in name else (name if os.path.isfile(name) else None)
        if path:
            return path
    return None


class MusicApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: subprocess.Popen | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 32)
        layout.setSpacing(16)

        title = QLabel("🎵  Music")
        tf = QFont()
        tf.setPointSize(28)
        tf.setWeight(QFont.Weight.Bold)
        title.setFont(tf)
        title.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(title)

        sub = QLabel("Spotify opens in its own window.")
        sf = QFont()
        sf.setPointSize(13)
        sub.setFont(sf)
        sub.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(sub)
        layout.addSpacing(8)

        # Big Spotify-green status card
        self.status_card = QFrame()
        self.status_card.setObjectName("musicStatusCard")
        self.status_card.setStyleSheet("""
            QFrame#musicStatusCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1DB954, stop: 1 #1ED760
                );
                border-radius: 20px;
            }
            QLabel { color: white; }
        """)
        card_layout = QVBoxLayout(self.status_card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(8)

        emoji = QLabel("🎶")
        ef = QFont()
        ef.setPointSize(64)
        emoji.setFont(ef)
        emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(emoji)

        self.status_label = QLabel("Tap below to open Spotify")
        slf = QFont()
        slf.setPointSize(18)
        slf.setWeight(QFont.Weight.DemiBold)
        self.status_label.setFont(slf)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.status_label)

        self.status_hint = QLabel("Audio plays through this device.")
        shf = QFont()
        shf.setPointSize(12)
        self.status_hint.setFont(shf)
        self.status_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.status_hint)
        card_layout.addStretch()

        layout.addWidget(self.status_card, 1)

        # Open / Close buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.open_btn = QPushButton("▶  Open Spotify")
        self.open_btn.setObjectName("saveBtn")
        self.open_btn.setMinimumHeight(48)
        self.open_btn.setMinimumWidth(180)
        self.open_btn.clicked.connect(self._launch_chrome)
        btn_row.addWidget(self.open_btn)

        self.close_btn = QPushButton("Close Spotify")
        self.close_btn.setObjectName("ghostBtn")
        self.close_btn.setMinimumHeight(48)
        self.close_btn.setMinimumWidth(160)
        self.close_btn.clicked.connect(self._kill_chrome)
        self.close_btn.setVisible(False)
        btn_row.addWidget(self.close_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Periodic check: did the user close Chrome from outside?
        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._poll_process)

    def _launch_chrome(self):
        binary = _find_chrome()
        if not binary:
            self.status_label.setText("Chrome not installed")
            self.status_hint.setText("Run ./download_widevine.sh to install it.")
            return
        if self._process and self._process.poll() is None:
            return  # already running
        CHROME_DATA.mkdir(exist_ok=True)
        try:
            self._process = subprocess.Popen([
                binary,
                f"--app={SPOTIFY_URL}",
                f"--user-data-dir={CHROME_DATA}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=Translate",
            ])
        except Exception as e:
            self.status_label.setText("Failed to open Spotify")
            self.status_hint.setText(str(e))
            return

        self.status_label.setText("Spotify is open")
        self.status_hint.setText("It runs in its own window. Use Home to close.")
        self.open_btn.setVisible(False)
        self.close_btn.setVisible(True)
        self._poll.start()

    def _kill_chrome(self):
        if self._process is None or self._process.poll() is not None:
            self._reset_status()
            return
        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
        except Exception:
            pass
        self._process = None
        self._reset_status()

    def _reset_status(self):
        self._poll.stop()
        self.status_label.setText("Tap below to open Spotify")
        self.status_hint.setText("Audio plays through this device.")
        self.open_btn.setVisible(True)
        self.close_btn.setVisible(False)

    def _poll_process(self):
        # If Chrome was closed by the user (window X / OS), reset our UI.
        if self._process is None or self._process.poll() is not None:
            self._process = None
            self._reset_status()

    # Music persists across navigation. Tapping Home should NOT kill
    # Spotify — only an explicit Close button or full launcher exit does.
    # That's why MusicApp has no start()/stop() hooks (which the launcher
    # auto-fires on enter/leave). It only has shutdown(), called from the
    # main window's closeEvent.
    def shutdown(self):
        self._kill_chrome()


# ============================================================================
# Camera app — live preview from the local camera
# ============================================================================

class CameraApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 32)
        layout.setSpacing(16)

        title = QLabel("Camera")
        tf = QFont()
        tf.setPointSize(28)
        tf.setWeight(QFont.Weight.Bold)
        title.setFont(tf)
        title.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(title)

        sub = QLabel("Live view of what Klyra sees.")
        sf = QFont()
        sf.setPointSize(13)
        sub.setFont(sf)
        sub.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(sub)

        self.frame_label = QLabel("Camera off")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setMinimumHeight(360)
        self.frame_label.setStyleSheet(
            f"background: {SUBTLE}; border-radius: 16px; "
            f"color: {MUTED}; font-size: 14px;"
        )
        layout.addWidget(self.frame_label, 1)

        self._capture = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        try:
            import cv2
            self._capture = cv2.VideoCapture(0)
            if not self._capture.isOpened():
                raise RuntimeError("camera unavailable")
            self.frame_label.setText("Loading…")
            self._timer.start(67)  # ~15 FPS
        except Exception as e:
            self.frame_label.setText(
                f"Camera unavailable\n({e}) — Klyra may be running."
            )
            self._capture = None

    def stop(self):
        self._timer.stop()
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        self.frame_label.clear()
        self.frame_label.setText("Camera off")

    def _tick(self):
        if self._capture is None:
            return
        import cv2
        ok, frame = self._capture.read()
        if not ok:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        scaled = qimg.scaledToWidth(
            self.frame_label.width(),
            Qt.TransformationMode.SmoothTransformation,
        )
        self.frame_label.setPixmap(QPixmap.fromImage(scaled))
        self.frame_label.setText("")


# ============================================================================
# Settings app — embeds the existing SettingsWindow's central widget
# ============================================================================

class SettingsApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Construct the existing SettingsWindow, then steal its central widget.
        # SettingsWindow stays alive (it owns load/save/preview state); we just
        # display its UI inside our launcher.
        self._sw = SettingsWindow()
        central = self._sw.centralWidget()
        # Detach — give the SettingsWindow a fresh empty central so it doesn't
        # try to delete what we're about to embed.
        self._sw.setCentralWidget(QWidget())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(central)

    def closeEvent(self, event):
        try:
            self._sw.close()
        except Exception:
            pass
        super().closeEvent(event)


# ============================================================================
# About app — version, credits, restart hint
# ============================================================================

class AboutApp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(20)

        title = QLabel("ℹ  About Klyra")
        tf = QFont()
        tf.setPointSize(28)
        tf.setWeight(QFont.Weight.Bold)
        title.setFont(tf)
        title.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(title)

        body = QLabel(
            "Klyra is a sarcastic AI companion that can see and hear you.\n\n"
            "Voice: Kokoro (local)\n"
            "Brain: Mistral Small 22B (local)\n"
            "Vision: Qwen2.5-VL 3B (local)\n"
            "Wake word: Vosk (local)\n\n"
            "Everything runs on this machine — no cloud."
        )
        bf = QFont()
        bf.setPointSize(13)
        body.setFont(bf)
        body.setStyleSheet(f"color: {TEXT};")
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch()

        version = QLabel("v0.1.0")
        vf = QFont()
        vf.setPointSize(11)
        version.setFont(vf)
        version.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(version)


# ============================================================================
# Top status bar — clock + back button when inside an app
# ============================================================================

class TopBar(QFrame):
    home_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setStyleSheet(f"""
            QFrame {{
                background: {SURFACE};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        self.back_btn = QPushButton("←  Home")
        self.back_btn.setObjectName("backBtn")
        self.back_btn.setMinimumHeight(36)
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.home_clicked.emit)
        self.back_btn.setVisible(False)
        layout.addWidget(self.back_btn)
        layout.addStretch()

        self.title = QLabel("Klyra")
        tf = QFont()
        tf.setPointSize(13)
        tf.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(tf)
        self.title.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(self.title)
        layout.addStretch()

        self.clock = QLabel("")
        cf = QFont()
        cf.setPointSize(13)
        cf.setWeight(QFont.Weight.Medium)
        self.clock.setFont(cf)
        self.clock.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(self.clock)

        # Tick every 30 seconds so the minute is always within ~30s of correct.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(30 * 1000)
        self._update_clock()

    def _update_clock(self):
        from datetime import datetime
        self.clock.setText(datetime.now().strftime("%H:%M"))

    def show_back(self, app_label: str):
        self.back_btn.setVisible(True)
        self.title.setText(app_label)

    def show_home(self):
        self.back_btn.setVisible(False)
        self.title.setText("Klyra")


# ============================================================================
# Main display window (the launcher shell)
# ============================================================================

class KlyraDisplay(QMainWindow):
    APP_LABELS = {a[0]: a[1] for a in APPS}

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Klyra")
        self.resize(1100, 760)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar = TopBar()
        self.topbar.home_clicked.connect(self._go_home)
        root.addWidget(self.topbar)

        # Stacked apps. Index 0 is the home screen; the rest are real apps.
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {BG};")

        self.home = HomeScreen()
        self.home.app_requested.connect(self._launch_app)
        self.stack.addWidget(self.home)

        # Lazy: build apps up front but only camera needs lifecycle handling.
        self.apps: dict[str, QWidget] = {}
        self._build_apps()

        root.addWidget(self.stack, 1)

        self._refresh_greeting()

    def _build_apps(self):
        # Settings
        self.settings_app = SettingsApp()
        self.stack.addWidget(self.settings_app)
        self.apps["settings"] = self.settings_app

        # Music (Spotify embed)
        self.music_app = MusicApp()
        self.stack.addWidget(self.music_app)
        self.apps["music"] = self.music_app

        # Camera
        self.camera_app = CameraApp()
        self.stack.addWidget(self.camera_app)
        self.apps["camera"] = self.camera_app

        # About
        self.about_app = AboutApp()
        self.stack.addWidget(self.about_app)
        self.apps["about"] = self.about_app

    def _refresh_greeting(self):
        """Pull user_name from config so the launcher greets them by name."""
        try:
            with open(CLIENT_DIR / "config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.home.update_greeting(cfg.get("user_name", "").strip())
        except Exception:
            pass

    def _launch_app(self, app_id: str):
        if app_id not in self.apps:
            return  # placeholder / not enabled
        widget = self.apps[app_id]
        # Lifecycle: start camera/music when entered
        if hasattr(widget, "start") and callable(widget.start):
            widget.start()
        self.stack.setCurrentWidget(widget)
        self.topbar.show_back(self.APP_LABELS.get(app_id, "App"))

    def _go_home(self):
        # Lifecycle: stop whichever app is currently in front
        current = self.stack.currentWidget()
        if hasattr(current, "stop") and callable(current.stop):
            try:
                current.stop()
            except Exception:
                pass
        self.stack.setCurrentWidget(self.home)
        self.topbar.show_home()
        self._refresh_greeting()  # pick up name changes from settings

    def closeEvent(self, event):
        # Full launcher exit: tear down everything. Apps expose shutdown()
        # for "the whole launcher is closing, kill subprocesses" — distinct
        # from stop() which is "user navigated away from this tab."
        for app in self.apps.values():
            for method_name in ("shutdown", "stop"):
                method = getattr(app, method_name, None)
                if callable(method):
                    try:
                        method()
                    except Exception:
                        pass
                    break
        try:
            self.settings_app.close()
        except Exception:
            pass
        super().closeEvent(event)


# ============================================================================
# Entry point
# ============================================================================

def apply_launcher_theme(app: QApplication):
    """Inherit the settings_app theme, then add launcher-specific styles."""
    apply_theme(app)
    extra = f"""
        QPushButton#backBtn {{
            background: transparent;
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 18px;
            padding: 4px 14px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton#backBtn:hover {{
            background: {SUBTLE};
        }}
    """
    app.setStyleSheet(app.styleSheet() + extra)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_launcher_theme(app)

    if needs_onboarding():
        wizard = OnboardingWizard()
        wizard.exec()

    win = KlyraDisplay()
    win.show()
    sys.exit(app.exec())
