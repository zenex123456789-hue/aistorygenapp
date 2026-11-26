import { post, put } from "../api.js";
import { S, refresh, startStage, isRunning } from "../state.js";
import { h, icon, toast, field, select, slider, empty, title } from "../ui.js";

let voiceInfo = null;
let audioEl = null;

function play(url) {
  if (audioEl) audioEl.pause();
  audioEl = new Audio(url);
  audioEl.play().catch(() => toast("Could not play audio in this browser", "bad"));
}

export async function render(root) {
  const p = S.project;
  root.append(h("div", { class: "page-head" }, h("h1", "Voice Generator"),
    h("p", "Give every character a distinct voice, preview it, then record the whole script. Each line is recorded with its own emotion and delivery, and captions are timed to the audio.")));
  if (!p || !p.characters.length) { root.append(h("div", { class: "card" }, empty("mic", "No characters yet", "Generate a story first."))); return; }
  if (!voiceInfo || voiceInfo._key !== S.caps.providers.tts.providers.find((x) => x.active).name) { voiceInfo = await fetch("/api/voices").then((r) => r.json()); voiceInfo._key = voiceInfo.provider; }
  const E = S.caps.enums;

  if (voiceInfo.offline) {
    root.append(h("div", { class: "notice warn" }, icon("mic", 18), h("div", h("b", "Offline “blip” voices are in use. "),
      "These are synthesised talking blips with exact word timing so captions and lip-sync still line up, but they are not speech and have no real accents. For human-sounding voices set ELEVENLABS_API_KEY or OPENAI_API_KEY in .env and restart (see Settings).")));
  } else {
    root.append(h("div", { class: "notice ok" }, icon("check", 18), h("div", `Using ${voiceInfo.label}. Accents are requested through the provider's voice choice and delivery instructions.`)));
  }

  const running = isRunning();
  const status = p.stages?.voices?.status || "idle";
  root.append(h("div", { class: "row spread", style: { margin: "16px 0" } }, h("div", { class: "row" }, h("span", { class: "badge " + (status === "done" ? "ok" : status === "stale" ? "warn" : "") }, `Voiceovers: ${title(status)}`)),
    h("div", { class: "row gap-s" },
      h("button", { class: "btn sm", onclick: async () => { try { await post(`/api/projects/${S.pid}/voices/auto`); await refresh(); toast("Voices re-assigned automatically", "ok"); } catch (e) { toast(e.message, "bad"); } } }, icon("wand", 13), "Auto-assign voices"),
      h("button", { class: "btn sm primary", disabled: running, onclick: async () => { try { await startStage("voices"); } catch (e) { toast(e.message, "bad"); } } }, icon("mic", 13), "Generate all voiceovers"))));

  root.append(h("div", { class: "grid g2" }, p.characters.map((c) => voiceCard(c, p, E))));

  // ---- recorded lines ----
  const lines = [];
  p.scenes.forEach((s) => s.dialogue.forEach((d) => lines.push({ s, d, a: (p.voice_assets || {})[d.id] })));
  if (lines.some((l) => l.a)) {
    root.append(h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Recorded lines"), h("div", { class: "small muted" }, "Click ▶ to hear each line as it will appear in the video."))),
      h("table", { class: "t" }, h("thead", h("tr", h("th", "Scene"), h("th", "Speaker"), h("th", "Line"), h("th", "Delivery"), h("th", "Length"), h("th", "Timing"), h("th", ""))),
        h("tbody", lines.map(({ s, d, a }) => {
          const ch = p.characters.find((c) => c.id === d.character_id);
          return h("tr", h("td", s.id.replace("s", "#")), h("td", ch ? ch.name : d.character_id), h("td", d.text), h("td", `${d.emotion} · ${d.delivery}`),
            h("td", a ? a.duration.toFixed(1) + " s" : "—"),
            h("td", a ? h("span", { class: "badge " + (a.timing === "exact" ? "ok" : "warn"), title: a.timing === "exact" ? "Word times come from the voice engine" : "Word times are estimated from the audio" }, a.timing) : h("span", { class: "badge warn" }, "not recorded")),
            h("td", a ? h("button", { class: "btn sm ghost", onclick: () => play(`/api/projects/${S.pid}/voice/${d.id}/audio`) }, icon("play", 13)) : ""));
        })))));
  }
}

function voiceCard(c, p, E) {
  const v = c.voice;
  const opts = voiceInfo.voices.map((x) => [x.id, x.name + (x.gender ? ` · ${x.gender}` : "") + (x.accent && x.accent !== "n/a" ? ` · ${x.accent}` : "")]);
  const sample = c.is_narrator ? "Welcome to a town where nothing is ever normal." : (p.scenes.flatMap((s) => s.dialogue).find((d) => d.character_id === c.id)?.text || "Wait, what just happened?");
  const upd = async (patch) => { try { await put(`/api/projects/${S.pid}/voices`, { character_id: c.id, ...patch }); await refresh(true); } catch (e) { toast(e.message, "bad"); } };
  const accent = h("input", { type: "text", value: v.accent || "", placeholder: "e.g. British, Southern US", onchange: (e) => upd({ accent: e.target.value }) });
  const btn = h("button", { class: "btn sm", onclick: async () => {
    const old = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spinner dark"></span>';
    try { const r = await post("/api/voices/preview", { text: sample, voice_id: v.voice_id || voiceInfo.voices[0]?.id, delivery: v.default_delivery, speed: v.speed, pitch: v.pitch, accent: v.accent, emotion: "neutral" }); play(r.url); }
    catch (e) { toast(e.message, "bad"); } finally { btn.disabled = false; btn.innerHTML = old; }
  } }, icon("play", 13), "Preview");
  return h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", c.name), h("div", { class: "small muted" }, c.is_narrator ? "Narrator" : title(c.role) + " · " + (c.personality || ""))), btn),
    h("div", { class: "col" },
      field("Voice", select(opts, v.voice_id || voiceInfo.voices[0]?.id, (x) => upd({ voice_id: x, provider: voiceInfo.provider }))),
      h("div", { class: "grid g2" }, field("Default delivery", select(E.deliveries, v.default_delivery, (x) => upd({ delivery: x }))), field("Accent", accent)),
      h("div", { class: "grid g2" }, slider("Speed", v.speed, 0.7, 1.4, 0.05, (x) => (v.speed = x), (x) => x.toFixed(2) + "×"), slider("Pitch", v.pitch, -1, 1, 0.1, (x) => (v.pitch = x), (x) => (x > 0 ? "+" : "") + x.toFixed(1))),
      h("div", { class: "small muted" }, `“${sample.slice(0, 80)}”`),
      h("button", { class: "btn sm", style: { alignSelf: "flex-start" }, onclick: () => upd({ speed: v.speed, pitch: v.pitch }).then(() => toast("Voice settings saved", "ok")) }, icon("check", 13), "Save speed & pitch")));
}
