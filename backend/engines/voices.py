"""Voice casting + per-line synthesis with caching."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .. import audio_util
from ..providers.base import ProviderError, TTSProvider

BLIP_BY_PROFILE = {
    ("kid", "any"): "blip_kid", ("teen", "male"): "blip_teen", ("teen", "female"): "blip_bright", ("teen", "neutral"): "blip_teen",
    ("adult", "male"): "blip_adult_m", ("adult", "female"): "blip_adult_f", ("adult", "neutral"): "blip_adult_m",
    ("elder", "any"): "blip_elder",
}


def _profile_key(ch: dict) -> tuple[str, str]:
    age = ch.get("age_look", "adult")
    g = ch["voice"].get("gender", "neutral")
    return (age, "any") if age in ("kid", "elder") else (age, g)


def assign_voices(chars: list[dict], tts: TTSProvider, keep_existing: bool = True) -> list[str]:
    """Give each character a distinct voice from the active provider. Returns warnings."""
    voices = tts.voices()
    used: set[str] = set()
    warnings: list[str] = []
    for ch in chars:
        v = ch["voice"]
        if keep_existing and v.get("provider") == tts.name and v.get("voice_id") and any(x["id"] == v["voice_id"] for x in voices):
            used.add(v["voice_id"])
    for ch in chars:
        v = ch["voice"]
        if keep_existing and v.get("provider") == tts.name and v.get("voice_id") in used:
            continue
        choice = None
        if tts.name == "blip":
            if ch.get("is_narrator"):
                choice = "blip_narrator"
            elif ch.get("role") == "villain":
                choice = "blip_deep"
            else:
                choice = BLIP_BY_PROFILE.get(_profile_key(ch)) or "blip_teen"
            if choice in used:
                choice = next((x["id"] for x in voices if x["id"] not in used), choice)
        else:
            g = v.get("gender", "neutral")
            acc = (v.get("accent") or "").lower()

            def score(x: dict) -> float:
                s = 0.0
                if x["id"] in used:
                    s -= 100
                if g != "neutral" and x.get("gender", "").lower() == g:
                    s += 10
                elif g != "neutral" and x.get("gender"):
                    s -= 6
                if acc and acc in (x.get("accent") or "").lower():
                    s += 6
                if ch.get("is_narrator") and any(k in (x.get("description") or "").lower() for k in ("narrat", "story", "calm", "warm")):
                    s += 4
                if ch.get("age_look") == "kid" and "young" in (x.get("age") or "").lower():
                    s += 4
                return s
            if voices:
                choice = max(voices, key=score)["id"]
        if not choice:
            warnings.append(f"No voice available for {ch['name']}")
            continue
        used.add(choice)
        v["voice_id"], v["provider"] = choice, tts.name
    return warnings


def cache_key(provider: str, voice_id: str, delivery: str, emotion: str, speed: float, pitch: float, accent: str, text: str) -> str:
    raw = json.dumps([provider, voice_id, delivery, emotion, round(speed, 2), round(pitch, 2), accent, text])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def synth_line(tts: TTSProvider, ch: dict, line: dict, audio_dir: Path, fps: int = 24) -> dict:
    """Synthesise one dialogue line. Returns an asset dict; audio is trimmed of silence so timing is tight."""
    v = ch["voice"]
    delivery = line.get("delivery") or v.get("default_delivery", "natural")
    if delivery == "natural" and v.get("default_delivery") not in (None, "natural"):
        delivery = v["default_delivery"]
    key = cache_key(tts.name, v["voice_id"], delivery, line["emotion"], v.get("speed", 1.0), v.get("pitch", 0.0), v.get("accent", ""), line["text"])
    wav = audio_dir / f"{key}.wav"
    meta = audio_dir / f"{key}.json"
    if wav.exists() and meta.exists():
        asset = json.loads(meta.read_text())
        asset["cached"] = True
        asset["wav"] = str(wav)
        return asset
    raw = audio_dir / f"{key}_raw"
    res = tts.synth(line["text"], v["voice_id"], raw, delivery=delivery, emotion=line["emotion"], speed=v.get("speed", 1.0),
                    pitch=v.get("pitch", 0.0), accent=v.get("accent", ""))
    src = Path(res["path"])
    full = audio_dir / f"{key}_full.wav"
    audio_util.to_wav(src, full)
    sr, arr = audio_util.read_wav(full)
    t0, t1 = audio_util.voiced_region(arr, sr)
    pad0, pad1 = max(0.0, t0 - 0.03), min(len(arr) / sr, t1 + 0.06)
    seg = arr[int(pad0 * sr):int(pad1 * sr)]
    if len(seg) < sr * 0.1:
        raise ProviderError(f"{tts.label} returned silent audio for: {line['text'][:40]}")
    audio_util.write_wav(wav, seg.astype(np.float32), sr)
    words = res.get("words")
    timing = res.get("timing")
    if words:
        words = [{"w": w["w"], "start": round(max(0.0, w["start"] - pad0), 3), "end": round(max(0.0, w["end"] - pad0), 3)} for w in words]
    else:
        words = audio_util.estimate_word_timings(line["text"], seg, sr)
        timing = "estimated"
    asset = {"wav": str(wav), "duration": round(len(seg) / sr, 3), "words": words, "timing": timing, "provider": tts.name,
             "voice_id": v["voice_id"], "delivery": delivery, "text": line["text"], "cached": False}
    meta.write_text(json.dumps({k: v_ for k, v_ in asset.items() if k != "wav"}))
    for tmp in (full, src):
        try:
            tmp.unlink()
        except OSError:
            pass
    return asset
