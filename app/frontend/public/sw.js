/* Kalakriti — minimal, safe service worker.
   Goal: installability + fast repeat loads. It NEVER caches API or media
   (those stay live), and never touches cross-origin requests (fonts/CDN). */
const CACHE = "artisan-ai-v1";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (e) => {
  e.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return; // never intercept POST/PATCH (auth, uploads)
  if (url.origin !== self.location.origin) return; // leave fonts / CDNs alone
  if (url.pathname.startsWith("/api") || url.pathname.startsWith("/media")) return; // live data

  // App shell + static assets: stale-while-revalidate.
  e.respondWith(
    (async () => {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(e.request);
      const network = fetch(e.request)
        .then((res) => {
          if (res && res.status === 200 && res.type === "basic") cache.put(e.request, res.clone());
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })()
  );
});
