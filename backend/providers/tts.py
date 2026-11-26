"""Text-to-speech adapters: ElevenLabs, OpenAI, and the offline "blip" voice.

The blip voice is NOT speech. It is a synthesised talking-blip sound (the kind used
by retro games) that follows the rhythm, pitch and punctuation of the line so you
can test the whole pipeline - timing, lip-flap, captions - without any API key.
Real voices need ElevenLabs or OpenAI.
"""
from __future__ import annotations

import base64
import re
import time
from pathlib import Path

import numpy as np

from .. import audio_util, config
from .base import ProviderError, TTSProvider, http

DELIVERY_PROMPTS = {
    "natural": "Natural, conversational pacing, like a friendly short-form video creator.",
    "funny": "Comedic timing, playful, exaggerated surprise and cheeky emphasis on the punchline.",
    "dramatic": "Dramatic, slow-burn tension with deliberate pauses.",
    "excited": "High energy, bright and enthusiastic, fast pace.",
    "scared": "Frightened, shaky, breathless and rushed.",
    "sad": "Sad, quiet and heavy, slower pace.",
    "angry": "Angry, sharp and forceful.",
    "whisper": "Whispering, hushed and secretive.",
    "deadpan": "Flat deadpan delivery with very dry humour.",
}

# ElevenLabs voice_settings per delivery: (stability, style)
EL_SETTINGS = {
    "natural": (0.5, 0.15), "funny": (0.3, 0.55), "dramatic": (0.35, 0.6), "excited": (0.25, 0.7),
    "scared": (0.25, 0.6), "sad": (0.5, 0.4), "angry": (0.3, 0.65), "whisper": (0.7, 0.1), "deadpan": (0.85, 0.0),
}


# --------------------------------------------------------------------------- ElevenLabs
class ElevenLabsTTS(TTSProvider):
    name = "elevenlabs"
    label = "ElevenLabs"
    env_keys = ("ELEVENLABS_API_KEY",)
    note = "Voices, accents and word timestamps come from the vendor. Model via ELEVENLABS_MODEL."
    _cache: tuple[float, list[dict]] | None = None

    def _headers(self) -> dict:
        return {"xi-api-key": config.env("ELEVENLABS_API_KEY"), "Content-Type": "application/json"}

    def voices(self) -> list[dict]:
        self.require()
        if ElevenLabsTTS._cache and time.time() - ElevenLabsTTS._cache[0] < 600:
            return ElevenLabsTTS._cache[1]
        r = http("GET", config.env("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io") + "/v1/voices", headers=self._headers(), timeout=60)
        out = []
        for v in r.json().get("voices", []):
            lab = v.get("labels") or {}
            out.append({"id": v["voice_id"], "name": v.get("name", v["voice_id"]), "gender": lab.get("gender", ""),
                        "accent": lab.get("accent", ""), "age": lab.get("age", ""),
                        "description": lab.get("description") or lab.get("use_case") or v.get("category", "")})
        ElevenLabsTTS._cache = (time.time(), out)
        return out

    def synth(self, text, voice_id, out_path, *, delivery="natural", emotion="neutral", speed=1.0, pitch=0.0, accent="") -> dict:
        self.require()
        stab, style = EL_SETTINGS.get(delivery, EL_SETTINGS["natural"])
        body = {"text": text, "model_id": config.env("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
                "voice_settings": {"stability": stab, "similarity_boost": 0.75, "style": style,
                                   "use_speaker_boost": True, "speed": max(0.7, min(1.2, speed))}}
        out_path = out_path.with_suffix(".mp3")
        words = None
        try:   # preferred: audio + character-level timestamps in one call
            r = http("POST", config.env("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io") + f"/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128",
                     headers=self._headers(), json_body=body, timeout=120)
            j = r.json()
            out_path.write_bytes(base64.b64decode(j["audio_base64"]))
            words = _words_from_alignment(text, j.get("alignment") or j.get("normalized_alignment"))
        except (ProviderError, KeyError, ValueError):
            r = http("POST", config.env("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io") + f"/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
                     headers=self._headers(), json_body=body, timeout=120)
            out_path.write_bytes(r.content)
        return {"path": out_path, "words": words, "timing": "exact" if words else None}


def _words_from_alignment(text: str, al: dict | None) -> list[dict] | None:
    if not al or not al.get("characters"):
        return None
    chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur, s, e = [], "", None, None
    for ch, a, b in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"w": cur, "start": round(s, 3), "end": round(e, 3)})
                cur, s = "", None
            continue
        if s is None:
            s = a
        cur += ch
        e = b
    if cur:
        words.append({"w": cur, "start": round(s, 3), "end": round(e, 3)})
    return words or None


