"""Shared vocabulary + normalisers.

Every engine (LLM-backed or offline) must hand back data that passes through the
normalisers here. That is what keeps the renderer safe: whatever a model invents,
the renderer only ever sees values from the enumerations below.
"""
from __future__ import annotations

import re
from typing import Any

from ..render import looks

GENRES = ["comedy", "mystery", "horror", "adventure", "drama", "fantasy", "everyday"]
GENRE_LABELS = {"everyday": "Unexpected everyday situation"}
TONES = ["silly", "wholesome", "suspenseful", "spooky", "dramatic", "absurd", "heartwarming", "chaotic"]
AUDIENCES = ["kids", "teens", "everyone"]
LENGTHS = {"short": 4, "standard": 6, "long": 9}          # default scene counts
DURATIONS = [15, 30, 45, 60, 90]

LOCATION_KINDS = ["town_street", "town_square", "school", "house", "shop", "park", "hospital", "city", "fantasy", "forest"]
TIMES_OF_DAY = ["day", "sunset", "night", "dawn"]
SCENE_KINDS = ["hook", "intro", "rule", "escalation", "twist", "ending", "other"]
ROLES = ["hero", "sidekick", "villain", "bystander"]

CAMERA_SHOTS = ["wide", "medium", "close", "extreme_close", "low_angle", "over_shoulder"]
CAMERA_MOVES = ["static", "push_in", "pull_out", "pan_left", "pan_right", "shake", "whip"]
EMOTIONS = ["neutral", "happy", "excited", "sad", "angry", "scared", "surprised", "confused", "smug", "worried"]
DELIVERIES = ["natural", "funny", "dramatic", "excited", "scared", "sad", "angry", "whisper", "deadpan"]
ANIMATIONS = ["idle", "walk", "run", "jump", "wave", "point", "dance", "shake", "faint", "spin", "shrink", "grow",
              "transform", "facepalm", "celebrate", "sneak", "vanish", "appear", "laugh"]
FORMS = ["cat", "dog", "frog", "pig", "bunny", "chicken", "bear", "duck"]
EFFECTS = ["shake", "flash", "poof", "sparkles", "color_shift", "exclaim", "question", "spotlight", "rain",
           "confetti", "vignette", "dark"]
TRANSITIONS = ["cut", "flash", "slide", "circle", "dissolve", "fade"]
MUSIC_MOODS = ["upbeat", "mysterious", "spooky", "epic", "calm", "funky", "tense", "silly"]
SFX_NAMES = ["pop", "whoosh", "boing", "ding", "buzzer", "sparkle", "poof", "thud", "gasp", "sting", "drone",
             "tick", "chime", "creak", "scratch", "sad_trombone", "transform", "explosion", "heartbeat", "alarm",
             "crowd_gasp", "rumble", "cheer", "laugh_pop", "wow", "bonk", "zap", "footsteps"]
HAIR_STYLES = ["bald", "short", "spiky", "long", "bun", "pigtails", "mohawk", "curly", "bob"]
ACCESSORIES = ["none", "glasses", "sunglasses", "cap", "beanie", "crown", "headband", "bowtie", "tie", "scarf",
               "cape", "backpack", "cat_ears", "bunny_ears", "top_hat", "bandana"]
EYES = ["dot", "round", "sleepy", "sparkle"]
SHIRT_PATTERNS = ["none", "stripes", "star", "zigzag", "pocket", "heart"]
AGE_LOOKS = ["kid", "teen", "adult", "elder"]
BUILDS = ["slim", "normal", "chunky"]
GENDERS = ["female", "male", "neutral"]

NARRATOR_ID = "narrator"


# ------------------------------------------------------------------ primitives
def pick(value: Any, allowed: list[str], default: str) -> str:
    if isinstance(value, str):
        v = value.strip().lower().replace(" ", "_").replace("-", "_")
        if v in allowed:
            return v
        for a in allowed:  # tolerant match: "close-up" -> "close"
            if v.startswith(a) or a.startswith(v) and len(v) >= 3:
                return a
    return default


def pick_list(values: Any, allowed: list[str], limit: int = 6) -> list[str]:
    out: list[str] = []
    for v in values or []:
        if isinstance(v, dict):
            v = v.get("name") or v.get("effect")
        p = pick(v, allowed, "")
        if p and p not in out:
            out.append(p)
    return out[:limit]


