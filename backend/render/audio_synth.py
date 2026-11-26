"""Procedural sound effects and music (numpy only - no samples, so no licensing issues).

Drop your own files into library/sfx/<name>.wav|mp3 or library/music/<mood>*.wav|mp3 and they
are used instead of the synthesised versions.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from scipy.signal import butter, lfilter

from .. import audio_util, config
from ..audio_util import SR


# ---------------------------------------------------------------- primitives
def _n(d: float) -> int:
    return max(1, int(d * SR))


def _t(d: float) -> np.ndarray:
    return np.arange(_n(d)) / SR


def sweep(f0: float, f1: float, d: float, wave: str = "sine", vib: float = 0.0) -> np.ndarray:
    n = _n(d)
    f = np.linspace(f0, f1, n)
    if vib:
        f = f * (1 + vib * np.sin(2 * np.pi * 9 * np.arange(n) / SR))
    ph = 2 * np.pi * np.cumsum(f) / SR
    if wave == "square":
        return np.sign(np.sin(ph)) * 0.6
    if wave == "saw":
        return (2 * ((ph / (2 * np.pi)) % 1) - 1) * 0.6
    if wave == "tri":
        return (2 * np.abs(2 * ((ph / (2 * np.pi)) % 1) - 1) - 1) * 0.8
    return np.sin(ph)


def noise(d: float, seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).normal(0, 0.5, _n(d))


def lp(x, fc, order=2):
    b, a = butter(order, min(fc, SR / 2 - 100) / (SR / 2), "low")
    return lfilter(b, a, x)


def hp(x, fc, order=2):
    b, a = butter(order, fc / (SR / 2), "high")
    return lfilter(b, a, x)


def bp(x, lo, hi):
    b, a = butter(2, [lo / (SR / 2), min(hi, SR / 2 - 100) / (SR / 2)], "band")
    return lfilter(b, a, x)


def decay(x, k):
    return x * np.exp(-np.arange(len(x)) / SR * k)


def swell(x, peak=0.5):
    n = len(x)
    p = np.linspace(0, 1, n)
    return x * np.where(p < peak, p / peak, (1 - p) / (1 - peak))


def fade(x, a=0.005, r=0.02):
    x = x.copy()
    na, nr = min(len(x), _n(a)), min(len(x), _n(r))
    x[:na] *= np.linspace(0, 1, na)
    x[-nr:] *= np.linspace(1, 0, nr)
    return x


def mixd(*parts) -> np.ndarray:
    """Sum signals of different lengths (shorter ones are zero-padded)."""
    n = max(len(x) for x in parts)
    out = np.zeros(n)
    for x in parts:
        out[:len(x)] += x
    return out


def place(buf: np.ndarray, x: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    if i >= len(buf):
        return
    seg = x[: len(buf) - i] if i >= 0 else x[-i:]
    i = max(i, 0)
    buf[i:i + len(seg)] += seg * gain


def midi(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------- SFX
def _bell(f, d):
    t = _t(d)
    return sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * k) for r, a, k in ((1, 1, 2.2), (2.76, 0.5, 3), (5.4, 0.3, 5), (8.9, 0.15, 7)))


def _sfx(name: str) -> np.ndarray:
    if name == "pop":
        return decay(sweep(900, 180, 0.12), 28) + decay(noise(0.12), 90) * 0.5
    if name == "whoosh":
        x = swell(bp(noise(0.7, 3), 400, 5000), 0.45)
        return x * 0.9
    if name == "boing":
        return decay(sweep(180, 620, 0.55, "tri", vib=0.05), 5) * 0.9
    if name == "ding":
        return decay(sweep(1318, 1318, 0.9) + 0.4 * sweep(2637, 2637, 0.9), 5)
    if name == "buzzer":
        return fade(sweep(120, 118, 0.55, "square") * 0.6 + sweep(127, 125, 0.55, "saw") * 0.4, 0.01, 0.05)
    if name == "sparkle":
        out = np.zeros(_n(0.8))
        rng = np.random.default_rng(5)
        for k in range(9):
            place(out, decay(sweep(rng.uniform(2200, 5200), rng.uniform(2200, 5200), 0.18), 18), k * 0.07, 0.5)
        return out
    if name == "poof":
        return mixd(decay(lp(noise(0.45, 7), 1400), 9) * 1.4, decay(sweep(260, 70, 0.2), 20) * 0.6)
    if name == "thud":
        return decay(sweep(95, 38, 0.3), 14) * 1.2 + decay(lp(noise(0.3, 2), 350), 25) * 0.8
    if name == "gasp":
        return swell(bp(noise(0.4, 9), 700, 3500), 0.7)
    if name == "sting":
        t = _t(0.9)
        return decay(sum(sweep(f, f, 0.9, "saw") for f in (233, 277, 349, 392)) * 0.25, 4)
    if name == "drone":
        t = _t(2.5)
        return fade((sweep(55, 55, 2.5, "saw") + sweep(82.4, 82.4, 2.5, "saw") * 0.6) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * t)) * 0.35, 0.3, 0.6)
    if name == "tick":
        out = np.zeros(_n(0.7))
        place(out, decay(hp(noise(0.05, 4), 1500), 120), 0.0, 1.0)
        place(out, decay(hp(noise(0.05, 5), 900), 120), 0.35, 0.8)
        return out
    if name == "chime":
        return _bell(392, 2.2) * 0.5
    if name == "creak":
        return fade(lp(sweep(300, 150, 0.9, "saw") * (0.5 + 0.5 * noise(0.9, 4)), 1500), 0.05, 0.2) * 0.8
    if name == "scratch":
        return fade(lp(sweep(1800, 250, 0.35, "saw"), 3500) * 0.8, 0.005, 0.05)
    if name == "sad_trombone":
        out = np.zeros(_n(1.8))
        for i, (m, d) in enumerate(((58, 0.4), (57, 0.4), (56, 0.4), (54, 0.8))):
            place(out, fade(lp(sweep(midi(m), midi(m) * (0.96 if i == 3 else 1.0), d, "saw", vib=0.02 if i == 3 else 0), 1800), 0.03, 0.08), i * 0.4, 0.7)
        return out
    if name == "transform":
        out = np.zeros(_n(1.1))
        for i in range(8):
            place(out, decay(sweep(midi(60 + i * 3), midi(60 + i * 3), 0.2, "tri"), 12), i * 0.06, 0.6)
        place(out, _sfx("poof"), 0.4, 0.8)
        return out
    if name == "explosion":
        t = _t(1.4)
        return decay(lp(noise(1.4, 6), 1800), 3.2) * 1.4 + decay(sweep(70, 30, 1.4), 3) * 0.8
    if name == "heartbeat":
        out = np.zeros(_n(1.4))
        for at in (0.0, 0.18, 0.7, 0.88):
            place(out, decay(sweep(70, 45, 0.18), 22) * 1.3, at)
        return out
    if name == "alarm":
        out = np.zeros(_n(1.4))
        for i in range(4):
            place(out, fade(sweep(800 if i % 2 == 0 else 1000, 800 if i % 2 == 0 else 1000, 0.34, "square") * 0.4, 0.005, 0.01), i * 0.35)
        return out
    if name == "crowd_gasp":
        out = np.zeros(_n(1.0))
        for k in range(5):
            place(out, swell(bp(noise(0.5, 20 + k), 600 + k * 120, 3200), 0.6), k * 0.05, 0.4)
        return out
    if name == "rumble":
        t = _t(1.8)
        return fade(lp(noise(1.8, 8), 120) * 2.2 * (0.7 + 0.3 * np.sin(2 * np.pi * 7 * t)), 0.2, 0.4)
    if name == "cheer":
        out = np.zeros(_n(1.3))
        for k in range(9):
            place(out, swell(bp(noise(0.9, 40 + k), 800 + k * 150, 4200), 0.4), k * 0.03, 0.3)
        return out
    if name == "laugh_pop":
        out = np.zeros(_n(0.6))
        for i in range(4):
            place(out, decay(sweep(300 + i * 90, 520 + i * 90, 0.12, "tri"), 16), i * 0.11)
        return out
    if name == "wow":
        return fade(np.concatenate([sweep(300, 950, 0.35, "sine", 0.01), sweep(950, 520, 0.4, "sine", 0.02)]) * 0.7, 0.02, 0.15)
    if name == "bonk":
        return mixd(decay(sweep(260, 120, 0.2, "tri"), 22), decay(hp(noise(0.06, 3), 1200), 80) * 0.5)
    if name == "zap":
        return fade(lp(sweep(3200, 180, 0.28, "saw"), 6000) * 0.6, 0.002, 0.03)
    if name == "footsteps":
        out = np.zeros(_n(1.9))
        for k in range(6):
            place(out, decay(lp(noise(0.1, 30 + k), 600), 40) * 1.3, k * 0.3)
        return out
    return decay(sweep(800, 300, 0.1), 30)


_sfx_cache: dict[str, np.ndarray] = {}


def load_sfx(name: str) -> np.ndarray:
    if name in _sfx_cache:
        return _sfx_cache[name]
    for ext in (".wav", ".mp3", ".ogg"):
        f = config.LIBRARY_DIR / "sfx" / f"{name}{ext}"
        if f.exists():
            try:
                tmp = config.CACHE_DIR / f"lib_sfx_{name}.wav"
                audio_util.to_wav(f, tmp)
                _, arr = audio_util.read_wav(tmp)
                _sfx_cache[name] = arr
                return arr
            except Exception:
                pass
    x = _sfx(name).astype(np.float32)
    peak = float(np.max(np.abs(x))) or 1.0
    _sfx_cache[name] = x / peak * 0.8
    return _sfx_cache[name]


def auto_sfx(scene: dict) -> list[dict]:
    """Sound effects implied by the scene data (transformations, flashes...) that the script did not list."""
    have = {s["name"] for s in scene.get("sfx", [])}
    extra = []
    for a in scene.get("actions", []):
        if a["animation"] in ("transform", "vanish", "appear") and "transform" not in have:
            extra.append({"name": "transform", "at": a.get("at", 0) + 0.05})
            have.add("transform")
        if a["animation"] == "faint" and "thud" not in have:
            extra.append({"name": "thud", "at": a.get("at", 0) + 0.5})
            have.add("thud")
        if a["animation"] == "jump" and "boing" not in have and a.get("at", 0) < 3:
            extra.append({"name": "boing", "at": a.get("at", 0) + 0.05})
            have.add("boing")
    ef = scene.get("effects", [])
    if "flash" in ef and "whoosh" not in have:
        extra.append({"name": "whoosh", "at": 0.0})
    if scene.get("kind") == "twist" and "sting" not in have:
        extra.append({"name": "sting", "at": 0.1})
    if "poof" in ef and "poof" not in have:
        extra.append({"name": "poof", "at": 0.35})
    return extra


# ---------------------------------------------------------------- music
MOODS = {
    #            bpm  scale(semitones)        progression (degrees)       drums  wave
    "upbeat":     (126, [0, 2, 4, 5, 7, 9, 11], [0, 4, 5, 3], "four", "square"),
    "silly":      (138, [0, 2, 4, 7, 9], [0, 3, 4, 0], "bounce", "tri"),
    "funky":      (106, [0, 3, 5, 7, 10], [0, 3, 0, 4], "funk", "square"),
    "mysterious": (84, [0, 2, 3, 5, 7, 8, 10], [0, 5, 3, 4], "soft", "tri"),
    "spooky":     (72, [0, 1, 3, 5, 6, 8, 10], [0, 1, 0, 5], "heart", "tri"),
    "tense":      (104, [0, 2, 3, 5, 7, 8, 10], [0, 0, 5, 4], "drive", "saw"),
    "epic":       (96, [0, 2, 3, 5, 7, 8, 10], [0, 5, 2, 6], "four", "saw"),
    "calm":       (72, [0, 2, 4, 7, 9], [0, 3, 4, 0], "none", "sine"),
}


def _note(m: float, d: float, wave: str, vol: float, k: float = 6.0) -> np.ndarray:
    f = midi(m)
    x = sweep(f, f, d, wave) if wave != "sine" else sweep(f, f, d)
    return fade(decay(x, k) * vol, 0.004, 0.02)


def make_music(mood: str, duration: float, seed: int = 0) -> np.ndarray:
    for ext in (".wav", ".mp3", ".ogg"):                       # user library override
        cands = sorted((config.LIBRARY_DIR / "music").glob(f"{mood}*{ext}"))
        if cands:
            try:
                tmp = config.CACHE_DIR / f"lib_music_{mood}.wav"
                audio_util.to_wav(cands[0], tmp)
                _, arr = audio_util.read_wav(tmp)
                reps = int(math.ceil(duration * SR / max(len(arr), 1)))
                return np.tile(arr, reps)[: _n(duration)].astype(np.float32)
            except Exception:
                pass
    bpm, scale, prog, drums, wave = MOODS.get(mood, MOODS["upbeat"])
    rng = np.random.default_rng(seed + hash(mood) % 1000)
    beat = 60.0 / bpm
    root = 48 + (seed % 5)
    out = np.zeros(_n(duration + 2))
    bars = int(duration / (beat * 4)) + 2
    major = mood in ("upbeat", "silly", "calm")
    for bar in range(bars):
        deg = prog[bar % len(prog)]
        base = root + scale[deg % len(scale)]
        t0 = bar * beat * 4
        triad = [base, base + (4 if major else 3), base + 7]
        # bass
        for q in range(4):
            if drums in ("funk",):
                if q in (0, 2):
                    place(out, _note(base - 12, beat * 0.6, "tri", 0.5, 7), t0 + q * beat)
                    place(out, _note(base - 12, beat * 0.3, "tri", 0.4, 9), t0 + q * beat + beat * 0.75)
            elif mood in ("calm", "mysterious", "spooky"):
                if q == 0:
                    place(out, _note(base - 12, beat * 3.6, "sine", 0.55, 0.9), t0)
            else:
                place(out, _note(base - 12 + (7 if q % 2 else 0), beat * 0.45, "tri", 0.5, 8), t0 + q * beat)
        # pad
        if mood in ("calm", "mysterious", "spooky", "epic", "tense"):
            for m in triad:
                place(out, fade(sweep(midi(m + 12), midi(m + 12), beat * 4, "sine") * 0.12 * (0.7 + 0.3 * np.sin(np.linspace(0, math.pi, _n(beat * 4)))), 0.2, 0.3), t0)
        # arp / lead
        steps = 8 if mood not in ("calm", "mysterious", "spooky") else 4
        step_d = beat * 4 / steps
        for s in range(steps):
            if mood in ("mysterious", "spooky") and rng.random() < 0.45:
                continue
            m = triad[(s * (3 if mood == "silly" else 1)) % 3] + 12 + (12 if (s % 4 == 3) else 0)
            if mood == "silly" and s % 2:
                m += 2 if rng.random() < 0.3 else 0
            place(out, _note(m, step_d * 0.8, wave if wave != "saw" else "tri", 0.22 if wave == "square" else 0.2, 10), t0 + s * step_d)
        # drums
        for q in range(8):
            tq = t0 + q * beat / 2
            on_beat = q % 2 == 0
            if drums in ("four", "bounce", "drive") and on_beat:
                place(out, decay(sweep(120, 45, 0.18), 22) * 0.9, tq)
            if drums == "funk" and q in (0, 3, 4, 7):
                place(out, decay(sweep(120, 45, 0.18), 22) * 0.9, tq)
            if drums in ("four", "bounce", "funk", "drive") and q in (2, 6):
                place(out, decay(hp(noise(0.14, q), 1800), 26) * 0.5, tq)
            if drums in ("four", "bounce", "funk", "drive", "soft") and not on_beat:
                place(out, decay(hp(noise(0.05, q + 9), 6000), 70) * 0.25, tq)
            if drums == "heart" and q in (0, 1) and bar % 2 == 0:
                place(out, decay(sweep(65, 40, 0.2), 20) * 0.9, tq)
    out = out[: _n(duration)]
    peak = float(np.max(np.abs(out))) or 1.0
    out = out / peak * 0.8
    k = min(_n(1.2), len(out))
    out[-k:] *= np.linspace(1, 0, k)
    return out.astype(np.float32)


def duck_gain(voice: np.ndarray, depth: float = 0.72) -> np.ndarray:
    """Per-sample music gain that dips while someone is talking (sidechain ducking)."""
    hop = int(SR * 0.01)
    n = len(voice) // hop + 1
    rms = np.array([np.sqrt(np.mean(voice[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(voice) else 0 for i in range(n)])
    pres = (rms > 0.01).astype(np.float32)
    sm = np.zeros(n, dtype=np.float32)
    for i in range(1, n):                              # fast attack (30 ms), slow release (350 ms)
        a = 0.35 if pres[i] > sm[i - 1] else 0.03
        sm[i] = sm[i - 1] + (pres[i] - sm[i - 1]) * a
    g = 1.0 - depth * sm
    return np.interp(np.arange(len(voice)) / hop, np.arange(n), g).astype(np.float32)
