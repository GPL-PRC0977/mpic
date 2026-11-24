const CACHE_NAME = "mpic-inventory-v2";
const APP_SHELL = [
  "/",
  "/history",
  "/static/manifest.webmanifest",
  "/static/primer-logo.png",
];
const EXTERNAL_ASSETS = [
  "https://cdn.tailwindcss.com",
  "https://unpkg.com/lucide@latest",
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(APP_SHELL);
    // These CDN responses are opaque, but can still be stored and returned while offline.
    await Promise.all(EXTERNAL_ASSETS.map(async (asset) => {
      try {
        const response = await fetch(asset, { mode: "no-cors" });
        await cache.put(asset, response);
      } catch {
        // The core pages remain available even if a third-party asset is unavailable.
      }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  event.respondWith((async () => {
    const cached = await caches.match(event.request);
    const isExternalAsset = new URL(event.request.url).origin !== self.location.origin;
    if (isExternalAsset && cached) return cached;
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
