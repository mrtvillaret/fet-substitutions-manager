import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { contrasenya, escenaris } from './entorn.js'

const toca = (element, tacte) => tacte ? element.tap() : element.click()
const filaAbsent = (page, nom) => page.getByRole('row').filter({ has: page.getByRole('cell', { name: nom, exact: true }) })

async function diaVisible(page, dia, professor, hora, grup) {
  await expect(page.getByPlaceholder('Selecciona data')).toHaveValue(dia.split('-').reverse().join('/'))
  const fila = filaAbsent(page, professor)
  await expect(fila).toHaveCount(1)
  await expect(fila.getByRole('cell', { name: hora, exact: true })).toBeVisible()
  await expect(fila.getByRole('cell', { name: grup, exact: true })).toBeVisible()
}

test.beforeEach(async ({ page, hasTouch }, testInfo) => {
  const { usuari, data } = escenaris[testInfo.project.name]
  await page.clock.setFixedTime(new Date(`${data}T10:00:00+02:00`))
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Usuari', exact: true }).fill(usuari)
  await page.getByLabel('Contrasenya', { exact: true }).fill(contrasenya)
  await toca(page.getByRole('button', { name: 'Inicia sessió', exact: true }), hasTouch)
  await expect(page.getByRole('heading', { name: '📋 Gestió de Substitucions', exact: true })).toBeVisible()
  await diaVisible(page, data, 'Prof 15', '10:00', '3-ESO-A')
})

test('sessió: entrar a Substitucions i sortir', async ({ page, hasTouch }) => {
  const capcalera = page.getByRole('banner')
  // Els botons d'icona encara no tenen nom accessible. S'acoten al rol
  // banner i a l'ordre de navegació, sense classes de PrimeVue.
  if (hasTouch) {
    await toca(capcalera.getByRole('button').first(), hasTouch)
    await toca(page.getByRole('dialog').getByRole('button', { name: 'Tancar sessió', exact: true }), hasTouch)
  } else {
    await capcalera.getByRole('button').last().click()
  }
  await expect(page.getByRole('button', { name: 'Inicia sessió', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('textbox', { name: 'Usuari', exact: true })).toBeVisible()
})

test('canvi de dia: següent, anterior i calendari recarreguen la taula', async ({ page, hasTouch }, testInfo) => {
  const { data, seguent, calendari } = escenaris[testInfo.project.name]
  // Ordre al banner: [menú,] anterior, calendari, següent.
  const botons = page.getByRole('banner').getByRole('button')
  await toca(botons.nth(hasTouch ? 3 : 2), hasTouch)
  await diaVisible(page, seguent, 'Prof 1', '08:00', '3-ESO-B')
  await expect(filaAbsent(page, 'Prof 15')).toHaveCount(0)
  await toca(botons.nth(hasTouch ? 1 : 0), hasTouch)
  await diaVisible(page, data, 'Prof 15', '10:00', '3-ESO-A')
  await expect(filaAbsent(page, 'Prof 1')).toHaveCount(0)
  await toca(page.getByPlaceholder('Selecciona data'), hasTouch)
  await toca(page.getByRole('gridcell', { name: String(Number(calendari.slice(-2))), exact: true }).first(), hasTouch)
  await diaVisible(page, calendari, 'Prof 1', '10:00', '2-ESO-C')
  await expect(filaAbsent(page, 'Prof 15')).toHaveCount(0)
})

test('assignació tàctil: substitut i vigilant es desen i persisteixen', async ({ page, hasTouch }, testInfo) => {
  const { data } = escenaris[testInfo.project.name]
  let fila = filaAbsent(page, 'Prof 15')
  await toca(fila.getByRole('cell', { name: 'Prof 15', exact: true }), hasTouch)
  await expect((hasTouch ? page.getByRole('toolbar', { name: 'Accions' }) : fila).getByRole('button', { name: 'Gestiona absències del professor', exact: true })).toBeVisible()
  await toca(fila.getByRole('button', { name: '🔄 Substitut', exact: true }), hasTouch)
  const guardat = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().includes(`/api/substitucions/${data}/10:00/`))
  await toca(page.getByRole('option', { name: /Prof 3\s/ }), hasTouch)
  expect((await guardat).ok()).toBeTruthy()
  await expect(fila.getByRole('button', { name: '🔄 Substitut', exact: true })).toContainText('Prof 3')
  let files = await (await page.request.get(`/api/substitucions/${data}`)).json()
  expect(files.find(f => f.professor_absent === 'Prof 15').substitut).toBe('Prof 3')
  await toca(fila.getByRole('button', { name: '🔄 Substitut', exact: true }), hasTouch)
  await expect(page.getByRole('listbox')).toBeVisible()
  await toca(page.getByRole('heading', { name: '📋 Gestió de Substitucions', exact: true }), hasTouch)
  await page.reload()
  await expect(filaAbsent(page, 'Prof 15').getByRole('button', { name: '🔄 Substitut', exact: true })).toContainText('Prof 3')

  await toca(page.getByRole('button', { name: /Vigilàncies$/ }), hasTouch)
  await expect(page.getByRole('heading', { name: /Vigilàncies/ })).toBeVisible()
  fila = page.getByRole('row').filter({ has: page.getByRole('button', { name: 'Aula', exact: true }).filter({ hasText: 'Aula E2E' }) })
  await expect(fila).toHaveCount(1)
  await (hasTouch ? fila.getByRole('cell').nth(1).tap({ position: { x: 2, y: 2 } }) : fila.getByRole('cell').nth(1).click({ position: { x: 2, y: 2 } }))
  await expect((hasTouch ? page.getByRole('toolbar', { name: 'Accions' }) : fila).getByRole('button', { name: 'Duplica la vigilància', exact: true })).toBeVisible()
  const vigs = await (await page.request.get(`/api/vigilancies/${data}`)).json()
  const vig = vigs.find(v => v.aula === 'Aula E2E')
  const disponibles = await (await page.request.get(`/api/vigilancies/${data}/11:30/disponibles`, { params: { vigilancia_id: vig.id } })).json()
  const candidat = disponibles.find(p => ['DISPONIBLE', 'ALLIBERAT', 'LLIURE'].includes(p.estat) && !p.ja_assignat)
  expect(candidat).toBeTruthy()
  await toca(fila.getByRole('button', { name: '👤 Vigilant', exact: true }), hasTouch)
  const vigilantDesat = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith(`/api/vigilancies/${data}/${vig.id}`))
  await toca(page.getByRole('option', { name: new RegExp(`${candidat.value}\\s`) }), hasTouch)
  expect((await vigilantDesat).ok()).toBeTruthy()
  await expect(fila.getByRole('button', { name: '👤 Vigilant', exact: true })).toContainText(candidat.value)
  files = await (await page.request.get(`/api/vigilancies/${data}`)).json()
  expect(files.find(v => v.id === vig.id).vigilant).toBe(candidat.value)
  await page.reload()
  await toca(page.getByRole('button', { name: /Vigilàncies$/ }), hasTouch)
  await expect(page.getByRole('button', { name: '👤 Vigilant', exact: true })).toContainText(candidat.value)
  await toca(page.getByRole('button', { name: '👤 Vigilant', exact: true }), hasTouch)
  await expect(page.getByRole('listbox')).toBeVisible()
})

