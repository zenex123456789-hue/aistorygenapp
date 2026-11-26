// Tiny DOM + UI helpers (no framework).
export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs && (typeof attrs !== "object" || attrs instanceof Node || Array.isArray(attrs))) { kids.unshift(attrs); attrs = null; }
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (k === "checked" || k === "disabled" || k === "selected" || k === "open") el[k] = !!v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  const add = (c) => {
    if (c == null || c === false) return;
    if (Array.isArray(c)) c.forEach(add);
    else el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  };
  kids.forEach(add);
  return el;
}

const ICONS = {
  spark: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z",
  image: "M3 5a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2z M8.5 10a1.5 1.5 0 100-3 1.5 1.5 0 000 3z M21 15l-5-5L5 21",
  book: "M4 19.5A2.5 2.5 0 016.5 17H20V3H6.5A2.5 2.5 0 004 5.5z M4 19.5A2.5 2.5 0 006.5 22H20v-5",
  user: "M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2 M12 11a4 4 0 100-8 4 4 0 000 8z",
  globe: "M12 21a9 9 0 100-18 9 9 0 000 18z M3 12h18 M12 3a14 14 0 010 18 M12 3a14 14 0 000 18",
  script: "M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z M14 3v6h6 M8 13h8 M8 17h6",
  mic: "M12 14a3 3 0 003-3V6a3 3 0 00-6 0v5a3 3 0 003 3z M19 11a7 7 0 01-14 0 M12 18v3",
  film: "M4 4h16a1 1 0 011 1v14a1 1 0 01-1 1H4a1 1 0 01-1-1V5a1 1 0 011-1z M7 4v16 M17 4v16 M3 9h4 M3 15h4 M17 9h4 M17 15h4",
  folder: "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z",
  gear: "M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z",
  play: "M6 4l14 8-14 8z", plus: "M12 5v14 M5 12h14", trash: "M3 6h18 M8 6V4h8v2 M19 6l-1 14H6L5 6", download: "M12 3v12 M7 10l5 5 5-5 M5 21h14",
  edit: "M12 20h9 M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z", check: "M5 12l5 5 9-10", x: "M6 6l12 12 M18 6L6 18", refresh: "M21 12a9 9 0 11-3-6.7 M21 4v5h-5",
  copy: "M9 9h11v11H9z M5 15H4V4h11v1", chevron: "M6 9l6 6 6-6", wand: "M15 4V2 M15 16v-2 M8 9h2 M20 9h2 M17.8 11.8L19 13 M17.8 6.2L19 5 M3 21l9-9 M12.2 6.2L11 5",
  sun: "M12 17a5 5 0 100-10 5 5 0 000 10z M12 1v2 M12 21v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M1 12h2 M21 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4",
  moon: "M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z", monitor: "M3 4h18a1 1 0 011 1v11a1 1 0 01-1 1H3a1 1 0 01-1-1V5a1 1 0 011-1z M8 21h8 M12 17v4",
  stop: "M6 6h12v12H6z", alert: "M12 9v4 M12 17h.01 M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z", video: "M23 7l-7 5 7 5z M3 5h13a2 2 0 012 2v10a2 2 0 01-2 2H3a2 2 0 01-2-2V7a2 2 0 012-2z",
};
export function icon(name, size = 18) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("width", size); svg.setAttribute("height", size); svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none"); svg.setAttribute("stroke", "currentColor"); svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round"); svg.setAttribute("stroke-linejoin", "round");
  const p = document.createElementNS(ns, "path"); p.setAttribute("d", ICONS[name] || ICONS.spark); svg.append(p);
  return svg;
}

export function toast(msg, kind = "") {
  const t = h("div", { class: "toast " + kind }, msg);
  document.getElementById("toasts").append(t);
  setTimeout(() => { t.style.transition = "opacity .3s"; t.style.opacity = "0"; setTimeout(() => t.remove(), 320); }, kind === "bad" ? 7000 : 3200);
}

export function modal(build) {
  return new Promise((resolve) => {
    const close = (v) => { bg.remove(); resolve(v); };
    const box = h("div", { class: "modal" });
    const bg = h("div", { class: "modal-bg", onmousedown: (e) => { if (e.target === bg) close(null); } }, box);
    box.append(build(close));
    document.body.append(bg);
    const first = box.querySelector("input,textarea,select");
    if (first) first.focus();
  });
}
export function confirmBox(title, body, okLabel = "Confirm", danger = false) {
  return modal((close) => h("div", { class: "col" },
    h("h2", title), h("p", { class: "muted" }, body),
    h("div", { class: "row", style: { justifyContent: "flex-end" } },
      h("button", { class: "btn", onclick: () => close(false) }, "Cancel"),
      h("button", { class: "btn " + (danger ? "danger" : "primary"), onclick: () => close(true) }, okLabel))));
}
export function promptBox(title, value = "", okLabel = "Save") {
  return modal((close) => {
    const inp = h("input", { type: "text", value });
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") close(inp.value.trim()); });
    return h("div", { class: "col" }, h("h2", title), inp,
      h("div", { class: "row", style: { justifyContent: "flex-end" } },
        h("button", { class: "btn", onclick: () => close(null) }, "Cancel"),
        h("button", { class: "btn primary", onclick: () => close(inp.value.trim()) }, okLabel)));
  });
}

export function field(label, input, hint) {
  return h("label", { class: "f" }, h("span", label, hint ? h("span", { class: "hint" }, " " + hint) : null), input);
}
export function select(options, value, onchange, attrs = {}) {
  const el = h("select", attrs, options.map((o) => {
    const [v, l] = Array.isArray(o) ? o : [o, String(o).replace(/_/g, " ")];
    return h("option", { value: v, selected: String(v) === String(value) }, l);
  }));
  if (onchange) el.addEventListener("change", () => onchange(el.value));
  return el;
}
export function toggle(label, checked, onchange) {
  const i = h("input", { type: "checkbox", checked });
  if (onchange) i.addEventListener("change", () => onchange(i.checked));
  return h("label", { class: "switch" }, i, label);
}
export function slider(label, value, min, max, step, onchange, fmt = (v) => v) {
  const out = h("b", fmt(value));
  const i = h("input", { type: "range", min, max, step, value });
  i.addEventListener("input", () => { out.textContent = fmt(+i.value); onchange && onchange(+i.value); });
  return h("label", { class: "f" }, h("span", { class: "row spread" }, label, out), i);
}

export const el$ = (sel, root = document) => root.querySelector(sel);
export const fmtDur = (s) => (s == null ? "" : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`);
export const fmtSize = (b) => (b > 1e6 ? (b / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1e3)) + " KB");
export const fmtDate = (t) => new Date(t * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
export const title = (s) => String(s || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function copyBtn(textFn) {
  return h("button", { class: "btn sm ghost copy", title: "Copy", onclick: async (e) => {
    try { await navigator.clipboard.writeText(typeof textFn === "function" ? textFn() : textFn); toast("Copied", "ok"); } catch { toast("Copy failed"); }
    e.stopPropagation();
  } }, icon("copy", 14));
}

export function busy(btn, fn) {
  return async (...a) => {
    if (btn.disabled) return;
    const old = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spinner dark"></span>';
    try { return await fn(...a); } finally { btn.disabled = false; btn.innerHTML = old; }
  };
}
export function empty(iconName, text, sub) {
  return h("div", { class: "empty" }, icon(iconName, 40), h("div", { style: { fontWeight: 600, color: "var(--label)" } }, text), sub ? h("div", { class: "small" }, sub) : null);
}
