#!/usr/bin/env python3
"""Start AI Story Factory:  python run.py   ->  http://127.0.0.1:8000"""
import sys

from backend import auth, config
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
    if auth.enabled():
        print("  Access:   personal access codes required (SF_ACCESS_CODES)")
    print()


def _is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")


if __name__ == "__main__":
    if not _is_loopback(config.HOST) and not auth.enabled():
        print(f"\n  Refusing to start: SF_HOST is {config.HOST} (reachable by other devices) but SF_ACCESS_CODES is not set.")
        print("  Anyone who can reach this machine could spend your API keys. Set a code, e.g.  set SF_ACCESS_CODES=alice:a-long-random-code\n")
        sys.exit(1)
    banner()
    app.run(host=config.HOST, port=config.PORT, threaded=True, debug=False)
