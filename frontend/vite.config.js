import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// VITE_BASE_PATH permet publicar el frontend sota una subruta (p.ex. /demo/).
const base = process.env.VITE_BASE_PATH || '/'
if (!base.startsWith('/') || !base.endsWith('/')) {
  throw new Error(`VITE_BASE_PATH ha de començar i acabar amb '/' (és '${base}')`)
}

export default defineConfig({
  base,
  plugins: [vue()],
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
