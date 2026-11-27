import { post, put } from "../api.js";
import { S, selectProject, loadProjects, startRun, startStage, isRunning, track, refresh, stageStatus } from "../state.js";
import { h, icon, toast, field, select, toggle, slider, copyBtn, busy, title, empty } from "../ui.js";

const REVIEW_STAGES = ["story", "characters", "script", "voices"];
const draft = { pid: null, idea: "", options: defaults(), review: false, concepts: null, conceptInfo: null, written: null };

function defaults() {
  return { genre: "comedy", tone: "silly", length: "standard", duration: 30, num_characters: 3, audience: "everyone", setting: "", humour: 70, twist: 60, narrator: true, style_id: "", art_style: "blocky" };
}
function syncDraft() {
  const p = S.project;
  if (p && draft.pid !== p.id) {
    draft.pid = p.id; draft.idea = p.idea || ""; draft.options = { ...defaults(), ...(p.options || {}) }; draft.concepts = null; draft.written = null;
  }
}

async function ensureProject() {
  // Never overwrite a finished story: make a fresh project instead.
  if (S.project && !S.project.story) return S.project.id;
  const p = await post("/api/projects", { name: "New story", idea: draft.idea, options: draft.options });
  draft.pid = p.id;
  await loadProjects();
  await selectProject(p.id);
  return p.id;
}

async function generate() {
  const idea = draft.idea.trim();
  if (!idea) { toast("Type a story idea first, e.g. “a funny story about a town where everyone turns into an animal at midnight”."); return; }
  await ensureProject();
  await startRun({ from: "story", to: "export", fresh: true, idea, options: draft.options, pause_after: draft.review ? REVIEW_STAGES : [] });
}

async function previewConcepts(btn) {
  const idea = draft.idea.trim();
  if (!idea) { toast("Type a story idea first."); return; }
  const r = await post("/api/story/concepts", { idea, options: draft.options, n: 5 });
  draft.concepts = r.concepts; draft.conceptInfo = r;
  window.__rerender();
}

async function useConcept(c) {
  await ensureProject();
  await post(`/api/projects/${S.pid}/story/choose`, { story: c });
  draft.concepts = null;
  await startRun({ from: "characters", to: "export", idea: draft.idea, options: draft.options, pause_after: draft.review ? REVIEW_STAGES : [] });
}

