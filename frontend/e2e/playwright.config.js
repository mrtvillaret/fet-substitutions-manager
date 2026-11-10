import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'
import { administrador, backendURL, contrasenya, escenaris, frontendURL } from './entorn.js'

const credencials = {
  ADMIN_USERNAME: administrador, ADMIN_PASSWORD: contrasenya, ADMIN_INSTITUCIO: 'centre_e2e',
  ADMIN_CENTRE1_USERNAME: escenaris.escriptori.usuari, ADMIN_CENTRE1_PASSWORD: contrasenya, ADMIN_CENTRE1_INSTITUCIO: 'centre_e2e',
  USER_CENTRE1_USERNAME: escenaris.mobil.usuari, USER_CENTRE1_PASSWORD: contrasenya, USER_CENTRE1_INSTITUCIO: 'centre_e2e'
}
const cita = (valor) => `'${valor.replaceAll("'", "'\\''")}'`
// Per defecte, el servidor de desenvolupament de Vite. Amb E2E_SERVIDOR=build
// (npm run e2e:build, el que fa la CI), es compila el frontend com a producció
// i se serveix amb `vite preview`: es prova el mateix codi que es publica.
const ambBuild = process.env.E2E_SERVIDOR === 'build'
const opcionsVite = '--config e2e/vite.config.js --mode e2e'

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.js',
  globalSetup: './prepara.js',
  outputDir: '../test-results',
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: resolve(import.meta.dirname, '../playwright-report'), open: 'never' }]],
  use: {
    baseURL: frontendURL, browserName: 'chromium', locale: 'ca-ES', timezoneId: 'Europe/Madrid',
    trace: 'retain-on-failure', screenshot: 'only-on-failure'
  },
  projects: [
    { name: 'escriptori', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobil', use: { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } }
  ],
  webServer: [
    {
      command: `${cita(process.env.E2E_PYTHON || resolve(import.meta.dirname, '../../backend/venv/bin/python'))} e2e/servidor.py ${cita(JSON.stringify(credencials))}`,
      cwd: '..', url: `${backendURL}/api/health`, reuseExistingServer: false, timeout: 60_000
    },
    {
      command: ambBuild
        ? `npm run build -- ${opcionsVite} && npm run preview -- ${opcionsVite}`
        : `npm run dev -- ${opcionsVite}`,
      cwd: '..', url: frontendURL, reuseExistingServer: false, timeout: ambBuild ? 180_000 : 60_000,
      env: { VITE_BASE_PATH: '/', VITE_VERSIO: 'e2e' }
    }
  ]
})
