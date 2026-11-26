"""Scene renderer: turns one scene plan into frames (and into an mp4 segment)."""
from __future__ import annotations

import math
import random
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from .. import config
from . import rig
from .draw import Cam, Canvas, bgr, W, H, star_pts
from .world import FEET_Y, draw_world, effective_palette, sky_image

SHOT_ZOOM = {"wide": 0.80, "medium": 1.0, "close": 1.5, "extreme_close": 2.15, "low_angle": 1.18, "over_shoulder": 1.32}
SHOT_FOCUS = {"wide": 0.0, "medium": 0.30, "close": 1.0, "extreme_close": 1.0, "low_angle": 0.35, "over_shoulder": 0.8}
CHAR_SCALE = {1: 1.12, 2: 0.98, 3: 0.84, 4: 0.72}
LAYOUT = {1: [540], 2: [350, 730], 3: [250, 540, 830], 4: [190, 410, 670, 890]}
EXTRA_COLORS = ["#ef476f", "#06d6a0", "#ffd166", "#118ab2", "#8338ec", "#fb5607", "#80ed99", "#ff99c8"]

_vignette_cache: dict = {}


def _vignette(h: int, w: int) -> np.ndarray:
    key = (h, w)
    if key not in _vignette_cache:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        m = np.clip(1.0 - 0.55 * np.clip(d - 0.55, 0, 1) ** 1.4, 0.35, 1.0)
        _vignette_cache[key] = m[:, :, None].astype(np.float32)
    return _vignette_cache[key]


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class SceneRenderer:
    def __init__(self, plan: dict, res: float = 1.0):
        self.plan = plan
        self.res = res
        self.scene = plan["scene"]
        self.world = plan["world"]
        self.fps = plan.get("fps", 24)
        self.duration = plan["duration"]
        self.cast = plan["cast"]                      # list of character specs (on-screen only)
        self.lines = plan.get("lines", [])
        self.sw, self.sh = int(W * res), int(H * res)
        self.sky: dict = {}
        self.rng = random.Random(self.scene["id"])
        n = max(1, min(4, len(self.cast)))
        self.xs = LAYOUT[n][: len(self.cast)] if self.cast else []
        self.cscale = CHAR_SCALE[n]
        self.cam_state: tuple[float, float] | None = None
        self.effects = set(self.scene.get("effects", []))
        self.actions: dict[str, list[dict]] = {}
        for a in sorted(self.scene.get("actions", []), key=lambda a: a.get("at", 0)):
            self.actions.setdefault(a["character_id"], []).append(a)
        self.start_forms = plan.get("start_forms", {})
        crowd = int(self.scene.get("environment", {}).get("crowd", 0) or 0)
        self.extras = []
        rr = random.Random(self.scene["id"] + "crowd")
        for k in range(min(crowd, 8)):
            self.extras.append({
                "x": 90 + (k + 0.5) * (900 / max(crowd, 1)) + rr.uniform(-30, 30),
                "spec": {"height": rr.uniform(0.7, 0.85), "build": rr.choice(["slim", "normal", "chunky"]),
                         "skin": rr.choice(["#f5c9a0", "#e0ac69", "#c68642", "#8d5524"]),
                         "hair_style": rr.choice(["short", "spiky", "bob", "curly", "bald"]), "hair_color": rr.choice(["#3b2a1a", "#222222", "#b5651d", "#d4a017"]),
                         "shirt_color": rr.choice(EXTRA_COLORS), "shirt_pattern": rr.choice(["none", "stripes", "none"]),
                         "pants_color": "#3d405b", "shoes_color": "#222222", "accessory": "none", "eyes": "dot"},
                "seed": rr.random() * 6,
            })

    # ------------------------------------------------------------ helpers
    def _speaker_at(self, t: float):
        for ln in self.lines:
            if ln["start"] <= t < ln["end"] + 0.12:
                return ln
        return None

    def _talk_level(self, ln: dict, t: float) -> float:
        env = ln.get("env")
        k = int((t - ln["start"]) * self.fps)
        if env is not None and 0 <= k < len(env):
            return float(env[k])
        if t < ln["end"]:                                 # no envelope: synthetic flap
            return 0.5 + 0.5 * math.sin(t * 18)
        return 0.0

    def _action_state(self, cid: str, t: float):
        cur, local, form = {"animation": "idle", "at": 0, "note": ""}, t, self.start_forms.get(cid, "")
        for a in self.actions.get(cid, []):
            if a["at"] <= t:
                cur, local = a, t - a["at"]
                if a.get("form"):
                    # the new form takes effect a quarter second after the transformation starts (hidden by the poof)
                    delay = 0.22 if a.get("animation") == "transform" else 0.0
                    form = "" if a["form"] == "human" else (a["form"] if local > delay else form)
        return cur, local, form

    def _camera(self, t: float, speaker_x: float | None, speaker_head: float | None) -> Cam:
        cam = self.scene.get("camera", {})
        shot, move = cam.get("shot", "medium"), cam.get("move", "static")
        zoom = SHOT_ZOOM.get(shot, 1.0)
        k = SHOT_FOCUS.get(shot, 0.3)
        fx = speaker_x if speaker_x is not None else (self.xs[0] if self.xs else 540)
        fy = speaker_head if speaker_head is not None else FEET_Y - 500
        tcx = 540 + (fx - 540) * k
        tcy = 960 + (fy - 960 + 60) * (k if k > 0.5 else 0.0) + (30 if k <= 0.5 else 0)
        if self.cam_state is None:
            self.cam_state = (tcx, tcy)
        cx, cy = self.cam_state
        cx += (tcx - cx) * 0.14
        cy += (tcy - cy) * 0.14
        self.cam_state = (cx, cy)
        p = t / max(self.duration, 0.01)
        if move == "push_in":
            zoom *= 1.0 + 0.14 * p
        elif move == "pull_out":
            zoom *= 1.14 - 0.14 * p
        elif move == "pan_left":
            cx += 90 * (0.5 - p)
        elif move == "pan_right":
            cx -= 90 * (0.5 - p)
        elif move == "whip":
            e = 1 - _ease(t / 0.35)
            cx += 520 * e
            zoom *= 1 + 0.25 * e
        if move == "shake" or "shake" in self.effects:
            amp = 12 if move == "shake" else 16 * max(0.0, 1 - t / 1.3)
            cx += math.sin(t * 61) * amp
            cy += math.cos(t * 53) * amp
        punch = 0.06 * max(0.0, 1 - t / 0.25)                   # tiny zoom punch on every scene start
        return Cam(zoom * (1 + punch), cx, cy)

    # ------------------------------------------------------------ frame
    def frame(self, t: float) -> np.ndarray:
        res = self.res
        hue = 0.0
        if "color_shift" in self.effects:
            hue = 300.0 * min(1.0, max(0.0, (t - 0.8) / max(self.duration - 1.2, 1.0)))
        tod = self.scene.get("environment", {}).get("time_of_day") or self.world.get("time_of_day", "day")
        pal = effective_palette(self.world, tod, hue)
        key = (tod, round(hue / 6))
        if key not in self.sky:
            self.sky = {key: sky_image(pal, res)}
        img = self.sky[key].copy()

        speaker = self._speaker_at(t)
        sp_id = speaker["character_id"] if speaker else None
        sp_idx = next((i for i, c in enumerate(self.cast) if c["id"] == sp_id), None)
        spk_x = self.xs[sp_idx] if sp_idx is not None else None
        spk_head = (FEET_Y - 5.0 * 100 * self.cast[sp_idx].get("height", 1.0) * self.cscale) if sp_idx is not None else None
        cam = self._camera(t, spk_x, spk_head)
        cv = Canvas(img, cam, res)

        clock = (11, int(55 + 5 * min(1.0, t / max(self.duration * 0.6, 1.0)))) if "clock_tower" in (self.world.get("landmark", "") + " ".join(self.world.get("props", []))).lower().replace(" ", "_") else (11, 55)
        draw_world(cv, self.world, pal, t, {"tod": tod, "clock": (clock[0] + (1 if clock[1] >= 60 else 0), clock[1] % 60)})

        # extras (background crowd)
        crowd_form = self.scene.get("environment", {}).get("crowd_form", "")
        for ex in self.extras:
            form = crowd_form if (crowd_form and t > 0.5) else ""
            pose = rig.make_pose("transform" if (crowd_form and 0.3 < t < 1.2) else "idle", max(0.0, t - 0.3), "neutral", 0.0, ex["seed"])
            rig.draw_character(cv, ex["spec"], ex["x"], FEET_Y - 190, 0.52, pose, emotion="surprised" if crowd_form else "neutral",
                               t=t, form=form, blink_seed=ex["seed"])
            if crowd_form and 0.25 < t < 0.9:
                self._poof(cv, ex["x"], FEET_Y - 190 - 140, (t - 0.25) / 0.65, 0.6)

        # main cast
        order = sorted(range(len(self.cast)), key=lambda i: (0 if i % 2 == 0 else 1))
        for i in order:
            ch = self.cast[i]
            cid = ch["id"]
            act, local, form = self._action_state(cid, t)
            talking = self._talk_level(speaker, t) if speaker and speaker["character_id"] == cid else 0.0
            emotion = speaker["emotion"] if talking > 0 or (speaker and speaker["character_id"] == cid) else self.scene.get("emotion", "neutral")
            if ch["id"] != sp_id and speaker and self.scene.get("emotion") in ("neutral", None):
                emotion = "surprised" if t - speaker["start"] < 0.6 else "neutral"
            pose = rig.make_pose(act["animation"], local, emotion, talking, i * 1.7)
            x = self.xs[i]
            note = (act.get("note") or "").lower()
            if act["animation"] in ("walk", "run", "sneak"):
                away = any(w in note for w in ("away", "off", "flee", "escape", "leave", "exit"))
                sp = {"walk": 110, "run": 260, "sneak": 55}[act["animation"]] * (1.6 if away else 1.0)
                direction = (1 if x >= 540 else -1) if away else (-1 if x >= 540 else 1)
                x += direction * min(sp * local, 700 if away else 240)
            feet = FEET_Y + (14 if i % 2 else -4)
            rig.draw_character(cv, ch, x, feet, self.cscale, pose, emotion=emotion, talk=talking, t=t,
                               facing=1 if self.xs[i] < 540 else -1, form=form, blink_seed=i * 0.9)
            if act["animation"] in ("transform", "vanish", "appear") and local < 0.9:
                self._poof(cv, x, feet - 260 * self.cscale, local / 0.9, 1.0 * self.cscale)

        if "poof" in self.effects and 0.3 < t < 1.1:
            for i, ch in enumerate(self.cast):
                self._poof(cv, self.xs[i], FEET_Y - 250 * self.cscale, (t - 0.3) / 0.8, self.cscale)

        # speech-bubble style markers
        if speaker and sp_idx is not None and (t - speaker["start"]) < 0.9:
            if "exclaim" in self.effects or speaker["emotion"] in ("surprised", "scared"):
                self._marker(cv, spk_x + 130, spk_head - 60, "!", (40, 40, 230), t)
            elif "question" in self.effects or speaker["emotion"] == "confused":
                self._marker(cv, spk_x + 130, spk_head - 60, "?", (230, 120, 40), t)

        if "sparkles" in self.effects:
            rr = random.Random(7)
            for k in range(14):
                px = 100 + rr.random() * 880
                py = 700 + rr.random() * 700
                s_ = 8 + 10 * (0.5 + 0.5 * math.sin(t * 5 + k))
                cv.poly(star_pts(px, py, s_, 4, 0.3), (120, 235, 255))

        out = cv.img
        sc = Canvas(out, Cam(1.0, W / 2, H / 2), res)                 # screen-space overlays (identity camera)
        if "rain" in self.effects:
            for k in range(70):
                px = (k * 97 + t * 260) % 1300 - 100
                py = (k * 211 + t * 1500) % 2100 - 100
                sc.line(px, py, px - 16, py + 52, (255, 225, 190), 3)
        if "confetti" in self.effects:
            for k in range(90):
                px = (k * 131) % 1080 + math.sin(t * 3 + k) * 30
                py = (k * 53 + t * 380 * (0.6 + (k % 5) * 0.2)) % 2000 - 60
                col = bgr(EXTRA_COLORS[k % len(EXTRA_COLORS)])
                sc.rect(px, py, 14, 22, col)
        if "spotlight" in self.effects and sp_idx is not None:
            mask = np.full(out.shape[:2], 0.38, dtype=np.float32)
            cx_, cy_ = cv.pt(spk_x, spk_head + 160)
            cv2.circle(mask, (int(cx_), int(cy_)), int(430 * cam.zoom * res), 1.0, -1, cv2.LINE_AA)
            mask = cv2.GaussianBlur(mask, (0, 0), 38 * res)
            out = (out.astype(np.float32) * mask[:, :, None]).astype(np.uint8)
        if "dark" in self.effects:
            out = (out.astype(np.float32) * 0.55).astype(np.uint8)
        if "vignette" in self.effects or "dark" in self.effects or tod == "night":
            out = (out.astype(np.float32) * _vignette(self.sh, self.sw)).astype(np.uint8)
        if "flash" in self.effects:
            if self.plan["scene"].get("index", 1) == 0:
                # opening scene: never start on a white frame (it can become the cover/thumbnail); pulse a moment later
                a = max(0.0, 1.0 - abs(t - 0.4) / 0.2) * 0.55
            else:
                a = max(0.0, 1.0 - t / 0.5) * 0.9
            if a > 0:
                out = cv2.addWeighted(out, 1 - a, np.full_like(out, 255), a, 0)
        # simple style-profile grade (saturation / brightness measured from the user's references)
        style = self.plan.get("style") or {}
        sat, bri = float(style.get("saturation_scale", 1.0)), float(style.get("brightness_scale", 1.0))
        if abs(sat - 1) > 0.02 or abs(bri - 1) > 0.02:
            hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat, 0, 255)
            hsv[:, :, 2] = np.clip(hsv[:, :, 2] * bri, 0, 255)
            out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        return out

    def _poof(self, cv: Canvas, x: float, y: float, p: float, s: float):
        p = max(0.0, min(1.0, p))
        a = 1 - p
        for k in range(9):
            ang = k * 40 + 11
            rad = (30 + 150 * p) * s
            cx_, cy_ = x + math.cos(math.radians(ang)) * rad, y + math.sin(math.radians(ang)) * rad * 0.8
            col = (255, 255, 255) if k % 2 else (225, 225, 235)
            cv.circle(cx_, cy_, (26 + 38 * (1 - abs(p - 0.4))) * s * (0.4 + a), col, (190, 190, 205), 2)
        if p < 0.6:
            for k in range(6):
                ang = k * 60 + 20
                cv.poly(star_pts(x + math.cos(math.radians(ang)) * 160 * p * s, y + math.sin(math.radians(ang)) * 130 * p * s, 14 * s, 4, 0.3), (90, 230, 255))

    def _marker(self, cv: Canvas, x: float, y: float, ch: str, color, t: float):
        bob = math.sin(t * 14) * 4
        cv.circle(x, y + bob, 52, (255, 255, 255), (30, 30, 30), 5)
        cv.text(ch, x, y + bob, 72, color, 7)


