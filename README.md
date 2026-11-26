# AI Story Factory

Type a story idea, press **GENERATE STORY**, and get a finished vertical **1080×1920 MP4** with a script,
characters, scenes, voiceovers, captions, sound effects and music, plus titles, hashtags and a pinned comment.

```
"Create a funny Roblox story about a town where everyone turns into a different animal
 every time the clock strikes twelve."          →  [ GENERATE STORY ]  →  video.mp4
```

## Download

### [⬇ Download for Windows (AI-Story-Factory-Setup.exe)](https://github.com/zenex123456789-hue/aistorygenapp/releases/latest/download/AI-Story-Factory-Setup.exe)

1. Download and run the installer. No Python or FFmpeg needed; it installs for your user only, with no admin password.
2. Windows may show **"Windows protected your PC"** because the installer isn't code-signed. Click **More info → Run anyway**.
3. Open **AI Story Factory** from the desktop or Start menu, type an idea and press **GENERATE STORY**.

All versions are on the [Releases page](https://github.com/zenex123456789-hue/aistorygenapp/releases). Without any API keys it runs on built-in offline engines
(basic writing, beep-style placeholder voices); add keys to unlock real AI, see [API keys](#api-keys-which-ones-and-what-they-unlock).

## Run from source (developers)

```bash
# 1. Requirements: Python 3.10+ and FFmpeg (with libx264 + libass)
pip install -r requirements.txt

# 2. (Optional) connect AI providers - see "API keys" below
cp .env.example .env        # then edit .env

# 3. Run
python run.py               # open http://127.0.0.1:8000
```

With **no keys at all** the whole pipeline still runs on built-in offline engines, so you can try everything
immediately. Those engines are clearly labelled and are lower quality than real AI providers (see "What is real,
what is a stand-in").

## Install it as a Windows app (no Python needed)

Download **`AI-Story-Factory-Setup.exe`**, run it, and open **AI Story Factory** from the desktop or Start menu. It opens in its own window.
It bundles Python, the app and FFmpeg, installs for your user only (no admin password), and keeps your projects and keys in
`%LOCALAPPDATA%\AIStoryFactory`, so updating or uninstalling never deletes them.

* **Where to get it:** the [Releases page](https://github.com/zenex123456789-hue/aistorygenapp/releases). Publishing a release with a tag like `v1.0.0`
  builds the installer in the cloud (**Actions → Windows installer**) and attaches `AI-Story-Factory-Setup.exe` to it a few minutes later.
  You can also run that workflow by hand (**Run workflow**) and take the file from the run's **Artifacts**.
* **API keys (optional):** create `%LOCALAPPDATA%\AIStoryFactory\.env` using the same lines as `.env.example`, then reopen the app.
* **No window appears?** If Windows' built-in web view isn't available, the app opens in your default browser instead.
* **Licence note:** the bundled FFmpeg is a GPL build (gyan.dev); its licence text ships in the `ffmpeg` folder next to the app. FFmpeg source code: https://ffmpeg.org/download.html

Each person who installs it has their own separate projects.

## API keys: which ones, and what they unlock

Put keys in `.env` (copied from `.env.example`) and restart `python run.py`. Keys are read by the server only and are
never sent to the browser. **Settings** in the dashboard shows which keys were detected and has a *Test* button.

| You want | Set | Notes |
|---|---|---|
| Better stories, scripts, viral critique, reference vision analysis | `ANTHROPIC_API_KEY` **or** `OPENAI_API_KEY` | Anthropic is used first if both exist. Models: `ANTHROPIC_MODEL`, `OPENAI_MODEL` |
| Human-sounding voices, many accents, exact caption timing | `ELEVENLABS_API_KEY` | Word timestamps come from ElevenLabs |
| Human-sounding voices (alternative) | `OPENAI_API_KEY` | Accent/emotion are steered by instructions. Caption timing is *estimated* and flagged |
| AI keyframe images per scene | `OPENAI_API_KEY` | Video Renderer → Visual mode → "AI keyframe images" |
| AI video clips per scene | `RUNWAY_API_KEY` (+ `OPENAI_API_KEY` for the keyframes it animates) | Video Renderer → Visual mode → "AI video clips". Runway clips are 5 or 10 s |

A sensible first setup: **one LLM key + one voice key** (for example `ANTHROPIC_API_KEY` + `ELEVENLABS_API_KEY`). You do
not need an AI video provider: the built-in renderer animates the characters itself.

## How it works

Pipeline stages (each can be re-run, edited, or paused for review):

`Story concept → Characters → Worlds → Script & scenes → Viral check → Voiceovers → Visuals → Captions → Music & SFX → Video render → Export`

* **Story** – hook in the first 1–2 s, one simple strange rule, escalation, twist, satisfying ending; no recycled premises.
* **Characters / Worlds** – each is one fixed specification that drives the reference sheet *and* every scene, so
  appearance and locations stay consistent by construction.
* **Script** – six beats (Hook, Introduction, Rule, Escalation, Twist, Ending) as scenes with dialogue, actions, camera,
  environment, emotion, duration, voiceover notes, sound effects and a visual prompt.
* **Viral check** – scores hook, curiosity, entertainment, clarity, pacing, surprise, ending and replay value; lists fixes;
  can auto-rewrite a weak script; gives 3 alternative hooks, 3 titles, description, hashtags and pinned comment.
  *It is an estimate of story craft. Nothing can predict or guarantee views.*
* **Render** – one timeline drives voices, captions, effects and transitions; FFmpeg assembles 1080×1920 H.264/AAC,
  loudness-normalised to −14 LUFS with music ducked under voices. A render only counts as successful after `ffprobe`
  confirms a real 1080×1920 file with audio.
* **References** – upload videos/images; colour, contrast, composition, cutting speed, motion, caption position and loudness
  are *measured* and saved as a reusable style profile (applied to colour grade, pacing, transitions, captions and
  prompts). Characters and plots are never copied.

Project data lives in `./data` (SQLite + files). Each project has its own folder; Files & Exports lets you preview,
download, rename and delete everything.

## What is real, what is a stand-in (please read)

* **Tested end to end in the build environment:** the whole pipeline in offline mode (story → verified MP4), the dashboard
  driven through a real headless browser, review/pause/continue, editing, reference analysis, file management.
* **Tested only against a local mock server:** the Anthropic, OpenAI (chat, TTS, images), ElevenLabs and Runway adapters.
  The build environment had no network access to those vendors, so request formats follow their public documentation
  but **have not been run against the live services.** If one fails, the error is shown verbatim in the pipeline bar;
  adapters live in `backend/providers/` and are short and easy to adjust.
* **Offline "blip" voices are not speech.** They are synthesised talking blips with exact word timing so captions and
  lip-sync line up. For real voices set an ElevenLabs or OpenAI key.
* **Offline writer** is a combinatorial template engine: it produces valid, structured stories but they are plainer
  than an LLM's. Quality scales with the LLM you connect.
* **Visuals** default to the app's own stylised, Roblox-*inspired* blocky renderer (no copyrighted characters or assets).
  It is not photoreal or generative video. AI keyframes/clips are optional and only used when you choose them.
* **Never faked:** if an AI provider fails and *Settings → fall back to the built-in renderer* is off, the render fails
  with the error. If it is on, every fallback is listed per scene in the render report and as a warning.
* Reference analysis of **characters and story structure** needs a vision-capable LLM; without one those fields are
  marked "not analysed" instead of guessed.
* Built with **Flask + vanilla JavaScript** (no Next.js/React/Tailwind build step) because it had to run with zero package
  installs. The frontend only talks to a JSON API, so it can be replaced by a React/Next.js app without touching the backend.
* Single-user local app: no authentication. Do not expose it to the internet as-is.

## Performance

Measured on 2 CPU cores: a 30 s, 1080×1920 video renders in roughly 1–2 minutes in offline mode (the `draft` quality
setting is about twice as fast; `high` is slower). AI providers add their own latency and cost.

## Project layout

```
run.py                     start the server (python run.py)
desktop.py                 the same app in a native window (what the Windows installer runs)
start-windows.bat          one-click launcher for running from source on Windows
installer/                 Inno Setup script + icon for the Windows installer
.github/workflows/         cloud build: Windows installer
backend/app.py             Flask JSON API + static files
backend/pipeline.py        stage orchestration (pause, resume, stale tracking)
backend/jobs.py            background jobs + progress + cancel
backend/providers/         LLM / TTS / image / video provider interfaces + adapters
backend/engines/           story, script, voices, viral scoring, reference analysis (offline + LLM paths)
backend/render/            character rig, scene renderer, audio synth, captions, FFmpeg assembly
frontend/                  dashboard (9 sections)
library/sfx, library/music   your own licensed files override the synthesised ones (sfx: pop.wav, whoosh.mp3 …; music: upbeat_1.mp3 — the file name starts with the mood)
```

### Adding a provider

Subclass `LLMProvider`, `TTSProvider`, `ImageProvider` or `VideoProvider` in `backend/providers/`, list its keys in
`env_keys`, implement `generate` / `synth` / `image_to_video`, and add it to the registry in
`backend/providers/__init__.py`. It then shows up in Settings automatically.

## Troubleshooting


* **"FFmpeg was not found"** – install FFmpeg and make sure `ffmpeg` is on PATH, or set `FFMPEG_BIN`.
* **Key added but still "not connected"** – restart `python run.py`; `.env` is read at start-up.
* **Provider error in the pipeline bar** – read the message; a 401/403 means a wrong or unauthorised key, 429 means rate
  limit. Use *Retry* after fixing it; finished stages are kept.
* **Render is slow** – set Quality to *Draft* in Video Renderer while iterating.

## Licences

Poppins font (SIL Open Font License) is bundled for captions. Music and sound effects are synthesised by the app; drop
your own licensed files in `library/` if you prefer. You are responsible for the rights to anything you upload as a reference.
