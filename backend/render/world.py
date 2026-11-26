"""Procedural environments. Each location kind draws a layered backdrop in world
coordinates (1080x1920 stage; ground plane starts at GROUND_TOP, characters stand at FEET_Y)."""
from __future__ import annotations

import math
import random

import numpy as np

from .draw import Canvas, bgr, hue_shift_hex, rrect_pts, shade, star_pts, vertical_gradient, mix, W, H

GROUND_TOP = 1060
FEET_Y = 1390
X0, X1 = -700, 1780          # world extents drawn (so zoomed-out cameras never see the edge)


def sky_image(palette: dict, res: float) -> np.ndarray:
    h, w = int(H * res), int(W * res)
    return vertical_gradient(w, h, bgr(palette["sky_top"]), bgr(palette["sky_bottom"]))


def effective_palette(world: dict, tod_override: str, hue: float) -> dict:
    from ..engines.schemas import default_palette
    pal = dict(world["palette"])
    if tod_override and tod_override != world.get("time_of_day"):
        pal = default_palette(tod_override)
    if hue:
        pal = {k: hue_shift_hex(v, hue) for k, v in pal.items()}
    return pal


# ---------------------------------------------------------------- building blocks
def cloud(cv: Canvas, x, y, s=1.0, color=(255, 255, 255)):
    for dx, dy, r in ((0, 0, 48), (55, -18, 62), (118, 0, 50), (60, 14, 52)):
        cv.circle(x + dx * s, y + dy * s, r * s, color)


def tree(cv: Canvas, x, base, s=1.0, leaf=(80, 170, 70), trunk=(70, 100, 140)):
    cv.rect(x - 16 * s, base - 150 * s, 32 * s, 150 * s, trunk, (30, 40, 60), 3)
    for dx, dy, r in ((0, -190, 85), (-55, -150, 62), (55, -150, 62), (0, -140, 70)):
        cv.circle(x + dx * s, base + dy * s, r * s, leaf, shade(leaf, 0.7), 3)


def window(cv: Canvas, x, y, w, h, lit: bool, frame=(255, 255, 255)):
    cv.rect(x, y, w, h, (255, 235, 160) if lit else (230, 200, 150), frame, 4)
    cv.line(x + w / 2, y, x + w / 2, y + h, frame, 3)
    cv.line(x, y + h / 2, x + w, y + h / 2, frame, 3)


def house(cv: Canvas, x, base, w, h, wall, roof, lit=False, door=(60, 90, 160)):
    cv.rect(x, base - h, w, h, wall, shade(wall, 0.65), 4)
    cv.poly([(x - 18, base - h), (x + w + 18, base - h), (x + w / 2, base - h - w * 0.42)], roof, shade(roof, 0.65), 4)
    cv.rect(x + w * 0.4, base - h * 0.52, w * 0.2, h * 0.52, door, shade(door, 0.6), 3)
    window(cv, x + w * 0.1, base - h * 0.8, w * 0.22, h * 0.26, lit)
    window(cv, x + w * 0.68, base - h * 0.8, w * 0.22, h * 0.26, lit)


def lamp(cv: Canvas, x, base, on=False):
    cv.rect(x - 6, base - 230, 12, 230, (70, 70, 80))
    cv.circle(x, base - 240, 22, (150, 240, 255) if on else (200, 200, 210), (60, 60, 70), 3)


def clock_tower(cv: Canvas, x, base, t: float, hands=(11, 55), s=1.0, wall=(200, 215, 235)):
    w, h = 190 * s, 640 * s
    cv.rect(x - w / 2, base - h, w, h, wall, shade(wall, 0.6), 5)
    cv.poly([(x - w / 2 - 22 * s, base - h), (x + w / 2 + 22 * s, base - h), (x, base - h - 190 * s)], (70, 80, 190), (40, 40, 100), 5)
    cy = base - h + 150 * s
    cv.circle(x, cy, 78 * s, (255, 255, 255), (50, 50, 60), 6)
    for i in range(12):
        a = math.radians(i * 30 - 90)
        cv.line(x + math.cos(a) * 62 * s, cy + math.sin(a) * 62 * s, x + math.cos(a) * 72 * s, cy + math.sin(a) * 72 * s, (60, 60, 70), 4)
    hh, mm = hands
    ma = math.radians(mm * 6 - 90)
    ha = math.radians((hh % 12) * 30 + mm * 0.5 - 90)
    cv.line(x, cy, x + math.cos(ma) * 62 * s, cy + math.sin(ma) * 62 * s, (40, 40, 50), 6)
    cv.line(x, cy, x + math.cos(ha) * 42 * s, cy + math.sin(ha) * 42 * s, (40, 40, 50), 8)
    cv.rect(x - 26 * s, base - 150 * s, 52 * s, 150 * s, (60, 90, 160), (30, 40, 90), 4)
    window(cv, x - 22 * s, base - h + 330 * s, 44 * s, 80 * s, False)


