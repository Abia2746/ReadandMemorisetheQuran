/* App-shell-only offline cache. Never cache authenticated API, purchases,
   audio, personally sensitive study records, or inaccurate offline Qur'an text. */
const CACHE = "almuallim-shell-v1";
const SHELL = ["/", "/verse/", "/journey/", "/sanctuary/", "/icon.svg"];
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).catch(()=>undefined));
  self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key !== CACHE).map(key => caches.delete(key))
  )));
  self.clients.claim();
});
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.includes("/billing")) return;
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match(req).then(
      found => found || caches.match("/")
    )));
  }
});
