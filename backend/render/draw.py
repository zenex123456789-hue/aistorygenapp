"""Tiny anti-aliased drawing layer on top of OpenCV with a 2D camera.

All geometry is given in "world" coordinates (a 1080x1920 portrait stage). The
camera maps world -> screen so zooms, pans and shakes apply to everything for free.
"""
from __future__ import annotations

import colorsys
import math

import cv2
import numpy as np

SHIFT = 4
ONE = 1 << SHIFT
W, H = 1080, 1920


def bgr(hexcolor: str) -> tuple[int, int, int]:
    h = hexcolor.lstrip("#")
    return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)


def shade(c: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    """k<1 darkens, k>1 lightens toward white."""
    if k <= 1:
        return tuple(int(max(0, min(255, v * k))) for v in c)  # type: ignore[return-value]
    f = k - 1
    return tuple(int(min(255, v + (255 - v) * f)) for v in c)  # type: ignore[return-value]


def mix(a, b, t: float):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def hue_shift_hex(hexcolor: str, deg: float) -> str:
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    hh = (hh + deg / 360.0) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hh, ss, vv)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


class Cam:
    def __init__(self, zoom: float = 1.0, cx: float = W / 2, cy: float = H / 2, rot: float = 0.0):
        self.zoom, self.cx, self.cy, self.rot = zoom, cx, cy, rot


class Canvas:
    """Draws world-space shapes onto a BGR image through a camera."""

    def __init__(self, img: np.ndarray, cam: Cam, res: float = 1.0):
        self.img = img
        self.cam = cam
        self.res = res                      # internal resolution factor (0.5 for draft renders)
        self.look = None                    # art style (render/looks.py); the character rig reads it
        self.k = cam.zoom * res
        self.ox = W / 2 * res
        self.oy = H / 2 * res
        r = math.radians(cam.rot)
        self._cos, self._sin = math.cos(r), math.sin(r)

    # -- transforms ---------------------------------------------------------
    def pt(self, x: float, y: float) -> tuple[float, float]:
        dx, dy = (x - self.cam.cx), (y - self.cam.cy)
        if self.cam.rot:
            dx, dy = dx * self._cos - dy * self._sin, dx * self._sin + dy * self._cos
        return dx * self.k + self.ox, dy * self.k + self.oy

    def pts(self, poly) -> np.ndarray:
        a = np.asarray(poly, dtype=np.float64)
        d = a - np.array([self.cam.cx, self.cam.cy])
        if self.cam.rot:
            d = np.stack([d[:, 0] * self._cos - d[:, 1] * self._sin, d[:, 0] * self._sin + d[:, 1] * self._cos], axis=1)
        d = d * self.k + np.array([self.ox, self.oy])
        return np.round(d * ONE).astype(np.int32)

    def s(self, v: float) -> float:
        return v * self.k

    # -- primitives ---------------------------------------------------------
    def poly(self, poly, color, outline=None, ow: float = 0):
        p = self.pts(poly)
        cv2.fillPoly(self.img, [p], color, lineType=cv2.LINE_AA, shift=SHIFT)
        if outline is not None and ow > 0:
            cv2.polylines(self.img, [p], True, outline, thickness=max(1, int(round(ow * self.k))),
                          lineType=cv2.LINE_AA, shift=SHIFT)

    def rect(self, x, y, w, h, color, outline=None, ow: float = 0):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], color, outline, ow)

    def rrect(self, x, y, w, h, r, color, outline=None, ow: float = 0):
        self.poly(rrect_pts(x, y, w, h, r), color, outline, ow)

    def ellipse(self, cx, cy, rx, ry, color, outline=None, ow: float = 0, angle: float = 0.0,
                a0: float = 0, a1: float = 360):
        c = self.pt(cx, cy)
        axes = (max(1, int(round(rx * self.k * ONE))), max(1, int(round(ry * self.k * ONE))))
        ctr = (int(round(c[0] * ONE)), int(round(c[1] * ONE)))
        ang = angle + self.cam.rot
        if color is not None:
            cv2.ellipse(self.img, ctr, axes, ang, a0, a1, color, -1, cv2.LINE_AA, SHIFT)
        if outline is not None and ow > 0:
            cv2.ellipse(self.img, ctr, axes, ang, a0, a1, outline, max(1, int(round(ow * self.k))), cv2.LINE_AA, SHIFT)

    def circle(self, cx, cy, r, color, outline=None, ow: float = 0):
        self.ellipse(cx, cy, r, r, color, outline, ow)

    def line(self, x0, y0, x1, y1, color, w: float = 4):
        a, b = self.pt(x0, y0), self.pt(x1, y1)
        cv2.line(self.img, (int(round(a[0] * ONE)), int(round(a[1] * ONE))),
                 (int(round(b[0] * ONE)), int(round(b[1] * ONE))), color,
                 max(1, int(round(w * self.k))), cv2.LINE_AA, SHIFT)

    def polyline(self, poly, color, w: float = 4, closed: bool = False):
        cv2.polylines(self.img, [self.pts(poly)], closed, color, max(1, int(round(w * self.k))),
                      lineType=cv2.LINE_AA, shift=SHIFT)

    def text(self, s: str, x: float, y: float, size: float, color, thick: float = 3, center: bool = True):
        scale = size * self.k / 40.0
        t = max(1, int(round(thick * self.k)))
        (tw, th), _ = cv2.getTextSize(s, cv2.FONT_HERSHEY_DUPLEX, scale, t)
        px, py = self.pt(x, y)
        if center:
            px -= tw / 2
            py += th / 2
        cv2.putText(self.img, s, (int(px), int(py)), cv2.FONT_HERSHEY_DUPLEX, scale, color, t, cv2.LINE_AA)


def rrect_pts(x, y, w, h, r, n: int = 5) -> list[tuple[float, float]]:
    r = max(0.0, min(r, w / 2, h / 2))
    pts: list[tuple[float, float]] = []
    corners = [(x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)]
    for cx, cy, a0 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def rot_pts(pts, pivot, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    px, py = pivot
    return [(px + (x - px) * c - (y - py) * s, py + (x - px) * s + (y - py) * c) for x, y in pts]


def star_pts(cx, cy, r, n: int = 5, inner: float = 0.45, rot: float = -90):
    out = []
    for i in range(n * 2):
        a = math.radians(rot + i * 180 / n)
        rr = r if i % 2 == 0 else r * inner
        out.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return out


def vertical_gradient(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> np.ndarray:
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    top_a, bot_a = np.array(top, dtype=np.float32), np.array(bottom, dtype=np.float32)
    col = (top_a[None, :] * (1 - t) + bot_a[None, :] * t)          # h x 3
    return np.repeat(col[:, None, :], w, axis=1).astype(np.uint8)
