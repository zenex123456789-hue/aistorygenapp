import { put } from "../api.js";
import { S, refresh, startRun, startStage, isRunning } from "../state.js";
import { h, icon, toast, field, select, empty, title, confirmBox } from "../ui.js";

let working = null, src = "", pid = null;
const open = new Set();
const BEATS = { hook: "Hook", intro: "Introduction", rule: "Rule", escalation: "Escalation", twist: "Twist", ending: "Ending", other: "Other" };

function load(p) {
  const s = JSON.stringify(p.scenes);
  if (pid !== p.id || src !== s) { working = JSON.parse(s); src = s; pid = p.id; }
}
const dirty = () => JSON.stringify(working) !== src;

export function render(root) {
  const p = S.project;
  root.append(h("div", { class: "page-head" }, h("h1", "Script Generator"),
    h("p", "The story broken into the six beats — Hook, Introduction, Rule, Escalation, Twist, Ending — as scenes. Each scene carries dialogue, actions, camera, environment, emotion, timing, voiceover notes, sound effects and a visual prompt. Edit anything, then save.")));
  if (!p || !p.scenes.length) { root.append(h("div", { class: "card" }, empty("script", "No script yet", "Generate a story first."))); return; }
  load(p);
  const chars = p.characters, worlds = p.worlds, E = S.caps.enums;
  const total = working.reduce((a, s) => a + (+s.duration || 0), 0);

  root.append(h("div", { class: "card", style: { padding: "12px 16px" } }, h("div", { class: "row wrap spread" },
    h("div", { class: "row gap-l" }, h("span", { class: "badge info" }, `${working.length} scenes`), h("span", { class: "badge" }, `≈ ${total.toFixed(1)} s planned`),
      h("span", { class: "small muted" }, "Final timing follows the recorded voice lines.")),
    h("div", { class: "row gap-s wrap" },
      h("button", { class: "btn sm", disabled: isRunning(), onclick: async () => { if (dirty() && !(await confirmBox("Discard edits?", "Re-writing the script replaces your unsaved edits.", "Re-write"))) return; try { await startStage("script", "score"); } catch (e) { toast(e.message, "bad"); } } }, icon("refresh", 13), "Re-write script"),
      h("button", { class: "btn sm", onclick: () => { working.push(blank(working.length, chars, worlds)); open.add(working.length - 1); window.__rerender(); } }, icon("plus", 13), "Add scene"),
      h("button", { class: "btn sm", onclick: () => save(false) }, icon("check", 13), "Save script"),
      h("button", { class: "btn sm primary", disabled: isRunning(), onclick: () => save(true) }, icon("film", 13), "Save & re-render video")))));

  root.append(h("div", { style: { marginTop: "14px" } }, working.map((sc, i) => sceneCard(sc, i, chars, worlds, E))));
}

async function save(rerun) {
  try {
    await put(`/api/projects/${S.pid}/scenes`, working);
    await refresh();
    toast("Script saved. Voices and visuals are marked out of date.", "ok");
    if (rerun) await startRun({ from: "score", to: "export" });
  } catch (e) { toast(e.message, "bad"); }
}

function blank(i, chars, worlds) {
  const on = chars.filter((c) => !c.is_narrator);
  return { id: "s" + (i + 1), kind: "escalation", title: "New scene", description: "", location_id: worlds[0].id, characters: on.slice(0, 2).map((c) => c.id),
    actions: [], dialogue: [{ character_id: (on[0] || chars[0]).id, text: "…", emotion: "neutral", delivery: "natural" }], camera: { shot: "medium", move: "push_in", note: "" },
    environment: { time_of_day: "", notes: "", crowd: 0, crowd_form: "" }, emotion: "neutral", duration: 5, voiceover_notes: "", sfx: [], effects: [], on_screen_text: "", music_mood: "", transition: "slide", visual_prompt: "" };
}

