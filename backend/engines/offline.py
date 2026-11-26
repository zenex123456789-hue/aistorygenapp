"""Offline story engine (no LLM).

A combinatorial generator: it parses the user's idea into place / effect / trigger,
detects motifs (animals, colours, vanishing...) that drive real visuals, then fills
a six-beat structure (hook, intro, rule, escalation, twist, ending) from banks of
line templates. Output is far less original than an LLM's, but it is real, varies
on every run, and exercises the full pipeline with zero API keys.
"""
from __future__ import annotations

import random
import re

from . import schemas as S

PLACE_WORDS = ["town", "city", "village", "school", "house", "island", "neighbourhood", "neighborhood", "kingdom",
               "world", "street", "hospital", "park", "shop", "store", "mall", "planet", "school", "city"]
PLACE_KIND = {"town": "town_street", "city": "city", "village": "town_street", "school": "school", "house": "house",
              "island": "park", "neighbourhood": "town_street", "neighborhood": "town_street", "kingdom": "fantasy",
              "world": "fantasy", "street": "town_street", "hospital": "hospital", "park": "park", "shop": "shop",
              "store": "shop", "mall": "shop", "planet": "fantasy"}

TRIGGERS = ["someone sneezes", "someone yawns", "the clock strikes twelve", "someone tells a lie", "it starts to rain",
            "someone laughs out loud", "the school bell rings", "someone says 'please'", "a door slams",
            "someone hiccups", "a phone rings", "someone steps on a crack", "someone says the word 'banana'"]
