#!/usr/bin/env python3
"""AI Story Factory as a desktop app (used by the Windows installer).

Runs the same server as `python run.py`, but on a private local port, and shows it in a native window.
User data (projects, videos, API keys) lives in  %LOCALAPPDATA%\\AIStoryFactory  so updates never touch it.

  AIStoryFactory.exe              open the app
  AIStoryFactory.exe --selftest   start the server, check it answers, exit 0/1 (used by the build to catch a broken bundle)
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
HERE = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent


def user_dir() -> Path:
    """%LOCALAPPDATA%\\AIStoryFactory on Windows; SF_HOME overrides it (used for testing)."""
    if os.environ.get("SF_HOME"):
        p = Path(os.environ["SF_HOME"])
    else:
        p = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "AIStoryFactory"
    p.mkdir(parents=True, exist_ok=True)
    return p


def setup_logging(home: Path) -> None:
    """A windowed app has no console (sys.stdout/stderr are None), so send output to a log file."""
    try:
        log = open(home / "app.log", "a", buffering=1, encoding="utf-8")
        sys.stdout = sys.stderr = log
    except OSError:
        pass


def hide_child_consoles() -> None:
    """Without this, every FFmpeg call flashes a black console window."""
    if os.name != "nt":
        return
    orig = subprocess.Popen.__init__

    def init(self, *a, **kw):
        kw["creationflags"] = kw.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
        orig(self, *a, **kw)

    subprocess.Popen.__init__ = init


def load_user_env(home: Path) -> None:
    f = home / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def pick_port() -> int:
    for port in (8000, 8001, 8002):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(port: int, timeout: float = 40) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.25)
    return False


def start_server(port: int):
    from werkzeug.serving import make_server
    from backend.app import app
    srv = make_server("127.0.0.1", port, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def selftest(port: int, home: Path) -> int:
    import urllib.request
    result = {"ok": False}
    try:
        start_server(port)
        if not wait_for(port):
            raise RuntimeError("server did not start")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=10) as r:
            health = json.loads(r.read())
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r:
            index_ok = r.status == 200 and b"Story Factory" in r.read()
        result.update(health=health, index_ok=index_ok, ok=bool(health.get("ok") and health.get("ffmpeg") and index_ok))
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
    (home / "selftest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


def show_window(url: str) -> None:
    """Native window via pywebview (Edge WebView2). If that is unavailable, fall back to the default browser."""
    try:
        import webview
        try:
            webview.settings["ALLOW_DOWNLOADS"] = True      # lets "Download" buttons save the MP4
        except Exception:  # noqa: BLE001
            pass
        webview.create_window("AI Story Factory", url, width=1280, height=860, min_size=(480, 640))
        webview.start()
        return
    except Exception as e:  # noqa: BLE001
        print("Native window unavailable, using your browser instead:", repr(e))
    import webbrowser
    webbrowser.open(url)
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title("AI Story Factory")
        root.geometry("360x120")
        tk.Label(root, text="AI Story Factory is running in your browser.\nClose this window to stop it.", pady=24).pack()
        root.mainloop()
    except Exception:  # noqa: BLE001
        while True:
            time.sleep(3600)


def main() -> int:
    home = user_dir()
    setup_logging(home)
    hide_child_consoles()
    os.environ.setdefault("SF_DATA_DIR", str(home / "data"))
    ff = HERE / "ffmpeg"
    if (ff / "ffmpeg.exe").exists():
        os.environ.setdefault("FFMPEG_BIN", str(ff / "ffmpeg.exe"))
        os.environ.setdefault("FFPROBE_BIN", str(ff / "ffprobe.exe"))
    load_user_env(home)
    port = pick_port()
    os.environ["SF_PORT"] = str(port)
    os.environ["SF_HOST"] = "127.0.0.1"

    if "--selftest" in sys.argv:
        return selftest(port, home)

    start_server(port)
    if not wait_for(port):
        print("Server failed to start; see app.log")
        return 1
    show_window(f"http://127.0.0.1:{port}")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)   # the server thread is a daemon; exit immediately when the window closes
