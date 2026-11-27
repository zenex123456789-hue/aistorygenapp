# AI Story Factory

Type a story idea, press **GENERATE STORY**, and get a finished vertical **1080×1920 MP4** with a script,
characters, scenes, voiceovers, captions, sound effects and music, plus titles, hashtags and a pinned comment.

```
"Create a funny Roblox story about a town where everyone turns into a different animal
 every time the clock strikes twelve."          →  [ GENERATE STORY ]  →  video.mp4
```

## Download

### [⬇ Download for Windows (AI-Story-Factory-Setup.exe)](https://github.com/zenex123456789-hue/aistorygenapp/releases/latest/download/AI-Story-Factory-Setup.exe)
### [⬇ Download for Android (Story-Factory.apk)](https://github.com/zenex123456789-hue/aistorygenapp/releases/latest/download/Story-Factory.apk)
### [⬇ Download for iPhone (Story-Factory.ipa)](https://github.com/zenex123456789-hue/aistorygenapp/releases/latest/download/Story-Factory.ipa)

The Android and iPhone files are small apps that open your group's [hosted address](#host-it-for-your-group-phones-and-any-browser); they need that server to exist.
The iPhone file is **unsigned** and has to be installed with a free sideloading tool, see [Install on a phone](#install-on-a-phone). If a link gives a 404, that release does not include the file yet (or no release has been published).

1. Download and run the installer. No Python or FFmpeg needed; it installs for your user only, with no admin password.
2. Windows may show **"Windows protected your PC"** because the installer isn't code-signed. Click **More info → Run anyway**.
3. Open **AI Story Factory** from the desktop or Start menu, type an idea and press **GENERATE STORY**.

**On a phone or tablet (Android, iPhone, iPad):** open your group's address in the browser and sign in with your personal code, then install it to your home screen.
This needs the app to be [hosted for your group](#host-it-for-your-group-phones-and-any-browser); the video engine cannot run on a phone itself.
Steps for [iPhone/iPad and Android](#install-on-a-phone) are below.

All versions are on the [Releases page](https://github.com/zenex123456789-hue/aistorygenapp/releases). Without any API keys it runs on built-in offline engines
(basic writing, beep-style placeholder voices); add keys to unlock real AI, see [API keys](#api-keys-which-ones-and-what-they-unlock).

## Important to know

* **Early release (v0.1.0).** The installer builds automatically and passes a start-up self-test, but it is new. If something breaks,
  open an Issue and attach `%LOCALAPPDATA%\AIStoryFactory\app.log` (see [Troubleshooting](#troubleshooting)).
* **Dark mode:** **Settings → Appearance** has *Light*, *Dark* and *Match system*, and the sun/moon button at the top right flips between light and dark. The choice is remembered.
* **Sharing with friends:** the safest way is to [host it for your group](#host-it-for-your-group-phones-and-any-browser): your API keys stay on the server and nobody can extract them.
  The Windows installer can also carry your keys ([Shared keys](#shared-keys-for-a-private-group-windows-installer)), but then anyone who has the installer can read them.
* **Needs:** Windows 10 or 11 (64-bit). The installer is about 137 MB. Internet is only needed for the AI providers you connect; the built-in engines work offline.
* **Out of the box it is a basic version.** With no API keys you get the built-in template writer and *beep-style placeholder voices* (not real speech).
  For better writing and real voices add keys, see [API keys](#api-keys-which-ones-and-what-they-unlock).
* **Your data stays on your PC.** Projects and finished videos are in `%LOCALAPPDATA%\AIStoryFactory\data`. Keys are read from a file on your PC, never shown in the
  browser or sent anywhere except to the provider they belong to. Updating or uninstalling does not delete your projects.
* **Windows security warnings.** The installer is not code-signed, so SmartScreen shows "Windows protected your PC" (More info → Run anyway), and some antivirus tools
  may flag unsigned apps built this way. The installer is built from the source in this repo by GitHub Actions; you can read and rebuild it yourself.
* **The Windows app is single-user.** Everyone who installs it has their own separate projects on their own PC. Do not put it on the internet yourself;
  to share one copy with friends use the hosted version, which has a login.
* **Vendor connections are not fully proven.** The Anthropic, OpenAI, ElevenLabs and Runway adapters were tested against a mock server only, not the live services.
  Errors are shown verbatim. Details in [What is real, what is a stand-in](#what-is-real-what-is-a-stand-in-please-read).
* **The viral score is an estimate** of story craft. Nothing can predict or guarantee views.
* **Rights are yours to check:** only upload references you have the right to use, and follow each platform's rules for AI-generated content when you post.
* **Not affiliated with Roblox.** The look is Roblox-*inspired* and uses no Roblox characters or assets.

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

To let other devices on your network use it, set `SF_HOST=0.0.0.0` **and** `SF_ACCESS_CODES` (see [Host it for your group](#host-it-for-your-group-phones-and-any-browser)).
It refuses to start on a reachable address without access codes.

## Windows app details

* **What the installer contains:** Python, the app and FFmpeg. It installs for your user only (no admin password) and opens in its own window.
  If Windows' built-in web view (WebView2) isn't available, the app opens in your default browser instead.
* **Where files go:** program in `%LOCALAPPDATA%\Programs\AI Story Factory`, your projects, videos and log in `%LOCALAPPDATA%\AIStoryFactory`.
* **Updates:** **New Updates** (left menu) tells you whether a newer version exists and downloads the installer for you; **Releases** (bottom of Settings) lists every release, and the arrow next to one shows what changed and its files (Windows, Android, iPhone), each with a download button. Downloads happen inside the app, not on GitHub. Run the new installer over the old one; projects live in a separate folder. Release notes come from the release description on GitHub, or from `CHANGELOG.md` when that is empty. The app version comes from the release tag (`v0.2.1` becomes 0.2.1). **While the repository is public this needs no sign-in and no token.** Only if you make it private does the app need a read-only token to see releases (see below); without one it says so and offers to open GitHub instead. It only contacts GitHub when you open these windows.
* **Adding API keys:** create `%LOCALAPPDATA%\AIStoryFactory\.env` (same lines as `.env.example`), then close and reopen the app. Keys built into the installer are described in [Shared keys](#shared-keys-for-a-private-group); yours take priority.
* **Uninstall:** Windows Settings → Apps → AI Story Factory. Your projects stay until you delete the `AIStoryFactory` folder yourself.
* **How the installer is made:** publishing a release with a tag like `v1.0.0` runs **Actions → Windows installer**, which builds it and attaches
  `AI-Story-Factory-Setup.exe` to that release a few minutes later. You can also run it by hand (**Run workflow**) and take the file from the run's **Artifacts**.
* **Licence note:** the bundled FFmpeg is a GPL build (gyan.dev); its licence text ships in the `ffmpeg` folder next to the app. FFmpeg source code: https://ffmpeg.org/download.html

## API keys: which ones, and what they unlock

Put keys in `.env` and restart the app. (Installed app: `%LOCALAPPDATA%\AIStoryFactory\.env`. From source: `.env` next to `run.py`, copied from `.env.example`.) Keys are read by the server only and are
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

## Shared keys for a private group (Windows installer)

**Prefer the [hosted version](#host-it-for-your-group-phones-and-any-browser) if your friends can use a web address:** there the keys never leave the server. This section is for when everyone must use the installed Windows app.

You can make the installer carry **your** Anthropic and ElevenLabs keys, so everyone in your group gets real AI without setting anything up.

**What this is not:** it does not use a Claude.ai plan (Free, Pro, Max). Those subscriptions do not include API access and Anthropic does not allow plan sign-ins to be used inside other apps.
Claude's API is a separate, pay-as-you-go product. You create an API key at <https://console.anthropic.com/> (Settings → API keys) and add a spend limit there. ElevenLabs works the same way: a key from your ElevenLabs profile.

**Set it up (once):**

1. Make the keys. Use keys made only for this group, so you can revoke them without touching anything else. Set a spend limit on the Anthropic key; on the ElevenLabs key set a credit limit and, if you can, restrict it to text-to-speech.
2. In this repo go to **Settings → Secrets and variables → Actions → New repository secret** and add `ANTHROPIC_API_KEY` and/or `ELEVENLABS_API_KEY`.
3. Make a new release (for example `v0.2.0`) or run **Actions → Windows installer → Run workflow**. The build writes the keys into a file next to the app, and the app's start-up self-test fails the build if they were not picked up.
4. Send your group the new installer. **Settings** in the app shows an amber notice saying shared keys are in use, and the sidebar says so too.

**Know the risks:**

* **The keys are inside the installer.** Anyone who has the installer or the installed app can read them (they are in `builtin.env` in the program folder). Treat the installer like the keys themselves: only give it to people you trust, and revoke and replace the keys if it spreads.
* **Keep this repository private.** The build refuses to embed keys while the repository is public (so right now, with a public repository, installers carry no keys and each person adds their own, or you use the hosted version), but do not rely on that alone. Never paste a key into an issue, a commit or a chat.
* **Everything your friends generate is billed to you.** The spend limits are your safety net, so set them.
* **Their own key wins.** If someone puts a key in `%LOCALAPPDATA%\AIStoryFactory\.env`, that is used instead of the shared one.
* **A safer design for a bigger group** is a small server that holds the keys and checks who is calling, so no key ever leaves it. That is a different (hosted) setup; it is not what this installer does.

## Letting the app list and download releases (only if the repository is private)

**Skip this section while the repository is public.** The in-app **Releases** and **New Updates** read GitHub's public list and need no token. (GitHub allows 60 anonymous requests an hour per internet address, which is plenty for opening these windows now and then.)

If you ever make the repository private, GitHub stops showing its releases to a program without a sign-in, so the app needs a read-only token:

1. GitHub → your profile picture → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Resource owner: you. **Repository access: Only select repositories**, choose this one. **Permissions → Repository permissions → Contents: Read-only** (Metadata is added automatically). Pick an expiry; when it ends, the in-app list stops working until you make a new token.
3. **Windows installer:** add the token as a repository secret named `UPDATE_TOKEN` (Settings → Secrets and variables → Actions), then publish a new release. It is embedded the same way as shared keys, so anyone with the installer can extract it. It can only read this one repository, which people with the installer already have access to. Keep the repository private and give the installer only to people you trust.
4. **Hosted version:** add it as the variable `SF_UPDATE_TOKEN` on your host. It stays on the server; friends signed in on a phone can then download the Android and iPhone files from **Releases** without a GitHub account.

## Host it for your group (phones and any browser)

Run one copy of the app on a server. Everyone opens the same `https://` address on any device, signs in with **their own personal code**, and makes videos together.

* **Your API keys stay on the server.** Friends can use them through the app but cannot read them (unlike the installer option).
* **One code per person.** Remove or change one code and only that person is locked out.
* **A daily limit per person** (default 20 video runs a day, `SF_DAILY_RUNS`) so one friend cannot burn through your credit. Your Anthropic and ElevenLabs spend limits are still the real safety net.
* **Everyone shares the same projects and files.** It is a login for people you know, not separate accounts. Do not hand out codes to strangers.
* **Works on** iPhone, iPad, Android and any computer. There is no App Store or Play Store listing; see [Install on a phone](#install-on-a-phone).

### What it needs and costs

One video render uses about **1.5 GB of memory at its peak**. I measured that with the built-in offline engines on a 2-vCPU test machine (a 30-second video took about 40 seconds). Only one heavy render runs at a time and the rest wait their turn, so
**pick a server with at least 2 GB of RAM (4 GB is comfortable).** Free hosting tiers with 512 MB will not work. Each project takes roughly 35-50 MB of disk, so delete old projects now and then.

| Where | Roughly | Notes |
|---|---|---|
| **Railway** (easiest) | Hobby plan, then pay for what you use. At the time of writing about US$5 a month minimum, with memory around US$10 per GB-month and CPU around US$20 per vCPU-month, so an app that sits idle is cheap | Connects to your private GitHub repo. Add a volume for your data |
| **Your own rented server** (cheapest, more technical) | A 2 vCPU / 4 GB cloud server is typically a few euros or dollars a month; prices change often, so check | You need a domain name pointing at it; HTTPS is automatic |
| Other hosts (Render, Fly.io) | Need a plan with 2 GB+ and a persistent disk | Use the same `Dockerfile`; set the same variables |

AI usage (Anthropic, ElevenLabs) is billed by those companies on top. Check each provider's current pricing before you start.

### Step 1: make personal codes

```bash
python tools/make_codes.py alice bob carol
```

It prints one line to paste into the `SF_ACCESS_CODES` setting and a code to send each person privately. Codes need at least 8 characters; the tool makes 14.

### Step 2a: Railway

1. Go to <https://railway.com>, sign in with GitHub, choose **New Project → GitHub repo** and pick this repository. Choose **Add Variables** before the first deploy.
2. Add these variables (see `host.env.example`):
   `SF_ACCESS_CODES` (the line from step 1), `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, and optionally `SF_DAILY_RUNS` and `SF_UPDATE_TOKEN` (only needed if the repository is private; it lets friends download the app files from **Releases**, see [above](#letting-the-app-list-and-download-releases-only-if-the-repository-is-private)). Railway builds the `Dockerfile` in this repo.
3. **Add a volume to the service and set its mount path to `/data`.** Without it, every project and video is deleted each time the service redeploys. (Railway's volumes guide: <https://docs.railway.com/volumes>.)
4. In the service's settings click **Generate Domain**. That `https://...up.railway.app` address is what you give your group.
5. In Railway's usage settings set a **hard limit** so a surprise cannot run up a bill (it takes the app offline when reached).

The app refuses to start if `SF_ACCESS_CODES` is missing, so it can never run open to the internet by mistake.

### Step 2b: your own server (Docker)

1. Rent an Ubuntu server (2 vCPU / 4 GB or more) and point a domain name at it (an `A` record to its IP address).
2. On the server install Docker (`curl -fsSL https://get.docker.com | sh`) and get this code onto it (for a private repo: `git clone` with a read-only personal access token).
3. `cp host.env.example .env`, fill it in (codes, keys, and `SITE_ADDRESS=your.domain.example`), then run `docker compose up -d --build`. Caddy fetches the HTTPS certificate for you.
4. To update later: `git pull && docker compose up -d --build`. Your data is in the `sf-data` Docker volume.

### Step 3: check it

```bash
python tools/smoke_test.py https://your-address your-personal-code --render
```

It checks that nothing is readable without signing in, that your code works, and that a 10-second video really renders and can be streamed. (If your server has AI keys, `--render` uses a little of your credit.)

**What has been tested:** the Docker image is built and tested by GitHub on every change (**Actions → Server image check**): FFmpeg features, refusing to start without codes, a root-owned data volume, login protection, a real render, a range request on the video, and data surviving a restart. I have **not** deployed it on Railway or a rented server myself, and I have not tried it with real Anthropic or ElevenLabs keys on a server, so expect to read a log or two the first time.

### Install on a phone

* **iPhone / iPad:** open your address in **Safari**, sign in, tap **Share → Add to Home Screen**. It then opens full-screen like an app. There is no App Store version: that would need an Apple Developer account (US$99 a year) and Apple's review. I could not test on an iPhone; if **Download MP4** only plays the video inside the home-screen app, open the address in Safari instead and download from there.
* **iPhone, as an app file (.ipa, sideloaded):** an `.apk` only exists for Android; the iPhone version is an `.ipa`, and Apple only runs signed ones. Set the repository variable `SERVER_URL` (as for Android below), then run **Actions → iPhone IPA (sideload) → Run workflow** and download `Story-Factory.ipa` from the run's **Artifacts**. The file is **unsigned**, so it will not install by tapping it. Each friend signs it for their own phone with a free tool on a Windows PC or Mac: [Sideloadly](https://sideloadly.io) (drag the file in, sign in with a free Apple ID, press Start) or [AltStore](https://altstore.io). Apps signed with a free Apple ID **stop opening after 7 days** until they are signed again (AltStore can renew automatically while the PC is on), and one Apple ID can have only 3 such apps. For most friends the Add to Home Screen option above is simpler and never expires. GitHub has built this file and checked its contents, but I have **not** installed it on an iPhone. macOS builds use up extra minutes on a private repository, so only run it when you need it.
* **Android, as a web app:** open your address in Chrome, sign in, then menu **⋮ → Install app** (or **Add to Home screen**).
* **Android, as an APK file:** set a repository variable `SERVER_URL` to your address (**Settings → Secrets and variables → Actions → Variables**), then run **Actions → Android APK → Run workflow** and download `Story-Factory.apk` from the run's **Artifacts**. The file contains only your address, no keys, so you can send it to friends directly. They must allow "install unknown apps", and Google Play Protect may warn because it is not from the Play Store. The APK is signed with a throwaway debug key, so installing a newer one over an older one fails: uninstall the old one first. You only need a new APK if the address changes.
  The Android build is checked by GitHub for a valid package with internet permission; I have **not** run it on a real phone.

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
* **Visuals** are drawn by the app's own renderer (no copyrighted characters or assets). The default is a Roblox-*inspired* blocky look; the **Art style** picker on the Story page also offers Round cartoon, Pixel art, Comic book, Ink sketch and Stick figures, and Anime or Realistic when an AI image provider (OpenAI key, Visual mode "AI keyframe images") is connected. Without one, those two fall back to the Round cartoon look and the project lists a warning.
* **Write story from my prompt:** type what you want (as long and detailed as you like) and press this button. The AI reads it as a brief, invents the story, and sets genre, tone, characters and art style if you asked for them. It needs Claude connected (`ANTHROPIC_API_KEY`); without a key it tells you so rather than echoing your words.
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
Dockerfile, docker-compose.yml, Caddyfile, railway.json   hosting the app for a group
android-app/               thin Android wrapper that opens your hosted address (built by Actions)
tools/                     make_codes.py (personal codes), smoke_test.py (check a hosted server)
.github/workflows/         cloud builds: Windows installer, Android APK, server image check
backend/app.py             Flask JSON API + static files
backend/auth.py            access codes, daily run cap, request checks for the hosted version
backend/version.py         the app version (release builds take it from the tag)
backend/updates.py         lists GitHub releases and passes their files through as downloads
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

* **The download button says 404:** the installer is only attached to a *published* release, and a few minutes after publishing. (If you ever make the repo private, you must be signed in to GitHub as someone with access.)
* **The app won't open / closes straight away:** look at `%LOCALAPPDATA%\AIStoryFactory\app.log` and send it with your bug report.
* **Windows or antivirus blocks the installer:** see "Windows security warnings" above. Only run it if you downloaded it from this repo's Releases page.
* **"FFmpeg was not found" (running from source only)** – install FFmpeg and make sure `ffmpeg` is on PATH, or set `FFMPEG_BIN`.
* **Key added but still "not connected"** – restart the app; `.env` is read at start-up.
* **Settings says shared keys are in use but a request fails with 401/403 or 429** – the shared key was revoked, ran out of credit or hit its spend limit. Ask whoever made the app, or add your own key.
* **The theme resets** – use **Settings → Appearance**; if the app can't save settings the choice only lasts until you close it.
* **Provider error in the pipeline bar** – read the message; a 401/403 means a wrong or unauthorised key, 429 means rate
  limit. Use *Retry* after fixing it; finished stages are kept.
* **Render is slow** – set Quality to *Draft* in Video Renderer while iterating.
* **Hosted: the container exits at start-up** – read its log. "SF_ACCESS_CODES" means you did not set the codes; a code under 8 characters or two people sharing a code is also refused.
* **Hosted: projects vanish after a redeploy** – no volume is mounted at `/data`. Add one.
* **Hosted: it crashes or restarts while rendering** – the server ran out of memory. Use a plan with at least 2 GB (4 GB is safer).
* **Hosted: "Daily limit reached"** – that person used their runs for today (resets at midnight UTC). Raise `SF_DAILY_RUNS` or set it to 0.
* **Hosted: "Too many wrong codes"** – wait five minutes; it is a per-address limit.
* **Hosted: signed out again and again** – someone changed or removed that person's code, or the browser blocks cookies for the site.

## Licences

Poppins font (SIL Open Font License) is bundled for captions. Music and sound effects are synthesised by the app; drop
your own licensed files in `library/` if you prefer. You are responsible for the rights to anything you upload as a reference.