# ---------------------------------------------------------------- encoding
def encode_frames(frame_fn, n_frames: int, out_path: Path, *, fps: int, res: float, crf: int, preset: str,
                  progress=None, check_cancel=None) -> None:
    sw, sh = int(W * res), int(H * res)
    vf = [] if res == 1.0 else ["-vf", f"scale={W}:{H}:flags=lanczos"]
    cmd = [config.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{sw}x{sh}",
           "-r", str(fps), "-i", "-", "-an", *vf, "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
    with tempfile.TemporaryFile() as errf:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=errf)
        try:
            for i in range(n_frames):
                if check_cancel:
                    check_cancel()
                img = frame_fn(i / fps)
                proc.stdin.write(np.ascontiguousarray(img).tobytes())
                if progress and i % 8 == 0:
                    progress(i / n_frames)
            proc.stdin.close()
            code = proc.wait(timeout=300)
        except BaseException:
            proc.kill()
            raise
        if code != 0:
            errf.seek(0)
            raise RuntimeError("ffmpeg segment encode failed: " + errf.read().decode(errors="replace")[-400:])


def render_segment(plan: dict, out_path: Path, *, res: float, crf: int, preset: str, progress=None, check_cancel=None) -> None:
    r = SceneRenderer(plan, res)
    n = max(2, int(round(plan["duration"] * plan.get("fps", 24))))
    encode_frames(r.frame, n, out_path, fps=plan.get("fps", 24), res=res, crf=crf, preset=preset,
                  progress=progress, check_cancel=check_cancel)


