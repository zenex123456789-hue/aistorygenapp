// Reads SERVER_URL (the hosted address) and writes it into capacitor.config.json so the app opens your site directly.
// With no SERVER_URL the app shows a screen asking for the address instead.
const fs = require("fs");
const file = "capacitor.config.json";
const cfg = JSON.parse(fs.readFileSync(file, "utf8"));
let url = (process.env.SERVER_URL || "").trim().replace(/\/+$/, "");
if (url) {
  if (!/^https?:\/\//i.test(url)) url = "https://" + url;
  const u = new URL(url);
  cfg.server.url = url;
  cfg.server.cleartext = u.protocol === "http:";
  cfg.server.allowNavigation = [u.host];
  console.log("App will open " + url + (cfg.server.cleartext ? " (plain http)" : ""));
} else {
  cfg.server.cleartext = true;      // the address screen lets people type any server, including http:// ones on a home network
  console.log("No SERVER_URL set: the app will ask for the address on first launch.");
}
fs.writeFileSync(file, JSON.stringify(cfg, null, 2) + "\n");
