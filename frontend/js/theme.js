import { put } from "./api.js";
import { S, emit } from "./state.js";

// "system" follows the operating system; "light" / "dark" are fixed.
const KEY = "sf_theme";
export const MODES = ["system", "light", "dark"];
const mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
let mode = "system";

export const getMode = () => mode;
export const resolved = () => (mode === "system" ? (mq && mq.matches ? "dark" : "light") : mode);

export function applyTheme(m) {
  mode = MODES.includes(m) ? m : "system";
  const r = resolved();
  document.documentElement.dataset.theme = r;
  document.documentElement.dataset.themePref = mode;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = r === "dark" ? "#0e1124" : "#7c5cff";
  try { localStorage.setItem(KEY, mode); } catch (e) { /* storage can be unavailable; the server copy is the source of truth */ }
  emit("theme", mode);
}

// Saved on the server too, so the choice survives even where the window does not keep browser storage.
export async function setTheme(m) {
  applyTheme(m);
  if (S.caps && S.caps.settings) S.caps.settings.theme = mode;
  try { await put("/api/settings", { theme: mode }); } catch (e) { /* the screen already changed; saving is best effort */ }
}

if (mq) {
  const follow = () => { if (mode === "system") applyTheme("system"); };
  if (mq.addEventListener) mq.addEventListener("change", follow); else if (mq.addListener) mq.addListener(follow);
}
