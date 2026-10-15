import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// VITE_BASE_PATH permet publicar el frontend sota una subruta (p.ex. /demo/).
const base = process.env.VITE_BASE_PATH || '/'
if (!base.startsWith('/') || !base.endsWith('/')) {
  throw new Error(`VITE_BASE_PATH ha de començar i acabar amb '/' (és '${base}')`)
}

// Identificador d'aquesta compilació: va dins del programa i a version.json.
// Les pàgines obertes el comparen per saber si hi ha una versió nova (versioApp.js).
const versio = process.env.VITE_VERSIO || Date.now().toString(36)

const fitxerVersio = {
  name: 'fitxer-versio',
  generateBundle() {
    this.emitFile({ type: 'asset', fileName: 'version.json', source: JSON.stringify({ versio }) })
  },
  configureServer(server) {
    server.middlewares.use(`${base}version.json`, (_req, res) => {
      res.setHeader('Content-Type', 'application/json')
      res.end(JSON.stringify({ versio }))
    })
  }
}

export default defineConfig({
  base,
  plugins: [vue(), fitxerVersio],
  define: { __VERSIO_APP__: JSON.stringify(versio) },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
