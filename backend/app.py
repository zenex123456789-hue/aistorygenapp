"""Flask API + static frontend."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import time
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory, stream_with_context
from werkzeug.utils import secure_filename

from . import audio_util, auth, config, db, jobs, pipeline, providers, updates
from .version import VERSION
from .engines import offline, references, schemas as S, llm_engine
from .engines import voices as voice_engine
from .providers.base import ProviderError

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 800 * 1024 * 1024
if os.getenv("SF_TRUST_PROXY", "").strip().lower() in ("1", "true", "yes"):
    # Behind a hosting platform's HTTPS proxy: believe its X-Forwarded-* headers (real client address, https, host name).
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
auth.init(app, config.HOSTED)
db.init()
jobs.recover_interrupted()


def err(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


@app.errorhandler(ProviderError)
def _provider_error(e):
    return err(str(e), 502)


@app.errorhandler(KeyError)
def _key_error(e):
    return err(f"Not found: {e}", 404)


@app.errorhandler(Exception)
def _any_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    import traceback
    traceback.print_exc()
    return err(f"{type(e).__name__}: {e}", 500)


# ------------------------------------------------------------------ static
@app.get("/")
def index():
    return send_from_directory(config.FRONTEND_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path):
    if path.startswith(("api/", "files/", "refs/", "preview/")):
        abort(404)
    return send_from_directory(config.FRONTEND_DIR, path)


# ------------------------------------------------------------------ system
@app.get("/api/health")
def health():
    return jsonify({"ok": True, "ffmpeg": audio_util.ffmpeg_ok(), "data_dir": str(config.DATA_DIR),
                    "video": {"width": config.WIDTH, "height": config.HEIGHT}})


@app.get("/api/update-check")
def update_check():
    return jsonify(updates.check())


@app.get("/api/releases")
def releases_list():
    return jsonify(updates.list_releases())


@app.get("/api/releases/asset/<int:asset_id>/check")
def release_asset_check(asset_id):
    """Is this file reachable? Lets the page show a clear message instead of saving an error page as a download."""
    try:
        r = updates.open_asset(asset_id)
    except updates.AssetError as exc:
        return err(exc.msg, exc.status)
    size = r.headers.get("Content-Length")
    r.close()
    return jsonify({"ok": True, "size": int(size) if size and size.isdigit() else None})


@app.get("/api/releases/asset/<int:asset_id>/file/<path:name>")
def release_asset_file(asset_id, name):
    """Pass a release file from GitHub through to the person as a download (the app fetches it, nobody is sent to GitHub)."""
    try:
        r = updates.open_asset(asset_id)
    except updates.AssetError as exc:
        return err(exc.msg, exc.status)
    headers = {"Content-Disposition": f'attachment; filename="{secure_filename(name) or "download-" + str(asset_id)}"', "Cache-Control": "no-store"}
    if (r.headers.get("Content-Length") or "").isdigit():
        headers["Content-Length"] = r.headers["Content-Length"]

    def body():
        try:
            for chunk in r.iter_content(1 << 20):
                if chunk:
                    yield chunk
        finally:
            r.close()

    return Response(stream_with_context(body()), mimetype="application/octet-stream", headers=headers)


@app.post("/api/open-external")
def open_external():
    """Desktop app only: open a page of this project's GitHub repository in the person's normal browser."""
    url = str((request.get_json(silent=True) or {}).get("url", ""))
    if config.HOSTED or auth.enabled() or request.remote_addr not in ("127.0.0.1", "::1"):
        return err("Not available here.", 403)
    if not updates.allowed_link(url):
        return err("That address is not allowed.", 400)
    import webbrowser
    webbrowser.open(url)
    return jsonify({"ok": True})


@app.get("/api/capabilities")
def capabilities():
    caps = providers.capabilities()
    shared = [k for k in os.environ.get("SF_SHARED_KEYS", "").split(",") if k]     # names only, never values
    return jsonify({"providers": caps, "ffmpeg": audio_util.ffmpeg_ok(), "settings": db.get_settings(),
                    "shared_keys": shared, "env_file": os.environ.get("SF_ENV_FILE", ""), "auth": auth.status(),
                    "version": VERSION, "releases_url": updates.RELEASES_URL, "hosted": bool(config.HOSTED),
                    "enums": {"genres": S.GENRES, "tones": S.TONES, "audiences": S.AUDIENCES, "lengths": list(S.LENGTHS), "durations": S.DURATIONS,
                              "location_kinds": S.LOCATION_KINDS, "emotions": S.EMOTIONS, "deliveries": S.DELIVERIES, "animations": S.ANIMATIONS,
                              "forms": S.FORMS, "effects": S.EFFECTS, "camera_shots": S.CAMERA_SHOTS, "camera_moves": S.CAMERA_MOVES,
                              "sfx": S.SFX_NAMES, "music_moods": S.MUSIC_MOODS, "transitions": S.TRANSITIONS, "hair_styles": S.HAIR_STYLES,
                              "accessories": S.ACCESSORIES, "eyes": S.EYES, "shirt_patterns": S.SHIRT_PATTERNS, "age_looks": S.AGE_LOOKS,
                              "builds": S.BUILDS, "genders": S.GENDERS, "times": S.TIMES_OF_DAY, "roles": S.ROLES,
                              "scene_kinds": S.SCENE_KINDS},
                    "stages": [{"id": s, "label": pipeline.LABELS[s]} for s in pipeline.STAGES]})


@app.get("/api/settings")
def get_settings():
    return jsonify(db.get_settings())


@app.put("/api/settings")
def put_settings():
    return jsonify(db.set_settings(request.get_json(force=True) or {}))


@app.post("/api/providers/<kind>/<name>/test")
def test_provider(kind, name):
    prov = providers.by_name(kind, name)
    if not prov:
        return err("Unknown provider", 404)
    if not prov.configured():
        return jsonify({"ok": False, "message": f"Not configured. Set {', '.join(prov.env_keys)} in .env and restart."})
    t0 = time.time()
    try:
        if kind == "llm" and not prov.offline:
            out = prov.generate("Reply with the single word OK.", "ping", json_mode=False, temperature=0, max_tokens=20)
            return jsonify({"ok": True, "message": f"Reply: {out.strip()[:40]!r} in {time.time() - t0:.1f}s"})
        if kind == "tts":
            vs = prov.voices()
            return jsonify({"ok": True, "message": f"{len(vs)} voices available" + ("" if prov.offline else " (voice list fetched)")})
        return jsonify({"ok": True, "message": "Key present. A live call is not made for this provider to avoid charges; generation will report any API error."})
    except ProviderError as exc:
        return jsonify({"ok": False, "message": str(exc)})


# ------------------------------------------------------------------ projects
def _project_out(p: dict) -> dict:
    p = dict(p)
    jb = jobs.list_jobs(p["id"], 5)
    p["active_job"] = next((j for j in jb if j["status"] in ("queued", "running")), None)
    p["last_job"] = jb[0] if jb else None
    return p


@app.get("/api/projects")
def list_projects():
    return jsonify(db.list_projects())


@app.post("/api/projects")
def create_project():
    b = request.get_json(force=True) or {}
    p = pipeline.new_project(b.get("name") or "Untitled project", b.get("idea", ""), b.get("options") or {})
    return jsonify(_project_out(p)), 201


@app.get("/api/projects/<pid>")
def get_project(pid):
    p = db.get_project(pid)
    if not p:
        return err("Project not found", 404)
    return jsonify(_project_out(p))


@app.patch("/api/projects/<pid>")
def patch_project(pid):
    b = request.get_json(force=True) or {}

    def fn(p):
        if "name" in b:
            p["name"] = str(b["name"])[:80] or p["name"]
        if "idea" in b:
            p["idea"] = str(b["idea"])[:2000]
        if "options" in b:
            p["options"] = S.normalize_options({**p["options"], **b["options"]})
    return jsonify(_project_out(db.update_project(pid, fn)))


@app.delete("/api/projects/<pid>")
def delete_project(pid):
    db.delete_project(pid)
    return jsonify({"ok": True})


@app.post("/api/projects/<pid>/duplicate")
def duplicate_project(pid):
    src = db.get_project(pid)
    if not src:
        return err("Project not found", 404)
    p = pipeline.new_project(src["name"] + " (copy)", src["idea"], src["options"])
    keep = {k: src.get(k) for k in ("story", "characters", "worlds", "scenes", "evaluation")}

    def fn(pp):
        pp.update(keep)
        for s in ("story", "characters", "worlds", "script", "score"):
            if keep.get({"script": "scenes", "score": "evaluation"}.get(s, s)):
                pp["stages"][s] = {"status": "done", "updated": time.time()}
        for s in ("voices", "visuals", "captions", "audio", "render", "export"):
            pp["stages"][s] = {"status": "idle"}
    db.update_project(p["id"], fn)
    pipeline._register_sheets(p["id"], keep["characters"] or [])
    pipeline._register_world_previews(p["id"], keep["worlds"] or [])
    if keep["scenes"]:
        pipeline._write_text_files(p["id"])
    return jsonify(_project_out(db.get_project(p["id"]))), 201


# ---- manual edits (each marks downstream stages as out of date)
@app.put("/api/projects/<pid>/story")
def put_story(pid):
    b = request.get_json(force=True) or {}

    def fn(p):
        cur = p.get("story") or {}
        merged = {**cur, **{k: v for k, v in b.items() if k in ("title", "logline", "premise", "rule", "hook_line", "twist", "ending", "comment_bait", "genre", "tone", "music_mood")}}
        merged["locked"] = True
        p["story"] = S.normalize_story({**merged, "parsed": cur.get("parsed"), "cast_sketch": cur.get("cast_sketch"), "location_sketch": cur.get("location_sketch"),
                                        "escalation_ideas": cur.get("escalation_ideas"), "motifs": cur.get("motifs")}, p["options"], cur.get("source", "llm"))
        p["stages"]["story"] = {"status": "done", "updated": time.time()}
    p = db.update_project(pid, fn)
    pipeline.invalidate(pid, "characters")
    return jsonify(_project_out(db.get_project(pid)))


@app.post("/api/projects/<pid>/story/choose")
def choose_story(pid):
    cand = (request.get_json(force=True) or {}).get("story")
    if not cand:
        return err("story required")

    def fn(p):
        st = S.normalize_story(cand, p["options"], cand.get("source", "llm"))
        st["locked"] = True
        st["originality"] = cand.get("originality")
        st["cast_sketch"], st["location_sketch"] = cand.get("cast_sketch") or [], cand.get("location_sketch") or []
        p["story"] = st
        p["stages"]["story"] = {"status": "done", "updated": time.time()}
        if p["name"] in ("Untitled project", "New story", ""):
            p["name"] = st["title"][:60]
    db.update_project(pid, fn)
    pipeline.invalidate(pid, "characters")
    db.remember_premise((cand.get("premise") or cand.get("rule") or "")[:300])
    return jsonify(_project_out(db.get_project(pid)))


@app.put("/api/projects/<pid>/characters")
def put_characters(pid):
    raw = request.get_json(force=True) or []
    p0 = db.get_project(pid)
    old = {c["id"]: c for c in p0["characters"]}
    chars = S.normalize_characters([{**c, **{"voice": c.get("voice", {})}} for c in raw if not c.get("is_narrator")], p0["options"] | {"num_characters": 5, "narrator": any(c.get("is_narrator") for c in raw) or p0["options"].get("narrator", True)})
    # keep narrator voice edits
    nar_in = next((c for c in raw if c.get("is_narrator")), None)
    for c in chars:
        if c.get("is_narrator") and nar_in:
            c["voice"] = {**c["voice"], **(nar_in.get("voice") or {})}
        if c["id"] in old and not c.get("is_narrator"):
            # keep voice assignment if the user did not touch it
            ov = old[c["id"]].get("voice", {})
            for k in ("voice_id", "provider"):
                if not c["voice"].get(k):
                    c["voice"][k] = ov.get(k, "")
    db.update_project(pid, lambda p: p.__setitem__("characters", chars))
    pipeline._register_sheets(pid, chars)
    pipeline.invalidate(pid, "voices")
    return jsonify(_project_out(db.get_project(pid)))


@app.put("/api/projects/<pid>/worlds")
def put_worlds(pid):
    raw = request.get_json(force=True) or []
    worlds = S.normalize_worlds(raw, 6)
    db.update_project(pid, lambda p: p.__setitem__("worlds", worlds))
    pipeline._register_world_previews(pid, worlds)
    pipeline.invalidate(pid, "visuals")
    return jsonify(_project_out(db.get_project(pid)))


@app.put("/api/projects/<pid>/scenes")
def put_scenes(pid):
    raw = request.get_json(force=True) or []
    p0 = db.get_project(pid)
    scenes = S.normalize_scenes(raw, p0["characters"], p0["worlds"], p0["options"], fit=False)
    if not scenes:
        return err("At least one scene is required")
    db.update_project(pid, lambda p: p.__setitem__("scenes", scenes))
    pipeline._write_text_files(pid)
    pipeline.invalidate(pid, "score")
    return jsonify(_project_out(db.get_project(pid)))


# ------------------------------------------------------------------ pipeline jobs
def _submit_run(pid: str, start: str, end: str, pause_after: list[str], force_story: bool, label: str) -> dict:
    p = db.get_project(pid)
    if not p:
        raise KeyError(pid)
    active = next((j for j in jobs.list_jobs(pid, 5) if j["status"] in ("queued", "running")), None)
    if active:
        raise ProviderError("A job is already running for this project. Wait for it to finish or cancel it.")
    heavy = pipeline.STAGES.index(end) >= pipeline.STAGES.index("visuals") and pipeline.STAGES.index(start) <= pipeline.STAGES.index("render")
    return jobs.submit(pid, "pipeline", label, lambda ctx: pipeline.run_pipeline(ctx, pid, start, end, pause_after, force_story), heavy=heavy)


@app.post("/api/projects/<pid>/run")
def run_project(pid):
    b = request.get_json(force=True) or {}
    start, end = b.get("from", "story"), b.get("to", "export")
    if start not in pipeline.STAGES or end not in pipeline.STAGES:
        return err("Unknown stage")
    if b.get("fresh"):
        def fn(p):
            if "idea" in b:
                p["idea"] = str(b["idea"])[:2000]
            if "options" in b:
                p["options"] = S.normalize_options({**p["options"], **b["options"]})
            if p.get("story"):
                p["story"]["locked"] = False
        db.update_project(pid, fn)
    else:
        if "idea" in b or "options" in b:
            db.update_project(pid, lambda p: (p.__setitem__("idea", str(b.get("idea", p["idea"]))[:2000]),
                                              p.__setitem__("options", S.normalize_options({**p["options"], **(b.get("options") or {})}))))
    label = "Generate story" if (start, end) == ("story", "export") else f"{pipeline.LABELS[start]} → {pipeline.LABELS[end]}"
    return jsonify(_submit_run(pid, start, end, b.get("pause_after") or [], bool(b.get("fresh")), label)), 202


@app.post("/api/projects/<pid>/stage/<stage>")
def run_stage(pid, stage):
    if stage not in pipeline.STAGES:
        return err("Unknown stage")
    b = request.get_json(silent=True) or {}
    return jsonify(_submit_run(pid, stage, b.get("to", stage), [], stage == "story", f"Re-run {pipeline.LABELS[stage]}")), 202


@app.post("/api/projects/<pid>/score/apply")
def apply_improvements(pid):
    """Rewrite the script using the viral engine's suggested fixes, then re-score."""
    p = db.get_project(pid)
    ev = p.get("evaluation") or {}
    if not ev:
        return err("Run the viral check first")

    def work(ctx):
        llm, settings = providers.llm(), db.get_settings()
        ctx.update(10, "Rewriting the script with the suggested improvements…", "script", force=True)
        feedback = "\n".join(f"- {x}" for x in ev.get("improvements", []))
        cur = db.get_project(pid)
        scenes = pipeline._make_scenes(cur, llm, settings, feedback)
        db.update_project(pid, lambda pp: pp.__setitem__("scenes", scenes))
        pipeline._write_text_files(pid)
        pipeline.invalidate(pid, "score")
        ctx.update(60, "Re-scoring…", "score", force=True)
        pipeline.set_stage(pid, "score", "running")
        info = pipeline.stage_score(ctx, pid, lambda f, m="": None)
        pipeline.set_stage(pid, "score", "done", info=info)
        return {"message": f"New score {info['overall']}"}
    return jsonify(jobs.submit(pid, "rewrite", "Apply improvements", work)), 202


