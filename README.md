# AI Story Factory

Type a story idea, press **GENERATE STORY**, and get a finished vertical **1080×1920 MP4** with a script,
characters, scenes, voiceovers, captions, sound effects and music, plus titles, hashtags and a pinned comment.

```
"Create a funny Roblox story about a town where everyone turns into a different animal
 every time the clock strikes twelve."          →  [ GENERATE STORY ]  →  video.mp4
```

## Quick start

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

## Using it with friends, on phones, or as an installed app

There are two ways to use it as a group. You can mix them.

**A. One shared copy (everyone works in the same projects).** One PC runs the app; everyone else opens it in a browser.
1. On the host PC, double-click **`start-host.bat`** (or run `start-windows.bat host`). It asks for a **group access code** and prints the addresses to share.
   The app refuses to listen on the network without a code, because anyone who reaches it could spend your API keys.
2. Friends open `http://<host-address>:8000` and enter the code. Same Wi-Fi works. For friends elsewhere, use
   [Tailscale](https://tailscale.com) (free): everyone installs it, joins one "tailnet", and uses the host's Tailscale address. Do not open the port on your router.
3. On a phone, open the address in Chrome and choose **Add to Home screen** / **Install app**. It then behaves like an app. (iPhone: Safari, Share, Add to Home Screen.)

The access code is one shared code for a small trusted group. It is **not** per-person accounts: everyone sees and can change every project.
Use `SF_ACCESS_CODE` (or `access-code.txt` next to `start-windows.bat`) to set it without being asked each time.

**B. Everyone has their own copy.** Each person installs the Windows app (below) and keeps separate projects. Send finished MP4s to each other.

### Windows installer (`AI-Story-Factory-Setup.exe`)
Built in the cloud by GitHub Actions (**Actions → Windows installer → Run workflow**, or push a tag like `v1.0.0`). It bundles Python, the app and FFmpeg, installs per-user (no admin),
and keeps your projects and keys in `%LOCALAPPDATA%\AIStoryFactory` so updates and uninstalls don't delete them. To add API keys, create `%LOCALAPPDATA%\AIStoryFactory\.env` (same format as `.env.example`).
The bundled FFmpeg is a GPL build (gyan.dev); its licence text ships in the `ffmpeg` folder.

### Android APK (`Story-Factory.apk`)
Built by **Actions → Android APK**. It is a window onto a running Story Factory server (a host PC from option A, or a hosted one); the video engine does **not** run on the phone.
On first launch type the server address (e.g. `192.168.1.20:8000`); it remembers it, and Back returns to that screen to switch. The APK is debug-signed: to install it, allow "install unknown apps" for your browser/files app.
Publishing to Google Play needs a release-signed build (a keystore you control), which is not set up here. For most groups the Chrome "Install app" route above is simpler and also lets you save videos.

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
start-windows.bat          one-click launcher; start-host.bat shares it with a group
installer/                 Inno Setup script + icon for the Windows installer
android-app/               thin Android wrapper (Capacitor) built by the APK workflow
.github/workflows/         cloud builds: Windows installer, Android APK
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

* **Friends can't connect to the host:** check you're on the same network (or Tailscale), allow Python through Windows Firewall on *private* networks, and use the address printed by `start-host.bat`.
* **"Refusing to start: SF_HOST is 0.0.0.0 ... SF_ACCESS_CODE is not set":** that's the safety check. Set a code (see above).

* **"FFmpeg was not found"** – install FFmpeg and make sure `ffmpeg` is on PATH, or set `FFMPEG_BIN`.
* **Key added but still "not connected"** – restart `python run.py`; `.env` is read at start-up.
* **Provider error in the pipeline bar** – read the message; a 401/403 means a wrong or unauthorised key, 429 means rate
  limit. Use *Retry* after fixing it; finished stages are kept.
* **Render is slow** – set Quality to *Draft* in Video Renderer while iterating.

## Licences

Poppins font (SIL Open Font License) is bundled for captions. Music and sound effects are synthesised by the app; drop
your own licensed files in `library/` if you prefer. You are responsible for the rights to anything you upload as a reference.
