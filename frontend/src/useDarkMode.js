import { useEffect, useState } from 'react'

const STORAGE_KEY = 'sap-job-hunter:theme' // 'light' | 'dark' | 'system'

function systemPrefersDark() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
}

function resolveIsDark(preference) {
  return preference === 'dark' || (preference === 'system' && systemPrefersDark())
}

/**
 * Returns [isDark, preference, setPreference]. `preference` is one of
 * 'light' | 'dark' | 'system' (default). The resolved theme is applied
 * via a `data-theme` attribute on <html> (see index.css's
 * [data-theme="dark"] block), and persisted to localStorage so it
 * survives reloads/reopening the installed app.
 */
export function useDarkMode() {
  const [preference, setPreference] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'system'
    } catch {
      return 'system'
    }
  })

  const [isDark, setIsDark] = useState(() => resolveIsDark(preference))

  useEffect(() => {
    setIsDark(resolveIsDark(preference))
    try {
      localStorage.setItem(STORAGE_KEY, preference)
    } catch {
      // localStorage unavailable (private browsing) -- preference just won't persist.
    }
  }, [preference])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', isDark ? '#0B1E3A' : '#0B1E3A')
  }, [isDark])

  // Follow the system preference live if the user hasn't overridden it.
  useEffect(() => {
    if (preference !== 'system' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => setIsDark(resolveIsDark('system'))
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [preference])

  return [isDark, preference, setPreference]
}
