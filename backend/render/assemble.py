"""Audio mixing and final video assembly (FFmpeg)."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .. import audio_util, config
from ..audio_util import SR
from . import audio_synth as syn
from .captions import build_ass, build_srt

QUALITY = {  # res factor, segment crf/preset, final crf/preset
    "draft": dict(res=0.5, crf=28, preset="ultrafast", fcrf=26, fpreset="ultrafast"),
    "standard": dict(res=1.0, crf=21, preset="veryfast", fcrf=20, fpreset="veryfast"),
    "high": dict(res=1.0, crf=17, preset="fast", fcrf=17, fpreset="medium"),
}


def mix_audio(project: dict, timeline: dict, voice_assets: dict, settings: dict, out_wav: Path,
              default_mood: str = "upbeat") -> dict:
    total = timeline["total"]
    n = int((total + 1.0) * SR)
    voice = np.zeros(n, dtype=np.float32)
    sfx = np.zeros(n, dtype=np.float32)
    report = {"voice_lines": 0, "sfx": [], "music": []}
    scenes = {s["id"]: s for s in project["scenes"]}

    for ts in timeline["scenes"]:
        for ln in ts["lines"]:
            va = voice_assets[ln["id"]]
            _, arr = audio_util.read_wav(Path(va["wav"]))
            syn.place(voice, arr.astype(np.float32), ts["start"] + ln["start"], 1.0)
            report["voice_lines"] += 1
        sc = scenes[ts["id"]]
        for s in list(sc.get("sfx", [])) + syn.auto_sfx(sc):
            at = ts["start"] + (ts["transition"]["dur"] if ts["transition"] else 0.0) * 0 + float(s.get("at", 0))
            syn.place(sfx, syn.load_sfx(s["name"]), at, 0.9)
            report["sfx"].append({"scene": sc["id"], "name": s["name"], "at": round(at, 2)})

    # music: one bed per mood, cross-faded per scene window
    music = np.zeros(n, dtype=np.float32)
    tracks: dict[str, np.ndarray] = {}
    story_mood = (project.get("story") or {}).get("music_mood") or default_mood
    for i, ts in enumerate(timeline["scenes"]):
        sc = scenes[ts["id"]]
        mood = sc.get("music_mood") or story_mood
        if mood not in tracks:
            tracks[mood] = syn.make_music(mood, total + 2, seed=len(project.get("id", "")) + len(tracks))
        a = int(ts["start"] * SR)
        b = int((ts["start"] + ts["duration"] + (0.35 if i < len(timeline["scenes"]) - 1 else 0)) * SR)
        seg = tracks[mood][a:b].copy()
        f = min(len(seg), int(0.3 * SR))
        if f > 0 and i > 0:
            seg[:f] *= np.linspace(0, 1, f)
        if f > 0 and i < len(timeline["scenes"]) - 1:
            seg[-f:] *= np.linspace(1, 0, f)
        music[a:a + len(seg)] += seg
        report["music"].append({"scene": sc["id"], "mood": mood})
    music *= syn.duck_gain(voice)

    mix = (voice * float(settings.get("voice_volume", 1.0))
           + sfx * float(settings.get("sfx_volume", 0.55))
           + music * float(settings.get("music_volume", 0.16)))
    mix = np.tanh(mix * 1.05)                                    # soft limiter, never clips
    mix = mix[: int((total + 0.2) * SR)]
    audio_util.write_wav(out_wav, mix, SR)
    peak = float(np.max(np.abs(mix))) if len(mix) else 0.0
    report["peak"] = round(peak, 3)
    report["duration"] = round(len(mix) / SR, 2)
    return report


def final_assemble(segments: list[Path], timeline: dict, scenes: list[dict], audio_wav: Path, out_mp4: Path,
                   workdir: Path, style: dict | None, quality: str, captions: bool, fps: int, footage: dict | None = None) -> dict:
    """footage (optional): {"path", "layout": "full" | "split", "start", "loop"}. "full" shows only the footage; "split" stacks the story
    scenes (top half) over the footage (bottom half) and moves the captions to the seam between them."""
    q = QUALITY.get(quality, QUALITY["standard"])
    W, H = config.WIDTH, config.HEIGHT
    layout = footage["layout"] if footage else None
    if layout == "split":
        sub = dict((style or {}).get("subtitle") or {})
        sub["position"] = "middle"
        style = {**(style or {}), "subtitle": sub}
    ass_text = build_ass(timeline, scenes, style)
    (workdir / "captions.ass").write_text(ass_text, encoding="utf-8")
    (workdir / "captions.srt").write_text(build_srt(timeline), encoding="utf-8")
    fonts = workdir / "fonts"
    fonts.mkdir(exist_ok=True)
    for f in config.FONTS_DIR.glob("*.ttf"):
        shutil.copy(f, fonts / f.name)

    inputs: list[str] = []
    for s in segments:
        inputs += ["-i", str(s.resolve())]
    n = len(segments)
    foot_idx = n
    if footage:
        inputs += (["-stream_loop", "-1"] if footage.get("loop") else ["-ss", f"{float(footage.get('start', 0)):.2f}"]) + ["-i", str(Path(footage["path"]).resolve())]
    aidx = n + (1 if footage else 0)
    inputs += ["-i", str(audio_wav.resolve())]
    parts: list[str] = []
    last = "0:v"
    for i in range(1, n):
        tr = timeline["scenes"][i]["transition"]
        out = f"v{i}"
        parts.append(f"[{last}][{i}:v]xfade=transition={tr['name']}:duration={max(tr['dur'], 0.04):.3f}:offset={timeline['scenes'][i]['start']:.3f}[{out}]")
        last = out
    vlabel = last
    if footage:
        fill = lambda w, h: f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1,format=yuv420p"
        if layout == "full":
            parts.append(f"[{foot_idx}:v]{fill(W, H)}[fv]")
        else:
            half = H // 2
            parts.append(f"[{vlabel}]crop={W}:{half}:0:{(H - half) // 2},setsar=1,format=yuv420p[top]")   # the middle band of each story frame
            parts.append(f"[{foot_idx}:v]{fill(W, half)}[bot]")
            parts.append("[top][bot]vstack=inputs=2[fv]")
        vlabel = "fv"
    if captions:
        parts.append(f"[{vlabel}]subtitles=captions.ass:fontsdir=fonts[vout]")
        vlabel = "vout"
    else:
        parts.append(f"[{vlabel}]null[vout]")
        vlabel = "vout"
    # The mixed track is a plain mono WAV with no channel-layout tag. FFmpeg 5.x (Debian/Ubuntu servers) cannot carry that through
    # loudnorm into the AAC encoder, so state the layout (stereo, what social platforms expect) before and after the normaliser.
    parts.append(f"[{aidx}:a]aformat=channel_layouts=stereo,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,aformat=channel_layouts=stereo[aout]")
    cmd = [config.FFMPEG, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(parts),
           "-map", f"[{vlabel}]", "-map", "[aout]", "-t", f"{timeline['total']:.3f}", "-r", str(fps),
           "-c:v", "libx264", "-preset", q["fpreset"], "-crf", str(q["fcrf"]), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_mp4.resolve())]
    r = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg assembly failed: " + r.stderr[-700:])
    return {"cmd_inputs": n + (1 if footage else 0)}


def verify_video(path: Path, expect_audio: bool = True) -> dict:
    """Probe the finished file. A render only counts as successful if this passes."""
    if not path.exists() or path.stat().st_size < 10_000:
        raise RuntimeError("Render produced no usable file.")
    info = audio_util.probe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not v:
        raise RuntimeError("Rendered file has no video stream.")
    if expect_audio and not a:
        raise RuntimeError("Rendered file has no audio stream.")
    w, h = int(v["width"]), int(v["height"])
    if (w, h) != (config.WIDTH, config.HEIGHT):
        raise RuntimeError(f"Rendered file is {w}x{h}, expected {config.WIDTH}x{config.HEIGHT}.")
    return {"width": w, "height": h, "duration": round(float(info["format"]["duration"]), 2),
            "video_codec": v["codec_name"], "audio_codec": a["codec_name"] if a else None,
            "size_mb": round(path.stat().st_size / 1e6, 2), "fps": v.get("r_frame_rate")}
