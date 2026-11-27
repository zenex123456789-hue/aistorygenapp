"""Blocky, Roblox-inspired 2.5D character rig (its roundness, outline and proportions follow the art style, see looks.py).

A character is fully described by its spec dict (see engines/schemas.py), so the
same person is drawn identically in every scene and in the reference sheet:
there is no way for clothing or colours to drift between scenes.
"""
from __future__ import annotations

import math

from . import looks
from .draw import Canvas, bgr, rot_pts, rrect_pts, shade, star_pts

OUTLINE = (30, 24, 20)

FORM_STYLE = {   # skin colour, ear kind, face kind
    "cat": ("#f4a259", "tri", "cat"), "dog": ("#b08968", "floppy", "dog"), "frog": ("#6bbf59", "frog", "frog"),
    "pig": ("#f7a8b8", "tri_small", "pig"), "bunny": ("#f2efe9", "long", "bunny"), "chicken": ("#fafafa", "comb", "chicken"),
    "bear": ("#8d5b3b", "round", "bear"), "duck": ("#ffd23f", "none", "duck"),
}


# ---------------------------------------------------------------- poses
class Pose:
    __slots__ = ("dx", "dy", "rot", "sx", "sy", "la", "ra", "ll", "rl", "tilt", "bounce", "visible")

    def __init__(self):
        self.dx = self.dy = self.rot = self.tilt = self.bounce = 0.0
        self.sx = self.sy = 1.0
        self.la = self.ra = 6.0
        self.ll = self.rl = 0.0
        self.visible = True


def make_pose(anim: str, t: float, emotion: str, talking: float, seed: float) -> Pose:
    """t = seconds since the animation started."""
    p = Pose()
    s2 = math.sin(2 * math.pi * 0.9 * (t + seed))
    p.dy = s2 * 3.0                                   # idle breathing
    p.la = 6 + s2 * 2
    p.ra = 6 - s2 * 2
    if talking > 0.05:
        p.dy -= talking * 4
        p.tilt += math.sin(t * 9 + seed) * 2.0 * talking
        p.ra = 14 + talking * 18 * (math.sin(t * 6 + seed) * 0.5 + 0.5)   # gesturing hand

    if emotion in ("scared", "worried"):
        p.dx += math.sin(t * 40) * (5 if emotion == "scared" else 2)
        p.la, p.ra = 26, 26
        p.sy = 0.97
    elif emotion == "angry":
        p.dx += math.sin(t * 55) * 2.2
        p.la, p.ra = 18, 18
    elif emotion == "sad":
        p.tilt += 7
        p.dy += 8
        p.la, p.ra = 2, 2
    elif emotion in ("happy", "excited"):
        p.dy -= abs(math.sin(t * (7 if emotion == "excited" else 3.5) + seed)) * (12 if emotion == "excited" else 5)
    elif emotion == "confused":
        p.tilt += math.sin(t * 2) * 9
    elif emotion == "surprised":
        p.dy -= 10 * max(0.0, 1 - t * 2.5)
        p.la, p.ra = 30, 30
    elif emotion == "smug":
        p.tilt -= 4

    a = anim
    if a in ("walk", "run"):
        f = 1.9 if a == "walk" else 3.2
        amp = 24 if a == "walk" else 42
        ph = math.sin(2 * math.pi * f * t)
        p.ll, p.rl = amp * ph, -amp * ph
        p.la, p.ra = -amp * 0.8 * ph + 6, amp * 0.8 * ph + 6
        p.dy = -abs(ph) * (9 if a == "walk" else 18)
        p.rot = 0 if a == "walk" else 7
    elif a == "jump":
        ph = abs(math.sin(math.pi * 1.25 * t))
        p.dy = -ph * 150
        p.la = p.ra = 40 + 120 * ph
        p.sy = 1 + 0.08 * ph
        p.sx = 1 - 0.05 * ph
        p.ll, p.rl = 12 * ph, -12 * ph
    elif a == "wave":
        p.ra = 150 + 24 * math.sin(2 * math.pi * 3 * t)
    elif a == "point":
        p.ra = 95 + 4 * math.sin(t * 4)
        p.tilt += 4
    elif a == "dance":
        ph = math.sin(2 * math.pi * 2.2 * t)
        p.dy = -abs(ph) * 22
        p.rot = ph * 6
        p.la = 90 + 55 * ph
        p.ra = 90 - 55 * ph
        p.ll, p.rl = 14 * ph, -14 * ph
    elif a == "shake":
        p.dx += math.sin(t * 45) * 7
        p.la = p.ra = 28
    elif a == "faint":
        k = min(1.0, t / 0.55)
        p.rot = 90 * (k * k)
        p.la = p.ra = 20 + 30 * k
        p.dx += 40 * k
    elif a == "spin":
        c = math.cos(2 * math.pi * 1.6 * t)
        p.sx = max(0.12, abs(c))
        p.la = p.ra = 70
        p.dy = -abs(math.sin(math.pi * 1.6 * t)) * 20
    elif a == "shrink":
        k = min(1.0, t / 0.6)
        p.sx = p.sy = 1 - 0.65 * k
    elif a == "grow":
        k = min(1.0, t / 0.6)
        p.sx = p.sy = 1 + 0.55 * k
    elif a == "transform":
        p.sy = 1 + 0.28 * math.sin(2 * math.pi * 3 * t) * max(0.0, 1 - t / 0.9)
        p.sx = 1 - 0.18 * math.sin(2 * math.pi * 3 * t) * max(0.0, 1 - t / 0.9)
        p.la = p.ra = 40
        p.dy -= 18 * max(0.0, 1 - t / 0.5)
    elif a == "facepalm":
        p.ra = 168
        p.tilt += 8
        p.dy += 5
    elif a == "celebrate":
        ph = abs(math.sin(2 * math.pi * 1.8 * t))
        p.la = p.ra = 150 + 15 * ph
        p.dy = -ph * 60
    elif a == "sneak":
        p.sy = 0.9
        p.dy += 14
        p.rot = 5
        ph = math.sin(2 * math.pi * 1.1 * t)
        p.ll, p.rl = 14 * ph, -14 * ph
        p.la, p.ra = 25, 25
    elif a == "vanish":
        k = min(1.0, t / 0.5)
        p.sx = p.sy = max(0.001, 1 - k)
        p.rot = 360 * k
        p.visible = k < 0.98
    elif a == "appear":
        k = min(1.0, t / 0.5)
        p.sx = p.sy = max(0.001, k * (1 + 0.15 * math.sin(math.pi * k)))
        p.rot = -360 * (1 - k)
    elif a == "laugh":
        p.dy = -abs(math.sin(t * 14)) * 7
        p.tilt -= 10
        p.la = p.ra = -4
    return p