@app.get("/api/jobs/<jid>")
def get_job(jid):
    j = jobs.get(jid)
    return jsonify(j) if j else err("Job not found", 404)


@app.get("/api/jobs")
def list_jobs():
    return jsonify(jobs.list_jobs(request.args.get("project"), int(request.args.get("limit", 30))))


@app.post("/api/jobs/<jid>/cancel")
def cancel_job(jid):
    return jsonify({"ok": jobs.cancel(jid)})


# ------------------------------------------------------------------ story concepts (Story Generator)
@app.post("/api/story/concepts")
def story_concepts():
    b = request.get_json(force=True) or {}
    opts = S.normalize_options(b.get("options"))
    idea = str(b.get("idea", ""))[:2000]
    llm = providers.llm()
    style = db.get_style(opts.get("style_id"))
    avoid = db.recent_premises(20)
    n = int(max(1, min(6, b.get("n", 5))))
    try:
        if llm.offline:
            rng = random.Random()
            cands = [S.normalize_story(c, opts, "offline") | {"originality": 5} for c in offline.make_concepts(idea, opts, n, rng, avoid)]
        else:
            cands = llm_engine.concepts(llm, idea, opts, n, style, avoid)
    except ProviderError:
        raise
    return jsonify({"provider": llm.name, "offline": llm.offline, "concepts": cands})


