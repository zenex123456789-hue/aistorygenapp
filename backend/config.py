"""Central configuration.

API keys are read ONLY from environment variables (or a local .env file) and are
never sent to the browser. Non-secret preferences live in the database (see db.py).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:  # real environment wins over .env
            os.environ[key] = value


_load_dotenv()

DATA_DIR = Path(os.getenv("SF_DATA_DIR", str(ROOT / "data"))).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
REFERENCES_DIR = DATA_DIR / "references"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "storyfactory.db"
LIBRARY_DIR = ROOT / "library"
FONTS_DIR = ROOT / "assets" / "fonts"
FRONTEND_DIR = ROOT / "frontend"

for _d in (DATA_DIR, PROJECTS_DIR, REFERENCES_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)
try:                                   # drop your own music/SFX files in here (see README)
    (LIBRARY_DIR / "music").mkdir(parents=True, exist_ok=True)
    (LIBRARY_DIR / "sfx").mkdir(parents=True, exist_ok=True)
except OSError:                        # read-only install location: the library is optional
    pass

FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")

HOST = os.getenv("SF_HOST", "127.0.0.1")
PORT = int(os.getenv("SF_PORT", "8000"))
# Hosted (shared) deployment: the container sets SF_HOSTED=1, and the app then refuses to start without access codes.
HOSTED = os.getenv("SF_HOSTED", "").strip().lower() in ("1", "true", "yes")

# Video constants (the product spec: vertical 9:16, 1080x1920)
WIDTH, HEIGHT = 1080, 1920


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# Provider selection. "auto" = first provider whose key is present, else offline.
DEFAULT_SETTINGS = {
    "llm_provider": env("LLM_PROVIDER", "auto"),
    "tts_provider": env("TTS_PROVIDER", "auto"),
    "image_provider": env("IMAGE_PROVIDER", "auto"),
    "video_provider": env("VIDEO_PROVIDER", "auto"),
    "theme": "system",               # system | light | dark
    # render defaults
    "fps": 24,
    "quality": "standard",          # draft | standard | high
    "visual_mode": "procedural",     # procedural | ai_images | ai_video
    "allow_fallback": True,          # fall back to the offline renderer/voice when a provider fails (always reported)
    "music_volume": 0.16,
    "sfx_volume": 0.55,
    "voice_volume": 1.0,
    "captions": True,
    # viral engine
    "viral_threshold": 65,
    "auto_improve": True,
    "max_rewrites": 1,
}