# ---------------------------------------------------------------- drawing
def _limb(cv: Canvas, px, py, w, length, ang, side, color, outline, ow=3.5):
    """Rounded block hanging from (px,py); ang 0 = down, 90 = straight out sideways."""
    pts = rrect_pts(px - w / 2, py, w, length, w * 0.22, 3)
    pts = rot_pts(pts, (px, py), -ang * side)
    cv.poly(pts, color, outline, ow)


def _emotion_face(emotion: str):
    # (brow_angle_inner, brow_height, mouth kind)
    return {
        "neutral": (0, 0, "flat"), "happy": (-6, -2, "smile"), "excited": (-10, -8, "open_smile"),
        "sad": (14, 2, "frown"), "angry": (-24, 2, "frown_hard"), "scared": (18, -8, "open_o"),
        "surprised": (-4, -14, "open_o"), "confused": (8, -3, "wave"), "smug": (-12, 0, "smirk"),
        "worried": (16, -2, "frown"),
    }.get(emotion, (0, 0, "flat"))


def draw_character(cv: Canvas, ch: dict, x: float, feet_y: float, scale: float, pose: Pose, *,
                   emotion: str = "neutral", talk: float = 0.0, t: float = 0.0, facing: int = 1,
                   form: str = "", blink_seed: float = 0.0) -> None:
    if not pose.visible:
        return
    look = getattr(cv, "look", None) or looks.get(looks.DEFAULT)
    if look.stick:
        _draw_stick(cv, ch, x, feet_y, scale, pose, look, emotion=emotion, talk=talk, t=t, facing=facing, form=form, blink_seed=blink_seed)
        return

    def rlook(x, y, w, h, r, n=5):                       # corner radius follows the art style (blocky 1.0, round cartoon 2.6, ...)
        return rrect_pts(x, y, w, h, r * look.radius, n)

    u = 100.0 * ch.get("height", 1.0) * scale
    build = {"slim": 0.88, "normal": 1.0, "chunky": 1.18}.get(ch.get("build", "normal"), 1.0)
    form_skin, ears, facekind = (None, None, None)
    if form in FORM_STYLE:
        fs, ears, facekind = FORM_STYLE[form]
        form_skin = bgr(fs)
    skin = form_skin or bgr(ch["skin"])
    shirt, pants, shoes = bgr(ch["shirt_color"]), bgr(ch["pants_color"]), bgr(ch["shoes_color"])
    hair = bgr(ch["hair_color"])
    acc_color = bgr(ch.get("accessory_color", "#ffd166"))
    ow = 3.6 * scale * look.outline

    # transform: scale/rotate everything about the feet
    def T(px, py):
        px, py = px * pose.sx * (1 if facing >= 0 else -1), py * pose.sy
        if pose.rot:
            r = math.radians(pose.rot)
            px, py = px * math.cos(r) - py * math.sin(r), px * math.sin(r) + py * math.cos(r)
        return x + pose.dx + px, feet_y + pose.dy + py

    def tp(pts):
        return [T(*p) for p in pts]

    class SubCV:    # canvas proxy that applies the character transform to every shape
        def poly(self, pts, c, o=None, w=0):
            cv.poly(tp(pts), c, o, w)

        def circle(self, cx, cy, r, c, o=None, w=0):
            cv.ellipse(*T(cx, cy), r * pose.sx, r * pose.sy, c, o, w, angle=pose.rot)

        def ellipse(self, cx, cy, rx, ry, c, o=None, w=0, angle=0.0, a0=0, a1=360):
            cv.ellipse(*T(cx, cy), rx * pose.sx, ry * pose.sy, c, o, w, angle=pose.rot + angle, a0=a0, a1=a1)

        def line(self, x0, y0, x1, y1, c, w=3):
            a, b = T(x0, y0), T(x1, y1)
            cv.line(a[0], a[1], b[0], b[1], c, w)

        def polyline(self, pts, c, w=3, closed=False):
            cv.polyline(tp(pts), c, w, closed)

    s = SubCV()

    # ---- ground shadow (not transformed)
    cv.ellipse(x + pose.dx, feet_y + 6, u * 1.25 * pose.sx, u * 0.22, (60, 90, 70), None)

    hip_y = -1.9 * u
    torso_w, torso_h = 2.0 * u * build, 2.0 * u
    top_y = hip_y - torso_h
    head_w, head_h = 1.55 * u * look.head, 1.38 * u * look.head
    head_top = top_y - head_h + 0.12 * u

    # ---- behind-body accessories
    acc = ch.get("accessory", "none")
    if acc == "cape":
        s.poly([(-torso_w * 0.55, top_y), (torso_w * 0.55, top_y), (torso_w * 0.95, hip_y + 0.9 * u), (-torso_w * 0.95, hip_y + 0.9 * u)],
               acc_color, OUTLINE, ow)
    if acc == "backpack":
        s.poly(rlook(-torso_w * 0.62, top_y + 0.2 * u, torso_w * 1.24, 1.5 * u, 0.25 * u), acc_color, OUTLINE, ow)
    if form == "cat" or form == "dog":
        s.polyline([(torso_w * 0.4, hip_y), (torso_w * 0.95, hip_y + 0.2 * u), (torso_w * 1.1, hip_y - 0.9 * u)],
                   skin, 0.45 * u)
    if ch.get("hair_style") == "long" and not form:
        s.poly(rlook(-head_w * 0.62, head_top + 0.2 * u, head_w * 1.24, head_h + 1.1 * u, 0.3 * u), hair, OUTLINE, ow)

    # ---- legs
    leg_w, leg_h = 0.95 * u * build, 1.95 * u
    for side, ang in ((-1, pose.ll), (1, pose.rl)):
        px = side * 0.52 * u * build
        pts = rlook(px - leg_w / 2, hip_y, leg_w, leg_h, 0.2 * u, 3)
        pts = rot_pts(pts, (px, hip_y), ang * side)
        s.poly(pts, pants, OUTLINE, ow)
        foot = rlook(px - leg_w / 2 - 0.05 * u, hip_y + leg_h - 0.42 * u, leg_w + 0.1 * u, 0.42 * u, 0.15 * u, 3)
        foot = rot_pts(foot, (px, hip_y), ang * side)
        s.poly(foot, shoes, OUTLINE, ow)

    # ---- torso
    s.poly(rlook(-torso_w / 2, top_y, torso_w, torso_h, 0.22 * u), shirt, OUTLINE, ow)
    dark = shade(shirt, 0.82)
    s.poly(rlook(-torso_w / 2 + 0.06 * u, hip_y - 0.38 * u, torso_w - 0.12 * u, 0.32 * u, 0.1 * u, 3), dark)
    pat = ch.get("shirt_pattern", "none")
    pc = shade(shirt, 1.45) if sum(shirt) < 480 else shade(shirt, 0.65)
    if pat == "stripes":
        for k in range(3):
            yy = top_y + 0.35 * u + k * 0.55 * u
            s.poly([(-torso_w / 2 + 0.05 * u, yy), (torso_w / 2 - 0.05 * u, yy), (torso_w / 2 - 0.05 * u, yy + 0.25 * u), (-torso_w / 2 + 0.05 * u, yy + 0.25 * u)], pc)
    elif pat == "star":
        s.poly(star_pts(0, top_y + torso_h * 0.45, 0.6 * u), pc)
    elif pat == "zigzag":
        s.polyline([(-torso_w * 0.42 + i * torso_w * 0.84 / 6, top_y + torso_h * (0.45 + (0.16 if i % 2 else -0.16))) for i in range(7)], pc, 0.17 * u)
    elif pat == "pocket":
        s.poly(rlook(-0.7 * u, top_y + 0.7 * u, 0.7 * u, 0.65 * u, 0.08 * u, 3), pc, OUTLINE, ow * 0.5)
    elif pat == "heart":
        cx0, cy0, r0 = 0, top_y + torso_h * 0.45, 0.28 * u
        s.circle(cx0 - r0, cy0 - r0 * 0.4, r0, pc)
        s.circle(cx0 + r0, cy0 - r0 * 0.4, r0, pc)
        s.poly([(cx0 - 2 * r0 + 0.02 * u, cy0 - r0 * 0.1), (cx0 + 2 * r0 - 0.02 * u, cy0 - r0 * 0.1), (cx0, cy0 + 1.35 * r0)], pc)
    if acc == "tie":
        s.poly([(-0.18 * u, top_y), (0.18 * u, top_y), (0.12 * u, top_y + 1.25 * u), (0, top_y + 1.45 * u), (-0.12 * u, top_y + 1.25 * u)], acc_color, OUTLINE, ow * 0.6)
    if acc == "scarf":
        s.poly(rlook(-torso_w * 0.5, top_y - 0.05 * u, torso_w, 0.4 * u, 0.15 * u, 3), acc_color, OUTLINE, ow)
        s.poly(rlook(0.3 * u, top_y + 0.2 * u, 0.4 * u, 1.1 * u, 0.1 * u, 3), acc_color, OUTLINE, ow)
    if acc == "bowtie":
        s.poly([(0, top_y + 0.12 * u), (-0.55 * u, top_y - 0.1 * u), (-0.55 * u, top_y + 0.34 * u)], acc_color, OUTLINE, ow * 0.6)
        s.poly([(0, top_y + 0.12 * u), (0.55 * u, top_y - 0.1 * u), (0.55 * u, top_y + 0.34 * u)], acc_color, OUTLINE, ow * 0.6)

    # ---- arms (skin-coloured forearms like the classic blocky look: sleeve + hand)
    arm_w, arm_h = 0.92 * u, 1.9 * u
    for side, ang in ((-1, pose.la), (1, pose.ra)):
        px = side * (torso_w / 2 + arm_w * 0.45)
        py = top_y + 0.25 * u
        pts = rlook(px - arm_w / 2, py, arm_w, arm_h, 0.2 * u, 3)
        hand = rlook(px - arm_w / 2, py + arm_h - 0.6 * u, arm_w, 0.6 * u, 0.18 * u, 3)
        s.poly(rot_pts(pts, (px, py), -ang * side), shirt, OUTLINE, ow)
        s.poly(rot_pts(hand, (px, py), -ang * side), skin, OUTLINE, ow)

    # ---- head
    hx = 0.0
    tilt = pose.tilt
    def H(pts):
        return rot_pts(pts, (0, top_y + 0.1 * u), tilt) if tilt else pts

    head_pts = rlook(hx - head_w / 2, head_top, head_w, head_h, 0.3 * u)
    # ears behind head for animals
    if ears == "tri":
        for sd in (-1, 1):
            s.poly(H([(sd * 0.75 * u, head_top + 0.3 * u), (sd * 0.35 * u, head_top - 0.55 * u), (sd * 0.1 * u, head_top + 0.15 * u)]), skin, OUTLINE, ow)
            s.poly(H([(sd * 0.6 * u, head_top + 0.2 * u), (sd * 0.35 * u, head_top - 0.3 * u), (sd * 0.22 * u, head_top + 0.15 * u)]), (180, 150, 230))
    elif ears == "tri_small":
        for sd in (-1, 1):
            s.poly(H([(sd * 0.78 * u, head_top + 0.2 * u), (sd * 0.55 * u, head_top - 0.35 * u), (sd * 0.2 * u, head_top + 0.12 * u)]), skin, OUTLINE, ow)
    elif ears == "floppy":
        for sd in (-1, 1):
            s.poly(H(rlook(sd * 0.95 * u - 0.28 * u, head_top + 0.05 * u, 0.56 * u, 1.1 * u, 0.25 * u, 3)), shade(skin, 0.7), OUTLINE, ow)
    elif ears == "long":
        for sd in (-1, 1):
            s.poly(H(rlook(sd * 0.38 * u - 0.22 * u, head_top - 1.3 * u, 0.44 * u, 1.5 * u, 0.22 * u, 3)), skin, OUTLINE, ow)
            s.poly(H(rlook(sd * 0.38 * u - 0.1 * u, head_top - 1.15 * u, 0.2 * u, 1.2 * u, 0.1 * u, 3)), (190, 170, 240))
    elif ears == "round":
        for sd in (-1, 1):
            s.circle(*_rp((sd * 0.62 * u, head_top + 0.05 * u), (0, top_y + 0.1 * u), tilt), 0.3 * u, skin, OUTLINE, ow)
    elif ears == "frog":
        for sd in (-1, 1):
            cx_, cy_ = _rp((sd * 0.45 * u, head_top - 0.12 * u), (0, top_y + 0.1 * u), tilt)
            s.circle(cx_, cy_, 0.36 * u, skin, OUTLINE, ow)
            s.circle(cx_, cy_, 0.2 * u, (255, 255, 255))
            s.circle(cx_, cy_, 0.1 * u, (20, 20, 20))
    elif ears == "comb":
        for i, sd in enumerate((-0.3, 0, 0.3)):
            cx_, cy_ = _rp((sd * u, head_top - 0.05 * u - (0.12 * u if i == 1 else 0)), (0, top_y + 0.1 * u), tilt)
            s.circle(cx_, cy_, 0.2 * u, (60, 60, 230), OUTLINE, ow * 0.7)

    s.poly(H(head_pts), skin, OUTLINE, ow)

    # ---- hair (human only)
    hs = ch.get("hair_style", "short")
    if not form and hs != "bald":
        top = head_top
        if hs in ("short", "bob", "long", "bun", "pigtails"):
            s.poly(H(rlook(hx - head_w / 2 - 0.03 * u, top - 0.04 * u, head_w + 0.06 * u, head_h * 0.38, 0.28 * u)), hair, OUTLINE, ow)
        if hs == "bob":
            for sd in (-1, 1):
                s.poly(H(rlook(sd * head_w / 2 - (0.2 * u if sd < 0 else 0), top + 0.2 * u, 0.2 * u, head_h * 0.7, 0.08 * u, 3)), hair, OUTLINE, ow * 0.7)
        if hs == "spiky":
            for i in range(5):
                bx = -head_w * 0.42 + i * head_w * 0.21
                s.poly(H([(bx - 0.17 * u, top + 0.3 * u), (bx + 0.02 * u, top - 0.55 * u + (0.2 * u if i in (0, 4) else 0)), (bx + 0.2 * u, top + 0.3 * u)]), hair, OUTLINE, ow * 0.8)
            s.poly(H(rlook(hx - head_w / 2, top + 0.05 * u, head_w, head_h * 0.25, 0.1 * u, 3)), hair)
        if hs == "mohawk":
            s.poly(H([(-0.28 * u, top + 0.35 * u), (-0.18 * u, top - 0.75 * u), (0.18 * u, top - 0.75 * u), (0.28 * u, top + 0.35 * u)]), hair, OUTLINE, ow)
        if hs == "curly":
            for i in range(6):
                s.circle(*_rp((-head_w * 0.45 + i * head_w * 0.18, top + 0.04 * u - (0.12 * u if i % 2 else 0)), (0, top_y + 0.1 * u), tilt), 0.26 * u, hair, OUTLINE, ow * 0.6)
        if hs == "bun":
            s.circle(*_rp((0, top - 0.2 * u), (0, top_y + 0.1 * u), tilt), 0.36 * u, hair, OUTLINE, ow)
        if hs == "pigtails":
            for sd in (-1, 1):
                s.circle(*_rp((sd * (head_w / 2 + 0.22 * u), top + 0.55 * u), (0, top_y + 0.1 * u), tilt), 0.3 * u, hair, OUTLINE, ow)

    # ---- face
    eye_y = head_top + head_h * 0.46
    ex = head_w * 0.22
    brow_in, brow_h, mouth = _emotion_face(emotion)
    blink = ((t + blink_seed) % 3.4) > 3.28
    eyes = ch.get("eyes", "dot")

    def FP(px, py):
        return _rp((px, py), (0, top_y + 0.1 * u), tilt)

    for sd in (-1, 1):
        cx_, cy_ = FP(sd * ex, eye_y)
        if blink or emotion == "happy" and talk < 0.1 and eyes == "sleepy":
            s.line(cx_ - 0.13 * u, cy_, cx_ + 0.13 * u, cy_, OUTLINE, 4 * scale)
        elif eyes == "round" or emotion in ("surprised", "scared"):
            rr = 0.2 * u if emotion not in ("surprised", "scared") else 0.26 * u
            s.circle(cx_, cy_, rr, (255, 255, 255), OUTLINE, ow * 0.7)
            s.circle(cx_ + sd * -0.02 * u, cy_, rr * (0.4 if emotion == "scared" else 0.5), (25, 20, 20))
        elif eyes == "sleepy":
            s.ellipse(cx_, cy_, 0.13 * u, 0.06 * u, (25, 20, 20))
        else:
            s.ellipse(cx_, cy_, 0.095 * u * look.eyes, 0.135 * u * look.eyes, (25, 20, 20))
            if eyes == "sparkle" or look.sparkle_eyes:
                s.circle(cx_ - 0.03 * u * look.eyes, cy_ - 0.05 * u * look.eyes, 0.04 * u * look.eyes, (255, 255, 255))
        # brows: positive brow_in raises the inner end (sad/worried), negative lowers it (angry)
        bl = 0.22 * u
        by0 = cy_ - 0.27 * u + brow_h * 0.012 * u
        if emotion == "confused" and sd > 0:
            by0 -= 0.1 * u
        k = math.sin(math.radians(brow_in)) * bl
        inner_x, outer_x = cx_ - sd * bl * 0.9, cx_ + sd * bl * 0.9
        s.line(inner_x, by0 - k, outer_x, by0 + k, shade(hair, 0.6) if not form else OUTLINE, 4.5 * scale)
    if emotion in ("happy", "excited", "smug") and not form:
        for sd in (-1, 1):
            cxb, cyb = FP(sd * head_w * 0.34, eye_y + 0.26 * u)
            s.ellipse(cxb, cyb, 0.14 * u, 0.08 * u, (150, 150, 245))

    # animal snouts / beaks
    my = head_top + head_h * 0.76
    if facekind in ("cat", "dog", "bear"):
        nx, ny = FP(0, eye_y + 0.2 * u)
        s.poly([(nx - 0.1 * u, ny), (nx + 0.1 * u, ny), (nx, ny + 0.1 * u)], (60, 60, 120))
        if facekind == "cat":
            for sd in (-1, 1):
                for k in (-0.06, 0.06):
                    a, b = FP(sd * 0.25 * u, ny + k * u), FP(sd * 0.75 * u, ny + k * u * 3)
                    s.line(a[0], a[1], b[0], b[1], (240, 240, 240), 2.5 * scale)
    elif facekind == "pig":
        sx_, sy_ = FP(0, eye_y + 0.32 * u)
        s.ellipse(sx_, sy_, 0.34 * u, 0.24 * u, bgr("#f48fb1"), OUTLINE, ow * 0.6)
        for sd in (-1, 1):
            s.ellipse(sx_ + sd * 0.1 * u, sy_, 0.05 * u, 0.08 * u, (60, 30, 90))
        my = head_top + head_h * 0.88
    elif facekind == "bunny":
        nx, ny = FP(0, eye_y + 0.22 * u)
        s.circle(nx, ny, 0.08 * u, (150, 130, 240))
    elif facekind in ("chicken", "duck"):
        bx_, by_ = FP(0, eye_y + 0.3 * u)
        col = bgr("#ff9f1c")
        s.poly([(bx_ - 0.3 * u, by_ - 0.1 * u), (bx_ + 0.3 * u, by_ - 0.1 * u), (bx_ + 0.2 * u, by_ + 0.22 * u), (bx_ - 0.2 * u, by_ + 0.22 * u)] if facekind == "duck"
               else [(bx_ - 0.18 * u, by_ - 0.1 * u), (bx_ + 0.18 * u, by_ - 0.1 * u), (bx_, by_ + 0.25 * u)], col, OUTLINE, ow * 0.7)
        my = head_top + head_h * 0.95

    # mouth
    mx, my2 = FP(0, my)
    wdt = 0.3 * u
    mouth_open = max(talk, 0.0)
    if mouth_open > 0.12 or mouth in ("open_smile", "open_o") and facekind not in ("chicken", "duck"):
        mo = max(mouth_open, 0.55 if mouth == "open_o" else 0.45 if mouth == "open_smile" else 0.0)
        mh = (0.05 + 0.3 * mo) * u
        mw = wdt * (0.55 if mouth == "open_o" else 1.0)
        s.ellipse(mx, my2 + mh * 0.3, mw, mh, (25, 20, 60), OUTLINE, ow * 0.5)
        if mh > 0.14 * u:
            s.ellipse(mx, my2 + mh * 0.75, mw * 0.6, mh * 0.35, (110, 110, 235))
    elif facekind not in ("chicken", "duck"):
        if mouth in ("smile", "open_smile", "smirk"):
            s.ellipse(mx + (0.08 * u if mouth == "smirk" else 0), my2 - 0.1 * u, wdt, 0.2 * u, None, OUTLINE, 4.5 * scale, a0=15, a1=165)
        elif mouth in ("frown", "frown_hard"):
            s.ellipse(mx, my2 + 0.12 * u, wdt * 0.8, 0.16 * u, None, OUTLINE, 4.5 * scale, a0=195, a1=345)
        elif mouth == "wave":
            s.polyline([FP(-0.26 * u + i * 0.13 * u, my + (0.04 if i % 2 else -0.04) * u) for i in range(5)], OUTLINE, 4 * scale)
        else:
            s.line(mx - 0.2 * u, my2, mx + 0.2 * u, my2, OUTLINE, 4.5 * scale)

    # ---- hats / glasses
    if acc in ("glasses", "sunglasses"):
        for sd in (-1, 1):
            cx_, cy_ = FP(sd * ex, eye_y)
            if acc == "glasses":
                s.ellipse(cx_, cy_, 0.24 * u, 0.22 * u, None, OUTLINE, 4.5 * scale)
            else:
                s.ellipse(cx_, cy_, 0.27 * u, 0.2 * u, (30, 25, 25), OUTLINE, 3 * scale)
        a, b = FP(-ex + 0.24 * u, eye_y), FP(ex - 0.24 * u, eye_y)
        s.line(a[0], a[1], b[0], b[1], OUTLINE, 4 * scale)
    elif acc == "cap":
        s.poly(H(rlook(-head_w / 2 - 0.04 * u, head_top - 0.28 * u, head_w + 0.08 * u, 0.62 * u, 0.3 * u)), acc_color, OUTLINE, ow)
        s.poly(H(rlook(-0.1 * u, head_top + 0.18 * u, head_w / 2 + 0.6 * u, 0.2 * u, 0.1 * u, 3)), shade(acc_color, 0.8), OUTLINE, ow)
    elif acc == "beanie":
        s.poly(H(rlook(-head_w / 2 - 0.05 * u, head_top - 0.35 * u, head_w + 0.1 * u, 0.8 * u, 0.35 * u)), acc_color, OUTLINE, ow)
        s.circle(*_rp((0, head_top - 0.42 * u), (0, top_y + 0.1 * u), tilt), 0.2 * u, shade(acc_color, 1.35), OUTLINE, ow * 0.7)
    elif acc == "crown":
        s.poly(H([(-0.65 * u, head_top + 0.12 * u), (-0.65 * u, head_top - 0.5 * u), (-0.33 * u, head_top - 0.2 * u), (0, head_top - 0.62 * u),
                  (0.33 * u, head_top - 0.2 * u), (0.65 * u, head_top - 0.5 * u), (0.65 * u, head_top + 0.12 * u)]), bgr("#ffd23f"), OUTLINE, ow)
    elif acc == "headband":
        s.poly(H(rlook(-head_w / 2, head_top + 0.18 * u, head_w, 0.22 * u, 0.08 * u, 3)), acc_color, OUTLINE, ow * 0.7)
    elif acc == "top_hat":
        s.poly(H(rlook(-head_w * 0.62, head_top - 0.02 * u, head_w * 1.24, 0.2 * u, 0.08 * u, 3)), (40, 35, 35), OUTLINE, ow)
        s.poly(H(rlook(-head_w * 0.38, head_top - 0.95 * u, head_w * 0.76, 1.0 * u, 0.1 * u, 3)), (40, 35, 35), OUTLINE, ow)
        s.poly(H(rlook(-head_w * 0.38, head_top - 0.2 * u, head_w * 0.76, 0.16 * u, 0.04 * u, 3)), acc_color)
    elif acc == "bandana":
        s.poly(H(rlook(-head_w / 2, head_top + 0.05 * u, head_w, 0.32 * u, 0.1 * u, 3)), acc_color, OUTLINE, ow * 0.7)
        s.poly(H([(head_w / 2, head_top + 0.1 * u), (head_w / 2 + 0.4 * u, head_top - 0.1 * u), (head_w / 2 + 0.35 * u, head_top + 0.35 * u)]), acc_color, OUTLINE, ow * 0.7)
    elif acc in ("cat_ears", "bunny_ears") and not ears:
        for sd in (-1, 1):
            if acc == "cat_ears":
                s.poly(H([(sd * 0.7 * u, head_top + 0.1 * u), (sd * 0.4 * u, head_top - 0.5 * u), (sd * 0.1 * u, head_top + 0.1 * u)]), acc_color, OUTLINE, ow)
            else:
                s.poly(H(rlook(sd * 0.4 * u - 0.2 * u, head_top - 1.15 * u, 0.4 * u, 1.3 * u, 0.2 * u, 3)), acc_color, OUTLINE, ow)