# ------------------------------------------------------------------ voices
@app.get("/api/voices")
def list_voices():
    t = providers.tts()
    return jsonify({"provider": t.name, "label": t.label, "offline": t.offline, "voices": t.voices(), "deliveries": list(S.DELIVERIES)})


@app.post("/api/voices/preview")
def preview_voice():
    b = request.get_json(force=True) or {}
    t = providers.by_name("tts", b.get("provider")) if b.get("provider") else providers.tts()
    text = (b.get("text") or "Wait, what? Did the whole town just turn into chickens?")[:200]
    delivery = S.pick(b.get("delivery"), S.DELIVERIES, "natural")
    emotion = S.pick(b.get("emotion"), S.EMOTIONS, "neutral")
    vid = b.get("voice_id") or (t.voices()[0]["id"] if t.voices() else "")
    pdir = config.CACHE_DIR / "previews"
    pdir.mkdir(exist_ok=True)
    key = voice_engine.cache_key(t.name, vid, delivery, emotion, float(b.get("speed", 1.0)), float(b.get("pitch", 0.0)), b.get("accent", ""), text)
    existing = next(pdir.glob(key + ".*"), None)
    if not existing:
        res = t.synth(text, vid, pdir / key, delivery=delivery, emotion=emotion, speed=float(b.get("speed", 1.0)),
                      pitch=float(b.get("pitch", 0.0)), accent=b.get("accent", ""))
        existing = Path(res["path"])
    return jsonify({"url": f"/preview/{existing.name}", "provider": t.name, "offline": t.offline})


