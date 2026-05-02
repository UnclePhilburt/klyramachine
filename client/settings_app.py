"""Klyra Settings — native PyQt6 app.

Touch-first design: big targets, card-based, light theme, coral accent.
Run with: python settings_app.py
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QImage, QPainter, QPalette, QFont, QFontDatabase, QBrush, QPen,
    QPainterPath, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDialog, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QStackedWidget, QStatusBar,
    QVBoxLayout, QWidget,
)

CLIENT_DIR = Path(__file__).parent
CONFIG_PATH = CLIENT_DIR / "config.json"
KOKORO_MODEL = CLIENT_DIR / "kokoro" / "kokoro-v1.0.onnx"
KOKORO_VOICES_BIN = CLIENT_DIR / "kokoro" / "voices-v1.0.bin"
HISTORY_DIR = CLIENT_DIR / "history"

# ============================================================================
# Theme
# ============================================================================
ACCENT      = "#FF6B47"      # coral — the Klyra color
ACCENT_DARK = "#E5532D"
BG          = "#FAF9F7"      # warm off-white
SURFACE     = "#FFFFFF"
BORDER      = "#EAE7E2"
TEXT        = "#1A1F2E"
MUTED       = "#6B7280"
SUBTLE      = "#F3F1ED"
DANGER      = "#DC2626"

# Per-category tints for voice card backgrounds (when not selected)
CATEGORY_TINTS = {
    "American Female": "#FFE4E6",
    "American Male":   "#DBEAFE",
    "British Female":  "#F3E8FF",
    "British Male":    "#FEF3C7",
}

# ============================================================================
# Voice metadata
# ============================================================================
DISPLAY_NAMES = {
    "af_alloy": "Iris", "af_aoede": "Aria", "af_bella": "Bella",
    "af_heart": "Hazel", "af_jessica": "Jessica", "af_kore": "Cora",
    "af_nicole": "Nicole", "af_nova": "Nova", "af_river": "River",
    "af_sarah": "Sarah", "af_sky": "Skye",
    "am_adam": "Adam", "am_echo": "Ethan", "am_eric": "Eric",
    "am_fenrir": "Finn", "am_liam": "Liam", "am_michael": "Michael",
    "am_onyx": "Owen", "am_puck": "Parker", "am_santa": "Nick",
    "bf_alice": "Alice", "bf_emma": "Emma", "bf_isabella": "Isabella",
    "bf_lily": "Lily",
    "bm_daniel": "Daniel", "bm_fable": "Theo", "bm_george": "George",
    "bm_lewis": "Lewis",
}

CATEGORIES = [
    ("American Female", [
        "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
        "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    ]),
    ("American Male", [
        "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
        "am_michael", "am_onyx", "am_puck", "am_santa",
    ]),
    ("British Female", ["bf_alice", "bf_emma", "bf_isabella", "bf_lily"]),
    ("British Male", ["bm_daniel", "bm_fable", "bm_george", "bm_lewis"]),
]

PERSONALITY_PRESETS = {
    "Sassy": {
        "emoji": "😏",
        "tagline": "Witty, sharp, never holds back",
        "prompt": (
            "You are Klyra, a sarcastic but genuinely helpful AI companion. Think "
            "clever friend with dry wit — you bust the user's chops AND actually "
            "help them. When they ask a real question, ANSWER IT FIRST with real "
            "information, then slip in attitude. Don't dodge questions to be sassy. "
            "Be sharp, not a roast comic.\n\n"
            "You CAN see the user through their camera. When their message includes "
            "'[What you can see: ...]', that is a description of what your camera "
            "shows right now. Use that information to answer questions about their "
            "appearance, what they're wearing, what they're doing, or their "
            "surroundings. When no '[What you can see: ...]' is included, don't "
            "fabricate visual details.\n\n"
            "Keep responses SHORT and punchy — you're speaking out loud. Usually one "
            "or two sentences. NO stage directions in parentheses. Just say the words."
        ),
    },
    "Friendly": {
        "emoji": "☺️",
        "tagline": "Warm, upbeat, encouraging",
        "prompt": (
            "You are Klyra, a warm and friendly AI companion. You're upbeat, "
            "encouraging, and genuinely interested in what the user is up to — like "
            "a kind friend who lights up when they walk in. Be supportive without "
            "being saccharine.\n\n"
            "You CAN see the user through their camera. When their message includes "
            "'[What you can see: ...]', use that to comment naturally on what "
            "they're doing or notice things you'd notice as a friend. Don't "
            "fabricate visuals when no scene is provided.\n\n"
            "Keep responses SHORT — one or two sentences. NO stage directions. "
            "Speak naturally."
        ),
    },
    "Helpful": {
        "emoji": "💼",
        "tagline": "Direct, clear, useful",
        "prompt": (
            "You are Klyra, a helpful AI assistant. Direct, clear, and informative. "
            "Answer questions efficiently with real, useful information. Keep tone "
            "warm but minimal personality — focus on being useful.\n\n"
            "You CAN see the user through their camera. When '[What you can see: "
            "...]' is provided, use it to answer questions about their surroundings "
            "or what they're doing. Don't make up visual details when no scene is "
            "described.\n\n"
            "Keep responses SHORT — one or two sentences. NO stage directions. "
            "Speak naturally."
        ),
    },
    "Chill": {
        "emoji": "😎",
        "tagline": "Laid-back, easygoing, no rush",
        "prompt": (
            "You are Klyra, a chill, laid-back AI companion. Casual, easygoing, "
            "like talking to a friend on a Sunday afternoon. Take your time. Don't "
            "be pushy. Roll with whatever the user brings up.\n\n"
            "You CAN see the user through their camera. When '[What you can see: "
            "...]' is provided, comment on what you see in a relaxed way. Don't "
            "fabricate visuals when no scene is included.\n\n"
            "Keep responses SHORT — one or two sentences. NO stage directions. "
            "Speak naturally."
        ),
    },
}

PREVIEW_LINE = "Hi, I'm Klyra. This is what I sound like."

NAV_ITEMS = [
    ("🏠", "Home"),
    ("🎙", "Voice"),
    ("🎭", "Personality"),
    ("🔒", "Privacy"),
    ("👂", "Listening"),
]

# ============================================================================
# Helpers
# ============================================================================

def display_name(voice_id: str) -> str:
    if voice_id in DISPLAY_NAMES:
        return DISPLAY_NAMES[voice_id]
    return voice_id.split("_", 1)[1].replace("_", " ").title()


def category_for(voice_id: str) -> str:
    for cat, voices in CATEGORIES:
        if voice_id in voices:
            return cat
    return ""


def slider_to_speed(v: int) -> float:    return round(0.70 + (v / 100.0) * 0.70, 2)
def speed_to_slider(s: float) -> int:    return max(0, min(100, int(round((s - 0.70) / 0.70 * 100))))
def slider_to_threshold(v: int) -> int:  return int(round(2500 - (v / 100.0) * (2500 - 600)))
def threshold_to_slider(t: int) -> int:  return max(0, min(100, int(round((2500 - t) / (2500 - 600) * 100))))
def slider_to_wait(v: int) -> float:     return round(1.0 + (v / 100.0) * 7.0, 1)
def wait_to_slider(w: float) -> int:     return max(0, min(100, int(round((w - 1.0) / 7.0 * 100))))


def get_activity_stats() -> tuple[int, float | None]:
    """Total user turns across all history files + most-recent file mtime."""
    if not HISTORY_DIR.exists():
        return 0, None
    total = 0
    latest = None
    for p in HISTORY_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            total += sum(1 for m in data if m.get("role") == "user")
            mt = p.stat().st_mtime
            if latest is None or mt > latest:
                latest = mt
        except Exception:
            continue
    return total, latest


def format_relative(ts: float | None) -> str:
    """'5 min ago', '2 hr ago', etc."""
    import time
    if ts is None:
        return "Never"
    delta = max(0, time.time() - ts)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def add_shadow(widget: QWidget, blur=24, offset_y=2, color=QColor(0, 0, 0, 18)):
    """Soft drop shadow under a card."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, offset_y)
    eff.setColor(color)
    widget.setGraphicsEffect(eff)


