"""Gameplay footage: the user's own screen recordings (Roblox, Minecraft, anything) used as the picture behind the story.

Stored under data/footage/<id>/ with a small meta.json, a thumbnail and the original file. Nothing is downloaded from anywhere: the clips
are only what the user uploads, and the app never connects to any game.
"""
from __future__ import annotations

import json
import re
import shutil
import time
import zlib
from pathlib import Path

from . import audio_util, config, db
from .engines import references

EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ID_RE = re.compile(r"^f_[0-9a-f]{10}$")
MIN_SECONDS = 2.0


def _read(d: Path) -> dict | None:
    try:
        return json.loads((d / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def list_all() -> list[dict]:
    out = []
    for d in config.FOOTAGE_DIR.iterdir():
        m = _read(d) if d.is_dir() else None
        if m:
            out.append(m)
    out.sort(key=lambda m: m.get("created", 0), reverse=True)
    return out


def get(fid: str) -> dict | None:
    if not fid or not ID_RE.match(fid):
        return None
    return _read(config.FOOTAGE_DIR / fid)


def video_path(meta: dict) -> Path:
    return config.FOOTAGE_DIR / meta["id"] / meta["file"]


def thumb_path(meta: dict) -> Path:
    return config.FOOTAGE_DIR / meta["id"] / "thumb.jpg"


def add(storage, filename: str) -> dict:
    """Save an uploaded clip after checking with ffprobe that it really is a video of a usable length. Raises ValueError with a plain message."""
    name = Path(filename).name or "footage"
    if Path(name).suffix.lower() not in EXT:
        raise ValueError(f"{name}: use an mp4, mov, m4v, webm or mkv screen recording.")
    fid = db.new_id("f_")
    d = config.FOOTAGE_DIR / fid
    d.mkdir(parents=True, exist_ok=True)
    try:
        path = d / ("clip" + Path(name).suffix.lower())
        storage.save(path)
        try:
            info = audio_util.probe(path)
        except Exception:
            raise ValueError(f"{name}: this file could not be read as a video.")
        v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        dur = float(info["format"].get("duration") or 0)
        if not v:
            raise ValueError(f"{name}: no video was found in this file.")
        if dur < MIN_SECONDS:
            raise ValueError(f"{name}: the clip is only {dur:.1f} s long. Use one that is at least {MIN_SECONDS:.0f} s (longer is better, so the footage does not repeat).")
        meta = {"id": fid, "name": name, "file": path.name, "duration": round(dur, 2), "width": int(v["width"]), "height": int(v["height"]),
                "size_mb": round(path.stat().st_size / 1e6, 2), "created": time.time()}
        meta["thumb"] = bool(references.make_thumb(path, d / "thumb.jpg"))
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise


def remove(fid: str) -> None:
    if fid and ID_RE.match(fid):
        shutil.rmtree(config.FOOTAGE_DIR / fid, ignore_errors=True)


def plan(meta: dict, total: float, seed: str) -> dict:
    """Which part of the clip to use. A clip longer than the video is used once from a start point picked from the project id (so a re-render
    repeats the same choice); a shorter one loops from the beginning."""
    dur = float(meta["duration"])
    spare = dur - total - 0.5
    if spare > 0:
        start = (zlib.crc32(seed.encode()) % 1000) / 1000 * spare
        return {"start": round(start, 2), "loop": False}
    return {"start": 0.0, "loop": True}
