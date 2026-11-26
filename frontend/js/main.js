import { post, patch, del } from "./api.js";
import { S, on, emit, loadCaps, loadProjects, loadStyles, loadRefs, selectProject, refresh, startRun, track, isRunning } from "./state.js";
import { h, icon, toast, select, confirmBox, promptBox, title } from "./ui.js";
import * as story from "./pages/story.js";
import * as references from "./pages/references.js";
import * as characters from "./pages/characters.js";
import * as worlds from "./pages/worlds.js";
import * as script from "./pages/script.js";
import * as voices from "./pages/voices.js";
import * as render from "./pages/render.js";
import * as files from "./pages/files.js";
import * as settings from "./pages/settings.js";

const PAGES = [
  { id: "references", label: "References", icon: "image", mod: references, stages: [] },
  { id: "story", label: "Story Generator", icon: "spark", mod: story, stages: ["story", "score"] },
  { id: "characters", label: "Character Engine", icon: "user", mod: characters, stages: ["characters"] },
  { id: "worlds", label: "World Engine", icon: "globe", mod: worlds, stages: ["worlds"] },
  { id: "script", label: "Script Generator", icon: "script", mod: script, stages: ["script"] },
  { id: "voices", label: "Voice Generator", icon: "mic", mod: voices, stages: ["voices"] },
  { id: "render", label: "Video Renderer", icon: "film", mod: render, stages: ["visuals", "captions", "audio", "render"] },
  { id: "files", label: "Files & Exports", icon: "folder", mod: files, stages: ["export"] },
  { id: "settings", label: "Settings", icon: "gear", mod: settings, stages: [] },
];
const STAGE_PAGE = {};
PAGES.forEach((p) => p.stages.forEach((s) => (STAGE_PAGE[s] = p.id)));

function aggregate(stages) {
  const st = stages.map((s) => S.project?.stages?.[s]?.status || "idle");
  if (st.includes("running")) return "running";
  if (st.includes("failed")) return "failed";
  if (st.includes("stale")) return "stale";
  if (st.length && st.every((x) => x === "done" || x === "review")) return "done";
  return "";
}

// ---------------------------------------------------------------- nav
function renderNav() {
  const nav = document.getElementById("nav");
  nav.replaceChildren(...PAGES.map((p) => h("a", { class: S.page === p.id ? "active" : "", href: "#/" + p.id, title: p.label },
    icon(p.icon), h("span", p.label), p.stages.length ? h("i", { class: "dot " + aggregate(p.stages) }) : null)));
  const caps = S.caps;
  if (caps) {
    const act = (k) => caps.providers[k].providers.find((x) => x.active);
    const offline = ["llm", "tts"].filter((k) => act(k).offline);
    document.getElementById("foot").replaceChildren(
      offline.length ? h("div", { class: "badge warn" }, "Offline mode") : h("div", { class: "badge ok" }, "AI connected"),
      h("div", { style: { marginTop: "6px" } }, offline.length ? "Add API keys in .env for full-quality AI. See Settings." : "Providers connected."));
  }
}

// ---------------------------------------------------------------- topbar
function renderTopbar() {
  const bar = document.getElementById("topbar");
  const sel = select([["", "— Select a project —"], ...S.projects.map((p) => [p.id, p.name])], S.pid, async (v) => { await selectProject(v); });
  const mk = (ic, label, fn, cls = "") => h("button", { class: "btn sm ghost " + cls, title: label, onclick: fn }, icon(ic, 15));
  bar.replaceChildren(
    h("div", { class: "proj" }, icon("folder", 16), sel,
      S.project ? mk("edit", "Rename project", async () => {
        const n = await promptBox("Rename project", S.project.name); if (!n) return;
        await patch("/api/projects/" + S.pid, { name: n }); await refresh(); await loadProjects();
      }) : null,
      S.project ? mk("copy", "Duplicate project", async () => {
        const p = await post(`/api/projects/${S.pid}/duplicate`); await loadProjects(); await selectProject(p.id); toast("Project duplicated", "ok");
      }) : null,
      S.project ? mk("trash", "Delete project", async () => {
        if (!(await confirmBox("Delete project?", `“${S.project.name}” and all of its files will be permanently removed.`, "Delete", true))) return;
        await del("/api/projects/" + S.pid); await loadProjects(); await selectProject(""); toast("Project deleted");
      }, "danger") : null),
    h("button", { class: "btn sm", onclick: async () => {
      const p = await post("/api/projects", { name: "Untitled project", idea: "", options: S.project?.options }); await loadProjects(); await selectProject(p.id); location.hash = "#/story";
    } }, icon("plus", 15), "New project"));
}