function sceneCard(sc, i, chars, worlds, E) {
  const isOpen = open.has(i);
  const charOpts = chars.map((c) => [c.id, c.name]);
  const t = (obj, k, label, rows = 0, attrs = {}) => {
    const inp = rows ? h("textarea", { rows, style: { minHeight: "0" } }) : h("input", { type: "text", ...attrs });
    inp.value = obj[k] || ""; inp.addEventListener("input", () => (obj[k] = inp.value)); return field(label, inp);
  };
  const num = (obj, k, label, min, max, step) => field(label, h("input", { type: "number", min, max, step, value: obj[k] ?? 0, oninput: (e) => (obj[k] = +e.target.value) }));
  const move = (d) => { const j = i + d; if (j < 0 || j >= working.length) return; [working[i], working[j]] = [working[j], working[i]]; open.clear(); open.add(j); window.__rerender(); };

  const dialogue = h("div", {}, sc.dialogue.map((d, di) => h("div", { class: "dl" },
    select(charOpts, d.character_id, (v) => (d.character_id = v)),
    h("input", { type: "text", value: d.text, oninput: (e) => (d.text = e.target.value) }),
    select(E.emotions, d.emotion, (v) => (d.emotion = v)), select(E.deliveries, d.delivery, (v) => (d.delivery = v)),
    h("button", { class: "btn sm ghost danger", onclick: () => { sc.dialogue.splice(di, 1); window.__rerender(); } }, icon("x", 13)))),
    h("button", { class: "btn sm", onclick: () => { sc.dialogue.push({ character_id: (chars.find((c) => !c.is_narrator) || chars[0]).id, text: "…", emotion: "neutral", delivery: "natural" }); window.__rerender(); } }, icon("plus", 13), "Add line"));

  const actions = h("div", {}, sc.actions.map((a, ai) => h("div", { class: "dl", style: { gridTemplateColumns: "130px 130px 90px 140px 30px" } },
    select(chars.filter((c) => !c.is_narrator).map((c) => [c.id, c.name]), a.character_id, (v) => (a.character_id = v)),
    select(E.animations, a.animation, (v) => (a.animation = v)),
    h("input", { type: "number", min: 0, step: 0.1, value: a.at, title: "starts at (s)", oninput: (e) => (a.at = +e.target.value) }),
    select([["", "form: keep"], ["human", "human"], ...E.forms], a.form || "", (v) => (a.form = v)),
    h("button", { class: "btn sm ghost danger", onclick: () => { sc.actions.splice(ai, 1); window.__rerender(); } }, icon("x", 13)))),
    h("button", { class: "btn sm", onclick: () => { sc.actions.push({ character_id: (chars.find((c) => !c.is_narrator) || chars[0]).id, animation: "idle", at: 0, note: "", form: "" }); window.__rerender(); } }, icon("plus", 13), "Add action"));

  const sfx = h("div", {}, sc.sfx.map((s, si) => h("div", { class: "row", style: { marginBottom: "6px" } },
    select(E.sfx, s.name, (v) => (s.name = v)), h("input", { type: "number", min: 0, step: 0.1, value: s.at, style: { width: "90px" }, oninput: (e) => (s.at = +e.target.value) }), h("span", { class: "tiny muted" }, "sec"),
    h("button", { class: "btn sm ghost danger", onclick: () => { sc.sfx.splice(si, 1); window.__rerender(); } }, icon("x", 13)))),
    h("button", { class: "btn sm", onclick: () => { sc.sfx.push({ name: "pop", at: 0, note: "" }); window.__rerender(); } }, icon("plus", 13), "Add sound effect"));

  const castChips = h("div", { class: "row wrap gap-s" }, chars.filter((c) => !c.is_narrator).map((c) => {
    const on = sc.characters.includes(c.id);
    return h("button", { class: "tab " + (on ? "on" : ""), onclick: (e) => { if (sc.characters.includes(c.id)) sc.characters = sc.characters.filter((x) => x !== c.id); else sc.characters.push(c.id); e.target.classList.toggle("on"); } }, c.name);
  }));
  const fxChips = h("div", { class: "row wrap gap-s" }, E.effects.map((f) => h("button", { class: "tab " + (sc.effects.includes(f) ? "on" : ""), style: { padding: "3px 10px", fontSize: "12px" },
    onclick: (e) => { if (sc.effects.includes(f)) sc.effects = sc.effects.filter((x) => x !== f); else if (sc.effects.length < 4) sc.effects.push(f); else return toast("Up to 4 effects per scene"); e.target.classList.toggle("on"); } }, title(f))));

  const body = h("div", { class: "bd" },
    h("div", { class: "grid g3" }, t(sc, "title", "Title"), field("Beat", select(E.scene_kinds.map((k) => [k, BEATS[k] || title(k)]), sc.kind, (v) => (sc.kind = v))), num(sc, "duration", "Planned length (s)", 1.5, 14, 0.5)),
    h("div", { style: { marginTop: "10px" } }, t(sc, "description", "Scene description", 2)),
    h("div", { class: "grid g3", style: { marginTop: "10px" } }, field("Environment", select(worlds.map((w) => [w.id, w.name]), sc.location_id, (v) => (sc.location_id = v))),
      field("Emotion", select(E.emotions, sc.emotion, (v) => (sc.emotion = v))), field("Transition in", select(E.transitions, sc.transition, (v) => (sc.transition = v)))),
    h("div", { class: "grid g3", style: { marginTop: "10px" } }, field("Camera shot", select(E.camera_shots, sc.camera.shot, (v) => (sc.camera.shot = v))), field("Camera move", select(E.camera_moves, sc.camera.move, (v) => (sc.camera.move = v))), t(sc.camera, "note", "Camera direction")),
    h("div", { class: "grid g3", style: { marginTop: "10px" } }, field("Time of day", select([["", "from location"], ...E.times], sc.environment.time_of_day, (v) => (sc.environment.time_of_day = v))),
      num(sc.environment, "crowd", "Background crowd", 0, 8, 1), field("Crowd form", select([["", "human"], ...E.forms], sc.environment.crowd_form, (v) => (sc.environment.crowd_form = v)))),
    h("h3", { style: { margin: "16px 0 6px" } }, "Characters on screen"), castChips,
    h("h3", { style: { margin: "16px 0 6px" } }, "Dialogue"), dialogue,
    h("h3", { style: { margin: "16px 0 6px" } }, "Character actions"), actions,
    h("h3", { style: { margin: "16px 0 6px" } }, "Sound effects"), sfx,
    h("h3", { style: { margin: "16px 0 6px" } }, "Visual effects"), fxChips,
    h("div", { class: "grid g2", style: { marginTop: "14px" } }, t(sc, "voiceover_notes", "Voiceover instructions", 2), t(sc, "visual_prompt", "Visual prompt (used by AI image/video providers)", 2)),
    h("div", { class: "grid g2", style: { marginTop: "10px" } }, t(sc, "on_screen_text", "On-screen text (optional)"), field("Music mood", select([["", "story default"], ...E.music_moods], sc.music_mood, (v) => (sc.music_mood = v)))),
    h("div", { class: "row", style: { marginTop: "14px" } },
      h("button", { class: "btn sm", disabled: i === 0, onclick: () => move(-1) }, "↑ Move up"), h("button", { class: "btn sm", disabled: i === working.length - 1, onclick: () => move(1) }, "↓ Move down"),
      h("button", { class: "btn sm danger", disabled: working.length < 2, onclick: () => { working.splice(i, 1); open.clear(); window.__rerender(); } }, icon("trash", 13), "Delete scene")));

  const hd = h("div", { class: "hd", onclick: () => { open.has(i) ? open.delete(i) : open.add(i); card.classList.toggle("open"); } },
    h("div", { class: "num" }, i + 1), h("div", { class: "grow" }, h("b", sc.title), h("div", { class: "small muted", style: { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } },
      sc.dialogue[0] ? `“${sc.dialogue[0].text}”` : sc.description)),
    h("span", { class: "badge" }, BEATS[sc.kind] || sc.kind), h("span", { class: "badge info" }, (+sc.duration).toFixed(1) + " s"), icon("chevron", 16));
  const card = h("div", { class: "scene" + (isOpen ? " open" : "") }, hd, body);
  return card;
}
