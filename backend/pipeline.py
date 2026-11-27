"""The end-to-end workflow. Each stage reads/writes the project document and registers its files.

STORY -> CHARACTERS -> WORLDS -> SCRIPT -> SCORE -> VOICES -> VISUALS -> CAPTIONS -> AUDIO -> RENDER -> EXPORT

(Characters and worlds are designed before the script so scenes can reference stable ids.)
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np

from . import audio_util, config, db, providers
from .engines import offline, schemas as S, viral, voices as voice_engine
from .engines import llm_engine
from .jobs import JobContext
from .providers.base import ProviderError, ProviderUnavailable
from .render import assemble, looks, scene as scene_render, sheets
from .render.captions import build_ass, build_srt
from .render.timeline import build_timeline

STAGES = ["story", "characters", "worlds", "script", "score", "voices", "visuals", "captions", "audio", "render", "export"]
LABELS = {"story": "Story concept", "characters": "Characters", "worlds": "Worlds", "script": "Script & scenes",
          "score": "Viral check", "voices": "Voiceovers", "visuals": "Visuals", "captions": "Captions",
          "audio": "Music & SFX", "render": "Video render", "export": "Export"}
WEIGHT = {"story": 5, "characters": 6, "worlds": 4, "script": 8, "score": 4, "voices": 14, "visuals": 10, "captions": 2,
          "audio": 6, "render": 36, "export": 5}
# editing X makes these stages out of date
EDIT_INVALIDATES = {"story": "characters", "characters": "voices", "worlds": "visuals", "scenes": "score",
                    "voices": "voices", "options": "story"}


# ------------------------------------------------------------------ project helpers
def new_project(name: str, idea: str, options: dict) -> dict:
    pid = db.new_id("p_")
    opts = S.normalize_options(options)
    p = {"id": pid, "name": name or "Untitled project", "idea": idea, "created": time.time(), "options": opts,
         "story": None, "story_candidates": [], "characters": [], "worlds": [], "scenes": [], "evaluation": None,
         "voice_assets": {}, "visual_assets": {}, "render": {}, "audio_report": None, "warnings": [],
         "stages": {s: {"status": "idle"} for s in STAGES}}
    db.save_project(p)
    db.project_dir(pid)
    return db.get_project(pid)


def relp(path: Path) -> str:
    return str(Path(path).resolve().relative_to(config.DATA_DIR))


def absp(rel: str) -> Path:
    return config.DATA_DIR / rel


def set_stage(pid: str, stage: str, status: str, **info) -> None:
    def fn(p):
        cur = p["stages"].get(stage, {})
        p["stages"][stage] = {**({} if status in ("running", "done") else cur), "status": status, "updated": time.time(), **info}
    db.update_project(pid, fn)


def invalidate(pid: str, from_stage: str) -> None:
    """Mark stages from `from_stage` onward as out of date (only those that had completed)."""
    idx = STAGES.index(from_stage)

    def fn(p):
        for s in STAGES[idx:]:
            if p["stages"].get(s, {}).get("status") in ("done", "review"):
                p["stages"][s] = {**p["stages"][s], "status": "stale"}
    db.update_project(pid, fn)


def warn(pid: str, stage: str, msg: str) -> None:
    def fn(p):
        p.setdefault("warnings", []).append({"stage": stage, "message": msg, "at": time.time()})
    db.update_project(pid, fn)


def clear_warnings(pid: str, stage: str) -> None:
    def fn(p):
        p["warnings"] = [w for w in p.get("warnings", []) if w["stage"] != stage]
    db.update_project(pid, fn)


def style_of(p: dict) -> dict | None:
    return db.get_style((p.get("options") or {}).get("style_id"))


def look_id_of(p: dict) -> str:
    """The art style chosen for this project (see render/looks.py)."""
    return looks.get((p.get("options") or {}).get("art_style")).id


def _fallback(pid: str, stage: str, settings: dict, what: str, exc: Exception) -> None:
    if not settings.get("allow_fallback"):
        raise exc
    warn(pid, stage, f"{what} failed ({exc}); used the offline fallback instead.")


# ------------------------------------------------------------------ stage: story
def stage_story(ctx: JobContext, pid: str, prog, force: bool = False) -> dict:
    p = db.get_project(pid)
    if p.get("story") and p["story"].get("locked") and not force:
        prog(1.0, "Using the story concept you selected")
        return {"info": "kept selected concept"}
    settings = db.get_settings()
    llm = providers.llm()
    opts = p["options"]
    style = style_of(p)
    avoid = db.recent_premises(20)
    prog(0.1, f"Writing story concepts with {llm.label}…")
    seed = opts.get("seed")
    rng = random.Random(seed if seed is not None else None)
    try:
        if llm.offline:
            cands = offline.make_concepts(p["idea"], opts, 3, rng, avoid)
            cands = [S.normalize_story(c, opts, "offline") | {"originality": 5} for c in cands]
        else:
            cands = llm_engine.concepts(llm, p["idea"], opts, 3, style, avoid)
    except Exception as exc:  # noqa: BLE001
        if llm.offline:
            raise
        _fallback(pid, "story", settings, "LLM story generation", exc)
        cands = [S.normalize_story(c, opts, "offline") | {"originality": 5} for c in offline.make_concepts(p["idea"], opts, 3, rng, avoid)]
    best = cands[0]
    prog(0.9, f"Chose “{best['title']}”")

    def fn(pp):
        pp["story"] = best
        pp["story_candidates"] = cands[1:]
        if pp["name"] in ("Untitled project", "New story", ""):
            pp["name"] = best["title"][:60]
    db.update_project(pid, fn)
    db.remember_premise(best.get("premise") or best.get("rule", ""))
    return {"title": best["title"], "source": best["source"]}


# ------------------------------------------------------------------ stage: characters
def _register_sheets(pid: str, chars: list[dict]) -> None:
    look_id = look_id_of(db.get_project(pid))
    d = db.project_dir(pid) / "characters"
    d.mkdir(exist_ok=True)
    for ch in chars:
        if ch.get("is_narrator"):
            continue
        out = d / f"{ch['id']}_{S.slug(ch['name'])}_sheet.png"
        cv2.imwrite(str(out), sheets.character_sheet(ch, look_id))
        db.register_file(pid, "character_sheet", out, f"{ch['name']} - reference sheet.png", {"character_id": ch["id"]})


def stage_characters(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    story, opts, settings = p["story"], p["options"], db.get_settings()
    llm = providers.llm()
    style = style_of(p)
    prog(0.1, "Designing characters…")
    raw = None
    if story.get("source") == "offline" or llm.offline:
        raw = story.get("cast_sketch")
        if not raw or not isinstance(raw[0].get("appearance"), dict):
            raw = offline.make_cast(random.Random(), opts, story.get("parsed") or offline.parse_idea(p["idea"], opts, random.Random()))
    else:
        try:
            raw = llm_engine.characters(llm, story, opts, style)
        except Exception as exc:  # noqa: BLE001
            _fallback(pid, "characters", settings, "LLM character design", exc)
            raw = offline.make_cast(random.Random(), opts, story.get("parsed") or offline.parse_idea(p["idea"], opts, random.Random()))
    chars = S.normalize_characters(raw, opts)
    prog(0.6, "Drawing reference sheets…")
    _register_sheets(pid, chars)

    def fn(pp):
        pp["characters"] = chars
    db.update_project(pid, fn)
    return {"count": len([c for c in chars if not c.get("is_narrator")])}


# ------------------------------------------------------------------ stage: worlds
def _register_world_previews(pid: str, worlds: list[dict]) -> None:
    look_id = look_id_of(db.get_project(pid))
    d = db.project_dir(pid) / "worlds"
    d.mkdir(exist_ok=True)
    for w in worlds:
        out = d / f"{w['id']}_{S.slug(w['name'])}.png"
        cv2.imwrite(str(out), sheets.world_preview(w, look_id))
        db.register_file(pid, "image", out, f"{w['name']} - location preview.png", {"world_id": w["id"]})


def stage_worlds(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    story, opts, settings = p["story"], p["options"], db.get_settings()
    llm = providers.llm()
    prog(0.1, "Building locations…")
    if story.get("source") == "offline" or llm.offline:
        raw = story.get("location_sketch") or []
        if not raw or "kind" not in raw[0] or "description" not in raw[0]:
            parsed = story.get("parsed") or offline.parse_idea(p["idea"], opts, random.Random())
            raw = offline.make_worlds(random.Random(), opts, parsed, "day")
    else:
        try:
            raw = llm_engine.worlds(llm, story, opts, style_of(p))
        except Exception as exc:  # noqa: BLE001
            _fallback(pid, "worlds", settings, "LLM world design", exc)
            raw = offline.make_worlds(random.Random(), opts, story.get("parsed") or {"place": "town", "motifs": []}, "day")
    worlds = S.normalize_worlds(raw)
    prog(0.6, "Drawing location previews…")
    _register_world_previews(pid, worlds)
    db.update_project(pid, lambda pp: pp.__setitem__("worlds", worlds))
    return {"count": len(worlds)}


# ------------------------------------------------------------------ stage: script
def _write_text_files(pid: str) -> None:
    p = db.get_project(pid)
    d = db.project_dir(pid)
    st = p.get("story") or {}
    names = {c["id"]: c["name"] for c in p["characters"]}
    md = [f"# {st.get('title', p['name'])}", "", f"**Logline:** {st.get('logline', '')}", "", f"**Premise:** {st.get('premise', '')}", "",
          f"**The rule:** {st.get('rule', '')}", "", f"**Twist:** {st.get('twist', '')}", "", f"**Ending:** {st.get('ending', '')}", ""]
    (d / "story.md").write_text("\n".join(md), encoding="utf-8")
    db.register_file(pid, "story", d / "story.md", f"{st.get('title', 'story')} - story.md")
    sm = [f"# Script: {st.get('title', p['name'])}", ""]
    for i, s in enumerate(p["scenes"], 1):
        sm += [f"## Scene {i} - {s['title']} ({s['kind']}, {s['duration']:.1f}s)", "", f"*{s['description']}*", "",
               f"- Camera: {s['camera']['shot']}, {s['camera']['move']}", f"- Emotion: {s['emotion']}",
               f"- Effects: {', '.join(s['effects']) or '-'}  |  SFX: {', '.join(x['name'] for x in s['sfx']) or '-'}", ""]
        for dl in s["dialogue"]:
            sm.append(f"**{names.get(dl['character_id'], 'Narrator')}** ({dl['emotion']}, {dl['delivery']}): {dl['text']}")
        sm += ["", f"Visual prompt: {s['visual_prompt']}", ""]
    (d / "script.md").write_text("\n".join(sm), encoding="utf-8")
    db.register_file(pid, "script", d / "script.md", f"{st.get('title', 'story')} - script.md")


def _make_scenes(p: dict, llm, settings: dict, feedback: str = "") -> list[dict]:
    opts, story = p["options"], p["story"]
    rng = random.Random()
    style = db.get_style(opts.get("style_id"))
    try:
        if llm.offline or story.get("source") == "offline":
            raw = offline.write_script(story, p["characters"], p["worlds"], opts, rng)
        else:
            raw = llm_engine.script(llm, story, p["characters"], p["worlds"], opts, style, feedback)
    except Exception as exc:  # noqa: BLE001
        if llm.offline or not settings.get("allow_fallback"):
            raise
        warn(p["id"], "script", f"LLM script writing failed ({exc}); used the offline writer instead.")
        raw = offline.write_script(story, p["characters"], p["worlds"], opts, rng)
    scenes = S.normalize_scenes(raw, p["characters"], p["worlds"], opts)
    if not scenes:
        raise ValueError("The script engine produced no scenes.")
    return scenes


def stage_script(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    llm, settings = providers.llm(), db.get_settings()
    prog(0.1, f"Writing the shot-by-shot script with {llm.label}…")
    scenes = _make_scenes(p, llm, settings)
    db.update_project(pid, lambda pp: pp.__setitem__("scenes", scenes))
    prog(0.8, "Saving script…")
    _write_text_files(pid)
    return {"scenes": len(scenes)}


# ------------------------------------------------------------------ stage: score (viral engine)
def stage_score(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    llm, settings = providers.llm(), db.get_settings()
    prog(0.2, "Scoring hook, pacing, twist and ending…")
    ev = viral.evaluate(llm, p)
    history = [ev["overall"]]
    rewrites = 0
    while (ev["overall"] < settings["viral_threshold"] and settings.get("auto_improve") and rewrites < int(settings.get("max_rewrites", 1))):
        rewrites += 1
        prog(0.4, f"Score {ev['overall']} is below {settings['viral_threshold']}: rewriting with the suggested fixes (attempt {rewrites})…")
        feedback = "\n".join(f"- {x}" for x in ev["improvements"])
        try:
            scenes = _make_scenes(p, llm, settings, feedback)
        except Exception as exc:  # noqa: BLE001
            warn(pid, "score", f"Auto-rewrite failed: {exc}")
            break
        trial = dict(p, scenes=scenes)
        ev2 = viral.evaluate(llm, trial)
        history.append(ev2["overall"])
        if ev2["overall"] > ev["overall"]:
            p["scenes"], ev = scenes, ev2
            db.update_project(pid, lambda pp: pp.__setitem__("scenes", scenes))
            _write_text_files(pid)
    ev["history"] = history
    ev["rewrites"] = rewrites
    ev["threshold"] = settings["viral_threshold"]
    db.update_project(pid, lambda pp: pp.__setitem__("evaluation", ev))
    if ev["overall"] < settings["viral_threshold"]:
        warn(pid, "score", f"Story scored {ev['overall']}/100, below your {settings['viral_threshold']} threshold. See the suggested improvements.")
    return {"overall": ev["overall"], "rewrites": rewrites}


# ------------------------------------------------------------------ stage: voices
def _timeline(p: dict) -> dict:
    style = style_of(p) or {}
    return build_timeline(p, p.get("voice_assets", {}), pace=float(style.get("pace_scale", 1.0) or 1.0))


def _voice_asset_abs(va: dict) -> dict:
    return {**va, "wav": str(absp(va["wav"]))}


def stage_voices(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    settings = db.get_settings()
    tts = providers.tts()
    chars = p["characters"]
    warns = voice_engine.assign_voices(chars, tts, keep_existing=True)
    for w in warns:
        warn(pid, "voices", w)
    db.update_project(pid, lambda pp: pp.__setitem__("characters", chars))
    by_id = {c["id"]: c for c in chars}
    audio_dir = db.project_dir(pid) / "audio"
    audio_dir.mkdir(exist_ok=True)
    lines = [(s, d) for s in p["scenes"] for d in s["dialogue"]]
    assets: dict = {}
    fallback_used = 0
    cached = 0
    for i, (sc, ln) in enumerate(lines):
        prog(i / max(len(lines), 1), f"Voice {i + 1}/{len(lines)} · {by_id.get(ln['character_id'], {}).get('name', 'Narrator')} via {tts.label}")
        ch = by_id.get(ln["character_id"]) or by_id.get("narrator") or chars[0]
        try:
            a = voice_engine.synth_line(tts, ch, ln, audio_dir)
        except ProviderError as exc:
            if not settings.get("allow_fallback") or tts.offline:
                raise ProviderError(f"Voice generation failed for “{ln['text'][:40]}”: {exc}")
            blip = providers.offline_for("tts")
            fch = json.loads(json.dumps(ch))
            fch["voice"]["voice_id"] = voice_engine.BLIP_BY_PROFILE.get(voice_engine._profile_key(fch), "blip_teen")
            a = voice_engine.synth_line(blip, fch, ln, audio_dir)
            a["fallback"] = True
            fallback_used += 1
            warn(pid, "voices", f"{tts.label} failed for one line ({str(exc)[:120]}); used the offline blip voice instead.")
        cached += 1 if a.get("cached") else 0
        a["wav"] = relp(Path(a["wav"]))
        assets[ln["id"]] = a
        db.register_file(pid, "audio", absp(a["wav"]), f"{sc['id']} - {ch['name']} - {ln['text'][:30]}.wav",
                         {"line_id": ln["id"], "provider": a["provider"], "timing": a.get("timing")})
    if tts.offline:
        warn(pid, "voices", "Offline blip voice in use: audio is a placeholder, not real speech. Connect ElevenLabs or OpenAI for real voices.")
    p2 = db.update_project(pid, lambda pp: pp.__setitem__("voice_assets", assets))
    tl = build_timeline(p2, assets, pace=float((style_of(p2) or {}).get("pace_scale", 1.0) or 1.0))
    return {"lines": len(lines), "cached": cached, "fallback": fallback_used, "provider": tts.name, "runtime": tl["total"]}


# ------------------------------------------------------------------ plans for the renderer
def _bias_palette(world: dict, style: dict | None) -> dict:
    w = json.loads(json.dumps(world))
    pal = (style or {}).get("palette") or []
    if len(pal) >= 2:
        for key, hx in zip(("building", "accent"), pal[:2]):
            a, b = w["palette"][key].lstrip("#"), hx.lstrip("#")
            mixed = "".join("%02x" % int(int(a[i:i + 2], 16) * 0.65 + int(b[i:i + 2], 16) * 0.35) for i in (0, 2, 4))
            w["palette"][key] = "#" + mixed
    return w


_env_cache: dict = {}


def _env_for(va: dict, fps: int):
    key = (va["wav"], fps)
    if key not in _env_cache:
        sr, arr = audio_util.read_wav(absp(va["wav"]))
        _env_cache[key] = audio_util.envelope(arr, sr, fps)
    return _env_cache[key]


def build_plan(p: dict, scene: dict, tl_scene: dict | None, fps: int, style: dict | None) -> dict:
    by_id = {c["id"]: c for c in p["characters"]}
    worlds = {w["id"]: w for w in p["worlds"]}
    cast = [by_id[c] for c in scene["characters"] if c in by_id and not by_id[c].get("is_narrator")]
    lines = []
    if tl_scene:
        for ln in tl_scene["lines"]:
            va = p["voice_assets"].get(ln["id"])
            lines.append({"character_id": ln["character_id"], "start": ln["start"], "end": ln["end"], "emotion": ln["emotion"],
                          "env": _env_for(va, fps) if va else None})
    dur = tl_scene["duration"] if tl_scene else float(scene["duration"])
    world = _bias_palette(worlds.get(scene["location_id"]) or p["worlds"][0], style)
    return {"scene": scene, "world": world, "cast": cast, "lines": lines, "duration": dur, "fps": fps, "style": style,
            "look": look_id_of(p)}


# ------------------------------------------------------------------ stage: visuals
def compose_image_prompt(p: dict, scene: dict, style: dict | None) -> str:
    by_id = {c["id"]: c for c in p["characters"]}
    world = next((w for w in p["worlds"] if w["id"] == scene["location_id"]), p["worlds"][0])
    chars = "; ".join(by_id[c].get("visual_prompt") or by_id[c]["name"] for c in scene["characters"] if c in by_id and not by_id[c].get("is_narrator"))
    acts = "; ".join(f"{by_id[a['character_id']]['name']} {a['animation']} {a['note']}".strip() for a in scene["actions"] if a["character_id"] in by_id)
    return (f"Vertical 9:16 frame from {looks.get(look_id_of(p)).prompt}. Original characters. "
            f"Location: {world['name']} - {world.get('visual_prompt') or world['description']}. Time of day: {scene['environment'].get('time_of_day') or world['time_of_day']}. "
            f"Characters (keep their looks EXACTLY as described): {chars}. Action: {scene['description']} {acts}. Mood: {scene['emotion']}. Camera: {scene['camera']['shot']} shot. "
            f"{(style or {}).get('directive', '')[:300]} No text, no watermark, no logos.")


def stage_visuals(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    settings = db.get_settings()
    style = style_of(p)
    fps = int(settings["fps"])
    tl = _timeline(p)
    tl_by = {t["id"]: t for t in tl["scenes"]}
    vdir = db.project_dir(pid) / "visuals"
    vdir.mkdir(exist_ok=True)
    mode = settings.get("visual_mode", "procedural")
    img_p, vid_p = providers.image(), providers.video()
    chosen = looks.get(look_id_of(p))
    if not chosen.procedural and not (mode in ("ai_images", "ai_video") and not img_p.offline):
        warn(pid, "visuals", f"The “{chosen.label}” look is made by an AI image provider, and none is set up (it needs an OpenAI key and Visual mode set to AI images). "
                             f"These scenes are drawn in the built-in “{looks.get(chosen.fallback).label}” look instead.")
    assets: dict = {}
    notes = {"procedural": 0, "ai_image": 0, "ai_video": 0, "fallback": 0}
    for i, sc in enumerate(p["scenes"]):
        prog(i / len(p["scenes"]), f"Scene {i + 1}/{len(p['scenes'])}: storyboard frame")
        plan = build_plan(p, sc, tl_by.get(sc["id"]), fps, style)
        still = scene_render.render_still(plan, min(1.4, plan["duration"] * 0.4), res=0.5)
        out = vdir / f"{sc['id']}_storyboard.png"
        cv2.imwrite(str(out), still)
        db.register_file(pid, "image", out, f"Scene {i + 1} - {sc['title']} - storyboard.png", {"scene_id": sc["id"]})
        asset = {"mode": "procedural", "storyboard": relp(out)}
        if mode in ("ai_images", "ai_video"):
            try:
                if img_p.offline:
                    raise ProviderUnavailable("No image provider is configured (set OPENAI_API_KEY).")
                prompt = compose_image_prompt(p, sc, style)
                key = vdir / f"{sc['id']}_ai.png"
                prog((i + 0.4) / len(p["scenes"]), f"Scene {i + 1}: generating keyframe with {img_p.label}")
                img_p.generate(prompt, key)
                db.register_file(pid, "image", key, f"Scene {i + 1} - AI keyframe.png", {"scene_id": sc["id"], "prompt": prompt})
                asset = {"mode": "ai_image", "keyframe": relp(key), "storyboard": relp(out), "prompt": prompt}
                if mode == "ai_video":
                    if vid_p.offline:
                        raise ProviderUnavailable("No video provider is configured (set RUNWAY_API_KEY). Using the AI keyframe with camera moves.")
                    clip = vdir / f"{sc['id']}_clip.mp4"
                    prog((i + 0.7) / len(p["scenes"]), f"Scene {i + 1}: animating with {vid_p.label} (this can take minutes)")
                    vid_p.image_to_video(key, f"{sc['description']} {sc['camera']['move'].replace('_', ' ')} camera", clip,
                                         duration=int(round(plan["duration"])), progress=lambda m: ctx.update(message=m))
                    db.register_file(pid, "video", clip, f"Scene {i + 1} - AI clip.mp4", {"scene_id": sc["id"]})
                    asset.update(mode="ai_video", clip=relp(clip))
            except ProviderError as exc:
                if not settings.get("allow_fallback"):
                    raise
                notes["fallback"] += 1
                warn(pid, "visuals", f"Scene {i + 1}: {exc} -> rendered as {'AI keyframe with camera moves' if asset['mode'] == 'ai_image' else 'the built-in procedural scene'} instead.")
                if asset["mode"] != "ai_image":
                    asset = {"mode": "procedural", "storyboard": relp(out), "fallback_reason": str(exc)[:200]}
        notes[asset["mode"]] += 1
        assets[sc["id"]] = asset
    db.update_project(pid, lambda pp: pp.__setitem__("visual_assets", assets))
    return notes


# ------------------------------------------------------------------ stage: captions
def stage_captions(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    tl = _timeline(p)
    if tl["missing_lines"]:
        raise RuntimeError("Voiceovers are missing for some lines. Run the Voices stage first.")
    rdir = db.project_dir(pid) / "render"
    rdir.mkdir(exist_ok=True)
    style = style_of(p)
    (rdir / "captions.ass").write_text(build_ass(tl, p["scenes"], style), encoding="utf-8")
    (rdir / "captions.srt").write_text(build_srt(tl), encoding="utf-8")
    db.register_file(pid, "caption", rdir / "captions.srt", f"{p['name']} - captions.srt")
    db.register_file(pid, "caption", rdir / "captions.ass", f"{p['name']} - captions.ass")
    methods = {}
    for t in tl["scenes"]:
        for ln in t["lines"]:
            methods[ln.get("timing") or "estimated"] = methods.get(ln.get("timing") or "estimated", 0) + 1
    if methods.get("estimated"):
        warn(pid, "captions", f"{methods['estimated']} caption line(s) use estimated word timing (this voice provider gives no timestamps).")
    return {"lines": sum(len(t["lines"]) for t in tl["scenes"]), "timing": methods}


# ------------------------------------------------------------------ stage: audio
def stage_audio(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    settings = db.get_settings()
    tl = _timeline(p)
    if tl["missing_lines"]:
        raise RuntimeError("Voiceovers are missing for some lines. Run the Voices stage first.")
    rdir = db.project_dir(pid) / "render"
    rdir.mkdir(exist_ok=True)
    prog(0.1, "Mixing voices, sound effects and music (with ducking)…")
    assets = {k: _voice_asset_abs(v) for k, v in p["voice_assets"].items()}
    rep = assemble.mix_audio(p, tl, assets, settings, rdir / "mix.wav", default_mood=(p.get("story") or {}).get("music_mood") or "upbeat")
    db.register_file(pid, "audio", rdir / "mix.wav", f"{p['name']} - full audio mix.wav")
    db.update_project(pid, lambda pp: pp.__setitem__("audio_report", rep))
    return {"sfx": len(rep["sfx"]), "voice_lines": rep["voice_lines"], "duration": rep["duration"]}


# ------------------------------------------------------------------ stage: render
def _clip_segment(clip: Path, dur: float, fps: int, out: Path) -> None:
    cmd = [config.FFMPEG, "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(clip), "-t", f"{dur:.3f}", "-an",
           "-vf", f"scale={config.WIDTH}:{config.HEIGHT}:force_original_aspect_ratio=increase,crop={config.WIDTH}:{config.HEIGHT},fps={fps}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("clip transcode failed: " + r.stderr[-300:])


def stage_render(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    settings = db.get_settings()
    style = style_of(p)
    fps = int(settings["fps"])
    q = assemble.QUALITY.get(settings.get("quality", "standard"), assemble.QUALITY["standard"])
    if not audio_util.ffmpeg_ok():
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and make sure `ffmpeg` is on your PATH (or set FFMPEG_BIN).")
    tl = _timeline(p)
    if tl["missing_lines"]:
        raise RuntimeError("Voiceovers are missing for some lines. Run the Voices stage first.")
    rdir = db.project_dir(pid) / "render"
    segdir = rdir / "segments"
    shutil.rmtree(segdir, ignore_errors=True)
    segdir.mkdir(parents=True, exist_ok=True)
    mix = rdir / "mix.wav"
    if not mix.exists():
        raise RuntimeError("Audio mix not found. Run the Music & SFX stage first.")
    tl_by = {t["id"]: t for t in tl["scenes"]}
    n = len(p["scenes"])
    done = {"n": 0}
    scene_reports: list[dict] = []

    def one(i: int, sc: dict):
        va = (p.get("visual_assets") or {}).get(sc["id"], {"mode": "procedural"})
        plan = build_plan(p, sc, tl_by[sc["id"]], fps, style)
        out = segdir / f"seg_{i:02d}.mp4"
        mode = va.get("mode", "procedural")
        if mode == "ai_video" and va.get("clip") and absp(va["clip"]).exists():
            _clip_segment(absp(va["clip"]), plan["duration"], fps, out)
            src = "AI video clip (loops to fit scene length)"
        elif mode in ("ai_image", "ai_video") and va.get("keyframe") and absp(va["keyframe"]).exists():
            scene_render.render_keyframe_segment(plan, absp(va["keyframe"]), out, res=q["res"], crf=q["crf"], preset=q["preset"],
                                                 check_cancel=ctx.check_cancel)
            src = "AI keyframe image + camera move"
        else:
            scene_render.render_segment(plan, out, res=q["res"], crf=q["crf"], preset=q["preset"], check_cancel=ctx.check_cancel)
            src = "built-in procedural renderer"
        return i, out, {"scene": sc["id"], "title": sc["title"], "source": src, "duration": round(plan["duration"], 2),
                        "fallback_reason": va.get("fallback_reason")}

    workers = max(1, min(os.cpu_count() or 2, 3))
    results: dict[int, Path] = {}
    prog(0.02, f"Rendering {n} scenes at {config.WIDTH}x{config.HEIGHT}, {fps} fps ({settings.get('quality', 'standard')} quality)…")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, i, sc) for i, sc in enumerate(p["scenes"])]
        for f in as_completed(futs):
            i, out, rep = f.result()
            results[i] = out
            scene_reports.append(rep)
            done["n"] += 1
            prog(0.05 + 0.8 * done["n"] / n, f"Rendered scene {done['n']}/{n}")
    segments = [results[i] for i in range(n)]
    prog(0.88, "Assembling: transitions, captions, loudness-normalised audio…")
    final = rdir / "final.mp4"
    assemble.final_assemble(segments, tl, p["scenes"], mix, final, rdir, style, settings.get("quality", "standard"),
                            bool(settings.get("captions", True)), fps)
    prog(0.96, "Verifying the finished file…")
    info = assemble.verify_video(final)                          # raises if the file is not a real 1080x1920 video with audio
    name = f"{S.slug(p['name'])}_{int(time.time())}.mp4"
    versioned = rdir / name
    shutil.copy(final, versioned)
    thumb = rdir / (versioned.stem + "_thumb.jpg")
    plan0 = build_plan(p, p["scenes"][0], tl_by[p["scenes"][0]["id"]], fps, style)
    cv2.imwrite(str(thumb), cv2.resize(scene_render.render_still(plan0, 1.0, res=0.5), (540, 960)))
    vf = db.register_file(pid, "video", versioned, f"{p['name']}.mp4", {"info": info})
    tf = db.register_file(pid, "image", thumb, f"{p['name']} - thumbnail.jpg")
    scene_reports.sort(key=lambda r: r["scene"])
    estimated = sum(1 for t in tl["scenes"] for ln in t["lines"] if ln.get("timing") == "estimated")
    report = {"status": "rendered", "video_file_id": vf["id"], "thumb_file_id": tf["id"], "info": info, "scenes": scene_reports,
              "voice_provider": providers.tts().name, "quality": settings.get("quality"), "rendered_at": time.time(),
              "caption_timing_estimated_lines": estimated}
    db.update_project(pid, lambda pp: pp.__setitem__("render", report))
    return {"duration": info["duration"], "size_mb": info["size_mb"]}


# ------------------------------------------------------------------ stage: export
def stage_export(ctx, pid, prog) -> dict:
    p = db.get_project(pid)
    r = p.get("render") or {}
    if r.get("status") != "rendered":
        raise RuntimeError("There is no rendered video to export yet. Run the render stage.")
    vf = db.get_file(r["video_file_id"])
    rdir = db.project_dir(pid) / "render"
    ev = p.get("evaluation") or {}
    st = p.get("story") or {}
    pack = [f"TITLE OPTIONS", *[f"- {t}" for t in ev.get("titles", [])], "", "DESCRIPTION", ev.get("description", ""), "",
            "HASHTAGS", " ".join(ev.get("hashtags", [])), "", "PINNED COMMENT", ev.get("pinned_comment", ""), "",
            "ALTERNATIVE HOOKS", *[f"- {h}" for h in ev.get("alt_hooks", [])], "",
            f"Story score: {ev.get('overall', 'n/a')}/100 ({ev.get('method', '')}). {ev.get('disclaimer', '')}"]
    (rdir / "post_copy.txt").write_text("\n".join(pack), encoding="utf-8")
    meta = {"title": st.get("title"), "project": p["name"], "render": r.get("info"), "scenes": r.get("scenes"), "evaluation": ev,
            "providers": {k: providers.resolve(k).name for k in providers.REGISTRY}, "warnings": p.get("warnings", [])}
    (rdir / "metadata.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    zpath = rdir / f"{S.slug(p['name'])}_package.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(db.file_path(vf), "video.mp4")
        for f in ("captions.srt", "captions.ass", "post_copy.txt", "metadata.json"):
            z.write(rdir / f, f)
        for name in ("story.md", "script.md"):
            fp = db.project_dir(pid) / name
            if fp.exists():
                z.write(fp, name)
        for f in (db.list_files(pid, "character_sheet")):
            z.write(db.file_path(f), f"characters/{Path(f['path']).name}")
    ef = db.register_file(pid, "export", zpath, f"{p['name']} - package.zip")
    db.update_project(pid, lambda pp: pp["render"].__setitem__("package_file_id", ef["id"]))
    return {"package": ef["id"]}


STAGE_FN = {"story": stage_story, "characters": stage_characters, "worlds": stage_worlds, "script": stage_script,
            "score": stage_score, "voices": stage_voices, "visuals": stage_visuals, "captions": stage_captions,
            "audio": stage_audio, "render": stage_render, "export": stage_export}


# ------------------------------------------------------------------ orchestration
def run_pipeline(ctx: JobContext, pid: str, start: str = "story", end: str = "export", pause_after: list[str] | None = None,
                 force_story: bool = False) -> dict:
    pause_after = pause_after or []
    i0, i1 = STAGES.index(start), STAGES.index(end)
    plan = STAGES[i0:i1 + 1]
    total_w = sum(WEIGHT[s] for s in plan)
    base = 0.0
    for st in plan:
        ctx.check_cancel()
        w = WEIGHT[st] / total_w * 100
        ctx.update(progress=base, message=f"{LABELS[st]}…", stage=st, force=True)
        invalidate(pid, STAGES[min(STAGES.index(st) + 1, len(STAGES) - 1)]) if st != STAGES[-1] else None
        clear_warnings(pid, st)
        set_stage(pid, st, "running")

        def prog(frac: float, msg: str = "", _base=base, _w=w, _st=st):
            ctx.update(progress=_base + _w * max(0.0, min(1.0, frac)), message=msg or f"{LABELS[_st]}…", stage=_st)
        ctx.log(f"▶ {LABELS[st]}")
        try:
            info = STAGE_FN[st](ctx, pid, prog, force_story) if st == "story" else STAGE_FN[st](ctx, pid, prog)
        except Exception as exc:
            set_stage(pid, st, "failed", error=str(exc)[:500])
            raise
        status = "review" if st in pause_after and st != plan[-1] else "done"
        set_stage(pid, st, "done" if status != "review" else "review", info=info)
        ctx.log(f"✔ {LABELS[st]} {json.dumps(info, default=str)[:160]}")
        base += w
        if st in pause_after and st != plan[-1]:
            nxt = STAGES[STAGES.index(st) + 1]
            return {"_status": "paused", "paused_after": st, "next": nxt, "message": f"Paused after {LABELS[st]} — review and edit, then continue."}
    return {"message": "Finished", "stages": plan}
