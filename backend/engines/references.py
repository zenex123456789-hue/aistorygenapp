"""Reference engine: measures uploaded images/videos and turns them into reusable style profiles.

Everything under "metrics" is MEASURED with OpenCV/FFmpeg. Fields that need real visual understanding
(character appearance, story structure...) are only filled when a vision-capable LLM is connected, and are
labelled as such. Profiles carry general direction only - never copyrighted characters or footage.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .. import audio_util, config
from . import llm_engine

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    return "image" if ext in IMAGE_EXT else "video" if ext in VIDEO_EXT else "other"


def make_thumb(path: Path, out: Path) -> bool:
    try:
        if kind_of(path) == "image":
            img = cv2.imread(str(path))
            if img is None:
                return False
        else:
            cap = cv2.VideoCapture(str(path))
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n // 5))
            ok, img = cap.read()
            cap.release()
            if not ok:
                return False
        h, w = img.shape[:2]
        k = 360 / max(h, w)
        cv2.imwrite(str(out), cv2.resize(img, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA))
        return True
    except Exception:
        return False


def _palette(frames: list[np.ndarray], k: int = 6) -> list[str]:
    px = np.concatenate([cv2.resize(f, (48, 48), interpolation=cv2.INTER_AREA).reshape(-1, 3) for f in frames]).astype(np.float32)
    k = min(k, len(px))
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(-counts)
    return ["#%02x%02x%02x" % (int(centers[i][2]), int(centers[i][1]), int(centers[i][0])) for i in order]


def _look_stats(frames: list[np.ndarray]) -> dict:
    sats, vals, cons = [], [], []
    for f in frames:
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        sats.append(hsv[:, :, 1].mean() / 255)
        vals.append(hsv[:, :, 2].mean() / 255)
        cons.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).std() / 128)
    return {"saturation": round(float(np.mean(sats)), 3), "brightness": round(float(np.mean(vals)), 3), "contrast": round(float(np.mean(cons)), 3)}


def _composition(frames: list[np.ndarray]) -> dict:
    """Where the visual weight sits (edge density on a 3x3 grid) - a cheap proxy for subject placement."""
    grid = np.zeros((3, 3), dtype=np.float64)
    for f in frames:
        g = cv2.cvtColor(cv2.resize(f, (192, 192)), cv2.COLOR_BGR2GRAY)
        e = cv2.Canny(g, 80, 160).astype(np.float64)
        for r in range(3):
            for c in range(3):
                grid[r, c] += e[r * 64:(r + 1) * 64, c * 64:(c + 1) * 64].mean()
    grid /= max(grid.sum(), 1e-9)
    r_i, c_i = np.unravel_index(np.argmax(grid), grid.shape)
    names_r, names_c = ["upper", "middle", "lower"], ["left", "centre", "right"]
    return {"busiest_region": f"{names_r[r_i]}-{names_c[c_i]}", "centre_weight": round(float(grid[1, 1]), 3),
            "grid": [[round(float(x), 3) for x in row] for row in grid]}


def _text_band(frames: list[np.ndarray]) -> dict:
    """Heuristic caption finder: which horizontal band most consistently holds thin, high-contrast, horizontally
    structured edges (what burned-in subtitles look like)? Confidence is reported; it can be wrong."""
    bands = {"upper": (0.08, 0.28), "middle": (0.40, 0.60), "lower": (0.62, 0.82), "bottom": (0.84, 0.97)}
    score = {k: 0.0 for k in bands}
    for f in frames:
        g = cv2.cvtColor(cv2.resize(f, (270, 480)), cv2.COLOR_BGR2GRAY)
        white = (g > 235).astype(np.uint8)
        dark = cv2.dilate((g < 40).astype(np.uint8), np.ones((5, 5), np.uint8))
        text_like = white & dark                       # bright pixels hugging dark outline pixels
        for k, (a, b) in bands.items():
            score[k] += float(text_like[int(a * 480):int(b * 480)].mean())
    total = sum(score.values())
    best = max(score, key=score.get)
    conf = score[best] / total if total > 0 else 0.0
    present = total / max(len(frames), 1) > 0.004 and conf > 0.4
    return {"position": best if present else "none detected", "confidence": round(conf, 2), "scores": {k: round(v / max(len(frames), 1), 4) for k, v in score.items()}}


def _video_metrics(path: Path) -> tuple[dict, list[np.ndarray]]:
    info = audio_util.probe(path)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    dur = float(info["format"].get("duration") or 0)
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, int(fps / 6))                          # ~6 samples per second
    cuts, diffs, last_hist, last_gray, idx, kept = [], [], None, None, 0, []
    sample_every = max(1, int((n / step) / 18)) if n else 1
    k = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, f = cap.retrieve()
            if not ok:
                break
            small = cv2.resize(f, (160, 284), interpolation=cv2.INTER_AREA)
            hist = cv2.calcHist([cv2.cvtColor(small, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 8], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if last_hist is not None:
                corr = cv2.compareHist(last_hist, hist, cv2.HISTCMP_CORREL)
                d = float(np.mean(cv2.absdiff(gray, last_gray))) / 255
                if corr < 0.55 or d > 0.30:
                    cuts.append(idx / fps)
                else:
                    diffs.append(d)
            last_hist, last_gray = hist, gray
            if k % sample_every == 0 and len(kept) < 18:
                kept.append(f)
            k += 1
        idx += 1
    cap.release()
    duration = dur or (idx / fps)
    shots = len(cuts) + 1
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    loud = None
    if audio:
        r = audio_util.run([config.FFMPEG, "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"], 120)
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
        loud = float(m.group(1)) if m else None
    metrics = {
        "duration_s": round(duration, 2), "fps": round(fps, 1), "width": int(vs["width"]), "height": int(vs["height"]),
        "aspect": round(int(vs["width"]) / max(int(vs["height"]), 1), 3), "vertical": int(vs["height"]) > int(vs["width"]),
        "shots": shots, "avg_shot_length_s": round(duration / shots, 2) if duration else None,
        "cuts_per_minute": round(len(cuts) / duration * 60, 1) if duration else None,
        "motion_intensity": round(float(np.mean(diffs)) if diffs else 0.0, 4), "has_audio": bool(audio), "mean_volume_db": loud,
    }
    return metrics, kept


def analyze(path: Path, llm=None) -> dict:
    kind = kind_of(path)
    if kind == "image":
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError("Cannot read this image.")
        frames, metrics = [img], {"width": img.shape[1], "height": img.shape[0], "vertical": img.shape[0] > img.shape[1]}
    elif kind == "video":
        metrics, frames = _video_metrics(path)
        if not frames:
            raise ValueError("No frames could be read from this video.")
    else:
        raise ValueError("Unsupported file type (use png/jpg/webp or mp4/mov/webm).")
    look = _look_stats(frames)
    result = {"kind": kind, "metrics": metrics, "look": look, "palette": _palette(frames), "composition": _composition(frames),
              "captions_guess": _text_band(frames) if kind == "video" else None, "source": "measured"}
    if llm is not None and not llm.offline:
        try:
            kd = [Path(config.CACHE_DIR / f"ref_{abs(hash(str(path))) % 10**8}_{i}.jpg") for i in range(min(6, len(frames)))]
            sel = [frames[int(i * (len(frames) - 1) / max(len(kd) - 1, 1))] for i in range(len(kd))]
            for p, f in zip(kd, sel):
                cv2.imwrite(str(p), cv2.resize(f, (448, int(448 * f.shape[0] / f.shape[1]))))
            result["llm_analysis"] = llm_engine.analyze_reference(llm, kd, {**metrics, **look})
        except Exception as exc:   # a failed vision call must not hide the measured results
            result["llm_error"] = str(exc)[:300]
    return result


def build_style(name: str, analyses: list[dict]) -> dict:
    """Merge one or more reference analyses into a reusable style profile."""
    pal: list[str] = []
    for a in analyses:
        for c in a["palette"][:4]:
            if c not in pal:
                pal.append(c)
    sat = float(np.mean([a["look"]["saturation"] for a in analyses]))
    bri = float(np.mean([a["look"]["brightness"] for a in analyses]))
    vids = [a for a in analyses if a["kind"] == "video"]
    pacing, pace_scale = {}, 1.0
    if vids:
        asl = float(np.mean([v["metrics"]["avg_shot_length_s"] or 4 for v in vids]))
        cpm = float(np.mean([v["metrics"]["cuts_per_minute"] or 10 for v in vids]))
        pacing = {"avg_shot_length_s": round(asl, 2), "cuts_per_minute": round(cpm, 1),
                  "feel": "very fast" if asl < 1.8 else "fast" if asl < 3 else "moderate" if asl < 5 else "slow"}
        pace_scale = float(np.clip(asl / 4.0, 0.7, 1.25))
    cap = next((v["captions_guess"] for v in vids if v.get("captions_guess") and v["captions_guess"]["position"] != "none detected"), None)
    sub = {"position": cap["position"] if cap else "lower", "size_scale": 1.0, "uppercase": True, "highlight": "#ffe600",
           "source": "measured from references" if cap else "default (none detected)"}
    motion = float(np.mean([v["metrics"]["motion_intensity"] for v in vids])) if vids else None
    camera = None if motion is None else ("dynamic, lots of movement" if motion > 0.06 else "moderate movement" if motion > 0.025 else "mostly static")
    llm_parts = [a["llm_analysis"] for a in analyses if a.get("llm_analysis")]
    directive = " ".join(p.get("directive", "") for p in llm_parts)[:900]
    if not directive:
        directive = (f"Use a {'vivid' if sat > 0.5 else 'muted'}, {'bright' if bri > 0.55 else 'moody'} look"
                     + (f", {pacing['feel']} cutting (about {pacing['avg_shot_length_s']}s per shot)" if pacing else "")
                     + (f", {camera} camera" if camera else "") + ". Original characters and plots only.")
    return {
        "name": name, "palette": pal[:6], "saturation": round(sat, 3), "brightness": round(bri, 3),
        "saturation_scale": round(float(np.clip(sat / 0.55, 0.75, 1.35)), 2), "brightness_scale": round(float(np.clip(bri / 0.65, 0.85, 1.15)), 2),
        "pacing": pacing, "pace_scale": round(pace_scale, 2), "subtitle": sub, "camera": camera,
        "composition": analyses[0].get("composition"), "mood": (llm_parts[0].get("mood") if llm_parts else ("vivid and playful" if sat > 0.5 else "calm")),
        "directive": directive, "llm_analysis": llm_parts[0] if llm_parts else None,
        "needs_llm_for": [] if llm_parts else ["character appearance", "story structure", "detailed camera-angle analysis"],
        "n_references": len(analyses),
    }
