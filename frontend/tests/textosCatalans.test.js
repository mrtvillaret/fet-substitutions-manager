import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { defaultOptions } from 'primevue/config/config.cjs.js'
import { textosPrimeVueCa } from '../src/primevueCa.js'

const arrel = new URL('../src/', import.meta.url)
const cataleg = llengua => JSON.parse(readFileSync(new URL(`locales/${llengua}.json`, arrel), 'utf8'))
const camps = text => [...text.matchAll(/\{[^}]*\}/g)].map(m => m[0]).sort()
test('el català defineix tots els textos de PrimeVue, inclosa l’accessibilitat', () => {
  const source = readFileSync(new URL('i18n.js', arrel), 'utf8')
  const objecte = source.slice(source.indexOf('export const primeLocales =') + 'export const primeLocales ='.length, source.indexOf('\nconst i18n ='))
  const locale = new Function('textosPrimeVueCa', `return (${objecte})`)(textosPrimeVueCa).ca
  const comprova = (original, traduit) => {
    for (const [clau, valor] of Object.entries(original)) {
      assert(Object.hasOwn(traduit, clau), clau)
      if (typeof valor === 'string') assert.deepEqual(camps(traduit[clau]), camps(valor), clau)
      else if (valor && typeof valor === 'object' && !Array.isArray(valor)) comprova(valor, traduit[clau])
    }
  }
  comprova(defaultOptions.locale, locale)
  assert.equal(locale.emptySearchMessage, 'No hi ha resultats')
})
test('el català no conté els anglicismes revisats', () => {
  const errors = []
  const visita = (objecte, prefix = '') => {
    for (const [clau, valor] of Object.entries(objecte)) {
      if (valor && typeof valor === 'object') visita(valor, prefix + clau + '.')
      else if (typeof valor === 'string' && /\b(?:slots?|items?|default|top|seeds?|greedy|backtracking)\b/i.test(valor.replace(/\{[^}]*\}/g, ''))) errors.push(prefix + clau)
    }
  }
  visita(cataleg('ca'))
  assert.deepEqual(errors, [])
})
test('els noms de rol estan traduïts i mantenen els tres codis de l’API', () => {
  for (const idioma of ['ca', 'es', 'en', 'it']) {
    const rols = cataleg(idioma).common.roles
    assert.deepEqual(Object.keys(rols).sort(), ['admin', 'super_admin', 'user'])
    for (const [codi, etiqueta] of Object.entries(rols)) assert.notEqual(codi, etiqueta)
  }
})
