"""LLM-backed engines: prompts + schema contracts. All output goes through schemas.normalize_*."""
from __future__ import annotations

import json

from . import schemas as S

SYSTEM = """You are the head writer and director of an automated short-form video studio. You make ORIGINAL, stylised, blocky 3D "Roblox-inspired" animated stories for TikTok, YouTube Shorts and Instagram Reels.

Hard rules:
- 100% original. Never use existing characters, brands, franchises, songs, real people, or copy a specific creator's story. References only inform general visual direction.
- Age-appropriate for the stated audience. No gore, sexual content, hate, self-harm or dangerous imitation. Horror means spooky, never graphic.
- Every story needs: a powerful hook in the first 1-2 seconds, a simple premise a viewer understands instantly, a strange/funny/unexpected/intriguing central idea, escalating tension, a genuinely surprising twist, and a satisfying ending that makes people comment or rewatch.
- Fresh ideas only. Avoid the example premises you are shown and anything similar to the "avoid" list.
- Never promise or imply guaranteed virality.
- Reply with ONLY valid JSON that matches the schema in the user message. Use only the allowed values for enumerated fields."""


def _style_block(style: dict | None) -> str:
    if not style:
        return ""
    bits = [f"STYLE PROFILE '{style.get('name', '')}' (derived from the user's reference material; use for general direction only, never reproduce copyrighted characters or footage):"]
    if style.get("directive"):
        bits.append(style["directive"])
    if style.get("pacing"):
        bits.append(f"Pacing: {json.dumps(style['pacing'])}")
    if style.get("mood"):
        bits.append(f"Mood: {style['mood']}")
    return "\n".join(bits) + "\n\n"


def _opts_block(o: dict) -> str:
    return (f"Genre: {o['genre']}\nTone: {o['tone']}\nTarget audience: {o['audience']}\nHumour level (0-100): {o['humour']}\n"
            f"Twist intensity (0-100): {o['twist']}\nVideo duration: {o['duration']} seconds\n"
            f"Number of on-screen characters: {o['num_characters']}\nPreferred setting: {o['setting'] or 'any (surprise me)'}\n")


# ------------------------------------------------------------------ concepts
def concepts(llm, idea: str, options: dict, n: int, style: dict | None, avoid: list[str]) -> list[dict]:
    schema = """{"concepts":[{
  "title": "catchy title, max 8 words",
  "logline": "one sentence",
  "premise": "2 sentences a viewer gets instantly",
  "rule": "the strange central rule/event in one sentence",
  "hook_line": "the very first line/moment (first 1-2 seconds)",
  "escalation_ideas": ["3-5 ways it gets more ridiculous/dangerous/interesting"],
  "twist": "the unexpected development",
  "ending": "the satisfying payoff",
  "comment_bait": "one closing line that makes viewers comment or rewatch",
  "genre": "one of %s", "tone": "one of %s",
  "motifs": ["1-3 visual motifs, one word each"],
  "music_mood": "one of %s",
  "cast_sketch": [{"name":"","role":"hero|sidekick|villain|bystander","personality":""}],
  "location_sketch": [{"name":"","kind":"one of %s"}],
  "originality_score": 1-10
}]}""" % (S.GENRES, S.TONES, S.MUSIC_MOODS, S.LOCATION_KINDS)
    user = (f"{_style_block(style)}Create {n} DIFFERENT story concepts for a {options['duration']}-second vertical video.\n"
            f"{_opts_block(options)}\n"
            + (f"The user's idea (build every concept on it, varying cast, twist and ending): \"{idea}\"\n" if idea.strip()
               else "No idea supplied: invent surprising premises of your own.\n")
            + ("Avoid premises similar to:\n- " + "\n- ".join(avoid[:20]) + "\n" if avoid else "")
            + "Illustration of the DIRECTION only (do NOT reuse): a town where sneezes change the colour of everything; a world where nobody can tell the truth.\n\n"
            + f"Schema:\n{schema}")
    data = llm.generate_json(SYSTEM, user, temperature=1.0, max_tokens=6000)
    items = data.get("concepts") if isinstance(data, dict) else data
    out = []
    for raw in items or []:
        st = S.normalize_story(raw, options, source="llm")
        st["originality"] = int(S.clamp(raw.get("originality_score"), 1, 10, 6))
        out.append(st)
    if not out:
        raise ValueError("The model returned no story concepts.")
    return sorted(out, key=lambda s: -s["originality"])


