import { patch, del } from "../api.js";
import { S } from "../state.js";
import { h, icon, toast, select, empty, promptBox, confirmBox, fmtSize, fmtDate, title } from "../ui.js";

let kind = "all", scope = "project";
const KINDS = [["all", "Everything"], ["video", "Videos"], ["export", "Packages"], ["story", "Stories"], ["script", "Scripts"], ["character_sheet", "Character sheets"], ["image", "Images"], ["audio", "Audio"], ["caption", "Captions"], ["style", "Style profiles"]];

export async function render(root) {
  root.append(h("div", { class: "page-head" }, h("h1", "Files & Exports"), h("p", "Everything the engine has made: preview, download, rename or delete. The package (.zip) bundles the video, captions, scripts, character sheets and the post copy.")));
  const q = scope === "project" && S.pid ? `?project=${S.pid}` : "";
  let files = await fetch("/api/files" + q).then((r) => r.json());
  const counts = {}; files.forEach((f) => (counts[f.kind] = (counts[f.kind] || 0) + 1));
  if (kind !== "all") files = files.filter((f) => f.kind === kind);

  root.append(h("div", { class: "row spread wrap", style: { marginBottom: "14px" } },
    h("div", { class: "tabs", style: { marginBottom: 0 } }, KINDS.filter(([k]) => k === "all" || counts[k]).map(([k, l]) => h("button", { class: "tab " + (kind === k ? "on" : ""), onclick: () => { kind = k; window.__rerender(); } }, l + (k !== "all" ? ` (${counts[k]})` : "")))),
    h("div", { class: "row" }, select([["project", "This project"], ["all", "All projects"]], scope, (v) => { scope = v; window.__rerender(); }))));

  if (!files.length) { root.append(h("div", { class: "card" }, empty("folder", "No files here yet", "Files appear as the pipeline produces them."))); return; }
  root.append(h("div", { class: "grid gauto" }, files.map((f) => card(f))));
}

function preview(f) {
  const url = f.url + "?v=" + f.created;
  if (f.mime.startsWith("image/")) return h("img", { src: url, loading: "lazy", alt: f.name });
  if (f.mime.startsWith("video/")) return h("video", { src: url, controls: true, preload: "metadata", playsinline: true });
  if (f.mime.startsWith("audio/")) return h("audio", { src: url, controls: true, style: { width: "92%" } });
  return icon(f.kind === "export" ? "folder" : "script", 38);
}

function card(f) {
  return h("div", { class: "card filecard", style: { padding: "12px" } },
    h("div", { class: "prev" }, preview(f)),
    h("div", { class: "nm", title: f.name }, f.name),
    h("div", { class: "row spread" }, h("span", { class: "badge" }, title(f.kind)), h("span", { class: "tiny muted" }, `${fmtSize(f.size)} · ${fmtDate(f.created)}`)),
    h("div", { class: "row gap-s" },
      h("a", { class: "btn sm", href: f.url, target: "_blank" }, icon("play", 12), "Open"),
      h("a", { class: "btn sm", href: f.url + "?download=1" }, icon("download", 12)),
      h("button", { class: "btn sm", title: "Rename", onclick: async () => { const n = await promptBox("Rename file", f.name); if (!n) return; try { await patch("/api/files/" + f.id, { name: n }); window.__rerender(); } catch (e) { toast(e.message, "bad"); } } }, icon("edit", 12)),
      h("button", { class: "btn sm danger", title: "Delete", onclick: async () => { if (!(await confirmBox("Delete file?", `“${f.name}” will be removed permanently.`, "Delete", true))) return; try { await del("/api/files/" + f.id); window.__rerender(); } catch (e) { toast(e.message, "bad"); } } }, icon("trash", 12))));
}