// ---------------------------------------------------------------- pipeline bar
const NEXT_FROM = (stage, caps) => stage;
function renderPipe() {
  const box = document.getElementById("pipebar");
  const p = S.project, j = S.job;
  if (!p) { box.replaceChildren(); return; }
  const running = isRunning();
  const relevant = j && j.project_id === S.pid;
  const anyStarted = Object.values(p.stages || {}).some((s) => s.status && s.status !== "idle");
  if (!anyStarted && !relevant) { box.replaceChildren(); return; }

  const chips = S.caps.stages.map((st) => {
    const s = p.stages?.[st.id]?.status || "idle";
    return h("span", { class: "chip " + s, title: (p.stages?.[st.id]?.error || title(s)), onclick: () => (location.hash = "#/" + (STAGE_PAGE[st.id] || "story")) }, h("i"), st.label);
  });
  const parts = [h("div", { class: "chips" }, chips)];
  if (relevant) {
    const pct = Math.round(j.progress || 0);
    const failed = j.status === "failed";
    parts.push(h("div", { class: "bar " + (running ? "active " : "") + (failed ? "failed" : "") }, h("div", { style: { width: (failed ? 100 : pct) + "%" } })));
    const msg = running ? (j.message || "Working…") : j.status === "paused" ? (j.result?.message || "Paused for review") : failed ? (j.error || "Failed") : j.status === "cancelled" ? "Cancelled" : j.status === "succeeded" ? "Finished" : "";
    parts.push(h("div", { class: "row spread", style: { marginTop: "9px" } },
      h("span", { class: "small " + (failed ? "" : "muted"), style: failed ? { color: "var(--bad)" } : null }, running ? `${pct}% · ${msg}` : msg),
      h("div", { class: "row gap-s" },
        running ? h("button", { class: "btn sm danger", onclick: () => post(`/api/jobs/${j.id}/cancel`).then(() => toast("Cancelling…")) }, icon("stop", 13), "Cancel") : null,
        j.status === "paused" ? h("button", { class: "btn sm primary", onclick: async () => {
          const order = S.caps.stages.map((x) => x.id);
          let next = j.result?.next || "characters";
          // If the user's edits made an earlier stage stale, resume from there so the edit takes effect.
          const stale = order.slice(0, order.indexOf(next) + 1).find((id) => p.stages?.[id]?.status === "stale");
          if (stale) next = stale;
          const rest = S.pausePlan.filter((s) => order.indexOf(s) >= order.indexOf(next));
          try { await startRun({ from: next, to: "export", pause_after: rest }); } catch (e) { toast(e.message, "bad"); }
        } }, icon("play", 13), "Continue") : null,
        failed ? h("button", { class: "btn sm", onclick: async () => {
          const bad = Object.entries(p.stages).find(([, v]) => v.status === "failed");
          try { await startRun({ from: bad ? bad[0] : "story", to: "export", pause_after: S.pausePlan }); } catch (e) { toast(e.message, "bad"); }
        } }, icon("refresh", 13), "Retry") : null)));
  }
  const warns = (p.warnings || []);
  if (warns.length) parts.push(h("div", { class: "notice warn", style: { marginTop: "10px" } }, icon("alert", 16), h("div", warns.slice(-3).map((w) => h("div", `${title(w.stage)}: ${w.message}`)))));
  box.replaceChildren(h("div", { class: "pipe" }, parts));
}

// ---------------------------------------------------------------- router
let currentPage = null;
function pageFromHash() { const id = location.hash.replace(/^#\//, ""); return PAGES.find((p) => p.id === id) ? id : "story"; }
export function renderPage() {
  if (!S.caps) return;                       // still booting
  const page = PAGES.find((p) => p.id === S.page);
  const host = document.getElementById("page");
  const node = h("div", { class: "page" });
  host.replaceChildren(node);
  try { page.mod.render(node); } catch (e) { console.error(e); node.append(h("div", { class: "notice bad" }, "This page failed to render: " + e.message)); }
  currentPage = S.page;
}
function navigate() {
  S.page = pageFromHash(); renderNav(); renderPage(); window.scrollTo({ top: 0 });
}

window.addEventListener("hashchange", navigate);
on("project", () => { renderTopbar(); renderNav(); renderPipe(); renderPage(); });
on("projects", renderTopbar);
on("job", () => { renderPipe(); renderNav(); });
on("jobdone", () => { renderPipe(); });
on("styles", () => { if (S.page === "references" || S.page === "story") renderPage(); });
on("refs", () => { if (S.page === "references") renderPage(); });
window.__rerender = renderPage;

(async function boot() {
  try {
    await Promise.all([loadCaps(), loadProjects(), loadStyles(), loadRefs()]);
    if (!S.projects.find((p) => p.id === S.pid)) S.pid = S.projects[0]?.id || "";
    S.page = pageFromHash();
    await selectProject(S.pid);
    renderTopbar(); renderNav(); renderPipe(); renderPage();
  } catch (e) {
    document.getElementById("page").replaceChildren(h("div", { class: "notice bad" }, "Could not start: " + e.message));
  }
})();