def _draw_stick(cv: Canvas, ch: dict, x: float, feet_y: float, scale: float, pose: Pose, look, *, emotion: str, talk: float,
                t: float, facing: int, form: str, blink_seed: float) -> None:
    """The same character as a stick figure: it uses the same pose (arm and leg angles, tilt, squash, rotation), the same face
    emotions and the same hair, accessories and animal forms, drawn with lines and circles."""
    u = 100.0 * ch.get("height", 1.0) * scale
    sg = 1 if facing >= 0 else -1
    ink = OUTLINE
    shirt, pants, shoes = bgr(ch["shirt_color"]), bgr(ch["pants_color"]), bgr(ch["shoes_color"])
    hair, acc_color = bgr(ch["hair_color"]), bgr(ch.get("accessory_color", "#ffd166"))
    ears = facekind = None
    skin = bgr(ch["skin"])
    if form in FORM_STYLE:
        fs, ears, facekind = FORM_STYLE[form]
        skin = bgr(fs)
    lw = 0.24 * u * look.outline                       # line thickness
    ow = 0.075 * u * look.outline

    def T(px, py):
        px, py = px * pose.sx * sg, py * pose.sy
        if pose.rot:
            r = math.radians(pose.rot)
            px, py = px * math.cos(r) - py * math.sin(r), px * math.sin(r) + py * math.cos(r)
        return x + pose.dx + px, feet_y + pose.dy + py

    def line(a, b, col, w=lw, cap=True, core=None):
        """A dark pen line; with `core` a thinner coloured line is drawn down the middle (the character's own colours)."""
        A, B = T(*a), T(*b)
        for colour, width in ((col, w), (core, w * 0.5)) if core is not None else ((col, w),):
            cv.line(A[0], A[1], B[0], B[1], colour, width)
            if cap:
                for P in (A, B):
                    cv.ellipse(P[0], P[1], width / 2 * pose.sx, width / 2 * pose.sy, colour)

    def circle(c, r, fill, outline=None, w=0):
        P = T(*c)
        cv.ellipse(P[0], P[1], r * pose.sx, r * pose.sy, fill, outline, w, angle=pose.rot)

    def poly(pts, fill, outline=None, w=0):
        cv.poly([T(*p) for p in pts], fill, outline, w)

    cv.ellipse(x + pose.dx, feet_y + 6, u * 1.0 * pose.sx, u * 0.18, (60, 90, 70), None)          # ground shadow

    hip, shoulder, neck = (0.0, -1.9 * u), (0.0, -3.3 * u), (0.0, -3.62 * u)
    r = 0.84 * u * look.head
    tilt = pose.tilt
    hc = (0.0, neck[1] - r * 0.92)

    def FP(dx, dy):                                    # a point on the head, following the head tilt
        return rot_pts([(hc[0] + dx, hc[1] + dy)], neck, tilt)[0] if tilt else (hc[0] + dx, hc[1] + dy)

    acc = ch.get("accessory", "none")
    if acc == "cape":
        poly([(-0.2 * u, shoulder[1]), (0.2 * u, shoulder[1]), (-0.95 * u, hip[1] + 0.5 * u)], acc_color, ink, ow * 0.7)
    if acc == "backpack":
        poly([(-0.62 * u, shoulder[1] + 0.1 * u), (-0.18 * u, shoulder[1] + 0.1 * u), (-0.18 * u, hip[1] - 0.2 * u), (-0.62 * u, hip[1] - 0.2 * u)], acc_color, ink, ow * 0.7)
    if form in ("cat", "dog"):
        line((0.0, hip[1] - 0.1 * u), (0.8 * u, hip[1] - 0.2 * u), skin, lw * 0.8)
        line((0.8 * u, hip[1] - 0.2 * u), (1.0 * u, hip[1] - 1.0 * u), skin, lw * 0.8)

    # legs: same swing angle as the blocky rig, then a little shoe
    LL = 1.9 * u
    for side, ang in ((-1, pose.ll), (1, pose.rl)):
        a = math.radians(ang)
        hx = side * 0.12 * u
        foot = (hx - side * LL * math.sin(a) + side * 0.3 * u, hip[1] + LL * math.cos(a))      # legs stand a little apart
        line((hx, hip[1]), foot, ink, core=pants)
        line(foot, (foot[0] + 0.34 * u, foot[1]), ink, lw * 0.8, core=shoes)
    line(hip, neck, ink, core=shirt)                   # body
    # arms
    LA = 1.7 * u
    for side, ang in ((-1, pose.la), (1, pose.ra)):
        a = math.radians(min(178.0, ang + 24.0))                 # arms hang a little out from the body
        hand = (side * LA * math.sin(a), shoulder[1] + LA * math.cos(a))
        line((0.0, shoulder[1]), hand, ink, core=shirt)
        circle(hand, 0.15 * u, skin, ink, ow * 0.5)

    # animal ears sit behind the head
    def tri(pts, col, o=True):
        cv.poly([T(*p) for p in [FP(px, py) for px, py in pts]], col, ink if o else None, ow * 0.7 if o else 0)

    def blob(c, rx, ry, col):
        P = T(*FP(*c))
        cv.ellipse(P[0], P[1], rx * pose.sx, ry * pose.sy, col, ink, ow * 0.7, angle=pose.rot + tilt)
    top = -r
    if ears == "tri":
        for sd in (-1, 1):
            tri([(sd * 0.62 * u, top + 0.3 * u), (sd * 0.4 * u, top - 0.5 * u), (sd * 0.1 * u, top + 0.1 * u)], skin)
    elif ears == "tri_small":
        for sd in (-1, 1):
            tri([(sd * 0.64 * u, top + 0.25 * u), (sd * 0.5 * u, top - 0.3 * u), (sd * 0.2 * u, top + 0.1 * u)], skin)
    elif ears == "floppy":
        for sd in (-1, 1):
            blob((sd * 0.78 * u, top + 0.55 * u), 0.2 * u, 0.5 * u, shade(skin, 0.7))
    elif ears == "long":
        for sd in (-1, 1):
            blob((sd * 0.3 * u, top - 0.5 * u), 0.2 * u, 0.7 * u, skin)
    elif ears == "round":
        for sd in (-1, 1):
            blob((sd * 0.58 * u, top + 0.12 * u), 0.26 * u, 0.26 * u, skin)
    elif ears == "frog":
        for sd in (-1, 1):
            blob((sd * 0.42 * u, top - 0.05 * u), 0.3 * u, 0.3 * u, skin)
    elif ears == "comb":
        for i, sd in enumerate((-0.3, 0.0, 0.3)):
            blob((sd * u, top - (0.16 * u if i == 1 else 0.03 * u)), 0.17 * u, 0.17 * u, (60, 60, 230))

    # head
    P = T(*FP(0, 0))
    cv.ellipse(P[0], P[1], r * pose.sx, r * pose.sy, skin, ink, ow, angle=pose.rot)

    # hair (people only)
    hs = ch.get("hair_style", "short")
    if not form and hs != "bald":
        def crescent(inner=0.72, a0=192, a1=348, outer=1.07):
            outer_pts = [FP(math.cos(math.radians(a)) * r * outer, math.sin(math.radians(a)) * r * outer) for a in range(a0, a1 + 1, 12)]
            inner_pts = [FP(math.cos(math.radians(a)) * r * inner, math.sin(math.radians(a)) * r * (inner + 0.04)) for a in range(a1, a0 - 1, -12)]
            poly(outer_pts + inner_pts, hair, ink, ow * 0.6)
        if hs in ("short", "bob", "long", "bun", "pigtails"):
            crescent()
        if hs == "bob" or hs == "long":
            for sd in (-1, 1):
                line(FP(sd * r * 0.96, -r * 0.2), FP(sd * r * 0.96, r * (0.5 if hs == "bob" else 1.5)), hair, lw * 0.7)
        if hs == "spiky":
            crescent(0.8)
            for i in range(5):
                bx = -r * 0.75 + i * r * 0.375
                poly([FP(bx - 0.14 * u, -r * 0.82), FP(bx, -r - 0.45 * u + (0.15 * u if i in (0, 4) else 0)), FP(bx + 0.14 * u, -r * 0.82)], hair, ink, ow * 0.6)
        if hs == "mohawk":
            poly([FP(-0.22 * u, -r * 0.9), FP(-0.12 * u, -r - 0.65 * u), FP(0.12 * u, -r - 0.65 * u), FP(0.22 * u, -r * 0.9)], hair, ink, ow * 0.6)
        if hs == "curly":
            for i in range(5):
                c = FP(-r * 0.8 + i * r * 0.4, -r * (0.85 if i % 2 else 0.95))
                circle(c, 0.22 * u, hair, ink, ow * 0.5)
        if hs == "bun":
            circle(FP(0, -r - 0.22 * u), 0.3 * u, hair, ink, ow * 0.6)
        if hs == "pigtails":
            for sd in (-1, 1):
                circle(FP(sd * (r + 0.2 * u), -r * 0.2), 0.27 * u, hair, ink, ow * 0.6)

    # face
    brow_in, brow_h, mouth = _emotion_face(emotion)
    blink = ((t + blink_seed) % 3.4) > 3.28
    ex, ey = 0.3 * u, -0.06 * u
    wide = emotion in ("surprised", "scared")
    for sd in (-1, 1):
        c = FP(sd * ex, ey)
        if blink:
            line((c[0] - 0.1 * u, c[1]), (c[0] + 0.1 * u, c[1]), ink, ow * 0.7, cap=False)
        elif wide or ch.get("eyes") == "round":
            circle(c, 0.16 * u * look.eyes, (255, 255, 255), ink, ow * 0.6)
            circle((c[0] - sd * 0.02 * u, c[1]), 0.07 * u * look.eyes, (25, 20, 20))
        else:
            circle(c, 0.075 * u * look.eyes, (25, 20, 20))
        bl = 0.17 * u
        by0 = c[1] - 0.24 * u + brow_h * 0.01 * u
        k = math.sin(math.radians(brow_in)) * bl
        line((c[0] - sd * bl * 0.9, by0 - k), (c[0] + sd * bl * 0.9, by0 + k), ink if not hs == "bald" else ink, ow * 0.8, cap=False)
    if facekind in ("cat", "dog", "bear", "bunny"):
        n = FP(0, 0.1 * u)
        poly([(n[0] - 0.08 * u, n[1]), (n[0] + 0.08 * u, n[1]), (n[0], n[1] + 0.08 * u)], (60, 60, 120))
        if facekind == "cat":
            for sd in (-1, 1):
                for k in (-0.05, 0.05):
                    line(FP(sd * 0.2 * u, 0.12 * u + k * u), FP(sd * 0.62 * u, 0.12 * u + k * u * 3), (245, 245, 245), ow * 0.5, cap=False)
    elif facekind == "pig":
        c = FP(0, 0.14 * u)
        P = T(*c)
        cv.ellipse(P[0], P[1], 0.26 * u * pose.sx, 0.18 * u * pose.sy, bgr("#f48fb1"), ink, ow * 0.6, angle=pose.rot)
    elif facekind in ("chicken", "duck"):
        b = FP(0, 0.14 * u)
        poly([(b[0] - 0.22 * u, b[1] - 0.06 * u), (b[0] + 0.22 * u, b[1] - 0.06 * u), (b[0], b[1] + 0.2 * u)], bgr("#ff9f1c"), ink, ow * 0.6)
    mo = max(talk, 0.0)
    my = 0.42 * u
    mx, myy = FP(0, my)
    if facekind in ("chicken", "duck"):
        pass
    elif mo > 0.12 or mouth in ("open_smile", "open_o"):
        mo = max(mo, 0.55 if mouth == "open_o" else 0.45 if mouth == "open_smile" else 0.0)
        mw = 0.2 * u * (0.55 if mouth == "open_o" else 1.0)
        P = T(mx, myy)
        cv.ellipse(P[0], P[1], mw * pose.sx, (0.04 + 0.22 * mo) * u * pose.sy, (25, 20, 60), ink, ow * 0.5, angle=pose.rot)
    elif mouth in ("smile", "smirk"):
        P = T(mx + (0.06 * u if mouth == "smirk" else 0), myy - 0.05 * u)
        cv.ellipse(P[0], P[1], 0.22 * u * pose.sx, 0.14 * u * pose.sy, None, ink, ow * 0.8, angle=pose.rot, a0=15, a1=165)
    elif mouth in ("frown", "frown_hard"):
        P = T(mx, myy + 0.1 * u)
        cv.ellipse(P[0], P[1], 0.2 * u * pose.sx, 0.12 * u * pose.sy, None, ink, ow * 0.8, angle=pose.rot, a0=195, a1=345)
    elif mouth == "wave":
        cv.polyline([T(*FP(-0.2 * u + i * 0.1 * u, my + (0.03 if i % 2 else -0.03) * u)) for i in range(5)], ink, ow * 0.8)
    else:
        line((mx - 0.16 * u, myy), (mx + 0.16 * u, myy), ink, ow * 0.8, cap=False)

    # hats and glasses
    if acc in ("glasses", "sunglasses"):
        for sd in (-1, 1):
            c = FP(sd * ex, ey)
            P = T(*c)
            cv.ellipse(P[0], P[1], 0.23 * u * pose.sx, 0.2 * u * pose.sy, (30, 25, 25) if acc == "sunglasses" else None, ink, ow * 0.8, angle=pose.rot)
        line(FP(-ex + 0.23 * u, ey), FP(ex - 0.23 * u, ey), ink, ow * 0.7, cap=False)
    elif acc == "cap":
        pts = [FP(math.cos(math.radians(a)) * r * 1.08, math.sin(math.radians(a)) * r * 1.08) for a in range(185, 356, 12)]
        poly(pts + [FP(r * 1.0, -r * 0.35), FP(-r * 1.0, -r * 0.35)], acc_color, ink, ow * 0.7)
        poly([FP(0.1 * u, -r * 0.4), FP(r + 0.5 * u, -r * 0.32), FP(r + 0.45 * u, -r * 0.18), FP(0.1 * u, -r * 0.22)], shade(acc_color, 0.8), ink, ow * 0.6)
    elif acc == "beanie":
        pts = [FP(math.cos(math.radians(a)) * r * 1.1, math.sin(math.radians(a)) * r * 1.2) for a in range(185, 356, 12)]
        poly(pts, acc_color, ink, ow * 0.7)
        circle(FP(0, -r * 1.25), 0.17 * u, shade(acc_color, 1.35), ink, ow * 0.5)
    elif acc == "crown":
        poly([FP(-0.6 * u, -r * 0.8), FP(-0.6 * u, -r - 0.4 * u), FP(-0.3 * u, -r - 0.1 * u), FP(0, -r - 0.5 * u), FP(0.3 * u, -r - 0.1 * u), FP(0.6 * u, -r - 0.4 * u), FP(0.6 * u, -r * 0.8)],
             bgr("#ffd23f"), ink, ow * 0.7)
    elif acc == "headband":
        line(FP(-r * 0.97, -r * 0.42), FP(r * 0.97, -r * 0.42), acc_color, lw * 0.6, cap=False)
    elif acc == "top_hat":
        poly([FP(-r * 1.15, -r * 0.78), FP(r * 1.15, -r * 0.78), FP(r * 1.15, -r * 0.92), FP(-r * 1.15, -r * 0.92)], (40, 35, 35), ink, ow * 0.6)
        poly([FP(-r * 0.62, -r * 0.9), FP(r * 0.62, -r * 0.9), FP(r * 0.62, -r - 0.9 * u), FP(-r * 0.62, -r - 0.9 * u)], (40, 35, 35), ink, ow * 0.6)
    elif acc == "bandana":
        line(FP(-r * 0.97, -r * 0.5), FP(r * 0.97, -r * 0.5), acc_color, lw * 0.7, cap=False)
    elif acc in ("cat_ears", "bunny_ears") and not ears:
        for sd in (-1, 1):
            if acc == "cat_ears":
                tri([(sd * 0.6 * u, top + 0.25 * u), (sd * 0.4 * u, top - 0.45 * u), (sd * 0.1 * u, top + 0.1 * u)], acc_color)
            else:
                blob((sd * 0.3 * u, top - 0.5 * u), 0.18 * u, 0.65 * u, acc_color)
    elif acc == "scarf":
        line((-0.3 * u, neck[1] + 0.05 * u), (0.3 * u, neck[1] + 0.05 * u), acc_color, lw * 0.8, cap=False)
        line((0.2 * u, neck[1] + 0.05 * u), (0.3 * u, neck[1] + 0.9 * u), acc_color, lw * 0.7)
    elif acc == "tie":
        poly([(-0.1 * u, neck[1] + 0.1 * u), (0.1 * u, neck[1] + 0.1 * u), (0.12 * u, neck[1] + 1.0 * u), (0, neck[1] + 1.15 * u), (-0.12 * u, neck[1] + 1.0 * u)], acc_color, ink, ow * 0.5)
    elif acc == "bowtie":
        poly([(0, neck[1] + 0.18 * u), (-0.4 * u, neck[1]), (-0.4 * u, neck[1] + 0.36 * u)], acc_color, ink, ow * 0.5)
        poly([(0, neck[1] + 0.18 * u), (0.4 * u, neck[1]), (0.4 * u, neck[1] + 0.36 * u)], acc_color, ink, ow * 0.5)


def _rp(p, pivot, deg):
    if not deg:
        return p
    return rot_pts([p], pivot, deg)[0]