# ---------------------------------------------------------------- locations
def _ground(cv: Canvas, pal: dict, top=GROUND_TOP, path=True):
    g = bgr(pal["ground"])
    cv.rect(X0, top, X1 - X0, 2600 - top, g)
    cv.rect(X0, top, X1 - X0, 14, shade(g, 0.8))
    if path:
        cv.poly([(X0, top + 240), (X1, top + 240), (X1, top + 430), (X0, top + 430)], (170, 170, 180))
        for i in range(-3, 10):
            cv.rect(i * 220 + 40, top + 328, 110, 12, (240, 240, 245))
        cv.rect(X0, top + 200, X1 - X0, 40, (210, 210, 215))


def draw_world(cv: Canvas, world: dict, pal: dict, t: float, ctx: dict) -> None:
    kind = world["kind"]
    rnd = random.Random(world["id"] + kind)
    night = world.get("time_of_day") == "night" or ctx.get("tod") == "night"
    bld = bgr(pal["building"])
    acc = bgr(pal["accent"])
    props = {p.lower().replace(" ", "_") for p in world.get("props", [])} | ({world.get("landmark", "").lower().replace(" ", "_")} - {""})
    # distant clouds / stars / sun
    if night:
        for i in range(60):
            sx, sy = rnd.uniform(X0, X1), rnd.uniform(-300, 700)
            cv.circle(sx, sy, rnd.uniform(1.5, 4), (255, 255, 235))
        cv.circle(830, 260, 70, (225, 245, 255))
        cv.circle(800, 245, 62, bgr(pal["sky_top"]))
    else:
        cv.circle(220, 300, 80, mix(acc, (255, 255, 255), 0.4))
        for i in range(5):
            cloud(cv, ((i * 430 + t * 18) % 2200) - 600, 200 + (i * 97) % 300, 0.9 + (i % 3) * 0.3, mix((255, 255, 255), bgr(pal["sky_bottom"]), 0.3))

    if kind in ("town_street", "town_square"):
        _ground(cv, pal)
        # back row of houses
        colors = [bld, shade(bld, 1.15), mix(bld, (200, 120, 240), 0.35), mix(bld, (90, 200, 120), 0.3)]
        x = X0 + 40
        i = 0
        while x < X1:
            w = rnd.choice([230, 270, 310])
            h = rnd.choice([260, 320, 380])
            house(cv, x, GROUND_TOP + 20, w, h, colors[i % 4], bgr("#d9534f") if i % 2 else bgr("#4f6fd9"), lit=night)
            x += w + rnd.choice([30, 60])
            i += 1
        if "clock_tower" in props or kind == "town_square":
            clock_tower(cv, 540, GROUND_TOP + 90, t, ctx.get("clock", (11, 55)), 1.0)
        if kind == "town_square" or "fountain" in props:
            cv.ellipse(540, GROUND_TOP + 420, 230, 56, (120, 190, 230), (60, 90, 130), 5)
            cv.rect(525, GROUND_TOP + 330, 30, 90, (190, 195, 210))
            for k in range(5):
                cv.circle(540 + math.sin(t * 3 + k) * 20, GROUND_TOP + 320 - k * 14, 10, (255, 240, 220))
        for lx in (60, 1020, -300, 1380):
            lamp(cv, lx, GROUND_TOP + 260, on=night)
        for tx in (150, 930, -260, 1330):
            tree(cv, tx, GROUND_TOP + 240, 1.0)
        if "bench" in props:
            cv.rect(180, GROUND_TOP + 220, 190, 22, (150, 100, 60), (80, 50, 30), 3)
    elif kind == "school":
        _ground(cv, pal, path=False)
        cv.rect(-150, GROUND_TOP - 330, 1380, 380, bld, shade(bld, 0.65), 5)
        cv.poly([(-190, GROUND_TOP - 330), (1270, GROUND_TOP - 330), (1190, GROUND_TOP - 440), (-110, GROUND_TOP - 440)], (80, 80, 200), (40, 40, 100), 5)
        for r_ in range(2):
            for c_ in range(7):
                window(cv, -100 + c_ * 190, GROUND_TOP - 300 + r_ * 130, 110, 90, night)
        cv.rect(440, GROUND_TOP - 150, 200, 200, (60, 90, 170), (30, 40, 90), 4)
        cv.rect(400, GROUND_TOP - 205, 280, 55, (255, 255, 255), (60, 60, 70), 4)
        cv.text("SCHOOL", 540, GROUND_TOP - 178, 42, (60, 60, 70), 3)
        cv.line(980, GROUND_TOP - 330, 980, GROUND_TOP - 640, (200, 200, 205), 8)
        cv.poly([(982, GROUND_TOP - 640), (1100 + math.sin(t * 4) * 8, GROUND_TOP - 600), (982, GROUND_TOP - 560)], (60, 60, 230))
        for k in range(14):
            cv.rect(-600 + k * 120, GROUND_TOP + 130, 100, 14, (255, 255, 255))
        cv.rect(X0, GROUND_TOP + 260, X1 - X0, 60, (190, 190, 195))
    elif kind == "house":     # indoor living room
        wall = bgr(pal["building"])
        cv.rect(X0, -400, X1 - X0, GROUND_TOP + 440, mix(wall, (255, 255, 255), 0.5))
        cv.rect(X0, GROUND_TOP + 120, X1 - X0, 2400, (110, 150, 205))
        cv.rect(X0, GROUND_TOP + 100, X1 - X0, 28, shade(wall, 0.7))
        for k in range(-6, 14):
            cv.line(k * 120, GROUND_TOP + 128, k * 120 - 260, 2400, (90, 125, 180), 3)
        cv.rect(60, 420, 340, 400, (255, 235, 170) if not night else (60, 70, 130), (255, 255, 255), 14)
        cv.line(230, 420, 230, 820, (255, 255, 255), 8)
        cv.line(60, 620, 400, 620, (255, 255, 255), 8)
        cv.rect(640, 380, 240, 300, (230, 200, 160), (110, 80, 50), 10)
        cv.circle(760, 530, 60, acc)
        cv.rect(560, GROUND_TOP - 70, 520, 190, (190, 90, 110), (110, 40, 60), 5)
        cv.rect(540, GROUND_TOP - 140, 120, 130, (190, 90, 110), (110, 40, 60), 5)
        cv.rect(980, GROUND_TOP - 140, 120, 130, (190, 90, 110), (110, 40, 60), 5)
        cv.ellipse(190, GROUND_TOP + 280, 230, 36, (140, 100, 200))
    elif kind == "shop":
        _ground(cv, pal)
        cv.rect(-200, GROUND_TOP - 340, 1480, 400, mix(bld, (255, 255, 255), 0.25), shade(bld, 0.6), 5)
        for k in range(14):
            cv.poly([(-240 + k * 110, GROUND_TOP - 340), (-130 + k * 110, GROUND_TOP - 340), (-150 + k * 110, GROUND_TOP - 200),
                     (-260 + k * 110, GROUND_TOP - 200)], (240, 240, 245) if k % 2 else bgr("#e63946"), (60, 60, 70), 3)
        cv.rect(-60, GROUND_TOP - 170, 520, 230, (230, 215, 160), (110, 90, 60), 6)
        cv.rect(620, GROUND_TOP - 170, 520, 230, (230, 215, 160), (110, 90, 60), 6)
        cv.rect(470, GROUND_TOP - 170, 130, 230, (60, 90, 170), (30, 40, 90), 5)
        cv.rect(300, GROUND_TOP - 470, 480, 100, (255, 255, 255), (60, 60, 70), 6)
        cv.text("SHOP", 540, GROUND_TOP - 420, 62, (60, 60, 70), 4)
        for k in range(3):
            cv.rrect(10 + k * 150, GROUND_TOP - 110, 110, 70, 14, mix(acc, (255, 255, 255), 0.2 * k), (60, 60, 60), 3)
    elif kind == "park":
        _ground(cv, pal, path=False)
        cv.ellipse(540, GROUND_TOP + 60, 900, 120, shade(bgr(pal["ground"]), 1.12))
        cv.ellipse(300, GROUND_TOP + 40, 600, 200, shade(bgr(pal["ground"]), 0.92))
        for tx, s_ in ((60, 1.2), (400, 0.9), (800, 1.3), (1100, 1.0), (-250, 1.1), (1400, 1.2)):
            tree(cv, tx, GROUND_TOP + 80, s_, shade(bgr(pal["ground"]), 1.05))
        cv.ellipse(820, GROUND_TOP + 300, 280, 60, (210, 170, 90), (150, 110, 50), 4)
        cv.ellipse(820, GROUND_TOP + 300, 250, 48, (130, 200, 240))
        cv.poly([(X0, GROUND_TOP + 380), (X1, GROUND_TOP + 360), (X1, GROUND_TOP + 430), (X0, GROUND_TOP + 440)], (205, 190, 150))
        cv.rect(120, GROUND_TOP + 240, 200, 20, (150, 100, 60), (80, 50, 30), 3)
        cv.rect(130, GROUND_TOP + 260, 12, 40, (80, 50, 30))
        cv.rect(300, GROUND_TOP + 260, 12, 40, (80, 50, 30))
    elif kind == "hospital":
        _ground(cv, pal)
        cv.rect(-120, GROUND_TOP - 460, 1320, 520, (250, 250, 252), (150, 150, 160), 5)
        cv.rect(-120, GROUND_TOP - 460, 1320, 60, (235, 235, 240))
        cv.rect(500, GROUND_TOP - 640, 80, 180, (250, 250, 252), (150, 150, 160), 4)
        cv.rect(520, GROUND_TOP - 620, 40, 140, (230, 57, 70))
        cv.rect(494, GROUND_TOP - 580, 92, 40, (230, 57, 70))
        for r_ in range(3):
            for c_ in range(7):
                window(cv, -70 + c_ * 180, GROUND_TOP - 380 + r_ * 120, 100, 80, night, (150, 190, 230))
        cv.rect(440, GROUND_TOP - 160, 200, 220, (190, 225, 245), (100, 120, 140), 5)
        cv.line(540, GROUND_TOP - 160, 540, GROUND_TOP + 60, (100, 120, 140), 4)
    elif kind == "city":
        cv.rect(X0, GROUND_TOP, X1 - X0, 2600 - GROUND_TOP, (80, 80, 92))
        for layer, (kk, dark) in enumerate(((0.6, 0.8), (0.85, 0.65), (1.0, 0.5))):
            rr = random.Random(layer * 7 + 3)
            x = X0
            while x < X1:
                w = rr.uniform(120, 220)
                h = rr.uniform(280, 760) * (0.7 + 0.3 * layer)
                col = shade(bld, dark + (0.15 * layer))
                cv.rect(x, GROUND_TOP + 40 - h * kk * 0.0 - h, w, h, col, shade(col, 0.6), 3)
                if layer == 2:
                    for wy in range(int(GROUND_TOP - h + 40), GROUND_TOP, 70):
                        for wx in range(int(x + 20), int(x + w - 40), 50):
                            lit = night and ((wx * 13 + wy * 7) % 5 != 0)
                            cv.rect(wx, wy, 26, 36, (150, 235, 255) if lit else shade(col, 1.25), None)
                x += w + rr.uniform(6, 26)
        cv.rect(X0, GROUND_TOP + 250, X1 - X0, 280, (70, 70, 80))
        for i in range(-3, 10):
            cv.rect(i * 200 + (t * 40) % 200, GROUND_TOP + 380, 100, 12, (240, 220, 120))
        cv.rect(X0, GROUND_TOP + 230, X1 - X0, 30, (150, 150, 160))
    elif kind == "forest":
        cv.rect(X0, GROUND_TOP, X1 - X0, 2600 - GROUND_TOP, bgr(pal["ground"]))
        for layer in range(3):
            rr = random.Random(layer + 11)
            col = shade(bgr(pal["ground"]), 0.7 + layer * 0.18)
            x = X0
            while x < X1:
                s_ = 0.8 + layer * 0.35
                tree(cv, x, GROUND_TOP + 60 + layer * 60, s_, col, shade(col, 0.5))
                x += rr.uniform(150, 260) * (0.8 + layer * 0.2)
        for k in range(5):
            cv.poly([(100 + k * 230, 0), (160 + k * 230, 0), (60 + k * 230 - 140, 1300), (k * 230 - 150, 1300)], mix(bgr(pal["sky_bottom"]), (255, 255, 255), 0.5))
    else:   # fantasy
        for k in range(14):
            rr = random.Random(k)
            cx_ = rr.uniform(X0, X1)
            cv.circle(cx_, rr.uniform(0, 600), rr.uniform(2, 5), (255, 255, 255))
        for ix, iy, iw in ((150, 560, 340), (820, 420, 300), (480, 780, 420)):
            bob = math.sin(t * 1.2 + ix) * 14
            cv.poly([(ix - iw / 2, iy + bob), (ix + iw / 2, iy + bob), (ix, iy + iw * 0.55 + bob)], bgr(pal["ground"]), shade(bgr(pal["ground"]), 0.6), 4)
            cv.rect(ix - 70, iy - 170 + bob, 140, 170, bld, shade(bld, 0.6), 4)
            cv.poly([(ix - 90, iy - 170 + bob), (ix + 90, iy - 170 + bob), (ix, iy - 300 + bob)], acc, shade(acc, 0.6), 4)
        cv.rect(X0, GROUND_TOP, X1 - X0, 2600 - GROUND_TOP, bgr(pal["ground"]))
        for k in range(7):
            cx_ = 80 + k * 170
            cv.poly([(cx_, GROUND_TOP + 220), (cx_ + 40, GROUND_TOP + 60 - (k % 3) * 40), (cx_ + 80, GROUND_TOP + 220)], mix(acc, (255, 120, 255), 0.5), (255, 255, 255), 3)

    # crowd / extras are drawn by the scene renderer (they use the character rig)
