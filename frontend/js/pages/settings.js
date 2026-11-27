import { post, put } from "../api.js";
import { S, loadCaps } from "../state.js";
import { h, icon, toast, field, select, toggle, slider, title } from "../ui.js";
import { getMode, setTheme } from "../theme.js";
import { showUpdates, showReleases } from "../updates.js";

const KINDS = [
  ["llm", "Story writer (LLM)", "Writes the story, characters, script and the viral critique."],
  ["tts", "Voices (text-to-speech)", "Records every line of dialogue."],
  ["image", "Images", "Optional AI keyframes for scenes (visual mode “AI keyframe images”)."],
  ["video", "Video", "Optional AI video clips for scenes (visual mode “AI video clips”)."],
];

export function render(root) {
  const caps = S.caps, st = caps.settings;
  root.append(h("div", { class: "page-head" }, h("h1", "Settings"),
    h("p", "Connect providers and tune the pipeline. API keys are read by the app itself and are never sent to this page. After editing your .env file, restart the app.")));

  const NAMES = { ANTHROPIC_API_KEY: "Anthropic Claude", ELEVENLABS_API_KEY: "ElevenLabs", OPENAI_API_KEY: "OpenAI", RUNWAY_API_KEY: "Runway" };
  if (caps.shared_keys && caps.shared_keys.length) {
    root.append(h("div", { class: "notice warn", style: { marginBottom: "16px" } }, icon("alert", 18), h("div",
      h("b", "Shared keys are in use: "), caps.shared_keys.map((k) => NAMES[k] || k).join(", "), ". They came built into this app from whoever made it, and what you generate is billed to their account, so keep it to what you need. To use your own key instead, add it to ",
      h("code", caps.env_file || ".env"), " and restart the app; your key takes priority.")));
  }
  root.append(h("div", { class: "notice", style: { marginBottom: "16px" } }, icon("check", 18), caps.env_file
    ? h("div", h("b", "How to connect your own provider: "), "open ", h("code", caps.env_file), " in Notepad (create it if it is missing), add a line such as ", h("code", "ANTHROPIC_API_KEY=your-key"), ", save, then restart the app. The status below turns green when the key is detected.")
    : h("div", h("b", "How to connect a provider: "), "copy ", h("code", ".env.example"), " to ", h("code", ".env"), ", paste the key next to its name, then restart ", h("code", "python run.py"), ". The status below turns green when the key is detected.")));

  const THEMES = [["system", "monitor", "Match system"], ["light", "sun", "Light"], ["dark", "moon", "Dark"]];
  root.append(h("div", { class: "card", style: { marginBottom: "16px" } },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Appearance"), h("div", { class: "small muted" }, "Pick a light or dark look, or follow your device."))),
    h("div", { class: "seg", role: "group", "aria-label": "Theme" }, THEMES.map(([id, ic, label]) =>
      h("button", { class: getMode() === id ? "on" : "", "aria-pressed": getMode() === id ? "true" : "false", onclick: async () => { await setTheme(id); window.__rerender(); } }, icon(ic, 15), label)))));

  if (caps.auth && caps.auth.enabled) {
    const a = caps.auth;
    root.append(h("div", { class: "card", style: { marginBottom: "16px" } },
      h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Account"),
        h("div", { class: "small muted" }, `Signed in as ${a.user || "?"}. ` + (a.run_limit ? `${a.runs_today} of ${a.run_limit} video runs used today (resets at midnight UTC).` : "No daily run limit.") + " Everyone shares the same projects.")),
        h("button", { class: "btn", onclick: async () => { try { await post("/api/logout"); } catch (e) { /* signing out anyway */ } location.href = "/login"; } }, "Sign out"))));
  }

  KINDS.forEach(([kind, label, sub]) => {
    const group = caps.providers[kind];
    const key = kind + "_provider";
    root.append(h("div", { class: "card" },
      h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", label), h("div", { class: "small muted" }, sub)),
        h("div", { style: { width: "250px" } }, select([["auto", "Automatic (first connected)"], ...group.providers.map((p) => [p.name, p.label])], st[key], async (v) => {
          await put("/api/settings", { [key]: v }); await loadCaps(); window.__rerender(); toast("Saved", "ok");
        }))),
      h("table", { class: "t" }, h("thead", h("tr", h("th", "Provider"), h("th", "Status"), h("th", "Environment variables"), h("th", ""))),
        h("tbody", group.providers.map((p) => {
          const out = h("span", { class: "tiny muted" });
          return h("tr",
            h("td", h("b", p.label), p.active ? h("span", { class: "badge info", style: { marginLeft: "8px" } }, "in use") : null),
            h("td", p.offline ? h("span", { class: "badge" }, "built in") : p.configured ? h("span", { class: "badge ok" }, "key found") : h("span", { class: "badge warn" }, "not connected")),
            h("td", { class: "small" }, p.env_keys.length ? p.env_keys.map((k) => h("code", { style: { marginRight: "6px" } }, k)) : h("span", { class: "muted" }, "none needed")),
            h("td", p.offline ? "" : h("div", { class: "row gap-s" }, h("button", { class: "btn sm", disabled: !p.configured, onclick: async (e) => {
              const b = e.currentTarget; b.disabled = true; out.textContent = "Testing…";
              try { const r = await post(`/api/providers/${kind}/${p.name}/test`); out.textContent = (r.ok ? "✔ " : "✖ ") + r.message; out.style.color = r.ok ? "var(--ok)" : "var(--bad)"; } catch (err) { out.textContent = err.message; }
              b.disabled = false;
            } }, "Test"), out)));
        })))));
  });

  const save = async (k, v) => { try { await put("/api/settings", { [k]: v }); await loadCaps(); } catch (e) { toast(e.message, "bad"); } };
  root.append(h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Viral optimisation"), h("div", { class: "small muted" }, "The script is scored on hook, curiosity, entertainment, clarity, pacing, surprise, ending and replay value."))),
    h("div", { class: "grid g3", style: { alignItems: "end" } },
      slider("Pass mark", st.viral_threshold, 30, 95, 1, (v) => save("viral_threshold", v), (v) => v + "/100"),
      slider("Max automatic rewrites", st.max_rewrites, 0, 3, 1, (v) => save("max_rewrites", v)),
      toggle("Automatically rewrite weak scripts", st.auto_improve, (v) => save("auto_improve", v))),
    h("div", { class: "small muted", style: { marginTop: "10px" } }, "Scores are estimates of story craft, not predictions. Nobody can promise views.")));

  root.append(h("div", { class: "card" }, h("h3", { style: { marginBottom: "8px" } }, "System"),
    h("div", { class: "small" }, `FFmpeg: ${caps.ffmpeg ? "found" : "NOT FOUND — rendering will fail until FFmpeg is installed"}`),
    h("div", { class: "small muted" }, "Output format: 1080×1920 (9:16), H.264 video, AAC audio, loudness-normalised to −14 LUFS.")));

  root.append(h("div", { class: "card" }, h("h3", { style: { marginBottom: "6px" } }, "Releases"),
    h("div", { class: "small muted" }, (caps.hosted ? "" : `This app is version ${caps.version || "unknown"}. `) + "See every release with what changed, and download the Windows installer, Android app or iPhone file right here."),
    h("div", { class: "row wrap", style: { marginTop: "12px" } },
      h("button", { class: "btn primary", onclick: () => showReleases() }, icon("download", 15), "Releases"),
      caps.hosted ? null : h("button", { class: "btn", onclick: () => showUpdates() }, icon("refresh", 14), "Check for new updates"))));
}