EFFECTS = [  # (effect text, motif)
    ("another person turns into a chicken", "animal"), ("everyone turns into a different animal", "animal"),
    ("the whole street changes colour", "color"), ("everything turns bright pink", "color"),
    ("somebody vanishes into thin air", "vanish"), ("one random neighbour disappears", "vanish"),
    ("everyone has to dance until the song ends", "dance"), ("everybody shrinks to the size of a mouse", "shrink"),
    ("everyone swaps places with a stranger", "swap"), ("the ground turns bouncy", "bounce"),
    ("everyone must tell the truth", "truth"), ("it starts raining confetti", "confetti"),
]
HERO = ["Milo", "Zara", "Finn", "Luna", "Otto", "Nina", "Jax", "Poppy", "Ziggy", "Remy", "Tilly", "Bo"]
SIDE = ["Pip", "Dot", "Gus", "Wren", "Bix", "Fern", "Moe", "Kit"]
FOIL = ["Mayor Bumble", "Principal Crumb", "Officer Doodle", "Grandma Gigi", "Captain Noodle", "Mr. Wobble", "Dr. Fizz"]
HAIR_COL = ["#3b2a1a", "#222222", "#b5651d", "#d4a017", "#c0392b", "#7b4ba8", "#2ec4b6"]
SHIRTS = ["#ef476f", "#118ab2", "#06d6a0", "#ffd166", "#8338ec", "#fb5607", "#3a86ff", "#ff006e"]
SKINS = ["#f5c9a0", "#e0ac69", "#c68642", "#8d5524", "#ffdbac", "#f1c27d"]
GOALS = ["free snacks", "my own parade", "a much bigger hat", "a day off", "my face on every sign", "unlimited pizza"]
GENRE_FLAVOR = {
    "comedy": ("silly", "day"), "mystery": ("mysterious", "sunset"), "horror": ("spooky", "night"),
    "adventure": ("epic", "day"), "drama": ("calm", "sunset"), "fantasy": ("upbeat", "dawn"), "everyday": ("funky", "day"),
}
MOTIF_RE = {
    "animal": r"animal|\bcat\b|\bdog\b|frog|\bpig\b|bunny|rabbit|chicken|\bbear\b|\bduck\b|turns? into",
    "color": r"colou?r|rainbow|\bpink\b|\bpaint",
    "vanish": r"disappear|vanish|invisible|teleport|thin air",
    "clock": r"clock|twelve|midnight|\bnoon\b|o.?clock",
    "dance": r"danc|\bsing|music",
    "shrink": r"shrink|\btiny\b|\bmouse\b|giant|\bgrow",
    "truth": r"truth|\blie\b|lying|honest",
    "confetti": r"confetti|party|balloon",
    "bounce": r"bounc|jump",
    "sneeze": r"sneez|yawn|hiccup|burp",
}
_STRIP = r"^(?:(?:please|create|make|write|generate|give me|me|a|an|the|funny|scary|spooky|wholesome|silly|dramatic|short|viral|roblox|animated|ai|story|stories|video|about|of|on|mystery|horror|adventure|tale|tales|comedy|fantasy|drama|cute|weird|strange|wild|new|original|kid-friendly|idea|concept)\b[\s,:\-]*)+"


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def parse_idea(idea: str, options: dict, rng: random.Random, avoid: list[str] | None = None) -> dict:
    idea = (idea or "").strip().rstrip(".!")
    parsed: dict = {"place": "", "rule": "", "effect": "", "trigger": "", "motifs": []}
    if idea:
        core = re.sub(_STRIP, "", idea, flags=re.I).strip() or idea
        core = re.sub(r"^(?:where|in which|that)\s+", "", core, flags=re.I)
        m = re.search(r"\b(?P<place>%s)\s+(?:where|in which|that|whose|with)\s+(?P<rule>.+)$" % "|".join(PLACE_WORDS), core, re.I)
        if m:
            parsed["place"], parsed["rule"] = m.group("place").lower(), m.group("rule")
        else:
            parsed["rule"] = core
            found = re.search(r"\b(%s)\b" % "|".join(PLACE_WORDS), idea, re.I)
            if found:
                parsed["place"] = found.group(1).lower()
        # "a kid who finds a door" -> "a kid finds a door" so it reads as a clause
        w = re.match(r"^(?P<n>(?!(?:a|an|the|my|his|her|their|our|everyone|nobody|no one|someone|every)\b)[a-z][a-z \-]{1,22}?)\s+who\s+(?P<v>.+)$", parsed["rule"], re.I)
        if w:
            parsed["rule"] = f"a {w.group('n')} {w.group('v')}"
        r = parsed["rule"]
        m1 = re.match(r"^(?P<effect>.+?)\s+(?:every time|whenever|each time)\s+(?P<trigger>.+)$", r, re.I)
        m2 = re.match(r"^(?:every time|whenever|each time)\s+(?P<trigger>.+?),\s*(?P<effect>.+)$", r, re.I)
        mm = m1 or m2
        if mm:
            parsed["effect"], parsed["trigger"] = mm.group("effect").strip(), mm.group("trigger").strip()
    else:
        for _ in range(30):
            trig = rng.choice(TRIGGERS)
            eff, motif = rng.choice(EFFECTS)
            rule = f"{eff} every time {trig}"
            if not any(rule[:25] in a for a in (avoid or [])):
                break
        parsed.update(rule=rule, effect=eff, trigger=trig, motifs=[motif])
        parsed["place"] = rng.choice(["town", "school", "city", "village", "neighbourhood"])
    blob = f"{idea} {parsed['rule']}".lower()
    for k, rx in MOTIF_RE.items():
        if re.search(rx, blob) and k not in parsed["motifs"]:
            parsed["motifs"].append(k)
    if not parsed["place"]:
        st = (options.get("setting") or "").lower()
        parsed["place"] = next((w for w in PLACE_WORDS if w in st), "town")
    if not parsed["effect"]:
        parsed["effect"] = parsed["rule"]
    return parsed


# ---------------------------------------------------------------- cast
def _hero_look(rng, idx, role, used_shirts):
    shirt = rng.choice([c for c in SHIRTS if c not in used_shirts] or SHIRTS)
    used_shirts.add(shirt)
    acc = {"hero": ["cap", "headband", "none", "beanie", "bandana"], "sidekick": ["glasses", "backpack", "bowtie", "none"],
           "villain": ["top_hat", "crown", "tie", "sunglasses"], "bystander": ["scarf", "none", "beanie"]}[role]
    return {
        "appearance": {
            "skin": rng.choice(SKINS), "hair": {"style": rng.choice(["short", "spiky", "bun", "curly", "bob", "pigtails", "mohawk"]), "color": rng.choice(HAIR_COL)},
            "shirt": {"color": shirt, "pattern": rng.choice(["none", "stripes", "star", "zigzag", "pocket", "heart"])},
            "pants_color": rng.choice(["#264653", "#3d405b", "#355070", "#4a4e69"]), "accessory": rng.choice(acc),
            "accessory_color": rng.choice(["#ffd166", "#ef476f", "#06d6a0", "#118ab2"]),
            "eyes": rng.choice(["dot", "round", "sparkle"]),
            "build": {"hero": "normal", "sidekick": "slim", "villain": "chunky", "bystander": "normal"}[role],
        }
    }


