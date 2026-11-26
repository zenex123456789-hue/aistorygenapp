"""Character reference sheets and location previews (drawn with the same rig used in the video)."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .. import config
from . import rig
from .draw import Cam, Canvas, bgr
from .scene import render_still

_font_cache: dict = {}


def _font(size: int, bold: bool = True):
    key = (size, bold)
    if key not in _font_cache:
        f = config.FONTS_DIR / ("Poppins-Bold.ttf" if bold else "Poppins-Medium.ttf")
        try:
            _font_cache[key] = ImageFont.truetype(str(f), size)
        except Exception:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def _place(img: np.ndarray, wx: float, wy: float, sx: float, sy: float, zoom: float = 1.0) -> Canvas:
    cam = Cam(zoom, wx - (sx - 540) / zoom, wy - (sy - 960) / zoom)
    return Canvas(img, cam, 1.0)


def character_sheet(ch: dict) -> np.ndarray:
    W_, H_ = 1500, 1000
    top, bot = np.array([250, 244, 255], np.float32), np.array([235, 245, 255], np.float32)
    t = np.linspace(0, 1, H_, dtype=np.float32)[:, None, None]
    img = np.repeat((top * (1 - t) + bot * t), W_, axis=1).astype(np.uint8)
    cv2.rectangle(img, (40, 40), (560, 960), (255, 255, 255), -1, cv2.LINE_AA)
    cv2.rectangle(img, (40, 40), (560, 960), (225, 215, 235), 3, cv2.LINE_AA)
    cv2.ellipse(img, (300, 880), (200, 22), 0, 0, 360, (235, 228, 240), -1, cv2.LINE_AA)
    cv = _place(img, 0, 0, 300, 880)
    pose = rig.make_pose("idle", 0.0, "neutral", 0.0, 0.0)
    rig.draw_character(cv, ch, 0, 0, 1.5, pose, emotion=ch.get("signature_expression", "neutral"), t=0.1)
    # expression strip
    exps = (ch.get("expressions") or ["neutral", "happy", "surprised", "scared", "angry"])[:6]
    for i, e in enumerate(exps):
        col, row = i % 3, i // 3
        cx, cy = 700 + col * 260, 360 + row * 330
        cv2.rectangle(img, (cx - 115, cy - 150), (cx + 115, cy + 125), (255, 255, 255), -1, cv2.LINE_AA)
        cv2.rectangle(img, (cx - 115, cy - 150), (cx + 115, cy + 125), (225, 215, 235), 2, cv2.LINE_AA)
        c2 = _place(img, 0, 0, cx, cy + 105, 1.0)
        rig.draw_character(c2, ch, 0, 0, 0.42, rig.make_pose("idle", 0, e, 0.0, 0.0), emotion=e, t=0.1)
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    d.text((620, 50), ch["name"], font=_font(64), fill=(40, 30, 60))
    d.text((622, 128), f"{ch.get('role', '').title()} · looks {ch.get('age_look', '')} · {ch.get('build', '')} build", font=_font(26, False), fill=(110, 100, 130))
    pers = ch.get("personality", "")
    d.text((622, 168), pers[:70], font=_font(24, False), fill=(110, 100, 130))
    d.text((622, 700), "EXPRESSIONS", font=_font(20), fill=(150, 140, 170))
    sw = [("Skin", ch["skin"]), ("Hair", ch["hair_color"]), ("Shirt", ch["shirt_color"]), ("Pants", ch["pants_color"]),
          ("Shoes", ch["shoes_color"]), ("Accent", ch.get("accessory_color", "#ffd166"))]
    for i, (lab, hx) in enumerate(sw):
        x = 622 + i * 140
        d.rounded_rectangle((x, 790, x + 110, 860), 14, fill=hx, outline=(60, 50, 80), width=3)
        d.text((x, 870), f"{lab}", font=_font(20), fill=(70, 60, 90))
        d.text((x, 896), hx, font=_font(18, False), fill=(130, 120, 150))
    d.text((622, 930), f"Hair: {ch.get('hair_style')} · Accessory: {ch.get('accessory')} · Pattern: {ch.get('shirt_pattern')}", font=_font(20, False), fill=(110, 100, 130))
    v = ch.get("voice", {})
    d.text((622, 962), f"Voice: {v.get('gender', '')}, {v.get('accent', '')}", font=_font(18, False), fill=(130, 120, 150))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def world_preview(world: dict) -> np.ndarray:
    plan = {"scene": {"id": "preview_" + world["id"], "camera": {"shot": "wide", "move": "static"}, "emotion": "neutral",
                      "effects": [], "actions": [], "environment": {"crowd": 0, "time_of_day": world.get("time_of_day", "day")}},
            "world": world, "cast": [], "lines": [], "duration": 3, "fps": 24}
    return render_still(plan, 1.0, res=0.5)
