// "New Updates" window and the helper that opens GitHub pages (Releases, downloads).
import { get, post } from "./api.js";
import { S } from "./state.js";
import { h, icon, modal } from "./ui.js";

const releasesUrl = () => (S.caps && S.caps.releases_url) || "https://github.com/zenex123456789-hue/aistorygenapp/releases";

// In the Windows app the page is opened in the person's normal browser (where they are signed in to GitHub); elsewhere a new tab.
export async function openLink(url) {
  if (S.caps && !(S.caps.auth && S.caps.auth.enabled)) {
    try { await post("/api/open-external", { url }); return; } catch { /* fall back to a normal new tab */ }
  }
  window.open(url, "_blank", "noopener");
}

const ASSET_LABEL = { windows: "Download for Windows (.exe)", android: "Download Android app (.apk)", iphone: "Download iPhone file (.ipa)" };

function view(r, close) {
  const out = [h("h2", "New Updates"), h("p", { class: "muted" }, `You have version ${r.current}.`)];
  const releasesBtn = h("button", { class: "btn", onclick: () => openLink(r.releases_url || releasesUrl()) }, icon("download", 14), "Open Releases");
  const closeBtn = h("button", { class: "btn", onclick: () => close(null) }, "Close");
  if (r.status === "ok" && r.newer) {
    out.push(h("div", { class: "notice ok" }, `Version ${r.latest.replace(/^v/, "")} is available${r.published ? " (published " + r.published + ")" : ""}.`));
    if (r.notes) out.push(h("div", { class: "small", style: { whiteSpace: "pre-wrap", maxHeight: "180px", overflow: "auto" } }, r.notes));
    out.push(h("div", { class: "col" }, r.assets.map((a) => h("button", { class: "btn primary", onclick: () => openLink(a.url) }, icon("download", 14), `${ASSET_LABEL[a.kind] || a.name} · ${a.size_mb} MB`))));
    out.push(h("div", { class: "small muted" }, "Close the app, run the new installer, and open the app again. Your projects are kept in a separate folder from the program, so they should still be there."));
    out.push(h("div", { class: "row wrap", style: { justifyContent: "flex-end" } }, releasesBtn, closeBtn));
    return out;
  }
  if (r.status === "ok") {
    out.push(h("div", { class: "notice ok" }, `You are up to date. The newest release is ${r.latest}.`));
  } else if (r.status === "unlisted") {
    out.push(h("div", { class: "notice warn" }, "The app cannot see any release from here. The project's GitHub page is probably private (a private page cannot be looked at automatically), or nothing has been published yet."));
    out.push(h("div", { class: "small muted" }, `Open Releases while signed in to GitHub and compare the newest version there with yours (${r.current}). If it is newer, download the installer from that page.`));
  } else if (r.status === "offline") {
    out.push(h("div", { class: "notice warn" }, "Could not reach GitHub. Check your internet connection and try again."));
  } else {
    out.push(h("div", { class: "notice warn" }, "GitHub did not answer the check" + (r.http ? ` (error ${r.http})` : "") + ". This is usually a temporary limit. Try again later, or open Releases."));
  }
  out.push(h("div", { class: "row wrap", style: { justifyContent: "flex-end" } }, releasesBtn, closeBtn));
  return out;
}

export function showUpdates() {
  return modal((close) => {
    const box = h("div", { class: "col" }, h("h2", "New Updates"), h("p", { class: "muted" }, "Checking for a newer version…"));
    get("/api/update-check").then((r) => box.replaceChildren(...view(r, close)))
      .catch((e) => box.replaceChildren(h("h2", "New Updates"), h("div", { class: "notice warn" }, e.message), h("div", { class: "row", style: { justifyContent: "flex-end" } }, h("button", { class: "btn", onclick: () => close(null) }, "Close"))));
    return box;
  });
}