# ------------------------------------------------------------------ characters
def characters(llm, story: dict, options: dict, style: dict | None) -> list[dict]:
    schema = """{"characters":[{
  "name": "unique short name", "role": "hero|sidekick|villain|bystander", "age_look": "%s",
  "personality": "one line", "clothing": "one line", "signature_expression": "one of %s",
  "expressions": ["3-6 of %s"], "animation_notes": "how they move",
  "appearance": {"build":"%s","height":0.8-1.2,"skin":"#hex","hair":{"style":"%s","color":"#hex"},
     "shirt":{"color":"#hex","pattern":"%s"},"pants_color":"#hex","shoes_color":"#hex",
     "accessory":"%s","accessory_color":"#hex","eyes":"%s"},
  "voice": {"gender":"female|male|neutral","pitch":-1..1,"speed":0.8-1.3,"accent":"e.g. American, British, Australian, Scottish",
     "description":"voice in a few words","default_delivery":"one of %s"}
}]}""" % (S.AGE_LOOKS, S.EMOTIONS, S.EMOTIONS, S.BUILDS, S.HAIR_STYLES, S.SHIRT_PATTERNS, S.ACCESSORIES, S.EYES, S.DELIVERIES)
    user = (f"{_style_block(style)}Design the cast for this story as simple, colourful, blocky Roblox-inspired characters.\n"
            f"Create exactly {options['num_characters']} on-screen characters (do not include the narrator).\n"
            "Make them visually distinct at a glance (different colours, hair, accessories, silhouettes) with distinct voices. "
            "These designs are used verbatim in every scene, so choose final colours now.\n\n"
            f"STORY: {json.dumps({k: story.get(k) for k in ('title', 'premise', 'rule', 'twist', 'ending', 'genre', 'tone')})}\n"
            f"CAST SKETCH FROM THE CONCEPT: {json.dumps(story.get('cast_sketch') or [])}\n"
            f"Audience: {options['audience']}\n\nSchema:\n{schema}")
    data = llm.generate_json(SYSTEM, user, temperature=0.8, max_tokens=5000)
    return data.get("characters") if isinstance(data, dict) else data


# ------------------------------------------------------------------ worlds
def worlds(llm, story: dict, options: dict, style: dict | None) -> list[dict]:
    schema = """{"locations":[{"name":"","kind":"one of %s","time_of_day":"one of %s",
  "description":"what the place looks like","props":["up to 6 simple props e.g. lamp, tree, bench, fountain, clock_tower"],
  "landmark":"optional single landmark e.g. clock_tower","palette":{"sky_top":"#hex","sky_bottom":"#hex","ground":"#hex","accent":"#hex","building":"#hex"},
  "visual_prompt":"one-sentence prompt for an image model, stylised blocky 3D toy look"}]}""" % (S.LOCATION_KINDS, S.TIMES_OF_DAY)
    user = (f"{_style_block(style)}Design the 2-4 locations this story needs (reuse locations across scenes for continuity).\n"
            f"STORY: {json.dumps({k: story.get(k) for k in ('title', 'premise', 'rule', 'twist', 'ending', 'genre', 'tone')})}\n"
            f"LOCATION SKETCH: {json.dumps(story.get('location_sketch') or [])}\nPreferred setting: {options['setting'] or 'any'}\n\nSchema:\n{schema}")
    data = llm.generate_json(SYSTEM, user, temperature=0.8, max_tokens=3000)
    return data.get("locations") if isinstance(data, dict) else data