def render_still(plan: dict, t: float, res: float = 0.5) -> np.ndarray:
    r = SceneRenderer(plan, res)
    for k in range(6):                       # warm the smoothed camera so stills match the video
        r.frame(max(0.0, t - (6 - k) * 0.04))
    return r.frame(t)


def render_keyframe_segment(plan: dict, image_path: Path, out_path: Path, *, res: float, crf: int, preset: str,
                            progress=None, check_cancel=None) -> None:
    """AI keyframe image -> animated segment (slow push-in / pan). Characters come from the image itself."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"cannot read keyframe {image_path.name}")
    sw, sh = int(W * res), int(H * res)
    ih, iw = img.shape[:2]
    k = max(sw / iw, sh / ih) * 1.25                      # cover with 25% spare for camera movement
    big = cv2.resize(img, (int(iw * k), int(ih * k)), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC)
    bh, bw = big.shape[:2]
    move = plan["scene"].get("camera", {}).get("move", "push_in")
    dur = plan["duration"]

    def frame(t: float) -> np.ndarray:
        p = t / max(dur, 0.01)
        zoom = 1.0 / (1.0 + (0.18 * p if move != "pull_out" else 0.18 * (1 - p)))
        cw, ch_ = int(sw * 1.25 * zoom * (1 / 1.0) / 1.25 * 1.0), int(sh * zoom)
        cw = int(bw / 1.25 * zoom)
        ch_ = int(bh / 1.25 * zoom)
        cx = bw / 2 + (60 * (p - 0.5) * (1 if move == "pan_right" else -1 if move == "pan_left" else 0))
        x0 = int(max(0, min(bw - cw, cx - cw / 2)))
        y0 = int(max(0, min(bh - ch_, bh / 2 - ch_ / 2)))
        crop = big[y0:y0 + ch_, x0:x0 + cw]
        return cv2.resize(crop, (sw, sh), interpolation=cv2.INTER_AREA)

    n = max(2, int(round(dur * plan.get("fps", 24))))
    encode_frames(frame, n, out_path, fps=plan.get("fps", 24), res=res, crf=crf, preset=preset,
                  progress=progress, check_cancel=check_cancel)