_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def hex_color(value: Any, default: str) -> str:
    if isinstance(value, str):
        m = _HEX.match(value.strip())
        if m:
            return "#" + m.group(1).lower()
        m3 = re.match(r"^#?([0-9a-fA-F]{3})$", value.strip())
        if m3:
            return "#" + "".join(c * 2 for c in m3.group(1)).lower()
    return default


def clamp(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def text(value: Any, default: str = "", limit: int = 600) -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s[:limit] if s else default


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "x"


# ------------------------------------------------------------------ options
def normalize_options(raw: dict | None) -> dict:
    raw = raw or {}
    return {
        "genre": pick(raw.get("genre"), GENRES, "comedy"),
        "tone": pick(raw.get("tone"), TONES, "silly"),
        "length": pick(raw.get("length"), list(LENGTHS), "standard"),
        "num_characters": int(clamp(raw.get("num_characters"), 1, 5, 3)),
        "setting": text(raw.get("setting"), "", 80),
        "humour": int(clamp(raw.get("humour"), 0, 100, 70)),
        "twist": int(clamp(raw.get("twist"), 0, 100, 60)),
        "audience": pick(raw.get("audience"), AUDIENCES, "everyone"),
        "duration": int(clamp(raw.get("duration"), 10, 120, 30)),
        "style_id": text(raw.get("style_id"), "", 40),
        "art_style": pick(raw.get("art_style"), looks.IDS, looks.DEFAULT),
        "narrator": bool(raw.get("narrator", True)),
        "seed": raw.get("seed"),
    }


# ------------------------------------------------------------------ story
def normalize_story(raw: dict, options: dict, source: str = "llm") -> dict:
    raw = raw or {}
    title = text(raw.get("title"), "Untitled Story", 90)
    rule = text(raw.get("rule") or raw.get("premise"), "", 300)
    return {
        "title": title,
        "logline": text(raw.get("logline"), rule, 300),
        "premise": text(raw.get("premise"), rule, 400),
        "rule": rule,
        "hook_line": text(raw.get("hook_line") or raw.get("hook"), "", 200),
        "twist": text(raw.get("twist"), "", 400),
        "ending": text(raw.get("ending"), "", 400),
        "comment_bait": text(raw.get("comment_bait"), "", 200),
        "genre": pick(raw.get("genre"), GENRES, options["genre"]),
        "tone": pick(raw.get("tone"), TONES, options["tone"]),
        "escalation_ideas": [text(x, "", 220) for x in (raw.get("escalation_ideas") or [])][:6],
        "cast_sketch": [x for x in (raw.get("cast_sketch") or raw.get("characters") or []) if isinstance(x, dict)][:6],
        "location_sketch": [x for x in (raw.get("location_sketch") or raw.get("locations") or []) if isinstance(x, dict)][:5],
        "why_it_works": text(raw.get("why_it_works"), "", 300),
        "motifs": [text(m, "", 24) for m in (raw.get("motifs") or [])][:6],
        "parsed": raw.get("parsed") if isinstance(raw.get("parsed"), dict) else {},
        "music_mood": pick(raw.get("music_mood"), MUSIC_MOODS, ""),
        "twist_kind": text(raw.get("twist_kind"), "", 20),
        "source": source,
        "locked": bool(raw.get("locked", False)),
    }


# ------------------------------------------------------------------ characters
_DEFAULT_SHIRTS = ["#ef476f", "#118ab2", "#06d6a0", "#ffd166", "#8338ec", "#fb5607", "#3a86ff", "#ff006e"]
_DEFAULT_PANTS = ["#264653", "#3d405b", "#2b2d42", "#355070", "#4a4e69"]
_SKINS = ["#f5c9a0", "#e0ac69", "#c68642", "#8d5524", "#ffdbac", "#f1c27d"]


def normalize_character(raw: dict, idx: int, taken_names: set[str]) -> dict:
    raw = raw or {}
    name = text(raw.get("name"), f"Character {idx + 1}", 30)
    base = name
    n = 2
    while name.lower() in taken_names:
        name = f"{base} {n}"
        n += 1
    taken_names.add(name.lower())
    app = raw.get("appearance") if isinstance(raw.get("appearance"), dict) else raw
    voice = raw.get("voice") if isinstance(raw.get("voice"), dict) else {}
    hair = app.get("hair") if isinstance(app.get("hair"), dict) else {}
    shirt = app.get("shirt") if isinstance(app.get("shirt"), dict) else {}
    role = pick(raw.get("role"), ROLES, "hero" if idx == 0 else "sidekick")
    age = pick(raw.get("age_look") or app.get("age_look"), AGE_LOOKS, "teen")
    build = pick(app.get("build"), BUILDS, "normal")
    ch = {
        "id": f"c{idx + 1}",
        "name": name,
        "role": role,
        "personality": text(raw.get("personality"), "curious and brave", 240),
        "age_look": age,
        "build": build,
        "height": clamp(app.get("height"), 0.8, 1.2, {"kid": 0.86, "teen": 0.95, "adult": 1.05, "elder": 0.98}[age]),
        "skin": hex_color(app.get("skin") or app.get("skin_color"), _SKINS[idx % len(_SKINS)]),
        "hair_style": pick(hair.get("style") or app.get("hair_style"), HAIR_STYLES, "short"),
        "hair_color": hex_color(hair.get("color") or app.get("hair_color"), "#3b2a1a"),
        "shirt_color": hex_color(shirt.get("color") or app.get("shirt_color"), _DEFAULT_SHIRTS[idx % len(_DEFAULT_SHIRTS)]),
        "shirt_pattern": pick(shirt.get("pattern") or app.get("shirt_pattern"), SHIRT_PATTERNS, "none"),
        "pants_color": hex_color(app.get("pants_color") or app.get("pants"), _DEFAULT_PANTS[idx % len(_DEFAULT_PANTS)]),
        "shoes_color": hex_color(app.get("shoes_color"), "#222222"),
        "accessory": pick(app.get("accessory"), ACCESSORIES, "none"),
        "accessory_color": hex_color(app.get("accessory_color"), "#ffd166"),
        "eyes": pick(app.get("eyes"), EYES, "dot"),
        "clothing": text(raw.get("clothing") or app.get("clothing"), "", 200),
        "appearance_text": text(raw.get("appearance_text") or raw.get("description") or (app.get("description") if isinstance(app.get("description"), str) else ""), "", 400),
        "signature_expression": pick(raw.get("signature_expression"), EMOTIONS, "neutral"),
        "expressions": pick_list(raw.get("expressions"), EMOTIONS, 10) or ["neutral", "happy", "surprised", "scared", "angry"],
        "animation_notes": text(raw.get("animation_notes"), "", 240),
        "voice": {
            "gender": pick(voice.get("gender"), GENDERS, "neutral"),
            "pitch": clamp(voice.get("pitch"), -1, 1, 0.0),
            "speed": clamp(voice.get("speed"), 0.7, 1.4, 1.0),
            "accent": text(voice.get("accent"), "American", 40),
            "description": text(voice.get("description"), "", 160),
            "default_delivery": pick(voice.get("default_delivery"), DELIVERIES, "natural"),
            "voice_id": text(voice.get("voice_id"), "", 80),
            "provider": text(voice.get("provider"), "", 30),
        },
    }
    ch["visual_prompt"] = text(raw.get("visual_prompt"), "", 600) or build_visual_prompt(ch)
    return ch


def build_visual_prompt(ch: dict) -> str:
    """Canonical, deterministic description reused verbatim in every AI image prompt."""
    acc = "" if ch["accessory"] == "none" else f", wearing {ch['accessory'].replace('_', ' ')}"
    return (f"{ch['name']}: a stylised blocky 3D toy-like character ({ch['age_look']}, {ch['build']} build), "
            f"skin {ch['skin']}, {ch['hair_style']} hair {ch['hair_color']}, {ch['shirt_pattern']} shirt {ch['shirt_color']}, "
            f"pants {ch['pants_color']}, shoes {ch['shoes_color']}{acc}, {ch['eyes']} eyes")


def narrator_character() -> dict:
    return {
        "id": NARRATOR_ID, "name": "Narrator", "role": "narrator", "is_narrator": True,
        "personality": "warm, playful storyteller", "age_look": "adult",
        "voice": {"gender": "neutral", "pitch": -0.2, "speed": 1.05, "accent": "American",
                  "description": "friendly, punchy storyteller", "default_delivery": "natural",
                  "voice_id": "", "provider": ""},
    }


def normalize_characters(raw_list: list, options: dict) -> list[dict]:
    chars: list[dict] = []
    taken: set[str] = set()
    for i, raw in enumerate(raw_list or []):
        if isinstance(raw, dict) and not raw.get("is_narrator") and slug(str(raw.get("name", ""))) != "narrator":
            chars.append(normalize_character(raw, len(chars), taken))
    chars = chars[: max(options.get("num_characters", 3), 1) + 1]
    if options.get("narrator", True):
        chars.append(narrator_character())
    return chars


# ------------------------------------------------------------------ worlds
_PALETTES = {
    "day": {"sky_top": "#5ec2ff", "sky_bottom": "#d9f3ff", "ground": "#7bc96f", "accent": "#ffd166", "building": "#f4a261"},
    "sunset": {"sky_top": "#ff7b54", "sky_bottom": "#ffd9a0", "ground": "#6aa84f", "accent": "#ff5d73", "building": "#e76f51"},
    "night": {"sky_top": "#0b1033", "sky_bottom": "#3b3f8f", "ground": "#2f6f4f", "accent": "#ffe66d", "building": "#5a5fa8"},
    "dawn": {"sky_top": "#9d7bd8", "sky_bottom": "#ffd1dc", "ground": "#8bcf86", "accent": "#fff1a8", "building": "#cdb4db"},
}


def default_palette(time_of_day: str) -> dict:
    return dict(_PALETTES.get(time_of_day, _PALETTES["day"]))


def normalize_world(raw: dict, idx: int) -> dict:
    raw = raw or {}
    tod = pick(raw.get("time_of_day"), TIMES_OF_DAY, "day")
    pal_raw = raw.get("palette") if isinstance(raw.get("palette"), dict) else {}
    base = default_palette(tod)
    palette = {k: hex_color(pal_raw.get(k), v) for k, v in base.items()}
    kind = pick(raw.get("kind") or raw.get("type"), LOCATION_KINDS, "town_street")
    return {
        "id": f"w{idx + 1}",
        "name": text(raw.get("name"), f"Location {idx + 1}", 40),
        "kind": kind,
        "description": text(raw.get("description"), "", 400),
        "time_of_day": tod,
        "palette": palette,
        "props": [text(p, "", 30) for p in (raw.get("props") or [])][:8],
        "landmark": text(raw.get("landmark"), "", 40),
        "visual_prompt": text(raw.get("visual_prompt"), "", 500),
    }


def normalize_worlds(raw_list: list, limit: int = 5) -> list[dict]:
    worlds = [normalize_world(r, i) for i, r in enumerate([r for r in (raw_list or []) if isinstance(r, dict)][:limit])]
    if not worlds:
        worlds = [normalize_world({"name": "Main street", "kind": "town_street"}, 0)]
    return worlds


# ------------------------------------------------------------------ scenes
def _resolve_char(ref: Any, chars: list[dict], default: str | None) -> str | None:
    if ref is None:
        return default
    ref_s = str(ref).strip().lower()
    for c in chars:
        if c["id"].lower() == ref_s or c["name"].lower() == ref_s or slug(c["name"]) == slug(ref_s):
            return c["id"]
    for c in chars:  # first-name match: "Milo" vs "Milo Park"
        if ref_s and (ref_s in c["name"].lower() or c["name"].lower().split(" ")[0] == ref_s.split(" ")[0]):
            return c["id"]
    return default


def normalize_scene(raw: dict, idx: int, chars: list[dict], worlds: list[dict], options: dict) -> dict:
    raw = raw or {}
    onscreen = [c for c in chars if not c.get("is_narrator")]
    has_narrator = any(c.get("is_narrator") for c in chars)
    fallback_speaker = NARRATOR_ID if has_narrator else (onscreen[0]["id"] if onscreen else None)
    world_ids = [w["id"] for w in worlds]
    loc = raw.get("location_id") or raw.get("location")
    location_id = loc if loc in world_ids else next((w["id"] for w in worlds if str(loc).lower() == w["name"].lower()), worlds[0]["id"])

    cast: list[str] = []
    for ref in raw.get("characters") or []:
        cid = _resolve_char(ref, onscreen, None)
        if cid and cid not in cast:
            cast.append(cid)

    dialogue = []
    for j, d in enumerate(raw.get("dialogue") or []):
        if not isinstance(d, dict):
            continue
        line = text(d.get("text") or d.get("line"), "", 220)
        if not line:
            continue
        sp_raw = d.get("character_id") or d.get("speaker") or d.get("character")
        if str(sp_raw).strip().lower() in ("narrator", "voiceover", "vo"):
            sp = NARRATOR_ID if has_narrator else fallback_speaker
        else:
            sp = _resolve_char(sp_raw, onscreen, fallback_speaker)
        if sp and sp != NARRATOR_ID and sp not in cast:
            cast.append(sp)
        dialogue.append({
            "id": f"s{idx + 1}_d{j + 1}",
            "character_id": sp,
            "text": line,
            "emotion": pick(d.get("emotion"), EMOTIONS, "neutral"),
            "delivery": pick(d.get("delivery"), DELIVERIES, "natural"),
        })

    actions = []
    for a in raw.get("actions") or []:
        if not isinstance(a, dict):
            continue
        cid = _resolve_char(a.get("character_id") or a.get("character"), onscreen, None)
        if not cid:
            continue
        if cid not in cast:
            cast.append(cid)
        form_raw = str(a.get("form") or "").strip().lower()
        form = "human" if form_raw in ("human", "normal", "original", "person", "back") else pick(a.get("form"), FORMS, "")
        actions.append({
            "character_id": cid,
            "animation": pick(a.get("animation"), ANIMATIONS, "idle"),
            "at": clamp(a.get("at"), 0, 30, 0.0),
            "note": text(a.get("note"), "", 160),
            "form": form,
        })
    if not cast and onscreen:
        cast = [onscreen[0]["id"]]

    cam = raw.get("camera") if isinstance(raw.get("camera"), dict) else {"note": raw.get("camera")}
    env = raw.get("environment") if isinstance(raw.get("environment"), dict) else {"notes": raw.get("environment")}
    sfx = []
    for s in raw.get("sfx") or []:
        if isinstance(s, str):
            s = {"name": s}
        if isinstance(s, dict):
            nm = pick(s.get("name"), SFX_NAMES, "")
            if nm:
                sfx.append({"name": nm, "at": clamp(s.get("at"), 0, 30, 0.0), "note": text(s.get("note"), "", 80)})
    kind = pick(raw.get("kind"), SCENE_KINDS, "other")
    default_trans = {"hook": "cut", "twist": "flash", "ending": "fade"}.get(kind, "slide" if idx % 2 else "circle")
    return {
        "id": f"s{idx + 1}",
        "index": idx,
        "kind": kind,
        "title": text(raw.get("title"), f"Scene {idx + 1}", 60),
        "description": text(raw.get("description"), "", 500),
        "location_id": location_id,
        "characters": cast[:4],
        "actions": actions[:8],
        "dialogue": dialogue[:6],
        "camera": {"shot": pick(cam.get("shot"), CAMERA_SHOTS, "medium"),
                   "move": pick(cam.get("move"), CAMERA_MOVES, "push_in"),
                   "note": text(cam.get("note"), "", 160)},
        "environment": {"time_of_day": pick(env.get("time_of_day"), TIMES_OF_DAY, ""),
                        "notes": text(env.get("notes"), "", 200),
                        "crowd": int(clamp(env.get("crowd"), 0, 8, 0)),
                        "crowd_form": pick(env.get("crowd_form"), FORMS, "")},
        "emotion": pick(raw.get("emotion"), EMOTIONS, "neutral"),
        "duration": clamp(raw.get("duration"), 1.5, 14.0, 5.0),
        "voiceover_notes": text(raw.get("voiceover_notes"), "", 200),
        "sfx": sfx[:6],
        "effects": pick_list(raw.get("effects"), EFFECTS, 4),
        "on_screen_text": text(raw.get("on_screen_text"), "", 30),
        "music_mood": pick(raw.get("music_mood"), MUSIC_MOODS, ""),
        "transition": pick(raw.get("transition"), TRANSITIONS, default_trans),
        "visual_prompt": text(raw.get("visual_prompt"), "", 700),
    }


def normalize_scenes(raw_list: list, chars: list[dict], worlds: list[dict], options: dict, fit: bool = True) -> list[dict]:
    scenes = [normalize_scene(r, i, chars, worlds, options)
              for i, r in enumerate([r for r in (raw_list or []) if isinstance(r, dict)][:14])]
    if scenes:
        scenes[0]["kind"] = "hook"
        scenes[0]["transition"] = "cut"
        if fit:
            scenes[0]["duration"] = min(scenes[0]["duration"], 5.0)
            fit_durations(scenes, options.get("duration", 30))
    return scenes


def fit_durations(scenes: list[dict], target: float) -> None:
    """Scale planned scene durations so they sum to the requested video length.
    (Actual durations are later stretched to fit the generated voiceover.)"""
    total = sum(s["duration"] for s in scenes) or 1.0
    k = target / total
    for s in scenes:
        s["duration"] = round(max(1.5, min(16.0, s["duration"] * k)), 2)
    if scenes and scenes[0]["duration"] > 4.0:   # the hook must land inside ~2-4 seconds of runtime
        scenes[0]["duration"] = 4.0


def scene_word_count(scene: dict) -> int:
    return sum(len(d["text"].split()) for d in scene.get("dialogue", []))