@app.get("/preview/<name>")
def serve_preview(name):
    return send_from_directory(config.CACHE_DIR / "previews", secure_filename(name), conditional=True)


@app.get("/api/projects/<pid>/voice/<line_id>/audio")
def voice_line_audio(pid, line_id):
    p = db.get_project(pid)
    a = (p or {}).get("voice_assets", {}).get(line_id)
    if not a or not a.get("wav"):
        abort(404)
    path = config.DATA_DIR / a["wav"]
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="audio/wav", conditional=True)


@app.put("/api/projects/<pid>/voices")
def assign_voice(pid):
    """Body: {character_id, voice_id, provider, delivery?, speed?, pitch?, accent?}"""
    b = request.get_json(force=True) or {}

    def fn(p):
        ch = next((c for c in p["characters"] if c["id"] == b.get("character_id")), None)
        if not ch:
            raise KeyError("character")
        v = ch["voice"]
        for k in ("voice_id", "provider", "accent"):
            if k in b:
                v[k] = str(b[k])
        if "delivery" in b:
            v["default_delivery"] = S.pick(b["delivery"], S.DELIVERIES, "natural")
        if "speed" in b:
            v["speed"] = S.clamp(b["speed"], 0.7, 1.4, 1.0)
        if "pitch" in b:
            v["pitch"] = S.clamp(b["pitch"], -1, 1, 0.0)
    db.update_project(pid, fn)
    pipeline.invalidate(pid, "voices")
    return jsonify(_project_out(db.get_project(pid)))