# --------------------------------------------------------------------------- OpenAI
class OpenAITTS(TTSProvider):
    name = "openai"
    label = "OpenAI TTS"
    env_keys = ("OPENAI_API_KEY",)
    note = ("Delivery and accent are steered with natural-language instructions (gpt-4o-mini-tts). "
            "No word timestamps, so caption timing is estimated from the audio.")
    CATALOG = [
        ("alloy", "Alloy", "neutral", "balanced, clear"), ("ash", "Ash", "male", "warm, casual"),
        ("ballad", "Ballad", "male", "smooth, expressive"), ("coral", "Coral", "female", "friendly, bright"),
        ("echo", "Echo", "male", "calm, steady"), ("fable", "Fable", "male", "storyteller, lively"),
        ("nova", "Nova", "female", "energetic, upbeat"), ("onyx", "Onyx", "male", "deep, authoritative"),
        ("sage", "Sage", "female", "calm, thoughtful"), ("shimmer", "Shimmer", "female", "soft, gentle"),
        ("verse", "Verse", "male", "dynamic, expressive"),
    ]

    def voices(self) -> list[dict]:
        return [{"id": i, "name": n, "gender": g, "accent": "steerable", "age": "", "description": d}
                for i, n, g, d in self.CATALOG]

    def synth(self, text, voice_id, out_path, *, delivery="natural", emotion="neutral", speed=1.0, pitch=0.0, accent="") -> dict:
        self.require()
        instr = DELIVERY_PROMPTS.get(delivery, DELIVERY_PROMPTS["natural"])
        if accent:
            instr += f" Accent: {accent}."
        if emotion and emotion != "neutral":
            instr += f" Emotion: {emotion}."
        if speed > 1.1:
            instr += " Speak a little quicker."
        elif speed < 0.9:
            instr += " Speak a little slower."
        body = {"model": config.env("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"), "voice": voice_id or "alloy",
                "input": text, "instructions": instr, "response_format": "mp3"}
        r = http("POST", config.env("OPENAI_BASE_URL", "https://api.openai.com") + "/v1/audio/speech",
                 headers={"Authorization": f"Bearer {config.env('OPENAI_API_KEY')}"}, json_body=body, timeout=120)
        out_path = out_path.with_suffix(".mp3")
        out_path.write_bytes(r.content)
        return {"path": out_path, "words": None, "timing": None}


