/**
 * PWA bootstrap: registers the service worker (public/sw.js, see that
 * file for caching/update strategy) and removes the inline splash
 * screen once React has mounted. Kept as one small, dependency-free
 * module rather than pulling in a PWA library.
 */
export function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return

  window.addEventListener('load', () => {
    const swUrl = `${import.meta.env.BASE_URL}sw.js`
    navigator.serviceWorker.register(swUrl).then((registration) => {
      // Check for a newer deployment whenever the tab becomes visible
      // again (e.g. the user switches back to the app) -- keeps the
      // "auto update on new deployment" behavior working even for a
      // tab/PWA window left open for a long time, without polling in
      // the background while it's not being looked at.
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') registration.update()
      })
    }).catch((err) => {
      // Never let a registration failure break the app itself.
      console.warn('Service worker registration failed:', err)
    })
  })
}

export function hideSplashScreen() {
  const splash = document.getElementById('app-splash')
  if (!splash) return
  splash.classList.add('app-splash--hidden')
  window.setTimeout(() => splash.remove(), 250)
}
