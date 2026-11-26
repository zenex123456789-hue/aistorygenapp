"""Single source of truth for timing. Audio mixing, captions and video assembly all use this."""
from __future__ import annotations

TRANSITIONS = {   # name -> (ffmpeg xfade transition, seconds)
    "cut": ("fade", 0.04), "flash": ("fadewhite", 0.28), "slide": ("slideleft", 0.30),
    "circle": ("circleopen", 0.35), "dissolve": ("dissolve", 0.30), "fade": ("fadeblack", 0.38),
}
LINE_GAP = 0.16
TAIL = 0.42


def build_timeline(project: dict, voice_assets: dict, *, pace: float = 1.0) -> dict:
    """pace < 1 tightens everything (style profiles measured from fast-cut references)."""
    scenes = project.get("scenes", [])
    out, cursor = [], 0.0
    missing: list[str] = []
    for i, sc in enumerate(scenes):
        tname, tdur = TRANSITIONS.get(sc.get("transition", "cut"), TRANSITIONS["cut"])
        tdur = round(tdur * min(1.0, max(0.5, pace)), 3)
        d_in = 0.0 if i == 0 else tdur
        lead = 0.12 if i == 0 else d_in + 0.1
        t = lead
        lines = []
        for ln in sc.get("dialogue", []):
            va = voice_assets.get(ln["id"])
            if not va or va.get("text") != ln["text"]:
                missing.append(ln["id"])
                continue
            start = t
            end = start + va["duration"]
            lines.append({
                "id": ln["id"], "character_id": ln["character_id"], "text": ln["text"], "emotion": ln["emotion"],
                "start": round(start, 3), "end": round(end, 3),
                "words": [{"w": w["w"], "start": round(start + w["start"], 3), "end": round(start + w["end"], 3)}
                          for w in va.get("words", [])],
                "timing": va.get("timing"),
            })
            t = end + LINE_GAP
        needed = t - LINE_GAP + TAIL if lines else 0.0
        planned = float(sc.get("duration", 4.0)) * pace
        if lines:
            dur = max(needed, min(planned, needed + 1.5))
        else:
            dur = max(1.8, min(planned, 6.0))
        if i == len(scenes) - 1:
            dur += 0.5                                   # let the ending land
        start_abs = cursor if i == 0 else cursor - d_in
        out.append({"id": sc["id"], "index": i, "start": round(start_abs, 3), "duration": round(dur, 3),
                    "transition": {"name": tname, "dur": d_in, "kind": sc.get("transition", "cut")} if i else None,
                    "lines": lines})
        cursor = start_abs + dur
    return {"scenes": out, "total": round(cursor, 3), "missing_lines": missing}
