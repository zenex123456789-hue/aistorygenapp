// "New Updates" and "Releases" windows: see the releases, read their notes, and download the Windows / Android / iPhone files from inside the app.
import { get, post } from "./api.js";
import { S } from "./state.js";
import { h, icon, modal, toast } from "./ui.js";

const githubUrl = () => (S.caps && S.caps.releases_url) || "https://github.com/zenex123456789-hue/aistorygenapp/releases";
const hosted = () => !!(S.caps && S.caps.hosted);

// Fallback only: open a GitHub page. In the Windows app it opens in the normal browser; elsewhere in a new tab.
export async function openLink(url) {
  if (S.caps && !(S.caps.auth && S.caps.auth.enabled)) {
    try { await post("/api/open-external", { url }); return; } catch { /* use a normal new tab */ }
  }
  window.open(url, "_blank", "noopener");
}

const KIND_LABEL = { windows: "Windows (.exe)", android: "Android (.apk)", iphone: "iPhone (.ipa)" };
const KIND_ORDER = () => {
  const ua = navigator.userAgent || "";
  const mine = /Android/i.test(ua) ? "android" : /iPhone|iPad|iPod/i.test(ua) ? "iphone" : "windows";
  return (a, b) => (b.kind === mine) - (a.kind === mine);
};

// Which files this browser/window has already downloaded (so a button can say so instead of piling up copies of the same installer).
const DL_KEY = "sf_downloaded";
const downloaded = () => { try { return JSON.parse(localStorage.getItem(DL_KEY) || "{}") || {}; } catch { return {}; } };
const rememberDownload = (a) => { try { const d = downloaded(); d[a.id] = new Date().toISOString().slice(0, 10); localStorage.setItem(DL_KEY, JSON.stringify(d)); } catch { /* storage may be unavailable */ } };
const niceDate = (iso) => { const d = new Date(iso + "T12:00:00"); return isNaN(d) ? iso : d.toLocaleDateString(undefined, { day: "numeric", month: "short" }); };

// Check that GitHub will hand the file over, then start the download. The app fetches the file itself; nobody is sent to GitHub.
// The saved file's name carries the version (AI-Story-Factory-Setup-0.2.3.exe), so several downloads can be told apart.
export async function downloadAsset(a, btn) {
  const keep = btn ? btn.innerHTML : "";
  const name = a.file_name || a.name;
  if (btn) { btn.disabled = true; btn.textContent = "Starting download…"; }
  let ok = false;
  try {
    await get(a.check_url);
    const link = h("a", { href: a.download_url, download: name });
    document.body.append(link); link.click(); link.remove();
    toast(`Downloading ${name}. ` + (hosted() ? "Check your downloads." : "If a Save window opens, choose where to keep it."), "ok");
    rememberDownload(a); ok = true;
  } catch (e) { toast(e.message, "bad"); }
  if (btn) {
    btn.disabled = false;
    if (ok) btn.replaceChildren(icon("download", 14), `Downloaded · download again (${a.size_mb} MB)`); else btn.innerHTML = keep;
  }
}

function assetButton(a, primary = true) {
  const before = downloaded()[a.id];
  const label = before ? `Downloaded ${niceDate(before)} · download again (${a.size_mb} MB)` : `Download for ${KIND_LABEL[a.kind] || a.name} · ${a.size_mb} MB`;
  const btn = h("button", { class: "btn" + (primary && !before ? " primary" : ""), title: a.file_name || a.name, onclick: () => downloadAsset(a, btn) }, icon("download", 14), label);
  return btn;
}

// A release whose files are missing: either the builds are still running (they attach the files a few minutes after publishing) or there are none.
function noFiles(r, refresh) {
  const box = h("div", { class: "col", style: { gap: "6px" } });
  box.append(h("div", { class: r.building ? "notice info" : "small muted" }, r.building
    ? "The Windows, Android and iPhone files are being built right now. This usually takes about 10 minutes after a release is published. Press Refresh to check again."
    : "This release has no files attached. If it was only just published, the files are added by the builds a few minutes later: press Refresh."));
  if (refresh) box.append(h("div", { class: "row" }, h("button", { class: "btn sm", onclick: refresh }, "Refresh")));
  return box;
}

