/* ============================================================
   DashCam Monitor — Service Worker
   Enables background notifications and offline support
   ============================================================ */

const CACHE_NAME = "dashcam-v1";
const STATIC_ASSETS = ["/", "/index.html", "/style.css", "/app.js", "/manifest.json"];

// ── Install: Cache static assets ──────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// ── Activate: Clean old caches ─────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: Serve from cache, fallback to network ───────────
self.addEventListener("fetch", (event) => {
  // Only cache GET requests for static assets
  if (event.request.method !== "GET") return;
  if (event.request.url.includes("/api/")) return; // Don't cache API

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

// ── Push: Show notification from background ────────────────
self.addEventListener("push", (event) => {
  let data = { title: "🚨 Motion Detected!", body: "Movement detected on camera", image: null };
  try {
    data = { ...data, ...event.data.json() };
  } catch (e) {}

  const options = {
    body: data.body,
    icon: "/icons/icon-192.png",
    badge: "/icons/badge-72.png",
    tag: "motion-alert",
    renotify: true,
    vibrate: [200, 100, 200, 100, 400],
    requireInteraction: true,
    data: { url: "/", alertId: data.alertId },
    actions: [
      { action: "view", title: "View Photo" },
      { action: "dismiss", title: "Dismiss" },
    ],
  };

  if (data.image) {
    options.image = data.image;
  }

  event.waitUntil(self.registration.showNotification(data.title, options));
});

// ── Notification Click ─────────────────────────────────────
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  if (event.action === "dismiss") return;

  event.waitUntil(
    clients.matchAll({ type: "window" }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          return client.focus();
        }
      }
      return clients.openWindow("/");
    })
  );
});

// ── Message from main app ──────────────────────────────────
self.addEventListener("message", (event) => {
  if (event.data?.type === "SHOW_NOTIFICATION") {
    const { title, body, image } = event.data.payload;
    self.registration.showNotification(title, {
      body,
      icon: "/icons/icon-192.png",
      tag: "motion-alert",
      renotify: true,
      vibrate: [200, 100, 200, 100, 400],
      requireInteraction: false,
      image,
    });
  }
});
