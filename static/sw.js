const CACHE_NAME = "mpic-inventory-v1";
const APP_SHELL = ["/", "/static/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  event.respondWith((async () => {
    const cached = await caches.match(event.request);
    try {
      const response = await fetch(event.request);
      // Store HTML, local assets, and opaque CDN assets after their first successful load.
      if (response.ok || response.type === "opaque") {
        const cache = await caches.open(CACHE_NAME);
        cache.put(event.request, response.clone());
      }
      return response;
    } catch {
      if (cached) return cached;
      if (event.request.mode === "navigate") return caches.match("/");
      return Response.error();
    }
  })());
});
