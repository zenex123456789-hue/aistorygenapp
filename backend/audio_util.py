"""Small audio helpers shared by TTS providers, the mixer and the lip-sync code."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from . import config

SR = 44100  # mixing sample rate


def run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ffmpeg_ok() -> bool:
    try:
        return run([config.FFMPEG, "-version"], 15).returncode == 0
    except Exception:
        return False


def probe(path: Path) -> dict:
    r = run([config.FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], 60)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path.name}: {r.stderr[-300:]}")
    return json.loads(r.stdout)


def duration(path: Path) -> float:
    info = probe(path)
    return float(info["format"].get("duration") or 0.0)


def to_wav(src: Path, dst: Path, sr: int = SR) -> Path:
    r = run([config.FFMPEG, "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(dst)])
    if r.returncode != 0:
        raise RuntimeError(f"audio decode failed: {r.stderr[-300:]}")
    return dst


def read_wav(path: Path) -> tuple[int, np.ndarray]:
    sr, data = wavfile.read(str(path))
    if data.dtype == np.int16:
        arr = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        arr = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        arr = (data.astype(np.float32) - 128.0) / 128.0
    else:
        arr = data.astype(np.float32)
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    return sr, arr


def write_wav(path: Path, arr: np.ndarray, sr: int = SR) -> None:
    arr = np.clip(arr, -1.0, 1.0)
    wavfile.write(str(path), sr, (arr * 32767).astype(np.int16))


def envelope(arr: np.ndarray, sr: int, fps: int = 24) -> np.ndarray:
    """Per-video-frame loudness 0..1, used to drive mouth movement."""
    hop = max(1, int(sr / fps))
    n = len(arr) // hop + 1
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        seg = arr[i * hop:(i + 1) * hop]
        if len(seg):
            out[i] = float(np.sqrt(np.mean(seg ** 2)))
    peak = float(np.percentile(out, 95)) if n else 0.0
    if peak > 1e-5:
        out = np.clip(out / peak, 0, 1)
    return out


def voiced_region(arr: np.ndarray, sr: int, thresh: float = 0.02) -> tuple[float, float]:
    """Start/end (seconds) of the audible part of a clip (TTS often has padding)."""
    if len(arr) == 0:
        return 0.0, 0.0
    win = max(1, int(sr * 0.01))
    n = len(arr) // win
    rms = np.sqrt(np.mean(arr[: n * win].reshape(n, win) ** 2, axis=1)) if n else np.array([0.0])
    mx = float(rms.max()) or 1e-9
    idx = np.where(rms > max(thresh * mx, 0.004))[0]
    if len(idx) == 0:
        return 0.0, len(arr) / sr
    return float(idx[0] * win / sr), float((idx[-1] + 1) * win / sr)


def estimate_word_timings(text: str, arr: np.ndarray, sr: int) -> list[dict]:
    """Spread words over the voiced region of the clip proportional to their
    length, with extra weight for punctuation pauses. These are ESTIMATES (flagged
    as such in the caption report) used only when the TTS vendor gives no timestamps."""
    words = text.split()
    if not words:
        return []
    t0, t1 = voiced_region(arr, sr)
    span = max(0.2, t1 - t0)
    weights = []
    for w in words:
        core = re.sub(r"\W", "", w)
        wgt = 0.6 + len(core)
        weights.append(wgt)
    pauses = [0.9 if re.search(r"[,;:]$", w) else 1.8 if re.search(r"[.!?…]$", w) else 0.0 for w in words]
    total = sum(weights) + sum(pauses[:-1])
    unit = span / total
    out, t = [], t0
    for w, wgt, pz in zip(words, weights, pauses):
        d = wgt * unit
        out.append({"w": w, "start": round(t, 3), "end": round(t + d, 3)})
        t += d + pz * unit
    return out
