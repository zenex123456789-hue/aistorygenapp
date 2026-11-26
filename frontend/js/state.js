import { get, post } from "./api.js";
import { toast } from "./ui.js";

export const S = {
  caps: null, projects: [], pid: localStorage.getItem("sf.pid") || "", project: null,
  job: null, pausePlan: [], styles: [], refs: [], page: "story",
};
export const bus = new EventTarget();
export const emit = (name, detail) => bus.dispatchEvent(new CustomEvent(name, { detail }));
export const on = (name, fn) => bus.addEventListener(name, (e) => fn(e.detail));

export async function loadCaps() { S.caps = await get("/api/capabilities"); return S.caps; }
export async function loadProjects() { S.projects = await get("/api/projects"); emit("projects"); return S.projects; }
export async function loadStyles() { S.styles = await get("/api/styles"); emit("styles"); return S.styles; }
export async function loadRefs() { S.refs = await get("/api/references"); emit("refs"); return S.refs; }

export async function selectProject(id) {
  S.pid = id || "";
  localStorage.setItem("sf.pid", S.pid);
  S.project = null;
  if (S.pid) {
    try { S.project = await get("/api/projects/" + S.pid); }
    catch { S.pid = ""; localStorage.removeItem("sf.pid"); }
  }
  emit("project");
  if (S.project && S.project.active_job) track(S.project.active_job);
  else if (S.project && S.project.last_job && S.project.last_job.status === "paused") { S.job = S.project.last_job; emit("job"); }
  else { S.job = null; emit("job"); }
}

export async function refresh(quiet = false) {
  if (!S.pid) return null;
  try {
    S.project = await get("/api/projects/" + S.pid);
    if (!quiet) emit("project");
    return S.project;
  } catch (e) { toast(e.message, "bad"); return null; }
}

let polling = null;
export function track(job) {
  S.job = job; emit("job");
  clearTimeout(polling);
  const tick = async () => {
    try {
      const j = await get("/api/jobs/" + S.job.id);
      S.job = j; emit("job");
      if (j.status === "queued" || j.status === "running") {
        if (j.project_id === S.pid && (j.stage !== S._lastStage)) { S._lastStage = j.stage; refresh(); }   // keep stage chips/page fresh as stages finish
        polling = setTimeout(tick, 800);
      } else {
        await Promise.all([refresh(), loadProjects(), j.type === "analyze" ? Promise.all([loadStyles(), loadRefs()]) : null]);
        emit("jobdone", j);
        if (j.status === "succeeded") toast(j.result?.message || "Done", "ok");
        else if (j.status === "failed") toast(j.error || "Job failed", "bad");
      }
    } catch (e) { polling = setTimeout(tick, 2500); }
  };
  tick();
}

// Start a pipeline run on the current project (from `from` to `to`).
export async function startRun({ from = "story", to = "export", fresh = false, idea, options, pause_after = [] } = {}) {
  if (!S.pid) throw new Error("No project selected");
  S.pausePlan = pause_after;
  const body = { from, to, fresh, pause_after };
  if (idea !== undefined) body.idea = idea;
  if (options) body.options = options;
  const job = await post(`/api/projects/${S.pid}/run`, body);
  track(job);
  return job;
}
export async function startStage(stage, to) {
  const job = await post(`/api/projects/${S.pid}/stage/${stage}`, to ? { to } : {});
  track(job);
  return job;
}
export const isRunning = () => !!(S.job && (S.job.status === "queued" || S.job.status === "running"));
export const stageStatus = (id) => (S.project?.stages?.[id]?.status) || "idle";
