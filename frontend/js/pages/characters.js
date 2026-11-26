import { put, post } from "../api.js";
import { S, refresh, startStage, isRunning } from "../state.js";
import { h, icon, toast, field, select, empty, title } from "../ui.js";

let sel = null;          // selected character id
let working = null;      // edited copy

function sheetUrl(c) {
  const f = (S.files_cache || []).find((x) => x.kind === "character_sheet" && x.name.startsWith(c.name + " "));
  return f ? `/files/${f.id}?v=${f.created || ""}` : null;
}

export async function render(root) {
  const p = S.project;
  root.append(h("div", { class: "page-head" }, h("h1", "Character Engine"),
    h("p", "Each character is one fixed spec — body, hair, outfit, accessory, face — that drives the reference sheet and every scene, so they look identical from the first shot to the last. Edit anything and re-render.")));
  if (!p || !p.characters.length) {
    root.append(h("div", { class: "card" }, empty("user", "No characters yet", "Generate a story first (Story Generator).")));
    return;
  }
  const files = await fetch(`/api/files?project=${S.pid}&kind=character_sheet`).then((r) => r.json());
  S.files_cache = files;
  const chars = p.characters;
  if (!sel || !chars.find((c) => c.id === sel)) sel = chars[0].id;
  const cur = chars.find((c) => c.id === sel);
  if (!working || working.id !== sel || working._src !== JSON.stringify(cur)) { working = JSON.parse(JSON.stringify(cur)); working._src = JSON.stringify(cur); }

  root.append(h("div", { class: "tabs" }, chars.map((c) => h("button", { class: "tab " + (c.id === sel ? "on" : ""), onclick: () => { sel = c.id; window.__rerender(); } }, c.name + (c.is_narrator ? " (narrator)" : "")))));
  root.append(h("div", { class: "grid", style: { gridTemplateColumns: "minmax(260px, 420px) 1fr", alignItems: "start" } },
    h("div", { class: "col" }, h("div", { class: "card" },
      sheetUrl(cur) && !cur.is_narrator ? h("img", { class: "sheet", src: sheetUrl(cur), alt: cur.name + " reference sheet" }) : empty("user", cur.is_narrator ? "The narrator is voice-only" : "No sheet yet", cur.is_narrator ? "Narrators don't appear on screen." : "Save to render a sheet."),
      cur.visual_prompt ? h("div", { class: "small muted", style: { marginTop: "10px" } }, h("b", "Image prompt (reused verbatim for every AI image): "), cur.visual_prompt) : null)),
    cur.is_narrator ? narratorForm(cur) : editor(p)));
}

function narratorForm(c) { return h("div", { class: "card" }, h("h3", "Narrator"), h("p", { class: "muted" }, "Set the narrator's voice in the Voice Generator.")); }

function editor(p) {
  const E = S.caps.enums;
  const w = working;
  const text = (k, label, ph) => field(label, h("input", { type: "text", value: w[k] || "", placeholder: ph || "", oninput: (e) => (w[k] = e.target.value) }));
  const color = (k, label) => {
    const hex = h("span", { class: "small muted" }, w[k]);
    return h("label", { class: "f" }, h("span", label), h("div", { class: "row gap-s" },
      h("input", { type: "color", value: w[k], oninput: (e) => { w[k] = e.target.value; hex.textContent = w[k]; } }), hex));
  };
  const sel2 = (k, label, opts) => field(label, select(opts, w[k], (v) => (w[k] = v)));
  const personality = h("textarea", { rows: 2, oninput: (e) => (w.personality = e.target.value) }); personality.value = w.personality || "";

  const save = async (rerun) => {
    const out = p.characters.map((c) => (c.id === w.id ? (() => { const x = { ...w }; delete x._src; return x; })() : c));
    try {
      await put(`/api/projects/${S.pid}/characters`, out);
      await refresh();
      toast("Character saved and sheet re-rendered", "ok");
    } catch (e) { toast(e.message, "bad"); }
  };
  return h("div", { class: "card" },
    h("div", { class: "grid g2" },
      text("name", "Name"), sel2("role", "Role", E.roles),
      sel2("age_look", "Age look", E.age_looks), sel2("build", "Build", E.builds),
      sel2("hair_style", "Hair style", E.hair_styles), sel2("accessory", "Accessory", E.accessories),
      sel2("shirt_pattern", "Shirt pattern", E.shirt_patterns), sel2("eyes", "Eyes", E.eyes),
      sel2("signature_expression", "Signature expression", E.emotions)),
    h("div", { class: "row wrap gap-l", style: { margin: "14px 0" } },
      color("skin", "Skin"), color("hair_color", "Hair"), color("shirt_color", "Shirt"), color("pants_color", "Pants"), color("shoes_color", "Shoes"), color("accessory_color", "Accessory")),
    field("Personality", personality),
    h("div", { class: "row", style: { marginTop: "14px" } },
      h("button", { class: "btn primary", onclick: () => save() }, icon("check", 15), "Save & re-render sheet"),
      h("span", { class: "small muted" }, "Changing a character marks voices and visuals out of date.")));
}