test('PDF: descarregar el del dia, vàlid i amb pàgines', async ({ page, hasTouch }, testInfo) => {
  const { data } = escenaris[testInfo.project.name]
  await toca(page.getByRole('button', { name: 'Genera PDF', exact: true }), hasTouch)
  const validacio = page.waitForResponse(r => r.url().includes(`/api/pdf/${data}/validacions`))
  const descarrega = page.waitForEvent('download')
  await toca(page.getByRole('dialog').getByRole('button', { name: 'Genera PDF', exact: true }), hasTouch)
  const resposta = await validacio
  expect(resposta.ok()).toBeTruthy()
  const avisos = await resposta.json()
  if (avisos.total > 0) {
    const dialeg = page.getByRole('dialog')
    if (avisos.conflicts?.length) await toca(dialeg.getByRole('checkbox', { name: 'Confirmo que vull imprimir amb problemes importants.', exact: true }), hasTouch)
    await toca(dialeg.getByRole('button', { name: 'Sí, continua', exact: true }), hasTouch)
  }
  const pdf = await descarrega
  expect(pdf.suggestedFilename()).toBe(`complet_${data}.pdf`)
  const fitxer = testInfo.outputPath('dia.pdf')
  await pdf.saveAs(fitxer)
  const bytes = await readFile(fitxer)
  expect(bytes.length).toBeGreaterThan(1000)
  expect(bytes.subarray(0, 5).toString()).toBe('%PDF-')
  expect(bytes.subarray(-32).toString()).toContain('%%EOF')
  // Un parser real comprova l'estructura, més enllà de la signatura.
  expect(execFileSync('pdfinfo', [fitxer], { encoding: 'utf8' })).toMatch(/Pages:\s+[1-9]\d*/)
})