# --------------------------------------------------------------------------- Offline blip voice
class BlipTTS(TTSProvider):
    name = "blip"
    label = "Offline blip voice (not speech)"
    offline = True
    verified = True
    note = ("Synthesised talking blips with exact timing. Placeholder for testing: it does not pronounce words and has "
            "no accents. Connect ElevenLabs or OpenAI for real voices.")

    PRESETS = {
        "blip_bright": ("Blip · Bright", "female", 330, 1.00, "sine"),
        "blip_kid": ("Blip · Kid", "neutral", 300, 1.10, "tri"),
        "blip_teen": ("Blip · Teen", "male", 235, 1.00, "tri"),
        "blip_adult_f": ("Blip · Adult woman", "female", 265, 0.95, "sine"),
        "blip_adult_m": ("Blip · Adult man", "male", 150, 0.92, "tri"),
        "blip_deep": ("Blip · Deep", "male", 105, 0.80, "saw"),
        "blip_elder": ("Blip · Elder", "neutral", 185, 0.80, "sine"),
        "blip_narrator": ("Blip · Narrator", "neutral", 165, 0.95, "tri"),
        "blip_robot": ("Blip · Robot", "neutral", 200, 1.05, "square"),
    }
    # delivery -> pitch x, rate x, jitter, vibrato depth, harshness, breathiness
    DELIVERY = {
        "natural": (1.0, 1.0, 0.06, 0.0, 0.0, 0.0), "funny": (1.12, 1.05, 0.28, 0.0, 0.0, 0.0),
        "dramatic": (0.88, 0.78, 0.05, 0.01, 0.1, 0.0), "excited": (1.2, 1.25, 0.15, 0.0, 0.0, 0.0),
        "scared": (1.25, 1.3, 0.10, 0.07, 0.0, 0.0), "sad": (0.85, 0.75, 0.04, 0.0, 0.0, 0.0),
        "angry": (0.9, 1.15, 0.10, 0.0, 0.5, 0.0), "whisper": (1.0, 1.0, 0.05, 0.0, 0.0, 0.9),
        "deadpan": (0.95, 0.9, 0.0, 0.0, 0.0, 0.0),
    }
    VOWELS = {"a": [1, .6, .5, .3, .15], "e": [1, .4, .2, .5, .3], "i": [1, .2, .1, .6, .5],
              "o": [1, .7, .2, .1, .05], "u": [1, .3, .05, .02, 0], "y": [1, .3, .3, .4, .2]}
    SEMI = {"a": 0, "e": 2, "i": 4, "o": -2, "u": -3, "y": 3}
    RATE = 24000

    def configured(self) -> bool:
        return True

    def voices(self) -> list[dict]:
        return [{"id": k, "name": v[0], "gender": v[1], "accent": "n/a", "age": "", "description": "placeholder blip voice"}
                for k, v in self.PRESETS.items()]

    def synth(self, text, voice_id, out_path, *, delivery="natural", emotion="neutral", speed=1.0, pitch=0.0, accent="") -> dict:
        preset = self.PRESETS.get(voice_id) or self.PRESETS["blip_teen"]
        _, _, base, rate_k, wave = preset
        px, rx, jitter, vib, harsh, breath = self.DELIVERY.get(delivery, self.DELIVERY["natural"])
        if emotion in ("scared", "excited") and delivery == "natural":
            px, rx = (1.15, 1.2)
        base = base * (2 ** (pitch * 0.35)) * px
        rate = rate_k * rx * max(0.6, min(1.5, speed))
        rng = np.random.default_rng(abs(hash((text, voice_id))) % (2 ** 32))
        sr = self.RATE
        chunks: list[np.ndarray] = []
        words: list[dict] = []
        t = 0.0

        def add(arr: np.ndarray) -> None:
            nonlocal t
            chunks.append(arr)
            t += len(arr) / sr

        for word in text.split():
            core = re.sub(r"[^A-Za-z']", "", word).lower() or "a"
            groups = re.findall(r"[aeiouy]+|[^aeiouy]+", core)
            sylls = []
            for g in groups:
                if g[0] in self.VOWELS:
                    sylls.append(g)
                elif sylls:
                    sylls[-1] += g
                else:
                    sylls.append(g)
            if not sylls:
                sylls = ["a"]
            w_start = t
            question = word.endswith("?")
            excl = word.endswith("!")
            for si, syl in enumerate(sylls):
                v = next((c for c in syl if c in self.VOWELS), "a")
                semi = self.SEMI.get(v, 0) + float(rng.normal(0, 1.5)) * jitter * 6
                f0 = base * 2 ** (semi / 12)
                if si == len(sylls) - 1 and (question or excl):
                    f_end = f0 * (1.35 if question else 1.12)
                else:
                    f_end = f0 * (0.97 if si == len(sylls) - 1 else 1.0)
                dur = (0.075 + 0.012 * min(len(syl), 4)) / rate
                if si == len(sylls) - 1 and delivery == "dramatic":
                    dur *= 1.4
                n = int(dur * sr)
                tt = np.arange(n) / sr
                f = np.linspace(f0, f_end, n)
                if vib:
                    f = f * (1 + vib * np.sin(2 * np.pi * 8 * tt))
                phase = 2 * np.pi * np.cumsum(f) / sr
                if wave == "square":
                    sig = np.sign(np.sin(phase)) * 0.45
                elif wave == "saw":
                    sig = (2 * ((phase / (2 * np.pi)) % 1) - 1) * 0.5
                elif wave == "tri":
                    sig = (2 * np.abs(2 * ((phase / (2 * np.pi)) % 1) - 1) - 1) * 0.5
                else:
                    sig = np.zeros(n)
                amps = self.VOWELS.get(v, self.VOWELS["a"])
                harm = sum(a * np.sin((k + 1) * phase) for k, a in enumerate(amps)) / 2.2
                sig = 0.55 * harm + 0.45 * sig if wave != "sine" else harm
                if harsh:
                    sig = np.tanh(sig * (1 + 3 * harsh))
                if breath:
                    noise = rng.normal(0, 0.35, n)
                    noise = np.convolve(noise, np.ones(6) / 6, mode="same")
                    sig = (1 - breath) * sig * 0.3 + breath * noise
                env = np.ones(n)
                a, r = int(0.006 * sr), int(0.03 * sr)
                env[:a] = np.linspace(0, 1, a)
                env[-r:] *= np.linspace(1, 0, r)
                stress = 1.0 if si == 0 else 0.85
                add((sig * env * stress * 0.55).astype(np.float32))
                add(np.zeros(int(0.008 * sr), dtype=np.float32))
            w_end = t
            words.append({"w": word, "start": round(w_start, 3), "end": round(w_end, 3)})
            gap = 0.045
            if word.endswith((",", ";", ":")):
                gap = 0.15
            elif word.endswith((".", "!", "?", "…")):
                gap = 0.30
            add(np.zeros(int(gap / rate_k * sr), dtype=np.float32))
        audio = np.concatenate(chunks) if chunks else np.zeros(int(0.2 * sr), dtype=np.float32)
        peak = float(np.max(np.abs(audio))) or 1.0
        audio = audio / peak * 0.65
        out_path = out_path.with_suffix(".wav")
        audio_util.write_wav(out_path, audio, sr)
        return {"path": out_path, "words": words, "timing": "exact"}