# ============================================================================
# Custom widgets
# ============================================================================

class ToggleSwitch(QCheckBox):
    """iOS-style pill toggle. Drop-in QCheckBox replacement."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):  # whole rect is clickable
        return self.rect().contains(pos)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        bg = QColor(ACCENT) if on else QColor("#D1D5DB")
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 16, 16)
        thumb_d = 24
        margin = 4
        x = (self.width() - thumb_d - margin) if on else margin
        # Subtle shadow under thumb
        p.setBrush(QBrush(QColor(0, 0, 0, 25)))
        p.drawEllipse(QRectF(x, margin + 1, thumb_d, thumb_d))
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(QRectF(x, margin, thumb_d, thumb_d))
        p.end()


class VoiceCard(QFrame):
    """Touch-friendly voice card with a colored avatar circle and name."""
    clicked = pyqtSignal(str)

    def __init__(self, voice_id: str, category: str, parent=None):
        super().__init__(parent)
        self.voice_id = voice_id
        self.category = category
        self._checked = False
        self._tint = CATEGORY_TINTS.get(category, "#F3F4F6")
        self.setFixedSize(120, 140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_style()

    def setChecked(self, checked: bool):
        if self._checked == checked:
            return
        self._checked = checked
        self._refresh_style()
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def _refresh_style(self):
        if self._checked:
            border = ACCENT
            bg = SURFACE
            border_w = 2
        else:
            border = BORDER
            bg = SURFACE
            border_w = 1
        self.setStyleSheet(f"""
            VoiceCard {{
                background: {bg};
                border: {border_w}px solid {border};
                border-radius: 16px;
            }}
        """)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.voice_id)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Avatar circle
        cx = self.width() // 2
        cy = 50
        r = 32
        avatar_color = QColor(ACCENT) if self._checked else QColor(self._tint)
        p.setBrush(QBrush(avatar_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)
        # Initial letter
        initial = display_name(self.voice_id)[0].upper()
        p.setPen(QPen(QColor("white" if self._checked else TEXT)))
        f = QFont()
        f.setPointSize(20)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.drawText(QRectF(cx - r, cy - r, r * 2, r * 2),
                   Qt.AlignmentFlag.AlignCenter, initial)
        # Voice name
        p.setPen(QPen(QColor(TEXT)))
        f.setPointSize(11)
        f.setWeight(QFont.Weight.Medium)
        p.setFont(f)
        p.drawText(QRectF(0, 95, self.width(), 30),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   display_name(self.voice_id))
        p.end()


class PresetCard(QFrame):
    """Big tappable preset card with emoji + name + tagline."""
    clicked = pyqtSignal(str)

    def __init__(self, name: str, emoji: str, tagline: str, parent=None):
        super().__init__(parent)
        self.preset_name = name
        self._checked = False
        self.setMinimumHeight(110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        emoji_label = QLabel(emoji)
        f = QFont()
        f.setPointSize(28)
        emoji_label.setFont(f)
        emoji_label.setFixedWidth(48)
        emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(emoji_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.name_label = QLabel(name)
        nf = QFont()
        nf.setPointSize(15)
        nf.setWeight(QFont.Weight.DemiBold)
        self.name_label.setFont(nf)
        text_box.addWidget(self.name_label)

        tag_label = QLabel(tagline)
        tf = QFont()
        tf.setPointSize(11)
        tag_label.setFont(tf)
        tag_label.setStyleSheet(f"color: {MUTED};")
        text_box.addWidget(tag_label)
        text_box.addStretch()
        layout.addLayout(text_box, 1)

        self._refresh_style()

    def setChecked(self, checked: bool):
        if self._checked == checked:
            return
        self._checked = checked
        self._refresh_style()

    def isChecked(self) -> bool:
        return self._checked

    def _refresh_style(self):
        if self._checked:
            self.setStyleSheet(f"""
                PresetCard {{
                    background: #FFF6F2;
                    border: 2px solid {ACCENT};
                    border-radius: 16px;
                }}
                QLabel {{ color: {TEXT}; }}
            """)
        else:
            self.setStyleSheet(f"""
                PresetCard {{
                    background: {SURFACE};
                    border: 1px solid {BORDER};
                    border-radius: 16px;
                }}
                QLabel {{ color: {TEXT}; }}
            """)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.preset_name)
        super().mouseReleaseEvent(event)


def make_card(child_layout_builder, *, parent=None) -> QFrame:
    """Wrap content in a card frame with shadow."""
    card = QFrame(parent)
    card.setObjectName("card")
    card.setStyleSheet(f"""
        QFrame#card {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 16px;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    child_layout_builder(layout)
    add_shadow(card)
    return card


def section_title(text: str, *, top_margin: int = 0) -> QLabel:
    label = QLabel(text)
    f = QFont()
    f.setPointSize(13)
    f.setWeight(QFont.Weight.DemiBold)
    label.setFont(f)
    label.setStyleSheet(f"color: {MUTED}; letter-spacing: 0.5px;")
    if top_margin:
        label.setContentsMargins(0, top_margin, 0, 0)
    return label


# ============================================================================
# Main window
# ============================================================================

