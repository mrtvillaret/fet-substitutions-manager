import { test, expect } from '@playwright/test'
import { administradorCarrega, contrasenya } from './entorn.js'

// Si la càrrega del planificador falla, la pantalla no té les restriccions ni
// els costos desats: «Desa» i «Genera» no hi han d'arribar (desarien la de la
// pantalla i esborrarien les bones). Una sola entrada per projecte.
const toca = (element, tacte) => tacte ? element.tap() : element.click()
const ESTAT = ['/api/scheduler/restriccions', '/api/scheduler/costos-professors', '/api/scheduler/config', '/api/scheduler/dates']

test('planificador: si la càrrega falla, «Desa» no canvia res i es pot tornar a carregar', async ({ page, hasTouch }) => {
  let falla = true
  await page.route('**/api/scheduler/restriccions', (route) =>
    falla && route.request().method() === 'GET' ? route.fulfill({ status: 500, body: '{}' }) : route.fallback())
  const escriptures = []
  page.on('request', (peticio) => {
    if (peticio.url().includes('/api/scheduler/') && peticio.method() !== 'GET') escriptures.push(`${peticio.method()} ${peticio.url()}`)
  })

  await page.goto('/scheduler')
  await page.getByRole('textbox', { name: 'Usuari', exact: true }).fill(administradorCarrega)
  await page.getByLabel('Contrasenya', { exact: true }).fill(contrasenya)
  await toca(page.getByRole('button', { name: 'Inicia sessió', exact: true }), hasTouch)

  const avis = page.getByText("No s'ha pogut carregar la configuració del planificador", { exact: false })
  await expect(avis).toBeVisible()
  // L'estat de la BD abans (page.request no passa per page.route)
  const llegeix = async () => Promise.all(ESTAT.map(async (ruta) => (await page.request.get(ruta)).json()))
  const abans = await llegeix()

  const desa = page.locator('#btn-save')
  await expect(desa).toBeDisabled()
  await desa.click({ force: true }) // un botó desactivat no envia res
  await page.waitForTimeout(500)

  expect(escriptures).toEqual([])
  expect(await llegeix()).toEqual(abans)

  // Torna a carregar: ara la càrrega va bé i ja es pot desar
  falla = false
  await toca(page.getByRole('button', { name: 'Torna a carregar', exact: true }), hasTouch)
  await expect(avis).toBeHidden()
  await expect(desa).toBeEnabled()
})