@app.post("/api/projects/<pid>/voices/auto")
def auto_voices(pid):
    p = db.get_project(pid)
    chars = p["characters"]
    for c in chars:
        c["voice"]["voice_id"] = ""
    voice_engine.assign_voices(chars, providers.tts(), keep_existing=False)
    db.update_project(pid, lambda pp: pp.__setitem__("characters", chars))
    pipeline.invalidate(pid, "voices")
    return jsonify(_project_out(db.get_project(pid)))


# ------------------------------------------------------------------ files
@app.get("/api/files")
def api_files():
    return jsonify(db.list_files(request.args.get("project"), request.args.get("kind")))


@app.get("/files/<fid>")
def serve_file(fid):
    f = db.get_file(fid)
    if not f:
        abort(404)
    path = db.file_path(f)
    if not path.exists():
        abort(404)
    return send_file(path, mimetype=f["mime"], conditional=True, as_attachment=bool(request.args.get("download")),
                     download_name=f["name"] if request.args.get("download") else None)


@app.patch("/api/files/<fid>")
def rename_file(fid):
    name = str((request.get_json(force=True) or {}).get("name", "")).strip()[:120]
    if not name:
        return err("name required")
    f = db.rename_file(fid, name)
    return jsonify(f) if f else err("not found", 404)


