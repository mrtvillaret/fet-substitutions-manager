// Errors de domini traduïts: el backend envia `codi` i `params` a més del
// `detail`. La web mostra `errors.<codi>` a l'idioma de la pantalla si en té la
// clau i, si no, el `detail` del servidor.
import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { missatgeDError, detallDError, registraTraductorErrors } from '../src/errorsApi.js'

const require = createRequire(import.meta.url)
const { createI18n } = require('vue-i18n')
const IDIOMES = ['ca', 'es', 'en', 'it']
const messages = Object.fromEntries(IDIOMES.map(l => [l, JSON.parse(readFileSync(new URL(`../src/locales/${l}.json`, import.meta.url), 'utf8'))]))
const i18n = locale => createI18n({ legacy: false, locale, fallbackLocale: 'ca', messages, missingWarn: false, fallbackWarn: false }).global

const error = (status, data) => ({ response: { status, data } })
const curta = { detail: 'La contrasenya ha de tenir almenys 8 caràcters', codi: 'contrasenya_curta', params: { minim: 8 } }

afterEach(() => registraTraductorErrors(null))

test('amb la clau del codi, el missatge surt traduït amb els paràmetres', async () => {
  registraTraductorErrors(i18n('es'))
  assert.equal(detallDError(error(400, curta)), 'La contraseña debe tener al menos 8 caracteres')
  assert.equal(await missatgeDError(error(400, curta), t => t), 'La contraseña debe tener al menos 8 caracteres')
})

test('també quan la resposta esperada era un fitxer (blob)', async () => {
  registraTraductorErrors(i18n('en'))
  const cos = new Blob([JSON.stringify({ detail: 'No hi ha vigilàncies per 2026-03-05', codi: 'sense_vigilancies', params: { data: '2026-03-05' } })], { type: 'application/json' })
  assert.equal(await missatgeDError(error(404, cos), t => t), 'There are no invigilations for 2026-03-05')
})

test('un codi sense traducció, o cap codi, mostra el detail del servidor', () => {
  registraTraductorErrors(i18n('it'))
  assert.equal(detallDError(error(400, { detail: 'Mode invàlid', codi: 'mode_invalid', params: {} })), 'Mode invàlid')
  assert.equal(detallDError(error(400, { detail: 'Format de data invàlid. Usa YYYY-MM-DD' })), 'Format de data invàlid. Usa YYYY-MM-DD')
})

test('sense traductor registrat, el detail; un detail que no és text no es toca', () => {
  assert.equal(detallDError(error(400, curta)), curta.detail)
  registraTraductorErrors(i18n('es'))
  const llista = [{ loc: ['body'], msg: 'x' }]
  assert.equal(detallDError(error(422, { detail: llista, codi: 'contrasenya_curta' })), llista)
  assert.equal(detallDError({}), undefined)
})

test('en català, cada errors.<codi> es mostra tal com el text del servidor', () => {
  // vue-i18n interpreta { } @ | $: cap text no pot canviar en passar-hi
  const { t } = i18n('ca')
  for (const [codi, text] of Object.entries(messages.ca.errors)) {
    const params = Object.fromEntries([...text.matchAll(/\{(\w+)\}/g)].map(m => [m[1], `«${m[1]}»`]))
    assert.equal(t(`errors.${codi}`, params), text.replace(/\{(\w+)\}/g, (_, p) => `«${p}»`), codi)
  }
})
