import { mergeConfig } from 'vite'
import base from '../vite.config.js'
import { backendURL } from './entorn.js'

export default mergeConfig(base, {
  // Vite també carrega .env per defecte: aquí queda desactivat explícitament.
  envDir: false,
  server: { host: '127.0.0.1', port: 5183, strictPort: true, proxy: { '/api': { target: backendURL } } }
})