def make_cast(rng: random.Random, options: dict, parsed: dict) -> list[dict]:
    n = options.get("num_characters", 3)
    used: set = set()
    hero_n, side_n, foil_n = rng.choice(HERO), rng.choice(SIDE), rng.choice(FOIL)
    spec = [("hero", hero_n, "kid", "curious, brave and a bit too honest", "male" if rng.random() < .5 else "female", 0.25),
            ("sidekick", side_n, "teen", "nervous, loyal and secretly hilarious", "female" if rng.random() < .5 else "male", 0.35),
            ("villain", foil_n, "adult", "pompous, dramatic and easily panicked", "male" if rng.random() < .6 else "female", -0.35),
            ("bystander", rng.choice(["Gran Pearl", "Chef Tubs", "Coach Rex"]), "elder", "calm, wise, always snacking", "neutral", -0.1)]
    cast = []
    for role, name, age, pers, gender, pitch in spec[: max(1, min(n, 4))]:
        c = {"name": name, "role": role, "age_look": age, "personality": pers, **_hero_look(rng, len(cast), role, used)}
        c["voice"] = {"gender": gender, "pitch": pitch, "speed": 1.0, "accent": rng.choice(["American", "British", "Australian"]) if role != "hero" else "American",
                      "description": pers.split(",")[0], "default_delivery": "natural"}
        c["clothing"] = f"{c['appearance']['shirt']['pattern'] if c['appearance']['shirt']['pattern'] != 'none' else 'plain'} shirt, {c['appearance']['accessory'].replace('_', ' ')}"
        c["expressions"] = ["neutral", "happy", "surprised", "scared", "angry"]
        c["animation_notes"] = {"hero": "big reactions, jumps when excited", "sidekick": "fidgets, trembles when scared",
                                "villain": "puffs up, points a lot", "bystander": "slow, unbothered"}[role]
        cast.append(c)
    return cast


def make_worlds(rng, options, parsed, tod):
    kind = PLACE_KIND.get(parsed["place"], "town_street")
    place = _cap(parsed["place"])
    worlds = [{"name": f"{place} centre", "kind": kind, "time_of_day": tod, "description": f"The main stretch of the {parsed['place']}.",
               "props": ["lamp", "tree"], "landmark": "clock_tower" if "clock" in parsed["motifs"] else ""}]
    worlds.append({"name": f"{place} square", "kind": "town_square", "time_of_day": tod,
                   "description": "A busy square with a fountain.", "props": ["fountain", "bench"],
                   "landmark": "clock_tower" if "clock" in parsed["motifs"] else ""})
    worlds.append({"name": "Cosy house", "kind": "house", "time_of_day": "day" if tod != "night" else "night",
                   "description": "A cosy living room.", "props": ["window"]})
    if options.get("setting"):
        k = next((v for w, v in PLACE_KIND.items() if w in options["setting"].lower()), None)
        if k:
            worlds[0]["kind"] = k
    return worlds[: 3 if options.get("length") != "short" else 2]


# ---------------------------------------------------------------- concepts
_SMALL = {"a", "an", "the", "of", "to", "in", "on", "at", "and", "or", "for", "into", "every", "when", "that", "is", "it"}


