// Minimal service worker: makes the app installable. It caches nothing (rendering needs the live server, and nothing private is stored).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;          // let media, API calls and range requests go straight through
  e.respondWith(fetch(e.request).catch(() => new Response(
    "<meta name=viewport content='width=device-width,initial-scale=1'><body style='font-family:system-ui;padding:28px'>" +
    "<h2>Can't reach Story Factory</h2><p>Check your internet connection and try again. If it keeps failing, " +
    "the server may be restarting; give it a minute.</p>",
    { headers: { "Content-Type": "text/html" } })));
});
