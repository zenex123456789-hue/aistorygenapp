import { put } from "../api.js";
import { S, refresh } from "../state.js";
import { h, icon, toast, field, select, empty, title } from "../ui.js";

let sel = null, working = null;

export async function render(root) {
  const p = S.project;
  root.append(h("div", { class: "page-head" }, h("h1", "World & Environment Engine"),
    h("p", "Every location is defined once — kind, time of day, palette, landmark and props — and reused in every scene set there, so the town looks the same each time you come back to it.")));
  if (!p || !p.worlds.length) { root.append(h("div", { class: "card" }, empty("globe", "No locations yet", "Generate a story first."))); return; }
  const files = await fetch(`/api/files?project=${S.pid}&kind=image`).then((r) => r.json());
  const worlds = p.worlds;
  if (!sel || !worlds.find((w) => w.id === sel)) sel = worlds[0].id;
  const cur = worlds.find((w) => w.id === sel);
  if (!working || working.id !== sel || working._src !== JSON.stringify(cur)) { working = JSON.parse(JSON.stringify(cur)); working._src = JSON.stringify(cur); }
  const prev = (w) => files.find((f) => f.name.startsWith(w.name + " - location preview"));
  const used = (w) => p.scenes.filter((s) => s.location_id === w.id).length;

  root.append(h("div", { class: "grid gauto", style: { marginBottom: "18px" } }, worlds.map((w) => h("div", {
    class: "card", style: { cursor: "pointer", padding: "12px", outline: w.id === sel ? "2px solid var(--p1)" : "none", boxShadow: w.id === sel ? "var(--shadow-lg)" : "var(--shadow)" },
    onclick: () => { sel = w.id; window.__rerender(); } },
    prev(w) ? h("img", { class: "thumb", style: { aspectRatio: "16 / 10" }, src: `/files/${prev(w).id}?v=${prev(w).created}`, alt: w.name }) : h("div", { class: "thumb", style: { aspectRatio: "16 / 10" } }),
    h("div", { class: "row spread", style: { marginTop: "9px" } }, h("b", w.name), h("span", { class: "badge" }, `${used(w)} scene${used(w) === 1 ? "" : "s"}`)),
    h("div", { class: "palette", style: { marginTop: "6px" } }, Object.values(w.palette).map((c) => h("span", { class: "swatch", style: { background: c } })))))));

  const E = S.caps.enums, w = working;
  const color = (k, label) => {
    const hex = h("span", { class: "tiny muted" }, w.palette[k]);
    return h("label", { class: "f" }, h("span", label), h("div", { class: "row gap-s" }, h("input", { type: "color", value: w.palette[k], oninput: (e) => { w.palette[k] = e.target.value; hex.textContent = e.target.value; } }), hex));
  };
  const desc = h("textarea", { rows: 2, oninput: (e) => (w.description = e.target.value) }); desc.value = w.description || "";
  const props = h("input", { type: "text", value: (w.props || []).join(", "), oninput: (e) => (w.props = e.target.value.split(",").map((x) => x.trim()).filter(Boolean)) });
  root.append(h("div", { class: "card" },
    h("div", { class: "card-head" }, h("h3", "Edit location")),
    h("div", { class: "grid g3" },
      field("Name", h("input", { type: "text", value: w.name, oninput: (e) => (w.name = e.target.value) })),
      field("Kind", select(E.location_kinds, w.kind, (v) => (w.kind = v))),
      field("Time of day", select(E.times, w.time_of_day, (v) => (w.time_of_day = v)))),
    h("div", { class: "grid g2", style: { marginTop: "12px" } }, field("Landmark", h("input", { type: "text", value: w.landmark || "", oninput: (e) => (w.landmark = e.target.value) })), field("Props", props, "comma separated")),
    h("div", { style: { marginTop: "12px" } }, field("Description", desc)),
    h("div", { class: "row wrap gap-l", style: { margin: "14px 0" } }, ["sky_top", "sky_bottom", "ground", "building", "accent"].map((k) => color(k, title(k)))),
    h("div", { class: "row" }, h("button", { class: "btn primary", onclick: async () => {
      const out = worlds.map((x) => (x.id === w.id ? (() => { const y = { ...w }; delete y._src; return y; })() : x));
      try { await put(`/api/projects/${S.pid}/worlds`, out); await refresh(); toast("Location saved", "ok"); } catch (e) { toast(e.message, "bad"); }
    } }, icon("check", 15), "Save location"), h("span", { class: "small muted" }, "Saving marks the visuals out of date; re-render from the Video Renderer."))));
}