def _title(t: str) -> str:
    words = t.split()
    return " ".join(w if (i and w.lower() in _SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def pick_twist(rng: random.Random, options: dict, cast: list[dict], hero: str, place: str) -> tuple[str, str]:
    """Decide the twist at concept time so the story card shows it (and the script then delivers it)."""
    on = [c for c in cast if not c.get("is_narrator")]
    tw = options["twist"]
    kinds = ["foil", "immune"] if tw < 35 else (["sidekick", "immune"] if tw < 70 else ["fourth", "sidekick"])
    tk = rng.choice(kinds)
    if tk == "foil" and len(on) < 3:
        tk = "immune"
    if tk == "sidekick" and len(on) < 2:
        tk = "immune"
    names = [c["name"] for c in on]
    text = {
        "sidekick": f"{names[1] if len(names) > 1 else 'The sidekick'} secretly caused the rule all along",
        "foil": f"{names[2] if len(names) > 2 else 'The mayor'} created the rule to fight boredom",
        "fourth": "The rule reaches the narrator too",
        "immune": f"{hero} is the reason the rule exists",
    }[tk]
    return tk, text


def make_concepts(idea: str, options: dict, n: int, rng: random.Random, avoid: list[str] | None = None) -> list[dict]:
    out = []
    mood, tod = GENRE_FLAVOR.get(options["genre"], ("silly", "day"))
    if options["tone"] == "spooky":
        mood, tod = "spooky", "night"
    if options["tone"] in ("wholesome", "heartwarming"):
        mood = "calm"
    for _ in range(n):
        crng = random.Random(rng.random())
        parsed = parse_idea(idea, options, crng, avoid)
        cast = make_cast(crng, options, parsed)
        hero = cast[0]["name"]
        place = _cap(parsed["place"])
        eff = _cap(parsed["effect"]) if len(parsed["effect"]) < 70 else _cap(parsed["rule"])[:70]
        title = crng.choice([f"The {place} Where {eff}", f"{hero} And The Impossible Rule", f"Welcome To {place}: {eff}",
                             f"{hero} Breaks The {place}'s Only Rule", f"Why {eff}"])
        title = _title(title)[:80]
        bait = comment_bait(parsed)
        tk, twist_text = pick_twist(crng, options, cast, hero, place)
        out.append({
            "title": title, "logline": f"{hero} lives in a {parsed['place']} where {parsed['rule']} — and today the rule goes too far.",
            "premise": f"In a {parsed['place']} where {parsed['rule']}, {hero} is the only one who wants a normal day.",
            "rule": _cap(parsed["rule"]), "hook_line": f"Nobody panic — it's happening again!",
            "twist": twist_text, "twist_kind": tk, "ending": "The chaos becomes the best day the town has ever had", "comment_bait": bait,
            "genre": options["genre"], "tone": options["tone"], "motifs": parsed["motifs"], "parsed": parsed,
            "escalation_ideas": ["the rule speeds up", "the authority figure tries to ban it", "someone tries to exploit it"],
            "cast_sketch": cast, "location_sketch": make_worlds(crng, options, parsed, tod), "music_mood": mood,
            "why_it_works": "A one-sentence rule the viewer gets instantly, with visible chaos from the first second.",
        })
    return out


def comment_bait(parsed: dict) -> str:
    m = parsed["motifs"]
    if "animal" in m:
        return "Which animal would YOU turn into? Tell me in the comments!"
    if "color" in m:
        return "What colour would your town turn? Comment below!"
    if "vanish" in m:
        return "Who would YOU make disappear? Comment below!"
    if "dance" in m:
        return "What song would you dance to forever? Comment below!"
    return f"Would you survive a day in this {parsed['place']}? Comment below!"


# ---------------------------------------------------------------- script
def _L(c, text, emo="neutral", deliv="natural"):
    return {"character_id": c, "text": text, "emotion": emo, "delivery": deliv}


def _A(c, anim, at=0.0, note="", form=""):
    return {"character_id": c, "animation": anim, "at": at, "note": note, "form": form}


def write_script(story: dict, chars: list[dict], worlds: list[dict], options: dict, rng: random.Random) -> list[dict]:
    parsed = story.get("parsed") or parse_idea(story.get("rule", ""), options, rng)
    motifs = set(story.get("motifs") or parsed.get("motifs", []))
    on = [c for c in chars if not c.get("is_narrator")]
    H = on[0]
    Sd = on[1] if len(on) > 1 else None
    F = on[2] if len(on) > 2 else None
    NAR = "narrator" if any(c.get("is_narrator") for c in chars) else H["id"]
    place, Place = parsed["place"], _cap(parsed["place"])
    rule, effect, trigger = parsed["rule"], parsed["effect"], parsed["trigger"]
    rule_line = f"Every time {trigger}, {effect}!" if trigger and len(rule) < 110 else f"{_cap(rule)}!"
    horror = options["genre"] == "horror" or options["tone"] == "spooky"
    funny = options["humour"] >= 40
    mood, tod = GENRE_FLAVOR.get(options["genre"], ("silly", "day"))
    if options["tone"] == "spooky":
        mood, tod = "spooky", "night"
    w_main = worlds[0]["id"]
    w2 = worlds[1]["id"] if len(worlds) > 1 else w_main
    w3 = worlds[2]["id"] if len(worlds) > 2 else w_main
    forms = rng.sample(S.FORMS, k=min(len(S.FORMS), 4))
    animal = "animal" in motifs
    crowd_form = forms[3] if animal else ""
    hv = "scared" if horror else "excited"
    fx_bg = ["vignette"] if horror else []

    def trans_actions(at=1.0):
        acts = []
        for i, c in enumerate(on):
            acts.append(_A(c["id"], "transform", at + i * 0.25, "transformation", forms[i % len(forms)] if animal else ""))
        return acts

    motif_fx = []
    if "color" in motifs:
        motif_fx.append("color_shift")
    if "confetti" in motifs:
        motif_fx.append("confetti")
    if animal or "vanish" in motifs or "shrink" in motifs:
        motif_fx.append("poof")
    if "bounce" in motifs:
        motif_fx.append("shake")
    motif_anim = {"dance": "dance", "bounce": "jump", "shrink": "shrink", "vanish": "vanish"}.get(next((m for m in ("dance", "bounce", "shrink", "vanish") if m in motifs), ""), "")

    hook_lines = [
        [_L(H["id"], rng.choice(["Okay, nobody panic. It's happening AGAIN.", "Why does this ALWAYS happen to me?!", "Three, two, one… here it comes!"] if not horror
                                else ["Don't look. Whatever you do, don't look.", "It's starting again. Run."]), hv, "scared" if horror else "excited"),
         _L(NAR, f"Welcome to {Place}, where {rule if len(rule) < 95 else effect}.", "neutral", "dramatic" if horror else "funny")]]
    scenes: list[dict] = []
    scenes.append({
        "kind": "hook", "title": "The Hook", "description": f"Cold open: the rule hits mid-chaos in {place}.", "location_id": w2 if "clock" in motifs else w_main,
        "characters": [H["id"]] + ([Sd["id"]] if Sd else []), "dialogue": hook_lines[0], "emotion": "surprised",
        "actions": [_A(H["id"], "shake" if horror else "jump", 0.0)] + trans_actions(0.8) if animal else [_A(H["id"], "shake", 0.0)],
        "camera": {"shot": "close", "move": "push_in", "note": "start inside the chaos"},
        "environment": {"crowd": 5, "crowd_form": crowd_form, "time_of_day": tod}, "duration": 4.0,
        "sfx": [{"name": "chime" if "clock" in motifs else "sting", "at": 0.0}, {"name": "crowd_gasp", "at": 1.0}],
        "effects": ["flash", "exclaim"] + motif_fx[:2] + fx_bg, "on_screen_text": "12:00" if "clock" in motifs else "",
        "voiceover_notes": "Punchy, urgent opening.", "music_mood": mood, "transition": "cut",
        "visual_prompt": f"{H['name']} in the middle of a chaotic {place} square, crowd reacting, bright cartoon Roblox style",
    })
    if options["length"] != "short":
        intro_side = [_L(Sd["id"], rng.choice([f"Morning, {H['name']}! Big day in {place}.", f"{H['name']}! You're up early!"]), "happy")] if Sd else []
        scenes.append({
            "kind": "intro", "title": "Meet the hero", "description": f"{H['name']} just wants a normal day.", "location_id": w_main,
            "characters": [H["id"]] + ([Sd["id"]] if Sd else []),
            "dialogue": [_L(NAR, f"This is {H['name']}. {H['name']} just wanted one normal day.", "neutral", "natural")] + intro_side +
                        [_L(H["id"], rng.choice(["Every day is a big day here.", "I'm TRYING to have a normal day."]), "worried", "deadpan")],
            "actions": [_A(H["id"], "walk", 0.0), _A(Sd["id"], "wave", 0.8)] if Sd else [_A(H["id"], "walk", 0.0)],
            "camera": {"shot": "medium", "move": "pan_right"}, "environment": {"crowd": 2, "time_of_day": tod}, "emotion": "neutral",
            "duration": 5.0, "sfx": [{"name": "footsteps", "at": 0.1}], "effects": fx_bg, "music_mood": mood, "transition": "slide",
            "visual_prompt": f"{H['name']} walking down a sunny {place} street, friendly neighbours",
        })
    rule_cast = [c["id"] for c in on[:3]]
    if animal:
        rule_actions = trans_actions(1.2)
    elif motif_anim == "vanish" and Sd:
        rule_actions = [_A(Sd["id"], "vanish", 1.4), _A(Sd["id"], "appear", 4.6)]
    else:
        rule_actions = [_A(c["id"], motif_anim or "shake", 1.2 + i * 0.2) for i, c in enumerate(on[:3])]
    scenes.append({
        "kind": "rule", "title": "The Rule", "description": f"The rule is explained — and shown.", "location_id": w2,
        "characters": rule_cast,
        "dialogue": [_L((Sd or H)["id"], f"You don't know the rule?! {rule_line}", "excited", "excited"),
                     _L(H["id"], "That's… not how anything is supposed to work.", "confused", "funny"),
                     _L(NAR, f"But in this {place}, it absolutely is.", "neutral", "dramatic")],
        "actions": rule_actions,
        "camera": {"shot": "wide", "move": "pull_out", "note": "show the whole square reacting"},
        "environment": {"crowd": 6, "crowd_form": crowd_form, "time_of_day": tod}, "emotion": "surprised", "duration": 6.5,
        "sfx": [{"name": "transform" if animal else "poof", "at": 1.3}, {"name": "wow", "at": 3.0}],
        "effects": motif_fx + ["question"] + fx_bg, "on_screen_text": "THE RULE", "music_mood": mood, "transition": "circle",
        "visual_prompt": f"Wide shot of {place} square where {effect}, characters shocked",
    })
    n_esc = {"short": 0, "standard": 1, "long": 3}[options["length"]]
    esc_bank = []
    if F:
        esc_bank.append(([_L(F["id"], f"Citizens! I will use the rule to get {rng.choice(GOALS)}!", "excited", "funny"),
                          _L((Sd or H)["id"], "That is a TERRIBLE plan.", "scared", "natural"),
                          _L(H["id"], "It's about to get worse, isn't it?", "worried", "deadpan")], "wave", "A leader tries to exploit the rule."))
        esc_bank.append(([_L(F["id"], f"By order of the {Place} council, the rule is now ILLEGAL!", "angry", "angry"),
                          _L(NAR, "The rule did not care.", "neutral", "deadpan"),
                          _L(H["id"], "Did it just get FASTER?!", "scared", "scared")], "point", "The ban backfires."))
    esc_bank.append(([_L(NAR, "Then the rule started happening faster.", "neutral", "dramatic"),
                      _L((Sd or H)["id"], "Is it supposed to do that?!", "scared", "scared"),
                      _L(H["id"], "RUN!", "scared", "excited")], "run", "The rule speeds up; everyone panics."))
    rng.shuffle(esc_bank)
    if options["length"] == "short":
        n_esc = 0
    elif options["length"] == "standard":
        n_esc = 1
    for k in range(max(n_esc, 0 if options["length"] == "short" else 1)):
        lines, anim, desc = esc_bank[k % len(esc_bank)]
        cast_ids = [c["id"] for c in on[:3]]
        scenes.append({
            "kind": "escalation", "title": f"It gets worse{'' if k == 0 else ' ' + str(k + 1)}", "description": desc,
            "location_id": [w_main, w2, w3][k % 3], "characters": cast_ids, "dialogue": lines,
            "actions": [_A(c["id"], anim if i != 0 else "run", 0.3 + i * 0.2, "away" if anim == "run" else "",
                           forms[i % len(forms)] if animal else "") for i, c in enumerate(on[:3])],
            "camera": {"shot": rng.choice(["medium", "low_angle"]), "move": rng.choice(["push_in", "shake", "pan_left"])},
            "environment": {"crowd": 5, "crowd_form": crowd_form, "time_of_day": tod}, "emotion": "scared", "duration": 6.0,
            "sfx": [{"name": rng.choice(["alarm", "rumble", "crowd_gasp", "zap"]), "at": 0.4}, {"name": "boing", "at": 2.0}],
            "effects": ["shake"] + (["rain"] if horror else ["sparkles"]) + motif_fx[:1] + fx_bg, "music_mood": "tense" if not funny else mood,
            "transition": "slide", "visual_prompt": f"{desc} cartoon Roblox style chaos",
        })
    # twist
    tw = options["twist"]
    kinds = ["foil", "immune"] if tw < 35 else (["sidekick", "immune"] if tw < 70 else ["fourth", "sidekick"])
    tk = story.get("twist_kind") if story.get("twist_kind") in ("foil", "immune", "sidekick", "fourth") else rng.choice(kinds)
    if tk == "foil" and not F:
        tk = "immune"
    if tk == "sidekick" and not Sd:
        tk = "immune"
    if tk == "sidekick":
        twist_lines = [_L(Sd["id"], "Surprise. I started the rule. All of it.", "smug", "dramatic"), _L(H["id"], f"YOU?! Why, {Sd['name']}?!", "surprised", "excited"),
                       _L(Sd["id"], "Because it's FUNNY.", "smug", "deadpan")]
        twist_desc = f"{Sd['name']} secretly caused the rule."
    elif tk == "foil":
        twist_lines = [_L(F["id"], f"I made the rule to keep {Place} safe.", "neutral", "dramatic"), _L(H["id"], "From WHAT?!", "surprised", "excited"),
                       _L(F["id"], "From boredom.", "smug", "deadpan")]
        twist_desc = f"{F['name']} created the rule to fight boredom."
    elif tk == "fourth":
        twist_lines = [_L(NAR, "Uh oh. I don't feel so good…", "worried", "scared"),
                       _L(NAR, "Did the rule just reach… the NARRATOR?!", "surprised", "funny")]
        twist_desc = "The rule reaches the narrator."
    else:
        twist_lines = [_L(H["id"], "Wait… why hasn't it happened to ME?", "surprised", "excited"),
                       _L(NAR, f"Because the rule was never about {Place}. It was about {H['name']}.", "neutral", "dramatic")]
        twist_desc = f"{H['name']} is the reason the rule exists."
    scenes.append({
        "kind": "twist", "title": "The Twist", "description": twist_desc, "location_id": w3, "characters": [c["id"] for c in on[:3]],
        "dialogue": twist_lines, "actions": [_A(H["id"], "faint" if tk == "fourth" else "point", 0.5)],
        "camera": {"shot": "close", "move": "push_in", "note": "hold on the reveal"},
        "environment": {"crowd": 0, "time_of_day": tod}, "emotion": "surprised", "duration": 5.5,
        "sfx": [{"name": "sting", "at": 0.1}, {"name": "gasp", "at": 0.5}], "effects": ["flash", "spotlight"] + fx_bg,
        "music_mood": "mysterious", "transition": "flash", "visual_prompt": f"Dramatic reveal close-up. {twist_desc}",
    })
    # ending
    end_lines = [_L(H["id"], rng.choice(["You know what? Best. Day. Ever.", "Honestly? I wouldn't change a thing."]) if not horror
                    else "Some rules… should never be broken.", "happy" if not horror else "worried", "natural"),
                 _L(NAR, story.get("comment_bait") or comment_bait(parsed), "happy", "excited")]
    scenes.append({
        "kind": "ending", "title": "The Ending", "description": "Payoff and comment bait.", "location_id": w2,
        "characters": [c["id"] for c in on[:3]], "dialogue": end_lines,
        "actions": [_A(c["id"], "celebrate" if not horror else "sneak", 0.4 + i * 0.2, "", forms[i % len(forms)] if animal else "") for i, c in enumerate(on[:3])],
        "camera": {"shot": "wide", "move": "pull_out"}, "environment": {"crowd": 5, "crowd_form": crowd_form, "time_of_day": tod},
        "emotion": "happy" if not horror else "worried", "duration": 5.0, "sfx": [{"name": "cheer" if not horror else "drone", "at": 0.2}],
        "effects": (["confetti", "sparkles"] if not horror else ["vignette"]), "music_mood": mood, "transition": "fade",
        "visual_prompt": "Everyone celebrating together, warm light, confetti" if not horror else "Quiet eerie street at night",
    })
    # keep a short video short: trim lines to a word budget (never the closing comment-bait line)
    budget = options["duration"] * 2.6
    def words(sc):
        return sum(len(d["text"].split()) for d in sc["dialogue"])
    guard = 0
    while sum(words(s) for s in scenes) > budget and guard < 40:
        guard += 1
        cand = [s for s in scenes if len(s["dialogue"]) > 1]
        if not cand:
            break
        s = max(cand, key=words)
        idx = len(s["dialogue"]) - 1
        if s["kind"] == "ending":
            idx = 0 if len(s["dialogue"]) > 1 else idx
        if s["kind"] == "hook":
            idx = 1
        s["dialogue"].pop(idx)
    weights = {"hook": 0.12, "intro": 0.15, "rule": 0.2, "escalation": 0.18, "twist": 0.17, "ending": 0.14}
    for s in scenes:
        s["duration"] = options["duration"] * weights.get(s["kind"], 0.15)
    return scenes
