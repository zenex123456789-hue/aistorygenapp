"""Art styles ("looks") for the video.

A look changes two things in the built-in renderer, so each one is really drawn and nothing is faked:

* the shapes of the characters (how round they are, how heavy the outline is, head and eye size), read by rig.py;
* a per-frame filter applied to the finished picture (pixelation, comic ink and halftone, pencil sketch, soft glow).

Two looks (realistic, anime) cannot be drawn by a procedural renderer. They are made by an AI image provider:
without one, the video is drawn in the look named in `fallback` and the project says so.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np


@dataclass(frozen=True)
class Look:
    id: str
    label: str
    blurb: str
    procedural: bool = True           # False: needs an AI image provider
    fallback: str = "cartoon"         # used when an AI-only look has no AI provider
    radius: float = 1.0               # corner roundness multiplier for every body part
    outline: float = 1.0              # outline thickness multiplier
    head: float = 1.0                 # head size multiplier
    eyes: float = 1.0                 # eye size multiplier
    sparkle_eyes: bool = False        # white highlight in the eyes
    writer: str = ""                  # how the story writer is told to picture it
    prompt: str = ""                  # how an image model is told to draw it
    tags: tuple = ()                  # hashtags that fit this look
    filter: Callable | None = None    # (frame BGR uint8, t seconds) -> frame


# ----------------------------------------------------------------- frame filters
_lut_cache: dict = {}
_pattern_cache: dict = {}


def _levels_lut(levels: int) -> np.ndarray:
    if levels not in _lut_cache:
        step = 256.0 / levels
        _lut_cache[levels] = np.array([min(255, int((int(i / step) + 0.5) * step)) for i in range(256)], np.uint8)
    return _lut_cache[levels]


def _pixel(img: np.ndarray, t: float) -> np.ndarray:
    h, w = img.shape[:2]
    bs = max(2, int(round(w / 150)))                                   # about 150 big pixels across, at any render size
    small = cv2.resize(img, (max(1, w // bs), max(1, h // bs)), interpolation=cv2.INTER_AREA)
    small = cv2.LUT(small, _levels_lut(6))                             # a limited retro palette
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def _halftone_mask(h: int, w: int) -> np.ndarray:
    key = (h, w)
    if key not in _pattern_cache:
        s = max(6, int(round(w / 90)))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        u, v = (xx + yy) * 0.7071, (xx - yy) * 0.7071                  # dots on a 45 degree grid, like printed comics
        du, dv = (u % s) - s / 2, (v % s) - s / 2
        _pattern_cache[key] = (du * du + dv * dv) < (s * 0.30) ** 2
    return _pattern_cache[key]


def _comic(img: np.ndarray, t: float) -> np.ndarray:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    out = cv2.LUT(img, _levels_lut(5))                                 # flat ink colours
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = np.minimum(255, hsv[:, :, 1].astype(np.uint16) * 5 // 4).astype(np.uint8)
    out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    shadow = (gray < 90) & _halftone_mask(h, w)                       # halftone dots in the dark areas
    out[shadow] = (out[shadow] * 0.62).astype(np.uint8)
    small = cv2.resize(gray, (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(cv2.GaussianBlur(small, (0, 0), 1.2), 70, 165)
    edges = cv2.resize(edges, (w, h), interpolation=cv2.INTER_LINEAR) > 40
    out[edges] = (22, 16, 16)                                          # bold black ink lines
    return out


def _paper(h: int, w: int) -> np.ndarray:
    key = ("paper", h, w)
    if key not in _pattern_cache:
        rng = np.random.default_rng(5)
        noise = cv2.resize(rng.random((max(2, h // 3), max(2, w // 3))).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
        base = np.array([0.90, 0.95, 0.98], np.float32)                # warm off-white (BGR)
        _pattern_cache[key] = (base[None, None, :] * (0.97 + 0.03 * noise[:, :, None])).astype(np.float32)
    return _pattern_cache[key]


def _sketch(img: np.ndarray, t: float) -> np.ndarray:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(255 - gray, (0, 0), max(2.0, w / 110))
    line = cv2.divide(gray, np.maximum(255 - blur, 1), scale=256)      # pencil outline (colour dodge)
    line = np.clip((line.astype(np.float32) / 255.0) ** 1.8, 0, 1)
    k = int(t * 8) % 3 - 1                                             # lines wobble slightly, like a hand-drawn boil
    line = np.roll(line, (k, -k), axis=(0, 1))
    wash = cv2.addWeighted(img, 0.72, np.full_like(img, 255), 0.28, 0).astype(np.float32) / 255.0   # watercolour wash
    g3 = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
    wash = wash * 0.85 + (0.55 + 0.45 * g3) * 0.15
    out = wash * line[:, :, None] * _paper(h, w)
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


def _cartoon(img: np.ndarray, t: float) -> np.ndarray:
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = np.minimum(255, hsv[:, :, 1].astype(np.uint16) * 9 // 8).astype(np.uint8)
    out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    small = cv2.resize(out, (max(1, w // 5), max(1, h // 5)), interpolation=cv2.INTER_AREA)
    glow = cv2.resize(cv2.GaussianBlur(small, (0, 0), 6), (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.addWeighted(out, 0.88, glow, 0.20, 4)                   # soft, friendly bloom


# ----------------------------------------------------------------- the list
LOOKS: dict[str, Look] = {l.id: l for l in [
    Look("blocky", "Blocky 3D (Roblox-like)", "Chunky square characters and a toy-block world. The original look.",
         writer='stylised, blocky 3D "Roblox-inspired" animated', tags=("#roblox", "#robloxstory"),
         prompt="a stylised blocky 3D toy-like animated short (blocky game-avatar look, original characters, bright saturated colours, clean lighting)"),
    Look("cartoon", "Round cartoon", "Soft, round, friendly 2D cartoon characters with big eyes and a gentle glow.",
         radius=3.6, outline=0.85, head=1.3, eyes=1.5, sparkle_eyes=True, filter=_cartoon,
         writer="friendly 2D cartoon (round shapes, big expressive eyes) animated", tags=("#cartoon",),
         prompt="a bright 2D cartoon short with round friendly characters, thick clean outlines and flat saturated colours"),
    Look("pixel", "Pixel art", "A retro 16-bit game look: big visible pixels and a small colour palette.",
         radius=0.3, outline=2.2, filter=_pixel,
         writer="retro 16-bit pixel-art game cutscene", tags=("#pixelart", "#retrogaming"),
         prompt="a retro pixel-art game cutscene, 16-bit style, limited colour palette, clearly visible pixels"),
    Look("comic", "Comic book", "Bold black ink lines, flat punchy colours and halftone dots in the shadows.",
         radius=0.7, outline=1.5, eyes=1.1, filter=_comic,
         writer="bold comic-book (thick ink outlines, halftone shading) animated", tags=("#comic", "#comicbook"),
         prompt="a comic-book style animated short: bold black ink outlines, halftone dot shading, punchy flat colours"),
    Look("sketch", "Ink sketch", "Pencil outlines with a light watercolour wash on warm paper, like a storyboard.",
         radius=1.3, outline=0.9, head=1.05, filter=_sketch,
         writer="hand-drawn ink-and-watercolour storyboard", tags=("#sketch", "#handdrawn"),
         prompt="a hand-drawn ink and watercolour storyboard look: loose pencil outlines on warm paper"),
    Look("anime", "Anime (needs AI images)", "Cel-shaded anime pictures. Made by an AI image provider, so it needs an OpenAI key.",
         procedural=False, fallback="cartoon", writer="anime-style animated", tags=("#anime",),
         prompt="an anime style animated short: cel-shaded characters, big expressive eyes, clean line art, painted backgrounds"),
    Look("realistic", "Realistic (needs AI images)", "Photo-like cinematic pictures. Made by an AI image provider, so it needs an OpenAI key.",
         procedural=False, fallback="cartoon", writer="realistic, cinematic live-action-style", tags=("#cinematic",),
         prompt="a realistic cinematic live-action look: natural lighting, shallow depth of field, photographic detail, real-looking people"),
]}
IDS = list(LOOKS)
DEFAULT = "blocky"


def get(look_id: str | None) -> Look:
    return LOOKS.get(look_id or DEFAULT) or LOOKS[DEFAULT]


def drawn(look_id: str | None) -> Look:
    """The look the built-in renderer actually draws (an AI-only look is drawn as its fallback when there is no AI image)."""
    lk = get(look_id)
    return lk if lk.procedural else get(lk.fallback)


def apply(look: Look | None, img: np.ndarray, t: float) -> np.ndarray:
    if look is None or look.filter is None:
        return img
    return look.filter(img, t)


def public() -> list[dict]:
    return [{"id": l.id, "label": l.label, "blurb": l.blurb, "procedural": l.procedural,
             "fallback": get(l.fallback).label if not l.procedural else ""} for l in LOOKS.values()]
