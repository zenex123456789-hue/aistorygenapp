#!/usr/bin/env python3
"""Start AI Story Factory:  python run.py   ->  http://127.0.0.1:8000"""
import sys

from backend import config
from backend.app import app
from backend.audio_util import ffmpeg_ok
from backend import providers


def banner() -> None:
    caps = providers.capabilities()
    print("\n  AI Story Factory")
    print("  ─────────────────────────────────────────")
    print(f"  FFmpeg:   {'found' if ffmpeg_ok() else 'NOT FOUND - install FFmpeg, rendering needs it'}")
    for kind, label in (("llm", "Writer "), ("tts", "Voices "), ("image", "Images "), ("video", "Video  ")):
        active = next(p for p in caps[kind]["providers"] if p["active"])
        tag = "offline fallback" if active["offline"] else "connected"
        print(f"  {label}  {active['label']}  [{tag}]")
    print(f"  Data:     {config.DATA_DIR}")
    print(f"  Open:     http://{config.HOST}:{config.PORT}")
    print()


if __name__ == "__main__":
    banner()
    app.run(host=config.HOST, port=config.PORT, threaded=True, debug=False)
