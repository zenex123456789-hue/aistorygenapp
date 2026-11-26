import { post, patch, del } from "../api.js";
import { S, loadRefs, loadStyles, track } from "../state.js";
import { h, icon, toast, field, empty, confirmBox, title, fmtDate } from "../ui.js";

const picked = new Set();

async function upload(fileList) {
  const fd = new FormData();
  [...fileList].forEach((f) => fd.append("files", f));
  try {
    const res = await fetch("/api/references", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    data.forEach((r) => picked.add(r.id));
    await loadRefs();
    toast(`${data.length} reference${data.length > 1 ? "s" : ""} uploaded`, "ok");
  } catch (e) { toast(e.message, "bad"); }
}

export function render(root) {
  root.append(h("div", { class: "page-head" }, h("h1", "References"),
    h("p", "Upload videos or images that show the look you want. The engine measures colour, contrast, composition, cutting speed, motion, caption position and loudness, then saves a reusable style profile. It learns the style only: no characters or footage are copied.")));

  const input = h("input", { type: "file", multiple: true, accept: "image/*,video/*", class: "hidden", onchange: (e) => e.target.files.length && upload(e.target.files) });
  const drop = h("div", { class: "drop", onclick: () => input.click(),
    ondragover: (e) => { e.preventDefault(); drop.classList.add("over"); }, ondragleave: () => drop.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files.length) upload(e.dataTransfer.files); } },
    icon("download", 30), h("div", { style: { fontWeight: 600, color: "#3b4068" } }, "Drop reference videos or images here, or click to browse"),
    h("div", { class: "small" }, "mp4, mov, webm, png, jpg, webp · only use material you have the right to analyse"), input);
  root.append(h("div", { class: "card" }, drop));

  const llm = S.caps.providers.llm.providers.find((x) => x.active);
  if (S.refs.length) {
    const name = h("input", { type: "text", value: "My style", placeholder: "Style profile name" });
    root.append(h("div", { class: "card" },
      h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Your references"), h("div", { class: "small muted" }, "Select one or more, then build a style profile.")),
        h("div", { style: { width: "200px" } }, name),
        h("button", { class: "btn primary", onclick: async () => {
          if (!picked.size) return toast("Select at least one reference");
          try { track(await post("/api/references/analyze", { ids: [...picked], name: name.value || "My style" })); } catch (e) { toast(e.message, "bad"); }
        } }, icon("wand", 15), "Analyse & save style")),
      llm.offline ? h("div", { class: "notice", style: { marginBottom: "12px" } }, "Measured properties (colour, pacing, composition, subtitles, loudness) work offline. Character appearance and story structure need a vision-capable LLM (set ANTHROPIC_API_KEY); until then they are marked as not analysed.") : null,
      h("div", { class: "grid", style: { gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))" } }, S.refs.map((r) => {
        const on = picked.has(r.id);
        return h("div", { class: "card", style: { padding: "10px", boxShadow: "none", outline: on ? "2px solid var(--p1)" : "none", cursor: "pointer" }, onclick: () => { on ? picked.delete(r.id) : picked.add(r.id); window.__rerender(); } },
          r.thumb ? h("img", { class: "thumb", style: { aspectRatio: "9 / 12" }, src: `/refs/${r.id}/thumb`, alt: r.name }) : h("div", { class: "thumb", style: { aspectRatio: "9 / 12" } }),
          h("div", { class: "nm small", style: { fontWeight: 600, marginTop: "6px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, r.name),
          h("div", { class: "row spread" }, h("span", { class: "badge" }, title(r.kind)), r.analysis ? h("span", { class: "badge ok" }, "analysed") : null),
          h("button", { class: "btn sm ghost danger", style: { marginTop: "4px" }, onclick: async (e) => { e.stopPropagation(); picked.delete(r.id); await del("/api/references/" + r.id); await loadRefs(); } }, icon("trash", 12)));
      }))));
  }

  // ---- style profiles ----
  root.append(h("div", { class: "card" }, h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", "Style profiles"), h("div", { class: "small muted" }, "Pick a profile in the Story Generator to apply its colour grade, pacing, transitions, caption position and prompt directive."))),
    S.styles.length ? h("div", { class: "grid g2" }, S.styles.map(styleCard)) : empty("image", "No style profiles yet", "Upload references above and press “Analyse & save style”.")));
}

function styleCard(s) {
  const dir = h("textarea", { rows: 3, onchange: async (e) => { await patch("/api/styles/" + s.id, { directive: e.target.value }); toast("Directive saved", "ok"); } }); dir.value = s.directive || "";
  const metric = (k, v) => (v == null || v === "" ? null : h("div", { class: "row spread small" }, h("span", { class: "muted" }, k), h("b", String(v))));
  return h("div", { class: "card", style: { boxShadow: "none" } },
    h("div", { class: "card-head" }, h("div", { class: "grow" }, h("h3", s.name), h("div", { class: "tiny muted" }, `${s.n_references} reference(s)`)),
      h("button", { class: "btn sm ghost danger", onclick: async () => { if (await confirmBox("Delete style profile?", `“${s.name}” will be removed.`, "Delete", true)) { await del("/api/styles/" + s.id); await loadStyles(); } } }, icon("trash", 13))),
    h("div", { class: "palette", style: { marginBottom: "10px" } }, (s.palette || []).map((c) => h("span", { class: "swatch", style: { background: c }, title: c }))),
    metric("Mood", s.mood), metric("Pacing", s.pacing?.feel ? `${s.pacing.feel} (${s.pacing.avg_shot_length_s}s per shot)` : null), metric("Camera", s.camera),
    metric("Saturation / brightness", `${s.saturation_scale}× / ${s.brightness_scale}×`), metric("Subtitle position", s.subtitle?.position),
    s.needs_llm_for?.length ? h("div", { class: "notice warn", style: { margin: "10px 0" } }, "Not analysed (needs a vision LLM): " + s.needs_llm_for.join(", ")) : null,
    field("Style directive (added to every prompt)", dir));
}
