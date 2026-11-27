import { post, del } from "../api.js";
import { S, refresh, startRun, startStage, isRunning } from "../state.js";
import { h, icon, toast, field, select, toggle, slider, empty, title, fmtDur } from "../ui.js";

export async function render(root) {
  const p = S.project;
  root.append(h("div", { class: "page-head" }, h("h1", "Video Renderer"),
    h("p", "Builds the visuals, captions and soundtrack, then assembles a vertical 1080×1920 MP4 with FFmpeg. Every scene reports exactly how it was produced; nothing is shown as a video unless a real file was written and verified.")));
  if (!p || !p.scenes.length) { root.append(h("div", { class: "card" }, empty("film", "Nothing to render", "Generate a story first."))); return; }
  const settings = S.caps.settings;
  const running = isRunning();
  const r = p.render || {};
  const files = await fetch(`/api/files?project=${S.pid}`).then((x) => x.json());
  const clips = await fetch("/api/footage").then((x) => (x.ok ? x.json() : [])).catch(() => []);
  const video = files.find((f) => f.id === r.video_file_id);
  const pkg = files.find((f) => f.id === r.package_file_id);
  const thumb = files.find((f) => f.id === r.thumb_file_id);

  const saveSetting = async (k, v) => { try { S.caps.settings = await fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [k]: v }) }).then((x) => x.json()); } catch (e) { toast(e.message, "bad"); } };
  const vm = S.caps.providers;
  const imgActive = vm.image.providers.find((x) => x.active), vidActive = vm.video.providers.find((x) => x.active);

  // ---- result ----
  const stale = p.stages?.render?.status === "stale";
  root.append(h("div", { class: "card hero" }, h("div", { class: "vwrap" },
    video ? h("video", { controls: true, playsinline: true, preload: "metadata", poster: thumb ? thumb.url : null, src: video.url + "?v=" + video.created }) : h("div", { class: "thumb", style: { display: "grid", placeItems: "center", color: "var(--muted)", textAlign: "center", padding: "20px" } }, "No video rendered yet"),
    h("div", { class: "col" },
      h("h2", video ? p.story?.title || p.name : "Render your video"),
      stale ? h("div", { class: "notice warn" }, "Something upstream changed since this video was rendered. Re-render to bring it up to date.") : null,
      r.info ? h("div", { class: "row wrap gap-s" },
        h("span", { class: "badge ok" }, `${r.info.width}×${r.info.height}`), h("span", { class: "badge" }, fmtDur(r.info.duration) + " min"), h("span", { class: "badge" }, `${r.info.fps} fps`),
        h("span", { class: "badge" }, `${r.info.video_codec} + ${r.info.audio_codec}`), h("span", { class: "badge" }, r.info.size_mb + " MB"), h("span", { class: "badge info" }, "verified with ffprobe"),
        r.footage ? h("span", { class: "badge info" }, `footage: ${r.footage.name} (${r.footage.layout === "full" ? "full screen" : "split"})`) : null) : null,
      h("div", { class: "row wrap" },
        h("button", { class: "btn primary", disabled: running, onclick: async () => { try { await startRun({ from: "visuals", to: "export" }); } catch (e) { toast(e.message, "bad"); } } }, icon("film", 16), video ? "Re-render video" : "Render video"),
        video ? h("a", { class: "btn", href: video.url + "?download=1" }, icon("download", 15), "Download MP4") : null,
        pkg ? h("a", { class: "btn", href: pkg.url + "?download=1" }, icon("download", 15), "Download package (.zip)") : null),
      r.voice_provider ? h("div", { class: "small muted" }, `Voices: ${r.voice_provider === "blip" ? "offline blip voices (not speech)" : r.voice_provider}`) : null,
      r.caption_timing_estimated_lines ? h("div", { class: "notice warn" }, `${r.caption_timing_estimated_lines} caption line(s) use estimated word timing (the voice provider returned no word times).`) : null))));

  // ---- visual source ----
  const mode = settings.visual_mode;
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "How the visuals are made"), h("div", { class: "small muted" }, "Choose where each scene's picture comes from."))),
    h("div", { class: "grid g3" },
      field("Visual mode", select([["procedural", "Built-in renderer (works offline)"], ["ai_images", "AI keyframe images + camera moves"], ["ai_video", "AI video clips"]], mode, async (v) => { await saveSetting("visual_mode", v); window.__rerender(); })),
      field("Quality", select([["draft", "Draft (fast)"], ["standard", "Standard"], ["high", "High (slower)"]], settings.quality, (v) => saveSetting("quality", v))),
      field("Frame rate", select([[24, "24 fps"], [30, "30 fps"]], settings.fps, (v) => saveSetting("fps", +v)))),
    h("div", { class: "row wrap gap-l", style: { marginTop: "12px" } },
      toggle("Burn in captions", settings.captions, (v) => saveSetting("captions", v)),
      toggle("If an AI provider fails, fall back to the built-in renderer (always reported)", settings.allow_fallback, (v) => saveSetting("allow_fallback", v))),
    mode !== "procedural" ? h("div", { class: "notice " + ((mode === "ai_images" ? imgActive.offline : vidActive.offline) ? "bad" : "ok"), style: { marginTop: "12px" } },
      mode === "ai_images" ? (imgActive.offline ? "No image provider is connected (set OPENAI_API_KEY). Scenes will use the built-in renderer" + (settings.allow_fallback ? " and say so in the report." : ", or the render will fail because fallback is off.") : `Image provider: ${imgActive.label}.`)
        : (vidActive.offline ? "No AI video provider is connected (set RUNWAY_API_KEY). Scenes will use the built-in renderer" + (settings.allow_fallback ? " and say so in the report." : ", or the render will fail because fallback is off.") : `Video provider: ${vidActive.label}.`)) : null,
    h("div", { class: "grid g3", style: { marginTop: "14px" } },
      slider("Voice volume", settings.voice_volume, 0, 1.5, 0.05, (v) => saveSetting("voice_volume", v), (v) => Math.round(v * 100) + "%"),
      slider("Sound effects", settings.sfx_volume, 0, 1, 0.05, (v) => saveSetting("sfx_volume", v), (v) => Math.round(v * 100) + "%"),
      slider("Music (ducks under voices)", settings.music_volume, 0, 0.6, 0.02, (v) => saveSetting("music_volume", v), (v) => Math.round(v * 100) + "%")),
    h("div", { class: "row wrap gap-s", style: { marginTop: "14px" } },
      ["visuals", "captions", "audio", "render"].map((st) => h("button", { class: "btn sm", disabled: running, onclick: async () => { try { await startStage(st, st === "render" ? "export" : st); } catch (e) { toast(e.message, "bad"); } } },
        icon("refresh", 12), "Re-run " + S.caps.stages.find((x) => x.id === st).label)))));

  // ---- gameplay footage ----
  const layout = settings.footage_layout || "off", clipId = settings.footage_id || "";
  const fileIn = h("input", { type: "file", accept: "video/*,.mp4,.mov,.m4v,.webm,.mkv", multiple: true, class: "hidden", onchange: async (e) => {
    if (!e.target.files.length) return;
    const fd = new FormData();
    [...e.target.files].forEach((f) => fd.append("files", f));
    toast("Uploading… large clips can take a minute");
    try {
      const res = await fetch("/api/footage", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");
      if (data.problems?.length) toast(data.problems.join(" "), "bad");
      await saveSetting("footage_id", data.added[0].id);
      if (layout === "off") await saveSetting("footage_layout", "split");
      toast("Clip added and selected", "ok");
      window.__rerender();
    } catch (err) { toast(err.message, "bad"); }
  } });
  const mmss = (t) => `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, "0")}`;
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Gameplay footage"),
      h("div", { class: "small muted" }, "Put your own screen recording (Roblox, Minecraft, anything) behind the story, the way many story videos on TikTok and Shorts do."))),
    field("Layout", select([["off", "Off"], ["split", "Split: story + footage"], ["full", "Full screen footage"]], layout,
      async (v) => { await saveSetting("footage_layout", v); window.__rerender(); })),
    h("div", { class: "small muted", style: { marginTop: "6px" } }, layout === "split" ? "The story's scenes play on the top half, your clip on the bottom half, and the captions sit on the line between them."
      : layout === "full" ? "Your clip fills the screen and the story is told by voice, captions and sound. The story scenes are not drawn, so these videos render much faster."
      : "The app draws the story scenes itself."),
    layout !== "off" && !clips.some((c) => c.id === clipId) ? h("div", { class: "notice warn", style: { marginTop: "10px" } }, clips.length ? "Pick one of your clips below, or the video will be made without footage." : "Upload a clip below, or the video will be made without footage.") : null,
    h("div", { class: "grid", style: { gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", marginTop: "12px" } },
      clips.map((c) => h("div", { class: "story-shot", style: { outline: c.id === clipId ? "2px solid var(--accent, #7c5cff)" : "none", borderRadius: "12px", padding: "6px" } },
        c.thumb_url ? h("img", { class: "thumb", src: c.thumb_url, alt: c.name }) : h("div", { class: "thumb" }),
        h("div", { class: "tiny", style: { marginTop: "4px", overflowWrap: "anywhere" } }, c.name),
        h("div", { class: "tiny muted" }, `${mmss(c.duration)} · ${c.width}×${c.height} · ${c.size_mb} MB`),
        h("div", { class: "row gap-s", style: { marginTop: "6px" } },
          h("button", { class: "btn sm" + (c.id === clipId ? " primary" : ""), onclick: async () => { await saveSetting("footage_id", c.id); window.__rerender(); } }, c.id === clipId ? "In use" : "Use this"),
          h("button", { class: "btn sm", title: "Delete this clip", onclick: async () => { try { await del(`/api/footage/${c.id}`); S.caps.settings = await fetch("/api/settings").then((x) => x.json()); window.__rerender(); } catch (e) { toast(e.message, "bad"); } } }, icon("trash", 12))))),
      h("button", { class: "btn", style: { minHeight: "120px" }, onclick: () => fileIn.click() }, icon("plus", 16), clips.length ? "Add a clip" : "Upload a clip")),
    fileIn,
    h("div", { class: "small muted", style: { marginTop: "10px" } }, "Best: a vertical (portrait) phone recording that is longer than your video, so it does not repeat. Wide recordings are cropped to the middle. Only use footage you recorded yourself or have permission to use. The app never connects to Roblox or any game; it only uses the files you upload here.")));

  // ---- per-scene report ----
  if (r.scenes && r.scenes.length) {
    root.append(h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Render report"), h("div", { class: "small muted" }, "How each scene was actually produced."))),
      h("table", { class: "t" }, h("thead", h("tr", h("th", "Scene"), h("th", "Length"), h("th", "Produced by"), h("th", "Note"))),
        h("tbody", r.scenes.map((s) => h("tr", h("td", `${s.scene.replace("s", "#")} · ${s.title}`), h("td", s.duration.toFixed(1) + " s"),
          h("td", h("span", { class: "badge " + (s.fallback_reason ? "warn" : "ok") }, s.source)), h("td", { class: "small muted" }, s.fallback_reason || ""))))),
      p.audio_report ? h("div", { class: "small muted", style: { marginTop: "10px" } }, `Audio mix: ${p.audio_report.voice_lines} voice lines, ${p.audio_report.sfx.length} sound effects, music per scene · peak ${p.audio_report.peak}`) : null));
  }

  // ---- storyboard ----
  const sb = files.filter((f) => f.kind === "image" && f.name.includes("storyboard")).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  if (sb.length) root.append(h("div", { class: "card" }, h("h3", { style: { marginBottom: "12px" } }, "Storyboard"),
    h("div", { class: "grid", style: { gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))" } }, sb.map((f) => h("div", { class: "story-shot" }, h("img", { class: "thumb", src: f.url + "?v=" + f.created, alt: f.name }), h("div", { class: "tiny muted", style: { marginTop: "4px" } }, f.name.replace(" - storyboard.png", "")))))));

  // ---- activity log ----
  const j = S.job;
  if (j && j.project_id === S.pid && (j.logs || []).length) root.append(h("div", { class: "card" }, h("h3", { style: { marginBottom: "8px" } }, "Activity log"), h("div", { class: "log" }, j.logs.join("\n"))));
}