async function writeFromPrompt() {
  const prompt = draft.idea.trim();
  if (!prompt) { toast("Type your prompt first: say what you want, e.g. “a spooky story about a school where the lights go out at 3pm, 4 characters, sad ending”."); return; }
  draft.concepts = null;
  try {
    const r = await post("/api/story/from-prompt", { prompt, options: draft.options });
    for (const a of r.applied || []) draft.options[a.key] = a.value;          // the settings the prompt asked for
    draft.written = r;
  } catch (e) {
    draft.written = { error: e.message };
  }
  window.__rerender();
  setTimeout(() => { const c = document.querySelector(".card.written, .card.written-err"); if (c) c.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, 60);
}

function writtenCard() {
  const w = draft.written;
  const close = h("button", { class: "btn sm ghost", onclick: () => { draft.written = null; window.__rerender(); } }, icon("x", 14));
  if (w.error) {
    const noAi = /not connected/i.test(w.error);
    return h("div", { class: "card written-err" },
      h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", noAi ? "The AI writer is not connected" : "Could not write the story")), close),
      h("div", { class: "notice " + (noAi ? "warn" : "bad") }, icon("alert", 18), h("div", w.error)),
      noAi ? h("div", { class: "row", style: { marginTop: "12px" } }, h("button", { class: "btn primary", onclick: () => (location.hash = "#/settings") }, icon("gear", 15), "Open Settings")) : null);
  }
  const st = w.story;
  const row = (label, text) => text ? h("div", { class: "col", style: { gap: "2px" } }, h("div", { class: "tiny muted", style: { fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em" } }, label), h("div", text)) : null;
  return h("div", { class: "card written" },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Written from your prompt"),
      h("div", { class: "small muted" }, `Story by ${w.label}. ${w.interpretation || ""}`)), close),
    (w.applied || []).length ? h("div", { class: "row wrap gap-s", style: { marginBottom: "12px" } },
      h("span", { class: "small muted" }, "Your prompt set:"), w.applied.map((a) => h("span", { class: "badge info" }, `${a.label}: ${typeof a.value === "string" ? title(String(a.value).replace(/_/g, " ")) : a.value}`))) : null,
    h("h2", { style: { margin: "0 0 4px" } }, st.title),
    h("div", { style: { marginBottom: "12px" } }, st.logline),
    h("div", { class: "grid g2" }, row("Hook", st.hook_line), row("The strange idea", st.rule), row("Twist", st.twist), row("Ending", st.ending)),
    h("div", { class: "row wrap", style: { marginTop: "16px" } },
      h("button", { class: "btn primary", disabled: isRunning(), onclick: async () => { try { const c = w.story; draft.written = null; await useConcept(c); } catch (e) { toast(e.message, "bad"); } } }, icon("spark", 15), "Make the video from this story"),
      h("button", { class: "btn", disabled: isRunning(), onclick: async (e) => { const b = e.currentTarget; b.disabled = true; b.innerHTML = '<span class="spinner dark"></span> Writing…'; await writeFromPrompt(); } }, icon("refresh", 15), "Write a different one")));
}

function lookPicker(o) {
  const caps = S.caps;
  const looks = caps.looks || [];
  const imgActive = caps.providers.image.providers.find((x) => x.active);
  const aiImages = ["ai_images", "ai_video"].includes(caps.settings.visual_mode) && !(imgActive && imgActive.offline);
  const chosen = looks.find((l) => l.id === o.art_style) || looks[0];
  const cards = looks.map((l) => h("button", { type: "button", class: "look" + (l.id === o.art_style ? " sel" : ""), "aria-pressed": String(l.id === o.art_style),
    onclick: () => { o.art_style = l.id; window.__rerender(); } },
    l.procedural ? h("img", { src: `/api/looks/${l.id}/preview.png`, alt: "", loading: "lazy" }) : h("div", { class: "look-ai" }, icon("spark", 26), h("span", "Made by AI images")),
    h("b", l.label.replace(" (needs AI images)", "")), h("span", { class: "tiny muted" }, l.blurb)));
  return h("div", { style: { marginTop: "16px" } },
    h("div", { class: "f" }, h("span", "Art style ", h("span", { class: "hint" }, "how the video looks")),
      h("div", { class: "looks" }, cards)),
    chosen && !chosen.procedural ? h("div", { class: "notice " + (aiImages ? "" : "warn"), style: { marginTop: "10px" } }, icon(aiImages ? "check" : "alert", 18),
      h("div", aiImages ? `${chosen.label.replace(" (needs AI images)", "")} pictures will be made by your AI image provider.`
        : `${chosen.label.replace(" (needs AI images)", "")} needs an AI image provider (an OpenAI key, then Visual mode set to “AI keyframe images” on the Render page). Without it the video is drawn in the built-in ${chosen.fallback} look instead, and the project says so.`)) : null);
}

export function render(root) {
  syncDraft();
  const p = S.project;
  const E = S.caps.enums;
  const running = isRunning();
  const llm = S.caps.providers.llm.providers.find((x) => x.active);

  root.append(h("div", { class: "page-head" }, h("h1", "Story Generator"),
    h("p", "Describe an idea, press one button, and the engine writes the story, designs characters and worlds, writes the script, records voiceovers, and renders a vertical 1080×1920 MP4.")));

  // ---- hero ----
  const idea = h("textarea", { class: "big", placeholder: "Write your idea or a full prompt, e.g. a funny story about a town where everyone turns into a different animal every time the clock strikes twelve, 3 characters, happy ending.", rows: 3 });
  idea.value = draft.idea;
  idea.addEventListener("input", () => (draft.idea = idea.value));
  const o = draft.options;
  const set = (k) => (v) => (draft.options[k] = v);
  const styleOpts = [["", "None"], ...S.styles.map((s) => [s.id, s.name])];
  const goBtn = h("button", { class: "btn go", onclick: async (e) => { try { await generate(); } catch (err) { toast(err.message, "bad"); } } },
    icon("spark", 20), running ? "Working…" : "GENERATE STORY");
  if (running) goBtn.disabled = true;
  const promptBtn = h("button", { class: "btn primary", title: "The AI reads your text as a brief and invents a new story from it" }, icon("wand", 16), "Write story from my prompt");
  promptBtn.onclick = async () => { const old = promptBtn.innerHTML; promptBtn.disabled = true; promptBtn.innerHTML = '<span class="spinner"></span> Writing…'; try { await writeFromPrompt(); } finally { promptBtn.disabled = false; promptBtn.innerHTML = old; } };
  const conceptBtn = h("button", { class: "btn" }, icon("wand", 16), "Preview concept ideas first");
  conceptBtn.onclick = async () => { const old = conceptBtn.innerHTML; conceptBtn.disabled = true; conceptBtn.innerHTML = '<span class="spinner dark"></span> Thinking…'; try { await previewConcepts(); } catch (e) { toast(e.message, "bad"); conceptBtn.disabled = false; conceptBtn.innerHTML = old; } };

  root.append(h("div", { class: "card hero" },
    llm.offline ? h("div", { class: "notice warn", style: { marginBottom: "14px" } }, icon("alert", 18),
      h("div", h("b", "No AI writer is connected, so no AI is writing your story. "), "The built-in generator can only slot the words you type into a template, which is why your idea comes back almost as you typed it. ",
        "Connect Claude, or a free AI such as Google Gemini or Ollama (see Settings), and restart the app to get a story actually written from your idea.")) : null,
    field("Your story idea or prompt", idea),
    h("div", { class: "grid g4", style: { marginTop: "14px" } },
      field("Genre", select(E.genres, o.genre, set("genre"))),
      field("Tone", select(E.tones, o.tone, set("tone"))),
      field("Video duration", select(E.durations.map((d) => [d, d + " seconds"]), o.duration, (v) => (o.duration = +v))),
      field("Story length", select(E.lengths.map((l) => [l, title(l) + " (more scenes = longer)"]), o.length, set("length"))),
      field("Characters", select([1, 2, 3, 4, 5].map((n) => [n, n + (n === 1 ? " character" : " characters")]), o.num_characters, (v) => (o.num_characters = +v))),
      field("Target audience", select(E.audiences, o.audience, set("audience"))),
      field("Setting", h("input", { type: "text", value: o.setting, placeholder: "optional: school, forest, city…", oninput: (e) => (o.setting = e.target.value) })),
      field("Style profile", select(styleOpts, o.style_id, set("style_id")), "from References")),
    lookPicker(o),
    h("div", { class: "grid g3", style: { marginTop: "14px", alignItems: "end" } },
      slider("Humour level", o.humour, 0, 100, 5, set("humour"), (v) => v + "%"),
      slider("Twist intensity", o.twist, 0, 100, 5, set("twist"), (v) => v + "%"),
      h("div", { class: "col gap-s" }, toggle("Narrator voice", o.narrator, set("narrator")),
        toggle("Pause for review between steps", draft.review, (v) => (draft.review = v)))),
    h("div", { class: "actions" }, goBtn, promptBtn, conceptBtn),
    h("div", { class: "small muted", style: { marginTop: "10px" } },
      llm.offline ? "Writer: offline generator — lower quality than a real LLM; add an LLM key in .env for better stories. " : `Writer: ${llm.label}. `,
      draft.review ? "The pipeline will pause after the story, characters, script and voices so you can edit each before continuing." : "Runs the whole pipeline automatically; you can still edit any stage afterwards.")));

  if (draft.written) root.append(writtenCard());

  // ---- concept picker ----
  if (draft.concepts) {
    root.append(h("div", { class: "card" },
      h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Pick a concept"), h("div", { class: "small muted" }, `${draft.concepts.length} fresh takes on your idea (${draft.conceptInfo.offline ? "offline generator" : draft.conceptInfo.provider}).`)),
        h("button", { class: "btn sm ghost", onclick: () => { draft.concepts = null; window.__rerender(); } }, icon("x", 14))),
      h("div", { class: "grid gauto" }, draft.concepts.map((c) => h("div", { class: "card", style: { boxShadow: "none", display: "flex", flexDirection: "column", gap: "8px" } },
        h("h3", c.title), h("div", { class: "small" }, c.logline),
        h("div", { class: "tiny muted" }, h("b", "Twist: "), c.twist), h("div", { class: "tiny muted" }, h("b", "Ending: "), c.ending),
        c.originality ? h("span", { class: "badge info" }, `Originality ${c.originality}/10`) : null,
        h("button", { class: "btn primary sm", style: { marginTop: "auto" }, onclick: async () => { try { await useConcept(c); } catch (e) { toast(e.message, "bad"); } } }, "Build this one"))))));
  }

  if (!p) {
    if (!draft.concepts && !draft.written) root.append(h("div", { class: "card" }, empty("spark", "Nothing generated yet", "Type an idea above and press GENERATE STORY.")));
    return;
  }

  // ---- story card ----
  if (p.story) root.append(storyCard(p));
  else if (!running) root.append(h("div", { class: "card" }, empty("book", "This project has no story yet", "Type an idea above and press GENERATE STORY.")));

  // ---- pipeline controls ----
  if (p.story) root.append(controls(p));

  // ---- viral ----
  if (p.evaluation) root.append(viralCard(p));
}

function storyCard(p) {
  const st = { ...p.story };
  const F = (k, label, rows = 2) => {
    const ta = h("textarea", { rows, style: { minHeight: "0" } }); ta.value = st[k] || ""; ta.addEventListener("input", () => (st[k] = ta.value)); return field(label, ta);
  };
  const t = h("input", { type: "text", value: st.title }); t.addEventListener("input", () => (st.title = t.value));
  return h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Story concept"),
      h("div", { class: "small muted" }, `${title(st.genre)} · ${title(st.tone)} · written by ${st.source === "offline" ? "the offline generator" : "your LLM"}`)),
      st.locked ? h("span", { class: "badge info" }, "Edited / locked") : null),
    h("div", { class: "grid g2" }, field("Title", t), F("hook_line", "Hook line (first 1–2 seconds)", 1),
      F("logline", "Logline"), F("premise", "Premise"), F("rule", "The rule / strange idea"), F("twist", "Twist"), F("ending", "Ending"), F("comment_bait", "Comment bait")),
    h("div", { class: "row", style: { marginTop: "14px" } },
      h("button", { class: "btn", onclick: async (e) => {
        try { await put(`/api/projects/${S.pid}/story`, st); await refresh(); toast("Story saved. Later stages are marked out of date.", "ok"); } catch (err) { toast(err.message, "bad"); }
      } }, icon("check", 15), "Save story"),
      h("button", { class: "btn primary", disabled: isRunning(), onclick: async () => {
        try { await put(`/api/projects/${S.pid}/story`, st); await startRun({ from: "characters", to: "export" }); } catch (err) { toast(err.message, "bad"); }
      } }, icon("refresh", 15), "Save & rebuild everything from this story")));
}

