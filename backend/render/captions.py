"""Caption files: ASS (styled, word-highlighted, burned into the video) and SRT (for upload)."""
from __future__ import annotations

import re

POSITIONS = {   # name -> (alignment, margin_v)
    "lower": (2, 330), "middle": (5, 0), "upper": (8, 360), "bottom": (2, 190),
}


def _t(sec: float) -> str:
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _srt_t(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _chunks(words: list[dict], max_words: int = 3, max_chars: int = 20) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        chars = sum(len(x["w"]) + 1 for x in cur)
        if len(cur) >= max_words or chars >= max_chars or re.search(r"[.!?,;:…]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def _ass_color(hexcolor: str) -> str:
    h = hexcolor.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def build_ass(timeline: dict, scenes: list[dict], style: dict | None = None) -> str:
    style = style or {}
    sub = style.get("subtitle", {}) if isinstance(style.get("subtitle"), dict) else {}
    align, margin = POSITIONS.get(sub.get("position", "lower"), POSITIONS["lower"])
    size = int(86 * float(sub.get("size_scale", 1.0)))
    hi = _ass_color(sub.get("highlight", "#ffe600"))
    upper = bool(sub.get("uppercase", True))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins,{size},&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,9,3,{align},70,70,{margin},1
Style: Big,Poppins,170,&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,11,4,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev: list[str] = []
    by_id = {s["id"]: s for s in scenes}
    for ts in timeline["scenes"]:
        sc = by_id.get(ts["id"], {})
        base = ts["start"]
        for ln in ts["lines"]:
            words = ln["words"] or [{"w": w, "start": ln["start"] + i * (ln["end"] - ln["start"]) / max(1, len(ln["text"].split())),
                                     "end": ln["start"] + (i + 1) * (ln["end"] - ln["start"]) / max(1, len(ln["text"].split()))}
                                    for i, w in enumerate(ln["text"].split())]
            # timeline words are local to the scene; shift to absolute video time
            words = [{"w": (w["w"].upper() if upper else w["w"]), "start": base + w["start"] if ln["words"] else base + w["start"],
                      "end": base + w["end"]} for w in words]
            for chunk in _chunks(words):
                for k, w in enumerate(chunk):
                    start = w["start"]
                    end = chunk[k + 1]["start"] if k + 1 < len(chunk) else w["end"] + 0.18
                    parts = []
                    for j, x in enumerate(chunk):
                        txt = _esc(x["w"])
                        parts.append(f"{{\\c{hi}}}{txt}{{\\c&HFFFFFF&}}" if j == k else txt)
                    pop = "{\\fscx88\\fscy88\\t(0,110,\\fscx100\\fscy100)}" if k == 0 else ""
                    ev.append(f"Dialogue: 0,{_t(start)},{_t(max(end, start + 0.05))},Cap,,0,0,0,,{pop}{' '.join(parts)}")
        if sc.get("on_screen_text"):
            s0 = base + (ts["transition"]["dur"] if ts["transition"] else 0) + 0.15
            ev.append(f"Dialogue: 1,{_t(s0)},{_t(min(base + ts['duration'] - 0.1, s0 + 1.8))},Big,,0,0,0,,"
                      f"{{\\an5\\pos(540,620)\\fscx60\\fscy60\\t(0,160,\\fscx108\\fscy108)\\t(160,260,\\fscx100\\fscy100)}}{_esc(sc['on_screen_text'].upper())}")
    return head + "\n".join(ev) + "\n"


def build_srt(timeline: dict) -> str:
    out, n = [], 1
    for ts in timeline["scenes"]:
        for ln in ts["lines"]:
            if ln["words"]:
                words = [w["w"] for w in ln["words"]]
                s, e = ts["start"] + ln["words"][0]["start"], ts["start"] + ln["words"][-1]["end"] + 0.1
            else:
                words, s, e = ln["text"].split(), ts["start"] + ln["start"], ts["start"] + ln["end"]
            for chunk in _chunks([{"w": w} for w in words], 6, 38):
                pass
            out.append(f"{n}\n{_srt_t(s)} --> {_srt_t(e)}\n{ln['text']}\n")
            n += 1
    return "\n".join(out)
