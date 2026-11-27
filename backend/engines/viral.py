"""Viral optimisation engine: scores a story before rendering and writes the post packaging.

Scores are retention-oriented estimates, never a promise of virality. With an LLM connected
the model scores the script; offline, transparent heuristics are measured from the script itself.
"""
from __future__ import annotations

import re

from . import llm_engine, schemas as S

WEIGHTS = {"hook": .22, "curiosity": .13, "entertainment": .15, "clarity": .10, "pacing": .10,
           "surprise": .12, "ending": .10, "replay": .08}
LABELS = {"hook": "Opening hook", "curiosity": "Viewer curiosity", "entertainment": "Entertainment", "clarity": "Story clarity",
          "pacing": "Pacing", "surprise": "Surprise factor", "ending": "Ending quality", "replay": "Replay potential"}
HOOK_WORDS = {"nobody", "never", "wait", "suddenly", "impossible", "what", "again", "run", "don't", "why", "secret", "everyone",
              "everything", "only", "last", "welcome", "three", "stop", "listen"}
FIX = {
    "hook": "Open on the strangest moment, mid-action, with one short line (under 8 words) in the first second. Put the rule on screen immediately.",
    "curiosity": "Plant an unanswered question in the first third (a '?' moment) and delay the explanation until the twist is near.",
    "entertainment": "Add more physical comedy and variety: different animations per character, sound effects on every reveal, one visual gag per scene.",
    "clarity": "Shorten lines (aim for 6-10 words), state the rule in a single sentence, and keep at most three speaking characters.",
    "pacing": "Tighten scenes to 3-6 seconds, cut filler lines, and keep spoken pace around 2.5-3 words per second.",
    "surprise": "Make the twist recontextualise the rule (who caused it, why it exists, who is immune) and punctuate it with a flash and a sting.",
    "ending": "End on a clear payoff beat plus a direct comment prompt (a question viewers can answer in one word).",
    "replay": "Echo a line or image from the hook in the final seconds so the loop rewards a rewatch.",
}


