/**
 * Service worker for SAP Job Hunter.
 *
 * Hand-rolled (no Workbox/vite-plugin-pwa) -- this app is small enough
 * that a plain, explicit service worker is simpler and lighter than
 * adding a new build-time dependency, per "do not introduce
 * unnecessary libraries".
 *
 * CACHE_VERSION is injected at build time by vite.config.js (from
 * GITHUB_SHA in CI, so every deployment gets a distinct value with no
 * workflow changes needed -- GitHub Actions sets GITHUB_SHA
 * automatically in every job). Every cache name below is derived from
 * it, so a new deployment always gets fresh cache names -- the old
 * ones are deleted in the `activate` handler below. That's the whole
 * auto-update mechanism: nothing to configure, nothing to remember to
 * bump by hand.
 */
const CACHE_VERSION = '__BUILD_ID__' // replaced with the real build id at build time -- see vite.config.js's swVersionPlugin
const SHELL_CACHE = `sap-job-hunter-shell-${CACHE_VERSION}`
const RUNTIME_CACHE = `sap-job-hunter-runtime-${CACHE_VERSION}`
const CACHE_PREFIX = 'sap-job-hunter-'

// Small, unhashed files we know the exact URL of ahead of time. The
// hashed JS/CSS bundles Vite produces (assets/index-XXXX.js) are NOT
// listed here since their filenames change every build -- they're
// cached opportunistically at runtime instead (see fetch handler).
const APP_SHELL_URLS = [
  './',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(APP_SHELL_URLS))
      .then(() => self.skipWaiting()) // activate this version as soon as it's installed
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((name) => name.startsWith(CACHE_PREFIX) && name !== SHELL_CACHE && name !== RUNTIME_CACHE)
          .map((name) => caches.delete(name))
      ))
      .then(() => self.clients.claim()) // take control of already-open tabs immediately
  )
})

function isNavigationRequest(request) {
  return request.mode === 'navigate' ||
    (request.method === 'GET' && request.headers.get('accept')?.includes('text/html'))
}

function isHashedBuildAsset(url) {
  return url.pathname.includes('/assets/')
}

function isDataSnapshot(url) {
  return url.pathname.endsWith('/data/jobs.json')
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return // never intercept cross-origin (fonts CDN, etc.)

  if (isNavigationRequest(request)) {
    // Network-first for the HTML shell: always try to get the latest
    // index.html (which references the latest hashed JS/CSS) when
    // online; fall back to the cached shell when offline.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone()
          caches.open(SHELL_CACHE).then((cache) => cache.put('./', copy))
          return response
        })
        .catch(() => caches.match('./'))
    )
    return
  }

  if (isDataSnapshot(url)) {
    // Network-first for the job data snapshot: prefer fresh data,
    // fall back to the last cached copy when offline.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone()
          caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy))
          return response
        })
        .catch(() => caches.match(request))
    )
    return
  }

  if (isHashedBuildAsset(url)) {
    // Cache-first for Vite's content-hashed JS/CSS bundles -- the
    // filename itself changes whenever the content does, so these are
    // safe to cache indefinitely.
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached
        return fetch(request).then((response) => {
          const copy = response.clone()
          caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy))
          return response
        })
      })
    )
    return
  }

  // Everything else (icons, manifest, misc static files): cache-first
  // with a network fallback that also populates the cache.
  event.respondWith(
    caches.match(request).then((cached) => {
      return cached || fetch(request).then((response) => {
        const copy = response.clone()
        caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy))
        return response
      }).catch(() => cached)
    })
  )
})
