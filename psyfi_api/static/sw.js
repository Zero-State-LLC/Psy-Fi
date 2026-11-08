// PsyFi Service Worker - progressive enhancement of the existing PWA shell.
// Strategies follow MOBILE_PWA_GUIDE.md + docs/PWA_GPU_ROUTE.md.
// Decision: /gpu/ is a separate route (not embedded); not shell-precached.

const CACHE_NAME = 'psyfi-shell-v43';
const SHELL_URLS = [
  '/',
  '/static/style.css',
  '/static/fonts/fonts.css',
  '/static/fonts/-F63fjptAgt5VM-kVkqdyU8n1i8q1w.woff2',
  '/static/fonts/-F63fjptAgt5VM-kVkqdyU8n1iEq129k.woff2',
  '/static/fonts/-F6qfjptAgt5VM-kVkqdyU8n3twJwl5FgtIU.woff2',
  '/static/fonts/-F6qfjptAgt5VM-kVkqdyU8n3twJwlBFgg.woff2',
  '/static/fonts/V8mDoQDjQSkFtoMM3T6r8E7mPb94C-s0.woff2',
  '/static/fonts/V8mDoQDjQSkFtoMM3T6r8E7mPbF4Cw.woff2',
  '/static/fonts/zYXzKVElMYYaJe8bpLHnCwDKr932-G7dytD-Dmu1syxQKYbABA.woff2',
  '/static/fonts/zYXzKVElMYYaJe8bpLHnCwDKr932-G7dytD-Dmu1syxeKYY.woff2',
  '/static/app.js',
  '/static/renderer.js',
  '/static/render_worker.js',
  '/static/viz/math.js',
  '/static/viz/instrumentMap.js',
  '/static/viz/compareSurface.js',
  '/static/viz/transitionSurface.js',
  '/static/viz/safetyPass.js',
  '/static/viz/engines/index.js',
  '/static/viz/parameterFieldWebGL.js',
  '/static/viz/deviceSensors.js',
  '/static/viz/launchSplash.js',
  '/static/viz/experiencePlayer.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/apple-touch-icon.png',
  '/static/images/psyfi-hero.jpg',
  '/assets/icons/pf-icon-reset-24.svg',
  '/assets/icons/pf-icon-field-grid-24.svg',
  '/assets/icons/pf-icon-binding-24.svg',
  '/assets/icons/pf-icon-psychedelic-24.svg',
  '/assets/icons/pf-icon-preset-24.svg',
  '/assets/icons/pf-icon-console-24.svg',
  '/assets/icons/pf-icon-ethics-24.svg',
  '/assets/icons/pf-icon-jhana-24.svg',
  '/assets/icons/pf-icon-valence-meter-24.svg',
  '/assets/icons/pf-icon-core-sigil-24.svg',
  '/assets/icons/pf-icon-core-sigil-48.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching app shell', CACHE_NAME);
      return cache.addAll(SHELL_URLS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log('[SW] Removing old cache:', name);
            return caches.delete(name);
          })
      )
    ).then(() => self.clients.claim())
  );
});

function isApiOrSimulateRequest(url) {
  return (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/simulate') ||
    url.pathname === '/health' ||
    url.pathname === '/docs' ||
    url.pathname.startsWith('/openapi')
  );
}

function isGpuRoute(url) {
  return url.pathname === '/gpu' || url.pathname.startsWith('/gpu/');
}

function isNavigationRequest(request) {
  return request.mode === 'navigate' || request.destination === 'document';
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);

  // Simulation/API traffic is network-only.
  if (isApiOrSimulateRequest(url)) {
    event.respondWith(fetch(request));
    return;
  }

  // GPU Lab (/gpu/): network-first; never use the legacy shell HTML as a
  // successful stand-in for GPU documents when online. Offline → shell `/`.
  if (isGpuRoute(url)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache hashed GPU assets opportunistically; skip opaque failures.
          if (response.ok && !isNavigationRequest(request)) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => {
          if (isNavigationRequest(request)) {
            return caches.match('/');
          }
          return caches.match(request).then((cached) => cached || Response.error());
        })
    );
    return;
  }

  // HTML navigation: network-first with shell fallback.
  if (isNavigationRequest(request)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match('/'))
    );
    return;
  }

  // Static assets under /static: cache-first.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) {
          return cached;
        }
        return fetch(request).then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        });
      })
    );
  }
});
