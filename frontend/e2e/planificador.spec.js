import { test, expect } from '@playwright/test'
import { administrador, contrasenya } from './entorn.js'

// El planificador és de l'administrador: a l'escriptori i al mòbil (390 px, tàctil).
// Amb l'usuari de la preparació: els altres fluxos ja entren 5 cops per minut
// amb els seus (el límit d'entrades per usuari)
const toca = (element, tacte) => tacte ? element.tap() : element.click()

test.beforeEach(async ({ page, hasTouch }) => {
  await page.goto('/scheduler')
  await page.getByRole('textbox', { name: 'Usuari', exact: true }).fill(administrador)
  await page.getByLabel('Contrasenya', { exact: true }).fill(contrasenya)
  await toca(page.getByRole('button', { name: 'Inicia sessió', exact: true }), hasTouch)
})

test('planificador: el cost total es desglossa (quantitat × pes = punts)', async ({ page, hasTouch }, testInfo) => {
  // L'últim horari (preparat per l'API) es recupera al pas de generació
  await toca(page.getByRole('navigation').getByText('Generació', { exact: true }), hasTouch)
  const boto = page.getByRole('button', { name: 'Veure el desglossament del cost', exact: true })
  await expect(boto).toBeVisible()
  const cost = (await boto.locator('xpath=ancestor::span[contains(@class, "kpi-value")]').innerText()).trim()

  await toca(boto, hasTouch)
  const panell = page.getByRole('dialog', { name: 'Desglossament del cost' })
  await expect(panell).toBeVisible()
  await expect(panell.getByRole('row', { name: /^Total/ })).toBeVisible()
  const files = await panell.getByRole('row').allInnerTexts()
  testInfo.attach('desglossament', { body: [`Cost total: ${cost}`, ...files].join('\n'), contentType: 'text/plain' })
  console.log(`[${testInfo.project.name}] Cost total: ${cost}\n${files.join('\n')}`)

  // Cada fila: «concepte  n × pes  punts»; la suma és el total i el total és el cost
  const punts = (text) => Number(text.trim().split(/\s+/).pop().replace(/\./g, ''))
  const conceptes = files.filter((f) => !f.startsWith('Total'))
  expect(conceptes.length).toBeGreaterThan(0)
  for (const fila of conceptes) expect(fila).toMatch(/\d+ × \d/)
  const total = punts(files.find((f) => f.startsWith('Total')))
  expect(conceptes.reduce((suma, f) => suma + punts(f), 0)).toBe(total)
  expect(Number(cost.replace(/\./g, ''))).toBe(total)

  // Al mòbil el panell cap a la pantalla
  const caixa = await panell.boundingBox()
  const amplada = page.viewportSize().width
  expect(caixa.x).toBeGreaterThanOrEqual(0)
  expect(caixa.x + caixa.width).toBeLessThanOrEqual(amplada)

  testInfo.attach('panell', { body: await page.screenshot(), contentType: 'image/png' })

  // Tornar-hi a tocar el tanca
  await toca(boto, hasTouch)
  await expect(panell).toBeHidden()
})
