// Minimal service worker: makes the app installable. It does not cache anything (rendering needs the live server).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;          // let media, API calls and range requests go straight through
  e.respondWith(fetch(e.request).catch(() => new Response(
    "<meta name=viewport content='width=device-width,initial-scale=1'><body style='font-family:system-ui;padding:28px'>" +
    "<h2>Can't reach Story Factory</h2><p>Check that the host PC is switched on and the app is running, " +
    "and that you're on the same network (or connected to Tailscale).</p>",
    { headers: { "Content-Type": "text/html" } })));
});