def _score_heuristic(project: dict) -> dict:
    scenes = project.get("scenes") or []
    opts = project.get("options") or {}
    if not scenes:
        return {k: 0 for k in WEIGHTS}
    first = scenes[0]
    first_line = (first["dialogue"][0]["text"] if first["dialogue"] else "")
    fw = first_line.split()
    hook = 45
    hook += 15 if first_line.endswith(("!", "?")) else 0
    hook += 10 if {w.lower().strip(".,!?'\"") for w in fw} & HOOK_WORDS else 0
    hook += 10 if 0 < len(fw) <= 10 else 0
    hook += 10 if first["effects"] or first["actions"] else 0
    hook += 10 if first["duration"] <= 4.5 else 0
    all_lines = [d["text"] for s in scenes for d in s["dialogue"]]
    nwords = sum(len(t.split()) for t in all_lines)
    q_first_half = sum(t.count("?") for t in all_lines[: max(1, len(all_lines) // 2)])
    kinds = {s["kind"] for s in scenes}
    curiosity = 50 + 8 * min(3, q_first_half) + (12 if "twist" in kinds else 0) + (8 if "rule" in kinds else 0) + (8 if any("question" in s["effects"] for s in scenes) else 0)
    anims = {a["animation"] for s in scenes for a in s["actions"]}
    fx = {e for s in scenes for e in s["effects"]}
    sfx = {x["name"] for s in scenes for x in s["sfx"]}
    entertainment = 42 + min(20, 4 * len(anims)) + min(12, 3 * len(fx)) + min(8, 2 * len(sfx)) + (8 if opts.get("humour", 50) >= 50 else 0)
    avg = nwords / max(1, len(all_lines))
    clarity = 62 + (10 if "rule" in kinds else -8) - max(0, (avg - 11)) * 3 + (6 if len(project.get("characters", [])) <= 5 else -6)
    total_dur = sum(s["duration"] for s in scenes) or 1
    wps = nwords / total_dur
    avg_scene = total_dur / len(scenes)
    pacing = 90 - abs(wps - 2.7) * 22 - max(0, avg_scene - 6.5) * 6 - max(0, 3 - avg_scene) * 8
    twist_scene = next((s for s in scenes if s["kind"] == "twist"), None)
    surprise = 40 + (28 if twist_scene else 0) + (10 if twist_scene and "flash" in twist_scene["effects"] else 0) \
        + (6 if twist_scene and any(x["name"] == "sting" for x in twist_scene["sfx"]) else 0) + opts.get("twist", 50) * 0.12
    last = scenes[-1]
    last_text = " ".join(d["text"] for d in last["dialogue"])
    ending = 50 + (15 if "?" in last_text or "comment" in last_text.lower() else 0) + (10 if last["kind"] == "ending" else 0) \
        + (10 if any(a["animation"] in ("celebrate", "dance", "laugh") for a in last["actions"]) else 0) + (8 if last["effects"] else 0)
    hw = {w.lower() for w in re.findall(r"[a-zA-Z']{4,}", first_line)}
    lw = {w.lower() for w in re.findall(r"[a-zA-Z']{4,}", last_text)}
    replay = 45 + (15 if len(hw & lw) >= 1 else 0) + (12 if "?" in last_text else 0) + (8 if twist_scene else 0) + (6 if opts.get("duration", 30) <= 45 else 0)
    raw = dict(hook=hook, curiosity=curiosity, entertainment=entertainment, clarity=clarity, pacing=pacing, surprise=surprise, ending=ending, replay=replay)
    return {k: int(max(5, min(97, v))) for k, v in raw.items()}


def _packaging_offline(project: dict) -> dict:
    st = project.get("story") or {}
    parsed = st.get("parsed") or {}
    chars = [c for c in project.get("characters", []) if not c.get("is_narrator")]
    hero = chars[0]["name"] if chars else "our hero"
    place = parsed.get("place", "town")
    eff = parsed.get("effect") or st.get("rule", "")
    genre = st.get("genre", "comedy")
    titles = [st.get("title") or "Untitled", f"POV: you live in a {place} where {eff}"[:90], f"{hero} had ONE normal day planned…"]
    hooks = [f"Nobody warned {hero} about this {place}.", f"Wait for what happens when {parsed.get('trigger') or 'the rule kicks in'}…",
             f"This {place} has exactly one rule — and it's insane."]
    from ..render import looks
    look = looks.get((project.get("options") or {}).get("art_style"))
    tags = [*look.tags, "#storytime", "#shorts", "#fyp", "#animation", f"#{genre}"] + [f"#{m}" for m in (st.get("motifs") or [])[:2]]
    return {"alt_hooks": hooks, "titles": titles,
            "description": f"{st.get('logline') or st.get('premise', '')} {st.get('comment_bait', '')}".strip()[:220],
            "hashtags": list(dict.fromkeys(tags))[:10],
            "pinned_comment": st.get("comment_bait") or "What would YOU do in this story? Tell me below!"}


def evaluate(llm, project: dict) -> dict:
    method = "heuristic"
    pack: dict = {}
    notes: dict = {}
    if llm.offline:
        crit = _score_heuristic(project)
        pack = _packaging_offline(project)
    else:
        raw = llm_engine.evaluate(llm, project)
        crit = {k: int(S.clamp((raw.get("criteria") or {}).get(k), 0, 100, 60)) for k in WEIGHTS}
        pack = {k: raw.get(k) for k in ("alt_hooks", "titles", "description", "hashtags", "pinned_comment")}
        fallback = _packaging_offline(project)
        for k, v in fallback.items():
            if not pack.get(k):
                pack[k] = v
        notes = {"strengths": raw.get("strengths") or [], "weaknesses": raw.get("weaknesses") or [], "improvements": raw.get("improvements") or []}
        method = "llm"
    overall = int(round(sum(crit[k] * w for k, w in WEIGHTS.items())))
    weak = [k for k, v in sorted(crit.items(), key=lambda kv: kv[1]) if v < 65][:4]
    improvements = notes.get("improvements") or [f"{LABELS[k]}: {FIX[k]}" for k in weak]
    return {
        "overall": overall, "criteria": crit, "labels": LABELS, "method": method,
        "strengths": notes.get("strengths") or [f"{LABELS[k]} is solid ({v}/100)" for k, v in crit.items() if v >= 75][:3],
        "weaknesses": notes.get("weaknesses") or [f"{LABELS[k]} is weak ({crit[k]}/100)" for k in weak],
        "improvements": improvements,
        "alt_hooks": (pack.get("alt_hooks") or [])[:3], "titles": (pack.get("titles") or [])[:3],
        "description": pack.get("description") or "", "hashtags": pack.get("hashtags") or [],
        "pinned_comment": pack.get("pinned_comment") or "",
        "disclaimer": ("This is a retention-oriented estimate of story craft. No score can predict or guarantee views or virality."
                       + (" Scores here are transparent heuristics measured from the script; connect an LLM for a deeper critique." if method == "heuristic" else "")),
    }
