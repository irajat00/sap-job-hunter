import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

// VITE_BASE_PATH is only set by the GitHub Pages deploy workflow
// (.github/workflows/deploy-pages.yml), to "/<repo-name>/" -- a GitHub
// Pages *project* site (as opposed to a <user>.github.io user/org
// site) is served from a subpath, so every asset URL needs that
// prefix. Local dev (`npm run dev`/`npm run build` with no env var
// set) is completely unaffected -- base stays '/' exactly as before.
const basePath = process.env.VITE_BASE_PATH || '/'

// A distinct value per deployment, used only to version the service
// worker's cache names (see public/sw.js) so a new deployment always
// invalidates old caches automatically. GITHUB_SHA is set
// automatically by every GitHub Actions run -- no workflow changes
// needed. Falls back to a timestamp for local builds/dev.
const buildId = process.env.GITHUB_SHA || String(Date.now())

/**
 * Tiny, dependency-free plugin: after Vite copies public/sw.js
 * verbatim into dist/sw.js (the same mechanism that already places
 * jobs.json/manifest.json/icons there), replace the '__BUILD_ID__'
 * placeholder with the real build id. Plain text substitution --
 * the service worker is never bundled/transformed by Rollup, so it
 * stays a simple classic script with no ESM/module-worker concerns.
 */
function swVersionPlugin() {
  return {
    name: 'sw-version',
    closeBundle() {
      const swPath = path.resolve(__dirname, 'dist/sw.js')
      if (!fs.existsSync(swPath)) return
      const contents = fs.readFileSync(swPath, 'utf-8')
      fs.writeFileSync(swPath, contents.replace('__BUILD_ID__', buildId))
    },
  }
}

export default defineConfig({
  base: basePath,
  plugins: [react(), swVersionPlugin()],
  server: {
    port: 5173,
  },
})