@app.delete("/api/files/<fid>")
def delete_file(fid):
    return jsonify({"ok": db.delete_file(fid)})


# ------------------------------------------------------------------ references & styles
@app.get("/api/references")
def list_refs():
    return jsonify(db.list_refs())


@app.post("/api/references")
def upload_refs():
    out = []
    for f in request.files.getlist("files"):
        name = secure_filename(f.filename or "reference")
        kind = references.kind_of(Path(name))
        if kind == "other":
            return err(f"{name}: unsupported type. Use png/jpg/webp or mp4/mov/webm.")
        rid = db.new_id("r_")
        d = config.REFERENCES_DIR / rid
        d.mkdir(parents=True, exist_ok=True)
        path = d / name
        f.save(path)
        thumb = d / "thumb.jpg"
        has_thumb = references.make_thumb(path, thumb)
        db.execute("INSERT INTO refs(id,name,kind,path,thumb,created,analysis) VALUES(?,?,?,?,?,?,?)",
                   (rid, name, kind, str(path.relative_to(config.DATA_DIR)), str(thumb.relative_to(config.DATA_DIR)) if has_thumb else "", time.time(), ""))
        out.append(db.get_ref(rid))
    return jsonify(out), 201


@app.get("/refs/<rid>/<what>")
def serve_ref(rid, what):
    r = db.get_ref(rid)
    if not r:
        abort(404)
    rel = r["thumb"] if what == "thumb" else r["path"]
    if not rel:
        abort(404)
    return send_file(config.DATA_DIR / rel, conditional=True)


@app.delete("/api/references/<rid>")
def delete_ref(rid):
    db.execute("DELETE FROM refs WHERE id=?", (rid,))
    shutil.rmtree(config.REFERENCES_DIR / rid, ignore_errors=True)
    return jsonify({"ok": True})


@app.post("/api/references/analyze")
def analyze_refs():
    """Body: {ids:[...], name}. Measures each reference, builds a style profile and saves it."""
    b = request.get_json(force=True) or {}
    ids = b.get("ids") or []
    refs = [db.get_ref(i) for i in ids]
    refs = [r for r in refs if r]
    if not refs:
        return err("Select at least one reference")
    name = (b.get("name") or "My style")[:60]

    def work(ctx):
        llm = providers.llm()
        analyses = []
        for i, r in enumerate(refs):
            ctx.update(100 * i / len(refs), f"Analysing {r['name']}…", force=True)
            a = references.analyze(config.DATA_DIR / r["path"], llm)
            db.execute("UPDATE refs SET analysis=? WHERE id=?", (json.dumps(a), r["id"]))
            analyses.append(a)
        ctx.update(90, "Building style profile…", force=True)
        style = references.build_style(name, analyses)
        style["reference_ids"] = [r["id"] for r in refs]
        saved = db.save_style(style)
        return {"style_id": saved["id"], "message": f"Saved style “{name}”"}
    return jsonify(jobs.submit(None, "analyze", f"Analyse {len(refs)} reference(s)", work)), 202


@app.get("/api/styles")
def list_styles():
    return jsonify(db.list_styles())


@app.patch("/api/styles/<sid>")
def patch_style(sid):
    s = db.get_style(sid)
    if not s:
        return err("not found", 404)
    b = request.get_json(force=True) or {}
    for k in ("name", "directive"):
        if k in b:
            s[k] = str(b[k])[:900]
    if isinstance(b.get("subtitle"), dict):
        s["subtitle"] = {**s.get("subtitle", {}), **b["subtitle"]}
    return jsonify(db.save_style(s))


@app.delete("/api/styles/<sid>")
def delete_style(sid):
    db.delete_style(sid)
    return jsonify({"ok": True})


def main():
    app.run(host=config.HOST, port=config.PORT, threaded=True, debug=False)


if __name__ == "__main__":
    main()