// A small, safe renderer for release notes: headings, bullet lists, **bold** and `code` (built from DOM nodes, never from HTML).
function inline(s) {
  const out = []; const re = /(\*\*[^*]+\*\*|`[^`]+`)/g; let last = 0, m;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    out.push(m[0].startsWith("**") ? h("b", m[0].slice(2, -2)) : h("code", m[0].slice(1, -1)));
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}
function notesEl(text) {
  if (!text) return h("div", { class: "small muted", style: { marginBottom: "10px" } }, "No notes were written for this release.");
  const root = h("div", { class: "rel-notes" });
  let ul = null, lastLi = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trimEnd(), li = line.match(/^\s*[-*]\s+(.*)/);
    if (li) { if (!ul) { ul = h("ul"); root.append(ul); } lastLi = h("li", inline(li[1])); ul.append(lastLi); continue; }
    if (ul && lastLi && /^\s{2,}\S/.test(raw)) { lastLi.append(" ", ...inline(line.trim())); continue; }
    ul = null; lastLi = null;
    const hd = line.match(/^#{1,6}\s+(.*)/);
    if (hd) root.append(h("div", { class: "rel-h" }, inline(hd[1])));
    else if (line.trim()) root.append(h("p", { style: { margin: "4px 0" } }, inline(line)));
  }
  return root;
}

function problem(r) {
  if (r.status === "unlisted") return [h("div", { class: "notice warn" }, "GitHub did not list any releases for this project. Either none has been published yet, or the project is private (a private page can only be read with a read-only token, see the README, \"Updates\")."),
    h("div", { class: "small muted" }, "You can still open the releases page in your browser and download from there.")];
  if (r.status === "offline") return [h("div", { class: "notice warn" }, "Could not reach GitHub. Check your internet connection and try again.")];
  return [h("div", { class: "notice warn" }, "GitHub did not answer" + (r.http ? ` (error ${r.http})` : "") + ". This is usually a temporary limit. Try again later.")];
}

function releaseRow(r, open, refresh) {
  const row = h("div", { class: "rel" + (open ? " open" : ""), "data-tag": r.tag });
  const head = h("button", { class: "rel-head", "aria-expanded": String(!!open), onclick: () => { const o = row.classList.toggle("open"); head.setAttribute("aria-expanded", String(o)); } },
    h("span", { class: "rel-arrow" }, "›"), h("span", { class: "rel-title" }, r.title && r.title !== r.tag ? `${r.tag} · ${r.title}` : r.tag),
    r.latest ? h("span", { class: "badge ok" }, "Latest") : null, r.current ? h("span", { class: "badge info" }, "You have this") : null, r.prerelease ? h("span", { class: "badge warn" }, "Pre-release") : null,
    r.assets.map((a) => h("span", { class: "badge" }, (KIND_LABEL[a.kind] || a.name).split(" ")[0])),
    h("span", { class: "rel-date" }, r.published));
  const files = r.assets.slice().sort(KIND_ORDER()).map((a, i) => assetButton(a, i === 0 && r.newer));
  row.append(head, h("div", { class: "rel-body" }, notesEl(r.notes), files.length ? h("div", { class: "rel-files" }, files) : noFiles(r, refresh)));
  return row;
}

export function showReleases() {
  return modal((close) => {
    const box = h("div", { class: "col" }, h("h2", "Releases"), h("p", { class: "muted" }, "Loading the releases…"));
    const footer = () => h("div", { class: "row wrap", style: { justifyContent: "flex-end" } },
      h("button", { class: "btn sm", onclick: () => openLink(githubUrl()) }, "Open on GitHub"),
      h("button", { class: "btn sm", onclick: () => load(true) }, icon("refresh", 14), "Refresh"), h("button", { class: "btn", onclick: () => close(null) }, "Close"));
    const load = (fresh) => {
      const openTags = new Set([...box.querySelectorAll(".rel.open")].map((el) => el.dataset.tag));
      get("/api/releases" + (fresh ? "?refresh=1" : "")).then((r) => {
        const intro = hosted() ? "The web app updates by itself whenever its owner updates the server. These are the files you can download."
          : `You have version ${r.current}. Tap the arrow next to a release to see what changed and to download its files.`;
        if (r.status !== "ok") return box.replaceChildren(h("h2", "Releases"), h("p", { class: "muted" }, intro), ...problem(r), footer());
        if (!r.releases.length) return box.replaceChildren(h("h2", "Releases"), h("div", { class: "notice warn" }, "No releases have been published yet."), footer());
        box.replaceChildren(h("h2", "Releases"), h("p", { class: "muted" }, intro),
          h("div", { style: { maxHeight: "58vh", overflow: "auto" } }, r.releases.map((x) => releaseRow(x, openTags.has(x.tag), () => load(true)))), footer());
        if (fresh) toast("Release list refreshed.", "ok");
      }).catch((e) => box.replaceChildren(h("h2", "Releases"), h("div", { class: "notice warn" }, e.message), footer()));
    };
    load(false);
    return box;
  }, "wide");
}

function updateView(r, close) {
  const out = [h("h2", "New Updates"), h("p", { class: "muted" }, `You have version ${r.current}.`)];
  const all = h("button", { class: "btn", onclick: () => { close(null); showReleases(); } }, "All releases");
  const closeBtn = h("button", { class: "btn", onclick: () => close(null) }, "Close");
  const foot = () => h("div", { class: "row wrap", style: { justifyContent: "flex-end" } }, all, closeBtn);
  if (r.status === "ok" && r.newer) {
    out.push(h("div", { class: "notice ok" }, `Version ${r.latest.replace(/^v/, "")} is available${r.published ? " (published " + r.published + ")" : ""}.`));
    out.push(h("div", { style: { maxHeight: "200px", overflow: "auto" } }, notesEl(r.notes)));
    if (r.assets.length) out.push(h("div", { class: "rel-files" }, r.assets.slice().sort(KIND_ORDER()).map((a, i) => assetButton(a, i === 0))));
    else out.push(noFiles({ building: r.building }, () => { close(null); showUpdates(true); }));
    if (r.assets.length) out.push(h("div", { class: "small muted" }, "After it downloads, close the app, run the new installer, and open the app again. Your projects are kept in a separate folder from the program, so they should still be there."));
    out.push(foot());
    return out;
  }
  if (r.status === "ok") out.push(h("div", { class: "notice ok" }, `You are up to date. The newest release is ${r.latest}.`));
  else out.push(...problem(r), h("div", { class: "row wrap", style: { justifyContent: "flex-end" } }, h("button", { class: "btn", onclick: () => openLink(githubUrl()) }, "Open on GitHub"), closeBtn));
  if (r.status === "ok") out.push(foot());
  return out;
}

export function showUpdates(fresh = false) {
  if (hosted()) return showReleases();           // the web app is always as new as its server; the files are what people need
  return modal((close) => {
    const box = h("div", { class: "col" }, h("h2", "New Updates"), h("p", { class: "muted" }, "Checking for a newer version…"));
    get("/api/update-check" + (fresh ? "?refresh=1" : "")).then((r) => box.replaceChildren(...updateView(r, close)))
      .catch((e) => box.replaceChildren(h("h2", "New Updates"), h("div", { class: "notice warn" }, e.message), h("div", { class: "row", style: { justifyContent: "flex-end" } }, h("button", { class: "btn", onclick: () => close(null) }, "Close"))));
    return box;
  });
}
