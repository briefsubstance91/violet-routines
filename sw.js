const CACHE = 'violet-v7';
const SHELL = ['/manifest.json', '/icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  // Delete old caches, claim clients — no navigate() needed since HTML is never cached
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  e.waitUntil(
    self.registration.showNotification(data.title || "Violet's Routines", {
      body:    data.body    || '',
      icon:    data.icon    || '/icon.svg',
      badge:   data.badge   || '/icon.svg',
      data:    data.data    || {},
      vibrate: [200, 100, 200],
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/routines';
  e.waitUntil(clients.openWindow(url));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Pass-through non-GET (POST saves, etc.)
  if (e.request.method !== 'GET') return;

  // Cache-first for /static/ — images and fonts rarely change
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      }))
    );
    return;
  }

  // Cache-first for shell files (manifest, icon)
  if (SHELL.includes(url.pathname)) {
    e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request)));
    return;
  }

  // Network-only for all Flask HTML routes — never cache so updates are instant
  // Falls back to cache only if completely offline
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