class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Klyra")
        self.resize(1000, 720)
        self._kokoro = None
        self._preview_proc = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----- Sidebar -----
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(24, 28, 16, 24)
        side_layout.setSpacing(16)

        brand = QLabel("Klyra")
        bf = QFont()
        bf.setPointSize(24)
        bf.setWeight(QFont.Weight.Bold)
        brand.setFont(bf)
        brand.setStyleSheet(f"color: {TEXT};")
        side_layout.addWidget(brand)

        sub = QLabel("Settings")
        sf = QFont()
        sf.setPointSize(11)
        sub.setFont(sf)
        sub.setStyleSheet(f"color: {MUTED};")
        side_layout.addWidget(sub)
        side_layout.addSpacing(20)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFrameShape(QFrame.Shape.NoFrame)
        self.nav.setIconSize(QSize(24, 24))
        for emoji, label in NAV_ITEMS:
            item = QListWidgetItem(f"  {emoji}   {label}")
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(lambda i: self.panels.setCurrentIndex(i))
        side_layout.addWidget(self.nav, 1)
        root.addWidget(sidebar)

        # ----- Content area -----
        content_wrap = QWidget()
        content_wrap.setObjectName("content")
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.panels = QStackedWidget()
        self.panels.addWidget(self._build_home_panel())
        self.panels.addWidget(self._build_voice_panel())
        self.panels.addWidget(self._build_personality_panel())
        self.panels.addWidget(self._build_privacy_panel())
        self.panels.addWidget(self._build_listening_panel())
        content_layout.addWidget(self.panels, 1)

        # Action bar
        action_bar = QWidget()
        action_bar.setObjectName("actionBar")
        action_bar.setFixedHeight(80)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(36, 16, 36, 16)
        action_layout.setSpacing(12)

        self.preview_btn = QPushButton("▶  Preview voice")
        self.preview_btn.setObjectName("previewBtn")
        self.preview_btn.setMinimumHeight(48)
        self.preview_btn.clicked.connect(self.preview_voice)
        action_layout.addWidget(self.preview_btn)
        action_layout.addStretch()

        self.reload_btn = QPushButton("Reload")
        self.reload_btn.setObjectName("ghostBtn")
        self.reload_btn.setMinimumHeight(48)
        self.reload_btn.setMinimumWidth(110)
        self.reload_btn.clicked.connect(self.load_config)
        action_layout.addWidget(self.reload_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setMinimumHeight(48)
        self.save_btn.setMinimumWidth(140)
        self.save_btn.clicked.connect(self.save_config)
        action_layout.addWidget(self.save_btn)
        content_layout.addWidget(action_bar)
        root.addWidget(content_wrap, 1)

        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.setStatusBar(self.status_bar)

        self.load_config()

    # ----- panel builders -----
    def _scrollable(self, content_widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {BG}; }}")
        scroll.setWidget(content_widget)
        return scroll

    def _panel_header(self, title: str, subtitle: str) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(6)
        t = QLabel(title)
        tf = QFont()
        tf.setPointSize(28)
        tf.setWeight(QFont.Weight.Bold)
        t.setFont(tf)
        t.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(t)
        s = QLabel(subtitle)
        sf = QFont()
        sf.setPointSize(13)
        s.setFont(sf)
        s.setStyleSheet(f"color: {MUTED};")
        s.setWordWrap(True)
        layout.addWidget(s)
        return layout

    def _build_home_panel(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 32, 40, 24)
        outer.setSpacing(16)

        # Greeting (filled in load_config)
        self.home_greeting = QLabel("Hi there")
        gf = QFont()
        gf.setPointSize(32)
        gf.setWeight(QFont.Weight.Bold)
        self.home_greeting.setFont(gf)
        self.home_greeting.setStyleSheet(f"color: {TEXT};")
        outer.addWidget(self.home_greeting)

        self.home_subtitle = QLabel("Klyra is ready to chat.")
        sf = QFont()
        sf.setPointSize(13)
        self.home_subtitle.setFont(sf)
        self.home_subtitle.setStyleSheet(f"color: {MUTED};")
        outer.addWidget(self.home_subtitle)
        outer.addSpacing(12)

        # Voice card
        def voice_card_builder(layout: QVBoxLayout):
            cap = QLabel("CURRENT VOICE")
            cap.setStyleSheet(f"color: {MUTED}; letter-spacing: 0.5px;")
            cf = QFont()
            cf.setPointSize(10)
            cf.setWeight(QFont.Weight.DemiBold)
            cap.setFont(cf)
            layout.addWidget(cap)

            row = QHBoxLayout()
            row.setSpacing(16)
            self.home_voice_avatar = QLabel("?")
            self.home_voice_avatar.setFixedSize(56, 56)
            self.home_voice_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            af = QFont()
            af.setPointSize(20)
            af.setWeight(QFont.Weight.Bold)
            self.home_voice_avatar.setFont(af)
            self.home_voice_avatar.setStyleSheet(
                f"background: {ACCENT}; color: white; border-radius: 28px;"
            )
            row.addWidget(self.home_voice_avatar)

            tcol = QVBoxLayout()
            tcol.setSpacing(2)
            self.home_voice_name = QLabel("—")
            nf = QFont()
            nf.setPointSize(16)
            nf.setWeight(QFont.Weight.DemiBold)
            self.home_voice_name.setFont(nf)
            self.home_voice_name.setStyleSheet(f"color: {TEXT};")
            tcol.addWidget(self.home_voice_name)
            self.home_voice_cat = QLabel("")
            tcol.addWidget(self.home_voice_cat)
            self.home_voice_cat.setStyleSheet(f"color: {MUTED};")
            row.addLayout(tcol, 1)
            layout.addLayout(row)
        outer.addWidget(make_card(voice_card_builder))

        # Personality card
        def pers_card_builder(layout: QVBoxLayout):
            cap = QLabel("CURRENT PERSONALITY")
            cap.setStyleSheet(f"color: {MUTED}; letter-spacing: 0.5px;")
            cf = QFont()
            cf.setPointSize(10)
            cf.setWeight(QFont.Weight.DemiBold)
            cap.setFont(cf)
            layout.addWidget(cap)

            row = QHBoxLayout()
            row.setSpacing(16)
            self.home_pers_emoji = QLabel("·")
            ef = QFont()
            ef.setPointSize(28)
            self.home_pers_emoji.setFont(ef)
            self.home_pers_emoji.setFixedWidth(56)
            self.home_pers_emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(self.home_pers_emoji)

            tcol = QVBoxLayout()
            tcol.setSpacing(2)
            self.home_pers_name = QLabel("—")
            nf = QFont()
            nf.setPointSize(16)
            nf.setWeight(QFont.Weight.DemiBold)
            self.home_pers_name.setFont(nf)
            self.home_pers_name.setStyleSheet(f"color: {TEXT};")
            tcol.addWidget(self.home_pers_name)
            self.home_pers_tag = QLabel("")
            self.home_pers_tag.setStyleSheet(f"color: {MUTED};")
            tcol.addWidget(self.home_pers_tag)
            row.addLayout(tcol, 1)
            layout.addLayout(row)
        outer.addWidget(make_card(pers_card_builder))

        # Activity card
        def activity_card_builder(layout: QVBoxLayout):
            cap = QLabel("ACTIVITY")
            cap.setStyleSheet(f"color: {MUTED}; letter-spacing: 0.5px;")
            cf = QFont()
            cf.setPointSize(10)
            cf.setWeight(QFont.Weight.DemiBold)
            cap.setFont(cf)
            layout.addWidget(cap)

            row = QHBoxLayout()
            row.setSpacing(40)

            # Total turns
            tcol = QVBoxLayout()
            tcol.setSpacing(2)
            self.home_activity_turns = QLabel("0")
            tf = QFont()
            tf.setPointSize(28)
            tf.setWeight(QFont.Weight.Bold)
            self.home_activity_turns.setFont(tf)
            self.home_activity_turns.setStyleSheet(f"color: {ACCENT};")
            tcol.addWidget(self.home_activity_turns)
            tlabel = QLabel("conversation turns")
            tlabel.setStyleSheet(f"color: {MUTED};")
            tcol.addWidget(tlabel)
            row.addLayout(tcol)

            # Last spoke
            lcol = QVBoxLayout()
            lcol.setSpacing(2)
            self.home_activity_last = QLabel("—")
            lf = QFont()
            lf.setPointSize(28)
            lf.setWeight(QFont.Weight.Bold)
            self.home_activity_last.setFont(lf)
            self.home_activity_last.setStyleSheet(f"color: {TEXT};")
            lcol.addWidget(self.home_activity_last)
            llabel = QLabel("since last chat")
            llabel.setStyleSheet(f"color: {MUTED};")
            lcol.addWidget(llabel)
            row.addLayout(lcol)
            row.addStretch()

            layout.addLayout(row)
        outer.addWidget(make_card(activity_card_builder))

        # Quick action
        action_row = QHBoxLayout()
        say_hi = QPushButton("👋  Say hi")
        say_hi.setObjectName("saveBtn")
        say_hi.setMinimumHeight(48)
        say_hi.setMinimumWidth(160)
        say_hi.clicked.connect(self.say_hi)
        action_row.addWidget(say_hi)
        action_row.addStretch()
        outer.addLayout(action_row)

        outer.addStretch()
        return self._scrollable(page)

    def _build_voice_panel(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 32, 40, 24)
        outer.setSpacing(20)

        outer.addLayout(self._panel_header(
            "Voice", "Pick how Klyra sounds. Tap any voice to select it."
        ))

        # Hero card: currently selected
        def hero(layout: QVBoxLayout):
            row = QHBoxLayout()
            row.setSpacing(20)

            self.hero_avatar = QLabel("?")
            self.hero_avatar.setFixedSize(72, 72)
            self.hero_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            af = QFont()
            af.setPointSize(28)
            af.setWeight(QFont.Weight.Bold)
            self.hero_avatar.setFont(af)
            self.hero_avatar.setStyleSheet(
                f"background: {ACCENT}; color: white; border-radius: 36px;"
            )
            row.addWidget(self.hero_avatar)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            self.hero_name = QLabel("—")
            hf = QFont()
            hf.setPointSize(20)
            hf.setWeight(QFont.Weight.DemiBold)
            self.hero_name.setFont(hf)
            self.hero_name.setStyleSheet(f"color: {TEXT};")
            text_col.addWidget(self.hero_name)
            self.hero_category = QLabel("")
            cf = QFont()
            cf.setPointSize(12)
            self.hero_category.setFont(cf)
            self.hero_category.setStyleSheet(f"color: {MUTED};")
            text_col.addWidget(self.hero_category)
            text_col.addStretch()
            row.addLayout(text_col, 1)
            layout.addLayout(row)

            # Speed slider
            speed_label_row = QHBoxLayout()
            slabel = QLabel("Speed")
            slf = QFont()
            slf.setPointSize(12)
            slf.setWeight(QFont.Weight.DemiBold)
            slabel.setFont(slf)
            slabel.setStyleSheet(f"color: {TEXT};")
            speed_label_row.addWidget(slabel)
            speed_label_row.addStretch()
            self.speed_value = QLabel("1.00×")
            svf = QFont()
            svf.setPointSize(12)
            svf.setWeight(QFont.Weight.DemiBold)
            self.speed_value.setFont(svf)
            self.speed_value.setStyleSheet(f"color: {ACCENT};")
            speed_label_row.addWidget(self.speed_value)
            layout.addLayout(speed_label_row)

            self.speed_slider = QSlider(Qt.Orientation.Horizontal)
            self.speed_slider.setRange(0, 100)
            self.speed_slider.setValue(speed_to_slider(1.0))
            self.speed_slider.setMinimumHeight(28)
            self.speed_slider.valueChanged.connect(self._on_speed_changed)
            layout.addWidget(self.speed_slider)

            # Volume slider
            vol_label_row = QHBoxLayout()
            vlabel = QLabel("Volume")
            vlf = QFont()
            vlf.setPointSize(12)
            vlf.setWeight(QFont.Weight.DemiBold)
            vlabel.setFont(vlf)
            vlabel.setStyleSheet(f"color: {TEXT};")
            vol_label_row.addWidget(vlabel)
            vol_label_row.addStretch()
            self.volume_value = QLabel("100%")
            vvf = QFont()
            vvf.setPointSize(12)
            vvf.setWeight(QFont.Weight.DemiBold)
            self.volume_value.setFont(vvf)
            self.volume_value.setStyleSheet(f"color: {ACCENT};")
            vol_label_row.addWidget(self.volume_value)
            layout.addLayout(vol_label_row)

            self.volume_slider = QSlider(Qt.Orientation.Horizontal)
            self.volume_slider.setRange(0, 100)
            self.volume_slider.setValue(100)
            self.volume_slider.setMinimumHeight(28)
            self.volume_slider.valueChanged.connect(self._on_volume_changed)
            layout.addWidget(self.volume_slider)
        outer.addWidget(make_card(hero))

        # Voice grid
        self._buttons_by_voice: dict[str, VoiceCard] = {}
        for cat_name, voices in CATEGORIES:
            outer.addWidget(section_title(cat_name.upper(), top_margin=8))
            grid_wrap = QWidget()
            grid = QGridLayout(grid_wrap)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            grid.setContentsMargins(0, 0, 0, 0)
            cols = 5
            for i, vid in enumerate(voices):
                card = VoiceCard(vid, cat_name)
                card.clicked.connect(self._on_voice_clicked)
                self._buttons_by_voice[vid] = card
                grid.addWidget(card, i // cols, i % cols)
            for c in range(cols):
                grid.setColumnStretch(c, 0)
            grid.setColumnStretch(cols, 1)  # eat extra space on the right
            outer.addWidget(grid_wrap)

        outer.addStretch()
        return self._scrollable(page)

    def _build_personality_panel(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 32, 40, 24)
        outer.setSpacing(20)

        outer.addLayout(self._panel_header(
            "Personality", "How Klyra acts. Pick a vibe."
        ))

        # 2x2 grid of preset cards
        self._preset_cards: dict[str, PresetCard] = {}
        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        names = list(PERSONALITY_PRESETS.keys())
        for i, name in enumerate(names):
            data = PERSONALITY_PRESETS[name]
            card = PresetCard(name, data["emoji"], data["tagline"])
            card.clicked.connect(self._on_preset_clicked)
            add_shadow(card)
            self._preset_cards[name] = card
            grid.addWidget(card, i // 2, i % 2)
        outer.addWidget(grid_wrap)

        # Your name card
        def name_card(layout: QVBoxLayout):
            label = QLabel("Your name")
            lf = QFont()
            lf.setPointSize(13)
            lf.setWeight(QFont.Weight.DemiBold)
            label.setFont(lf)
            label.setStyleSheet(f"color: {TEXT};")
            layout.addWidget(label)
            sub = QLabel("What should Klyra call you?")
            sf = QFont()
            sf.setPointSize(11)
            sub.setFont(sf)
            sub.setStyleSheet(f"color: {MUTED};")
            layout.addWidget(sub)
            self.user_name = QLineEdit()
            self.user_name.setMinimumHeight(44)
            self.user_name.setPlaceholderText("e.g. Cody")
            layout.addWidget(self.user_name)
        outer.addWidget(make_card(name_card))
        outer.addStretch()
        return self._scrollable(page)

    def _build_privacy_panel(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 32, 40, 24)
        outer.setSpacing(20)

        outer.addLayout(self._panel_header(
            "Privacy",
            "What Klyra can see, what it remembers."
        ))

        def camera_card(layout: QVBoxLayout):
            row = QHBoxLayout()
            row.setSpacing(16)

            icon = QLabel("📷")
            f = QFont()
            f.setPointSize(28)
            icon.setFont(f)
            icon.setFixedWidth(48)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(icon)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            t = QLabel("Camera")
            tf = QFont()
            tf.setPointSize(15)
            tf.setWeight(QFont.Weight.DemiBold)
            t.setFont(tf)
            t.setStyleSheet(f"color: {TEXT};")
            text_col.addWidget(t)
            d = QLabel("Let Klyra see you. Off means no images are ever captured.")
            df = QFont()
            df.setPointSize(11)
            d.setFont(df)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {MUTED};")
            text_col.addWidget(d)
            row.addLayout(text_col, 1)

            self.camera_enabled = ToggleSwitch()
            row.addWidget(self.camera_enabled, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addLayout(row)
        outer.addWidget(make_card(camera_card))

        # Camera preview card
        def preview_card(layout: QVBoxLayout):
            row = QHBoxLayout()
            row.setSpacing(16)
            icon = QLabel("👁")
            f = QFont()
            f.setPointSize(28)
            icon.setFont(f)
            icon.setFixedWidth(48)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(icon)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            t = QLabel("Show me what Klyra sees")
            tf = QFont()
            tf.setPointSize(15)
            tf.setWeight(QFont.Weight.DemiBold)
            t.setFont(tf)
            t.setStyleSheet(f"color: {TEXT};")
            text_col.addWidget(t)
            d = QLabel("Live camera preview. Won't work while Klyra is running "
                       "(camera locked).")
            df = QFont()
            df.setPointSize(11)
            d.setFont(df)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {MUTED};")
            text_col.addWidget(d)
            row.addLayout(text_col, 1)

            self.preview_toggle = ToggleSwitch()
            self.preview_toggle.toggled.connect(self._on_preview_toggled)
            row.addWidget(self.preview_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addLayout(row)

            # Frame area (hidden until toggle on)
            self.preview_frame = QLabel("")
            self.preview_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_frame.setMinimumHeight(240)
            self.preview_frame.setStyleSheet(
                f"background: {SUBTLE}; border-radius: 12px; color: {MUTED};"
            )
            self.preview_frame.setVisible(False)
            layout.addWidget(self.preview_frame)
        outer.addWidget(make_card(preview_card))

        # Camera preview state
        self._cam_capture = None
        self._cam_timer = QTimer(self)
        self._cam_timer.timeout.connect(self._update_preview_frame)

        def memory_card(layout: QVBoxLayout):
            row = QHBoxLayout()
            row.setSpacing(16)
            icon = QLabel("🧠")
            f = QFont()
            f.setPointSize(28)
            icon.setFont(f)
            icon.setFixedWidth(48)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(icon)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            t = QLabel("Memory")
            tf = QFont()
            tf.setPointSize(15)
            tf.setWeight(QFont.Weight.DemiBold)
            t.setFont(tf)
            t.setStyleSheet(f"color: {TEXT};")
            text_col.addWidget(t)
            d = QLabel("Klyra remembers your past conversations across sessions.")
            df = QFont()
            df.setPointSize(11)
            d.setFont(df)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {MUTED};")
            text_col.addWidget(d)
            row.addLayout(text_col, 1)
            layout.addLayout(row)

            btn_row = QHBoxLayout()
            self.clear_memory_btn = QPushButton("Clear all memory")
            self.clear_memory_btn.setObjectName("dangerBtn")
            self.clear_memory_btn.setMinimumHeight(44)
            self.clear_memory_btn.clicked.connect(self.clear_memory)
            btn_row.addWidget(self.clear_memory_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)
        outer.addWidget(make_card(memory_card))
        outer.addStretch()
        return self._scrollable(page)

    def _build_listening_panel(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 32, 40, 24)
        outer.setSpacing(20)

        outer.addLayout(self._panel_header(
            "Listening", "How Klyra hears you."
        ))

        def wake_card(layout: QVBoxLayout):
            t = QLabel("Wake word")
            tf = QFont()
            tf.setPointSize(13)
            tf.setWeight(QFont.Weight.DemiBold)
            t.setFont(tf)
            t.setStyleSheet(f"color: {TEXT};")
            layout.addWidget(t)
            d = QLabel("What you say to wake Klyra. Common words work best.")
            df = QFont()
            df.setPointSize(11)
            d.setFont(df)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {MUTED};")
            layout.addWidget(d)
            self.wake_word = QLineEdit()
            self.wake_word.setMinimumHeight(44)
            self.wake_word.setPlaceholderText("hey buddy")
            layout.addWidget(self.wake_word)
        outer.addWidget(make_card(wake_card))

        def conv_card(layout: QVBoxLayout):
            row = QHBoxLayout()
            row.setSpacing(16)
            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            t = QLabel("Conversation mode")
            tf = QFont()
            tf.setPointSize(15)
            tf.setWeight(QFont.Weight.DemiBold)
            t.setFont(tf)
            t.setStyleSheet(f"color: {TEXT};")
            text_col.addWidget(t)
            d = QLabel(
                "Keep listening after Klyra responds — no need to say the wake "
                "word every time."
            )
            df = QFont()
            df.setPointSize(11)
            d.setFont(df)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {MUTED};")
            text_col.addWidget(d)
            row.addLayout(text_col, 1)
            self.conversation_mode = ToggleSwitch()
            row.addWidget(self.conversation_mode, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addLayout(row)
        outer.addWidget(make_card(conv_card))

        def sens_card(layout: QVBoxLayout):
            t = QLabel("Microphone sensitivity")
            tf = QFont()
            tf.setPointSize(13)
            tf.setWeight(QFont.Weight.DemiBold)
            t.setFont(tf)
            t.setStyleSheet(f"color: {TEXT};")
            layout.addWidget(t)
            d = QLabel(
                "Strict ignores background noise — good for noisy rooms. Sensitive "
                "picks up softer speech."
            )
            df = QFont()
            df.setPointSize(11)
            d.setFont(df)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {MUTED};")
            layout.addWidget(d)
            row = QHBoxLayout()
            row.addWidget(self._slider_endpoint("Strict"))
            self.sensitivity = QSlider(Qt.Orientation.Horizontal)
            self.sensitivity.setRange(0, 100)
            self.sensitivity.setMinimumHeight(28)
            row.addWidget(self.sensitivity, 1)
            row.addWidget(self._slider_endpoint("Sensitive"))
            layout.addLayout(row)
        outer.addWidget(make_card(sens_card))

        def wait_card(layout: QVBoxLayout):
            head = QHBoxLayout()
            t = QLabel("Wait time")
            tf = QFont()
            tf.setPointSize(13)
            tf.setWeight(QFont.Weight.DemiBold)
            t.setFont(tf)
            t.setStyleSheet(f"color: {TEXT};")
            head.addWidget(t)
            head.addStretch()
            self.wait_value = QLabel("4.5 seconds")
            wvf = QFont()
            wvf.setPointSize(12)
            wvf.setWeight(QFont.Weight.DemiBold)
            self.wait_value.setFont(wvf)
            self.wait_value.setStyleSheet(f"color: {ACCENT};")
            head.addWidget(self.wait_value)
            layout.addLayout(head)
            d = QLabel("How long Klyra waits for you to start speaking after the wake word.")
            df = QFont()
            df.setPointSize(11)
            d.setFont(df)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {MUTED};")
            layout.addWidget(d)
            row = QHBoxLayout()
            row.addWidget(self._slider_endpoint("Quick"))
            self.wait_time = QSlider(Qt.Orientation.Horizontal)
            self.wait_time.setRange(0, 100)
            self.wait_time.setMinimumHeight(28)
            self.wait_time.valueChanged.connect(self._on_wait_changed)
            row.addWidget(self.wait_time, 1)
            row.addWidget(self._slider_endpoint("Patient"))
            layout.addLayout(row)
        outer.addWidget(make_card(wait_card))

        outer.addStretch()
        return self._scrollable(page)

    def _slider_endpoint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        f = QFont()
        f.setPointSize(11)
        lbl.setFont(f)
        lbl.setStyleSheet(f"color: {MUTED};")
        lbl.setMinimumWidth(70)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    # ----- handlers -----
    def _on_voice_clicked(self, vid: str):
        for v, card in self._buttons_by_voice.items():
            card.setChecked(v == vid)
        self._update_hero(vid)

    def _on_preset_clicked(self, name: str):
        for n, card in self._preset_cards.items():
            card.setChecked(n == name)

    def _on_speed_changed(self, value: int):
        self.speed_value.setText(f"{slider_to_speed(value):.2f}×")

    def _on_volume_changed(self, value: int):
        self.volume_value.setText(f"{value}%")

    def _on_wait_changed(self, value: int):
        self.wait_value.setText(f"{slider_to_wait(value):.1f} seconds")

    def _on_preview_toggled(self, on: bool):
        if on:
            try:
                import cv2
                self._cam_capture = cv2.VideoCapture(0)
                if not self._cam_capture.isOpened():
                    raise RuntimeError("camera unavailable")
                self.preview_frame.setVisible(True)
                self.preview_frame.setText("Loading...")
                self._cam_timer.start(67)  # ~15 FPS
            except Exception as e:
                self.preview_toggle.blockSignals(True)
                self.preview_toggle.setChecked(False)
                self.preview_toggle.blockSignals(False)
                self.status_bar.showMessage(
                    f"Camera unavailable ({e}) — likely in use by Klyra", 5000
                )
                self._cam_capture = None
        else:
            self._cam_timer.stop()
            if self._cam_capture is not None:
                try:
                    self._cam_capture.release()
                except Exception:
                    pass
                self._cam_capture = None
            self.preview_frame.setVisible(False)

    def _update_preview_frame(self):
        if self._cam_capture is None:
            return
        import cv2
        ok, frame = self._cam_capture.read()
        if not ok:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        # Scale to label width, keep aspect ratio
        target_w = max(320, self.preview_frame.width())
        scaled = qimg.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation)
        self.preview_frame.setPixmap(QPixmap.fromImage(scaled))
        self.preview_frame.setText("")

    def _selected_voice(self) -> str | None:
        for vid, card in self._buttons_by_voice.items():
            if card.isChecked():
                return vid
        return None

    def _selected_preset(self) -> str | None:
        for name, card in self._preset_cards.items():
            if card.isChecked():
                return name
        return None

    def _update_hero(self, vid: str):
        if not vid:
            self.hero_name.setText("—")
            self.hero_category.setText("")
            self.hero_avatar.setText("?")
            return
        self.hero_name.setText(display_name(vid))
        self.hero_category.setText(category_for(vid))
        self.hero_avatar.setText(display_name(vid)[0].upper())

    # ----- config -----
    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            self.status_bar.showMessage(f"Load failed: {e}", 5000)
            return

        # Voice
        vid = cfg.get("kokoro_voice", "bm_lewis")
        for v, card in self._buttons_by_voice.items():
            card.setChecked(v == vid)
        self._update_hero(vid)
        self.speed_slider.setValue(speed_to_slider(float(cfg.get("voice_speed", 1.0))))
        self.volume_slider.setValue(int(round(float(cfg.get("volume", 1.0)) * 100)))

        # Personality
        prompt = cfg.get("system_prompt", "")
        preset = cfg.get("personality_preset", "")
        matched = None
        for name, data in PERSONALITY_PRESETS.items():
            if data["prompt"].strip() == prompt.strip():
                matched = name
                break
        if not matched and preset in PERSONALITY_PRESETS:
            matched = preset
        if not matched:
            matched = next(iter(PERSONALITY_PRESETS))
        for n, card in self._preset_cards.items():
            card.setChecked(n == matched)
        self.user_name.setText(cfg.get("user_name", ""))

        # Privacy
        self.camera_enabled.setChecked(bool(cfg.get("enable_camera", True)))

        # Listening
        self.wake_word.setText(cfg.get("wake_word", "hey buddy"))
        self.conversation_mode.setChecked(bool(cfg.get("conversation_mode", True)))
        self.sensitivity.setValue(threshold_to_slider(int(cfg.get("silence_threshold", 1500))))
        self.wait_time.setValue(wait_to_slider(float(cfg.get("pre_speech_timeout", 4.0))))

        # Home dashboard
        name = cfg.get("user_name", "").strip()
        self.home_greeting.setText(f"Hi, {name}" if name else "Hi there")
        self.home_voice_name.setText(display_name(vid))
        self.home_voice_cat.setText(category_for(vid))
        self.home_voice_avatar.setText(display_name(vid)[0].upper())
        if matched in PERSONALITY_PRESETS:
            data = PERSONALITY_PRESETS[matched]
            self.home_pers_emoji.setText(data["emoji"])
            self.home_pers_name.setText(matched)
            self.home_pers_tag.setText(data["tagline"])
        turns, last = get_activity_stats()
        self.home_activity_turns.setText(str(turns))
        self.home_activity_last.setText(format_relative(last))

        self.status_bar.showMessage("Loaded", 3000)

    def say_hi(self):
        """Quick action — synthesize a greeting in the current voice."""
        vid = self._selected_voice()
        if not vid:
            self.status_bar.showMessage("Pick a voice first", 4000)
            return
        name = self.user_name.text().strip()
        line = f"Hey {name}, what's up?" if name else "Hey there. I'm Klyra."
        self._synth_and_play(vid, line)

    def save_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            self.status_bar.showMessage(f"Read failed: {e}", 5000)
            return

        vid = self._selected_voice()
        if vid:
            cfg["kokoro_voice"] = vid
        cfg["voice_speed"] = slider_to_speed(self.speed_slider.value())
        cfg["volume"] = round(self.volume_slider.value() / 100.0, 2)

        preset = self._selected_preset() or next(iter(PERSONALITY_PRESETS))
        cfg["personality_preset"] = preset
        cfg["system_prompt"] = PERSONALITY_PRESETS[preset]["prompt"]
        cfg["user_name"] = self.user_name.text().strip()

        cfg["enable_camera"] = self.camera_enabled.isChecked()
        if not self.camera_enabled.isChecked():
            cfg["vision_engine"] = "off"
        elif cfg.get("vision_engine") == "off":
            cfg["vision_engine"] = "local"

        cfg["wake_word"] = self.wake_word.text().strip() or "hey buddy"
        cfg["conversation_mode"] = self.conversation_mode.isChecked()
        cfg["silence_threshold"] = slider_to_threshold(self.sensitivity.value())
        cfg["pre_speech_timeout"] = slider_to_wait(self.wait_time.value())

        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            self.status_bar.showMessage("Saved · restart Klyra to apply", 6000)
        except Exception as e:
            self.status_bar.showMessage(f"Save failed: {e}", 5000)

    def closeEvent(self, event):
        """Release camera + kill any preview process on window close."""
        try:
            self._cam_timer.stop()
            if self._cam_capture is not None:
                self._cam_capture.release()
        except Exception:
            pass
        if self._preview_proc and self._preview_proc.poll() is None:
            try:
                self._preview_proc.terminate()
            except Exception:
                pass
        super().closeEvent(event)

    def clear_memory(self):
        confirm = QMessageBox.question(
            self, "Clear memory",
            "Delete all of Klyra's conversation history? This can't be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if not HISTORY_DIR.exists():
            self.status_bar.showMessage("Nothing to clear", 3000)
            return
        deleted = 0
        for p in HISTORY_DIR.glob("*.json"):
            try:
                p.unlink()
                deleted += 1
            except Exception:
                pass
        self.status_bar.showMessage(f"Cleared {deleted} conversation file(s)", 4000)

    # ----- preview -----
    def preview_voice(self):
        vid = self._selected_voice()
        if not vid:
            self.status_bar.showMessage("Pick a voice first", 4000)
            return
        self._synth_and_play(vid, PREVIEW_LINE)

    def _synth_and_play(self, voice_id: str, line: str):
        """Shared path for both Preview and Say Hi."""
        if self._kokoro is None:
            self.status_bar.showMessage("Loading Kokoro...")
            QApplication.processEvents()
            try:
                from kokoro_onnx import Kokoro
                self._kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES_BIN))
            except Exception as e:
                self.status_bar.showMessage(f"Kokoro load failed: {e}", 6000)
                return

        speed = slider_to_speed(self.speed_slider.value())
        self.status_bar.showMessage(f"Synthesizing {display_name(voice_id)}...")
        QApplication.processEvents()
        try:
            samples, sr = self._kokoro.create(
                line, voice=voice_id, speed=speed, lang="en-us"
            )
        except Exception as e:
            self.status_bar.showMessage(f"Synth failed: {e}", 5000)
            return

        import numpy as np
        pcm = (samples * 32767).clip(-32768, 32767).astype(np.int16)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm.tobytes())
        finally:
            tmp.close()

        if self._preview_proc and self._preview_proc.poll() is None:
            self._preview_proc.terminate()
        for player in (["paplay"], ["aplay", "-q"]):
            try:
                self._preview_proc = subprocess.Popen(player + [tmp.name])
                break
            except FileNotFoundError:
                continue
        else:
            self.status_bar.showMessage("No audio player found (paplay/aplay)", 6000)
            return
        self.status_bar.showMessage(f"Playing {display_name(voice_id)}", 3000)


# ============================================================================
# Theming
# ============================================================================

# ============================================================================
# Onboarding wizard (first-launch only)
# ============================================================================

class OnboardingWizard(QDialog):
    """Three-step wizard: Welcome+Name → Voice → Personality."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome to Klyra")
        self.setModal(True)
        self.setFixedSize(900, 640)

        self._chosen_voice = "bm_lewis"
        self._chosen_preset = next(iter(PERSONALITY_PRESETS))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Step indicator at the top
        self.indicator = QLabel("Step 1 of 3")
        f = QFont()
        f.setPointSize(11)
        f.setWeight(QFont.Weight.DemiBold)
        self.indicator.setFont(f)
        self.indicator.setStyleSheet(f"color: {ACCENT}; padding: 24px 40px 0 40px;")
        root.addWidget(self.indicator)

        # Stacked pages
        self.pages = QStackedWidget()
        self.pages.addWidget(self._page_welcome())
        self.pages.addWidget(self._page_voice())
        self.pages.addWidget(self._page_personality())
        root.addWidget(self.pages, 1)

        # Footer
        footer = QWidget()
        footer.setObjectName("actionBar")
        footer.setFixedHeight(80)
        flayout = QHBoxLayout(footer)
        flayout.setContentsMargins(40, 16, 40, 16)
        flayout.setSpacing(12)

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setObjectName("ghostBtn")
        self.skip_btn.setMinimumHeight(48)
        self.skip_btn.setMinimumWidth(110)
        self.skip_btn.clicked.connect(self._on_skip)
        flayout.addWidget(self.skip_btn)
        flayout.addStretch()

        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("ghostBtn")
        self.back_btn.setMinimumHeight(48)
        self.back_btn.setMinimumWidth(110)
        self.back_btn.clicked.connect(self._on_back)
        self.back_btn.setVisible(False)
        flayout.addWidget(self.back_btn)

        self.next_btn = QPushButton("Continue")
        self.next_btn.setObjectName("saveBtn")
        self.next_btn.setMinimumHeight(48)
        self.next_btn.setMinimumWidth(140)
        self.next_btn.clicked.connect(self._on_next)
        flayout.addWidget(self.next_btn)

        root.addWidget(footer)

    # ---- pages ----
    def _page_welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 30, 60, 30)
        layout.setSpacing(16)

        title = QLabel("👋  Welcome to Klyra")
        tf = QFont()
        tf.setPointSize(36)
        tf.setWeight(QFont.Weight.Bold)
        title.setFont(tf)
        title.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(title)

        sub = QLabel(
            "Klyra is a sarcastic AI companion that can see and hear you. "
            "Let's get you set up — should only take a minute."
        )
        sf = QFont()
        sf.setPointSize(14)
        sub.setFont(sf)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(sub)
        layout.addSpacing(24)

        name_label = QLabel("What should Klyra call you?")
        nf = QFont()
        nf.setPointSize(13)
        nf.setWeight(QFont.Weight.DemiBold)
        name_label.setFont(nf)
        name_label.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(name_label)

        self.wizard_name = QLineEdit()
        self.wizard_name.setMinimumHeight(56)
        self.wizard_name.setPlaceholderText("e.g. Cody")
        nfd = QFont()
        nfd.setPointSize(16)
        self.wizard_name.setFont(nfd)
        layout.addWidget(self.wizard_name)
        layout.addStretch()
        return page

    def _page_voice(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 30, 60, 20)
        layout.setSpacing(16)

        title = QLabel("Pick a voice")
        tf = QFont()
        tf.setPointSize(28)
        tf.setWeight(QFont.Weight.Bold)
        title.setFont(tf)
        title.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(title)

        sub = QLabel("How should Klyra sound?")
        sf = QFont()
        sf.setPointSize(13)
        sub.setFont(sf)
        sub.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(sub)
        layout.addSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(12)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        self._wizard_voice_cards: dict[str, VoiceCard] = {}
        for cat_name, voices in CATEGORIES:
            cap = section_title(cat_name.upper())
            inner_layout.addWidget(cap)
            grid_wrap = QWidget()
            grid = QGridLayout(grid_wrap)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)
            grid.setContentsMargins(0, 0, 0, 0)
            cols = 5
            for i, vid in enumerate(voices):
                card = VoiceCard(vid, cat_name)
                card.clicked.connect(self._on_wizard_voice_clicked)
                self._wizard_voice_cards[vid] = card
                grid.addWidget(card, i // cols, i % cols)
            grid.setColumnStretch(cols, 1)
            inner_layout.addWidget(grid_wrap)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        # Default selection
        self._wizard_voice_cards[self._chosen_voice].setChecked(True)
        return page

    def _page_personality(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 30, 60, 30)
        layout.setSpacing(16)

        title = QLabel("Pick a personality")
        tf = QFont()
        tf.setPointSize(28)
        tf.setWeight(QFont.Weight.Bold)
        title.setFont(tf)
        title.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(title)

        sub = QLabel("How should Klyra act?")
        sf = QFont()
        sf.setPointSize(13)
        sub.setFont(sf)
        sub.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(sub)
        layout.addSpacing(8)

        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        self._wizard_preset_cards: dict[str, PresetCard] = {}
        for i, (name, data) in enumerate(PERSONALITY_PRESETS.items()):
            card = PresetCard(name, data["emoji"], data["tagline"])
            card.clicked.connect(self._on_wizard_preset_clicked)
            add_shadow(card)
            self._wizard_preset_cards[name] = card
            grid.addWidget(card, i // 2, i % 2)
        layout.addWidget(grid_wrap)
        layout.addStretch()

        # Default selection
        self._wizard_preset_cards[self._chosen_preset].setChecked(True)
        return page

    # ---- handlers ----
    def _on_wizard_voice_clicked(self, vid: str):
        for v, card in self._wizard_voice_cards.items():
            card.setChecked(v == vid)
        self._chosen_voice = vid

    def _on_wizard_preset_clicked(self, name: str):
        for n, card in self._wizard_preset_cards.items():
            card.setChecked(n == name)
        self._chosen_preset = name

    def _on_next(self):
        idx = self.pages.currentIndex()
        if idx < self.pages.count() - 1:
            self.pages.setCurrentIndex(idx + 1)
            self._sync_footer()
        else:
            # Final step → save & accept
            self._save_choices()
            self.accept()

    def _on_back(self):
        idx = self.pages.currentIndex()
        if idx > 0:
            self.pages.setCurrentIndex(idx - 1)
            self._sync_footer()

    def _on_skip(self):
        # Skipping still marks onboarding done so we don't pester next time.
        self._mark_complete_only()
        self.reject()

    def _sync_footer(self):
        idx = self.pages.currentIndex()
        last = self.pages.count() - 1
        self.indicator.setText(f"Step {idx + 1} of {self.pages.count()}")
        self.back_btn.setVisible(idx > 0)
        self.next_btn.setText("Done" if idx == last else "Continue")

    def _save_choices(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        cfg["user_name"] = self.wizard_name.text().strip()
        cfg["kokoro_voice"] = self._chosen_voice
        cfg["personality_preset"] = self._chosen_preset
        cfg["system_prompt"] = PERSONALITY_PRESETS[self._chosen_preset]["prompt"]
        cfg["onboarding_complete"] = True
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _mark_complete_only(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["onboarding_complete"] = True
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def needs_onboarding() -> bool:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return not cfg.get("onboarding_complete", False)
    except Exception:
        return True


def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(BG))
    p.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(SUBTLE))
    p.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    p.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    app.setPalette(p)

    # Set base font (system stack, slightly larger)
    f = QFont()
    f.setPointSize(11)
    app.setFont(f)

    app.setStyleSheet(f"""
        QMainWindow, QWidget {{ background: {BG}; color: {TEXT}; }}
        QWidget#sidebar {{
            background: {SUBTLE};
            border-right: 1px solid {BORDER};
        }}
        QWidget#content {{ background: {BG}; }}
        QListWidget#nav {{
            background: transparent;
            border: none;
            font-size: 14px;
            outline: 0;
        }}
        QListWidget#nav::item {{
            padding: 14px 12px;
            border-radius: 10px;
            color: {TEXT};
            margin: 2px 0;
        }}
        QListWidget#nav::item:selected {{
            background: {SURFACE};
            color: {ACCENT};
            font-weight: 600;
        }}
        QListWidget#nav::item:hover:!selected {{
            background: rgba(255, 107, 71, 0.06);
        }}
        QWidget#actionBar {{
            background: {SURFACE};
            border-top: 1px solid {BORDER};
        }}
        QPushButton#previewBtn {{
            background: transparent;
            color: {ACCENT};
            border: 2px solid {ACCENT};
            border-radius: 24px;
            padding: 0 24px;
            font-size: 14px;
            font-weight: 600;
        }}
        QPushButton#previewBtn:hover {{ background: rgba(255, 107, 71, 0.08); }}
        QPushButton#previewBtn:pressed {{ background: rgba(255, 107, 71, 0.16); }}
        QPushButton#saveBtn {{
            background: {ACCENT};
            color: white;
            border: none;
            border-radius: 24px;
            padding: 0 24px;
            font-size: 14px;
            font-weight: 600;
        }}
        QPushButton#saveBtn:hover {{ background: {ACCENT_DARK}; }}
        QPushButton#ghostBtn {{
            background: transparent;
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 24px;
            padding: 0 24px;
            font-size: 14px;
            font-weight: 500;
        }}
        QPushButton#ghostBtn:hover {{ background: {SUBTLE}; }}
        QPushButton#dangerBtn {{
            background: transparent;
            color: {DANGER};
            border: 1px solid #FCA5A5;
            border-radius: 22px;
            padding: 8px 20px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton#dangerBtn:hover {{
            background: {DANGER};
            color: white;
            border-color: {DANGER};
        }}
        QStatusBar {{ background: {SURFACE}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
        QLineEdit {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 10px;
            padding: 10px 14px;
            font-size: 14px;
            color: {TEXT};
        }}
        QLineEdit:focus {{ border-color: {ACCENT}; }}
        QSlider::groove:horizontal {{
            background: {BORDER};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{
            background: {ACCENT};
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: white;
            border: 2px solid {ACCENT};
            width: 22px;
            height: 22px;
            margin: -9px 0;
            border-radius: 13px;
        }}
        QSlider::handle:horizontal:hover {{ background: #FFF6F2; }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 4px 2px 4px 0;
        }}
        QScrollBar::handle:vertical {{
            background: #D6D2CB;
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{ background: #B8B4AC; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_theme(app)

    # Show onboarding wizard on first launch (or when config has no
    # onboarding_complete marker — handles re-installs and fresh boxes).
    if needs_onboarding():
        wizard = OnboardingWizard()
        wizard.exec()  # blocks until accepted/rejected; saves config either way

    win = SettingsWindow()
    win.show()
    sys.exit(app.exec())
