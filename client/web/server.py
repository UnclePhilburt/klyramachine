"""Klyra Web UI — FastAPI backend.

Serves the launcher UI at http://localhost:8080. Reads/writes config.json
and provides a few endpoints for actions (launch Spotify, get Ollama
models, etc.). The frontend is a single-page web app in static/.

Run with: python web/server.py
"""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).parent
CLIENT_DIR = WEB_DIR.parent
CONFIG_PATH = CLIENT_DIR / "config.json"
HISTORY_DIR = CLIENT_DIR / "history"
STATIC_DIR = WEB_DIR / "static"

app = FastAPI(title="Klyra")


# ---- Config ---------------------------------------------------------------

@app.get("/api/config")
def read_config():
    if not CONFIG_PATH.exists():
        raise HTTPException(404, "config.json not found")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/config")
def write_config(updates: dict):
    """Merge incoming keys into config.json. Preserves keys we don't expose
    in the UI so a partial update doesn't drop them."""
    if not CONFIG_PATH.exists():
        raise HTTPException(404, "config.json not found")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        current = json.load(f)
    current.update(updates)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return {"ok": True, "saved": list(updates.keys())}


# ---- Activity / History ---------------------------------------------------

@app.get("/api/activity")
def activity():
    """Total user turns + most-recent file mtime, for the Home dashboard."""
    if not HISTORY_DIR.exists():
        return {"turns": 0, "last_seen": None}
    total = 0
    latest: float | None = None
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
    return {"turns": total, "last_seen": latest}


@app.post("/api/clear-memory")
def clear_memory():
    if not HISTORY_DIR.exists():
        return {"deleted": 0}
    deleted = 0
    for p in HISTORY_DIR.glob("*.json"):
        try:
            p.unlink()
            deleted += 1
        except Exception:
            pass
    return {"deleted": deleted}


# ---- Spotify launcher -----------------------------------------------------

def _find_spotify() -> str | None:
    for name in ("spotify", "spotify-launcher", "/snap/bin/spotify"):
        path = shutil.which(name) if "/" not in name else (name if Path(name).is_file() else None)
        if path:
            return path
    return None


_SPOTIFY_PROC: subprocess.Popen | None = None


@app.post("/api/spotify/open")
def spotify_open():
    """Launch the Spotify Linux app (or focus it if already running)."""
    global _SPOTIFY_PROC
    binary = _find_spotify()
    if not binary:
        return JSONResponse(
            {"ok": False, "error": "Spotify not installed. Run: sudo snap install spotify"},
            status_code=400,
        )
    if _SPOTIFY_PROC is not None and _SPOTIFY_PROC.poll() is None:
        return {"ok": True, "status": "already_running"}
    try:
        _SPOTIFY_PROC = subprocess.Popen([binary])
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return {"ok": True, "status": "launched"}


@app.post("/api/spotify/close")
def spotify_close():
    global _SPOTIFY_PROC
    if _SPOTIFY_PROC is None or _SPOTIFY_PROC.poll() is not None:
        # Try to kill any system-launched Spotify too
        subprocess.run(["pkill", "-f", "spotify"], check=False)
        _SPOTIFY_PROC = None
        return {"ok": True, "status": "not_running"}
    try:
        _SPOTIFY_PROC.terminate()
        _SPOTIFY_PROC.wait(timeout=3)
    except Exception:
        try:
            _SPOTIFY_PROC.kill()
        except Exception:
            pass
    _SPOTIFY_PROC = None
    return {"ok": True, "status": "closed"}


@app.get("/api/spotify/status")
def spotify_status():
    binary = _find_spotify()
    if not binary:
        return {"installed": False, "running": False}
    # Check if any Spotify process is alive — covers cases where the user
    # launched it from outside Klyra.
    running = subprocess.run(
        ["pgrep", "-x", "spotify"], capture_output=True
    ).returncode == 0
    return {"installed": True, "running": running}


# ---- Browser launcher -----------------------------------------------------

BROWSERS = {
    "chrome":  {"name": "Chrome",  "binary": "/usr/bin/google-chrome"},
    "firefox": {"name": "Firefox", "binary": "/usr/bin/firefox"},
    "brave":   {"name": "Brave",   "binary": "/usr/bin/brave-browser-stable"},
}
_BROWSER_PROCS: list[subprocess.Popen] = []


def _read_config_safe() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _resolve_default_browser() -> str | None:
    cfg = _read_config_safe()
    bid = cfg.get("browser")
    if bid in BROWSERS and Path(BROWSERS[bid]["binary"]).exists():
        return bid
    for bid_, b in BROWSERS.items():
        if Path(b["binary"]).exists():
            return bid_
    return None


@app.get("/api/browsers")
def list_browsers():
    return {
        "browsers": [
            {"id": bid, "name": b["name"], "installed": Path(b["binary"]).exists()}
            for bid, b in BROWSERS.items()
        ],
        "default": _resolve_default_browser(),
    }


@app.post("/api/browser/open")
def browser_open():
    bid = _resolve_default_browser()
    if bid is None:
        return JSONResponse({"ok": False, "error": "No browser installed"}, status_code=400)
    binary = BROWSERS[bid]["binary"]
    try:
        proc = subprocess.Popen([binary])
        _BROWSER_PROCS.append(proc)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return {"ok": True, "browser": bid, "name": BROWSERS[bid]["name"]}


# ---- Static frontend (must be mounted last so /api/* wins) ----------------

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Klyra Web UI")
    print("=" * 60)
    print(f"  config.json: {CONFIG_PATH}")
    print(f"  open:        http://localhost:8080")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8080)
