# Changelog

Each release's notes are shown inside the app (Settings → Releases). Add a section here for every new release, newest first, and paste the same text into the
release description on GitHub; the app prefers the GitHub text and falls back to this file.

## v0.2.3 - 2026-11-27

- **Write story from my prompt:** a new button next to GENERATE STORY. The AI reads what you typed as a brief and invents a story from it (new title, characters, twist and ending), and fills in the settings your prompt asked for (genre, tone, number of characters, art style...). It needs Claude to be connected: without it the app now says so instead of handing your own words back, and a warning on the Story page explains why the built-in generator only echoes your idea.
- **Art styles:** the video no longer has to look like Roblox. Pick Blocky 3D, Round cartoon, Pixel art, Comic book, Ink sketch or Stick figures (hand-drawn stick people on notebook paper; all drawn by the built-in renderer, with a preview of each), or Anime / Realistic if you have an AI image provider (OpenAI key). Without one, those two are drawn in the Round cartoon look and the project says so.
- Story prompts and hashtags follow the chosen style instead of always saying Roblox.
- **Releases** now opens a list inside the app: every release with its notes (tap the arrow), and a download button for the Windows, Android and iPhone files.
- **New Updates** downloads the new installer itself instead of sending you to GitHub.
- The app's version number now comes from the release tag, so the app always knows which version it is.
- The GitHub page has download links for the Android and iPhone files next to the Windows one.

## v0.2.0 - 2026-11-27

- Dark mode, with a Light / Dark / Match system choice in Settings.
- A hosted version for a group: personal access codes, your API keys kept on the server, a daily limit per person, Docker and Railway setup, and an
  installable web app for iPhone and Android.
- An Android app file (APK) and an iPhone app file (IPA, installed by sideloading) that open your hosted address.
- A **New Updates** button that checks for a newer version.
- Fixed the audio step on servers that use FFmpeg 5, which stopped the video from being finished there. Video audio is now stereo.
- Note: the installer for this release reports itself as version 0.1.0 inside the app, so it keeps offering v0.2.0 until a newer release exists.

## v0.1.0 - 2026-11-26

- First release: type an idea and get a finished vertical 1080x1920 video with script, characters, voices, captions, sound effects and music.
- Windows installer with a start-up self-test; works offline with built-in engines, and with your own Claude, OpenAI and ElevenLabs keys.