function controls(p) {
  const stages = S.caps.stages;
  const first = stages.find((s) => !["done", "review"].includes(p.stages?.[s.id]?.status || "idle"));
  const row = h("div", { class: "row wrap gap-s" }, stages.map((s) => h("button", { class: "btn sm", disabled: isRunning(), title: "Re-run just this stage",
    onclick: async () => { try { await startStage(s.id); } catch (e) { toast(e.message, "bad"); } } }, icon("refresh", 12), s.label)));
  return h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Pipeline controls"), h("div", { class: "small muted" }, "Re-run a single stage, or continue where the pipeline stopped. Editing a stage marks everything after it out of date.")),
      first ? h("button", { class: "btn primary sm", disabled: isRunning(), onclick: async () => { try { await startRun({ from: first.id, to: "export" }); } catch (e) { toast(e.message, "bad"); } } }, icon("play", 13), `Continue from “${first.label}”`) : h("span", { class: "badge ok" }, "All stages complete")),
    row);
}

function viralCard(p) {
  const e = p.evaluation;
  const circ = 2 * Math.PI * 50;
  const col = e.overall >= 80 ? "#19b37a" : e.overall >= 65 ? "#6c5ce7" : "#e89b0c";
  const ring = h("div", { class: "ring" });
  ring.innerHTML = `<svg width="118" height="118" viewBox="0 0 118 118"><circle cx="59" cy="59" r="50" fill="none" style="stroke:var(--soft)" stroke-width="11"/><circle cx="59" cy="59" r="50" fill="none" stroke="${col}" stroke-width="11" stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${circ * (1 - e.overall / 100)}" style="transition:stroke-dashoffset .8s ease"/></svg><b>${e.overall}</b>`;
  const crit = Object.entries(e.criteria).map(([k, v]) => h("div", { class: "crit" }, h("span", (e.labels && e.labels[k]) || title(k)), h("div", { class: "track" }, h("div", { class: v < 65 ? "low" : "", style: { width: v + "%" } })), h("b", v)));
  const list = (items, mapper) => h("div", { class: "col gap-s" }, items.map(mapper));
  const box = (txt) => h("div", { class: "listbox" }, txt, copyBtn(txt));
  return h("div", { class: "card" },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Viral optimisation"), h("div", { class: "small muted" }, `Scored by ${e.method === "llm" ? "your LLM critic" : "transparent script heuristics"} · pass mark ${e.threshold} · ${e.rewrites || 0} auto-rewrite(s)`)),
      h("button", { class: "btn sm", disabled: isRunning(), onclick: async () => { try { await startStage("score"); } catch (err) { toast(err.message, "bad"); } } }, icon("refresh", 13), "Re-score"),
      h("button", { class: "btn sm primary", disabled: isRunning() || !(e.improvements || []).length, onclick: async () => { try { track(await post(`/api/projects/${S.pid}/score/apply`)); } catch (err) { toast(err.message, "bad"); } } }, icon("wand", 13), "Apply improvements & re-score")),
    h("div", { class: "row gap-l wrap", style: { alignItems: "flex-start" } }, ring, h("div", { class: "grow", style: { minWidth: "260px" } }, crit)),
    (e.history || []).length > 1 ? h("div", { class: "small muted", style: { marginTop: "6px" } }, "Score history: " + e.history.join(" → ")) : null,
    h("div", { class: "grid g2", style: { marginTop: "16px" } },
      h("div", { class: "col" }, h("h3", "What to improve"), (e.improvements || []).length ? list(e.improvements, (x) => h("div", { class: "notice warn" }, x)) : h("div", { class: "notice ok" }, "No critical weaknesses found."),
        (e.strengths || []).length ? h("div", { class: "small muted" }, "Strengths: " + e.strengths.join(" · ")) : null),
      h("div", { class: "col" }, h("h3", "3 alternative hooks"), list(e.alt_hooks || [], box), h("h3", { style: { marginTop: "6px" } }, "3 titles"), list(e.titles || [], box))),
    h("div", { class: "grid g2", style: { marginTop: "14px" } },
      h("div", { class: "col gap-s" }, h("h3", "Description"), box(e.description || "")),
      h("div", { class: "col gap-s" }, h("h3", "Pinned comment"), box(e.pinned_comment || ""), h("h3", { style: { marginTop: "6px" } }, "Hashtags"), box((e.hashtags || []).join(" ")))),
    h("div", { class: "small muted", style: { marginTop: "12px" } }, e.disclaimer));
}