# ------------------------------------------------------------------ script
def script(llm, story: dict, chars: list[dict], worlds_: list[dict], options: dict, style: dict | None,
           feedback: str = "") -> list[dict]:
    n_default = S.LENGTHS[options["length"]]
    cast = [{"id": c["id"], "name": c["name"], "role": c.get("role"), "personality": c.get("personality")} for c in chars if not c.get("is_narrator")]
    locs = [{"id": w["id"], "name": w["name"], "kind": w["kind"]} for w in worlds_]
    schema = """{"scenes":[{
  "kind": "hook|intro|rule|escalation|twist|ending",
  "title": "", "description": "what we see",
  "location_id": "one of the location ids", "characters": ["character ids visible on screen"],
  "actions": [{"character_id":"","animation":"one of %s","at":seconds,"note":"","form":"optional animal form: %s, or 'human' to revert"}],
  "dialogue": [{"character_id":"character id or 'narrator'","text":"max 18 words","emotion":"one of %s","delivery":"one of %s"}],
  "camera": {"shot":"one of %s","move":"one of %s","note":""},
  "environment": {"time_of_day":"one of %s","notes":"","crowd":0-8,"crowd_form":"optional animal form for background people"},
  "emotion": "one of %s", "duration": seconds,
  "voiceover_notes": "how the lines should be performed",
  "sfx": [{"name":"one of %s","at":seconds}],
  "effects": ["up to 3 of %s"], "on_screen_text": "optional 1-3 big words",
  "music_mood": "one of %s", "transition": "one of %s",
  "visual_prompt": "one-sentence image prompt incl. the characters' fixed looks"
}]}""" % (S.ANIMATIONS, S.FORMS, S.EMOTIONS, S.DELIVERIES, S.CAMERA_SHOTS, S.CAMERA_MOVES, S.TIMES_OF_DAY, S.EMOTIONS,
          S.SFX_NAMES, S.EFFECTS, S.MUSIC_MOODS, S.TRANSITIONS)
    words_budget = int(options["duration"] * 2.6)
    user = (f"{_style_block(style)}Write the shot-by-shot script for a {options['duration']}-second vertical video.\n"
            f"{_opts_block(options)}\n"
            f"STORY: {json.dumps({k: story.get(k) for k in ('title', 'logline', 'premise', 'rule', 'hook_line', 'escalation_ideas', 'twist', 'ending', 'comment_bait')})}\n"
            f"CAST: {json.dumps(cast)}\nLOCATIONS: {json.dumps(locs)}\n"
            f"The narrator is available as character_id 'narrator' (voice only).\n\n"
            "STRUCTURE (mandatory order): scene 1 HOOK (grab attention immediately, <=4 seconds, start mid-action, state the strange thing), "
            "then INTRODUCTION (hero + situation), THE RULE (the unusual event/problem), ESCALATION (increasingly ridiculous/dangerous/interesting; "
            f"you may use several scenes), THE TWIST (unexpected development), THE ENDING (satisfying payoff that invites comments or a rewatch). "
            f"Use about {n_default} scenes (more or fewer if the story needs it, between 4 and 10).\n"
            f"Total spoken words across the whole video: about {words_budget}. Scene durations must sum to about {options['duration']} seconds. "
            "Short punchy lines, natural speech, real jokes. Every scene must have visible action: use animations, camera and effects. "
            "Forms (animal transformations) do NOT carry over between scenes: restate `form` on a character's first action in every scene where they should still look like that animal. "
            "Keep each character's appearance exactly as designed (the renderer enforces it); put their fixed look into visual_prompt.\n"
            + (f"\nFEEDBACK TO APPLY FROM THE PREVIOUS DRAFT:\n{feedback}\n" if feedback else "")
            + f"\nSchema:\n{schema}")
    data = llm.generate_json(SYSTEM, user, temperature=0.9, max_tokens=9000)
    return data.get("scenes") if isinstance(data, dict) else data


# ------------------------------------------------------------------ evaluation
def evaluate(llm, project: dict) -> dict:
    scenes = []
    names = {c["id"]: c["name"] for c in project.get("characters", [])}
    for s in project.get("scenes", []):
        scenes.append({"kind": s["kind"], "duration": s["duration"], "lines": [f"{names.get(d['character_id'], 'Narrator')}: {d['text']}" for d in s["dialogue"]],
                       "effects": s["effects"], "animations": [a["animation"] for a in s["actions"]]})
    schema = """{"criteria":{"hook":0-100,"curiosity":0-100,"entertainment":0-100,"clarity":0-100,"pacing":0-100,"surprise":0-100,"ending":0-100,"replay":0-100},
 "strengths":["..."],"weaknesses":["..."],"improvements":["specific, actionable rewrite instructions"],
 "alt_hooks":["3 alternative opening lines"],"titles":["3 titles"],"description":"short caption","hashtags":["#..."],
 "pinned_comment":"a comment that drives replies"}"""
    user = ("Act as a ruthless short-form retention analyst. Score this story honestly (most stories deserve 55-80; reserve 90+ for exceptional work) "
            "on each criterion: hook = opening 1-2 seconds, curiosity = viewer wants to know what happens, entertainment, clarity = instantly understandable, "
            "pacing, surprise = twist quality, ending = satisfying payoff, replay = reason to rewatch/comment. Do NOT claim any video will go viral.\n"
            f"Target: {project.get('options', {}).get('audience', 'everyone')}, {project.get('options', {}).get('duration', 30)} seconds.\n"
            f"STORY: {json.dumps({k: (project.get('story') or {}).get(k) for k in ('title', 'premise', 'rule', 'twist', 'ending')})}\n"
            f"SCRIPT: {json.dumps(scenes)}\n\nSchema:\n{schema}")
    return llm.generate_json(SYSTEM, user, temperature=0.4, max_tokens=3000)


# ------------------------------------------------------------------ reference style (vision)
def analyze_reference(llm, images: list, metrics: dict) -> dict:
    schema = """{"visual_style":"","character_appearance":"general description only, no named characters","camera_angles":"","scene_composition":"",
 "editing_style":"","subtitle_style":"position, size, colours, animation","pacing":"","story_structure":"",
 "mood":"2-4 words","directive":"3-5 sentences instructing a writer/art director how to emulate the GENERAL style with 100% original characters and plots"}"""
    user = ("These frames are from a reference video/image supplied by the user. Analyse the general visual and editing style only. "
            "Do not name or describe any copyrighted character in a way that could be used to reproduce it; stay at the level of style.\n"
            f"Measured metrics: {json.dumps(metrics)}\n\nSchema:\n{schema}")
    return llm.generate_json("You are a film-style analyst. Reply with only JSON.", user, images=images, temperature=0.3, max_tokens=2000)
