import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createI18n } from 'vue-i18n'
import { tradueixMissatge } from '../src/views/scheduler/missatges.js'

const messages = Object.fromEntries(['ca', 'es', 'en', 'it'].map(lang => [lang, JSON.parse(readFileSync(new URL(`../src/locales/${lang}.json`, import.meta.url), 'utf8'))]))
const i18n = createI18n({ legacy: false, locale: 'ca', fallbackLocale: false, messages })
const t = i18n.global.t
const msg = (codi, params = {}) => ({ codi, params })

test('capacitat amb singular i plural en els quatre idiomes', () => {
  const units = { ca: ['1 hora', '2 hores', '1 dia', '2 dies'], es: ['1 hora', '2 horas', '1 día', '2 días'], en: ['1 time', '2 times', '1 day', '2 days'], it: ['1 ora', '2 ore', '1 giorno', '2 giorni'] }
  for (const [lang, [oneHour, hours, oneDay, days]] of Object.entries(units)) {
    i18n.global.locale.value = lang
    const one = tradueixMissatge(msg('capacitat_nivell_dates', { nivell: 'N', count: 3, hores: 1, dies: 1 }), t)
    const many = tradueixMissatge(msg('capacitat_nivell_dates', { nivell: 'N', count: 3, hores: 2, dies: 2 }), t)
    assert.ok(one.includes(oneHour) && one.includes(oneDay), one)
    assert.ok(many.includes(hours) && many.includes(days), many)
  }
})

test('la causa es tradueix i el nom de l’examen es conserva literalment', () => {
  const causes = { ca: 'Dia/hora fixat', es: 'Día/hora fijado', en: 'Fixed day/time', it: 'Giorno/ora fissato' }
  for (const [lang, causa] of Object.entries(causes)) {
    i18n.global.locale.value = lang
    const text = tradueixMissatge(msg('examen_sense_hora_causa', { nom: 'Examen {A} <B>', causa: 'dia_hora_fix' }), t)
    assert.ok(text.includes('Examen {A} <B>') && text.includes(causa), text)
  }
})

test('mateix codi es torna a traduir quan canvia l’idioma', () => {
  const m = msg('examens_pendents')
  i18n.global.locale.value = 'ca'
  assert.equal(tradueixMissatge(m, t), 'No s’han pogut col·locar tots els exàmens')
  i18n.global.locale.value = 'en'
  assert.equal(tradueixMissatge(m, t), 'Not all exams could be placed')
  assert.deepEqual(m, msg('examens_pendents'))
})

test('tots els codis emesos pel backend tenen text i paràmetres resolts als quatre idiomes', () => {
  const files = ['planificador/diagnostic.py', 'planificador/generacio.py', 'scheduler_engine/core/diagnostic.py', 'scheduler_engine/generators/v2_intents.py', 'scheduler_engine/generators/v2_backtrack.py', 'scheduler_engine/generators/v3_sa.py']
  const codes = new Set(files.flatMap(file => [...readFileSync(new URL(`../../backend/${file}`, import.meta.url), 'utf8').matchAll(/missatge\("([^"]+)"/g)].map(m => m[1])))
  const params = { nivell: 'N', nom: 'A', altre: 'B', count: 3, hores: 2, dies: 2, causa: 'dia_hora_fix', assignatures: ['A', 'B'], noms: ['A', 'B'], grup: 'G', index: 1, dia: 'Dilluns', hora: '09:00', collocats: 1, esperats: 3 }
  for (const lang of Object.keys(messages)) {
    i18n.global.locale.value = lang
    for (const code of codes) {
      assert.equal(typeof messages[lang].scheduler.diagnostic[code], 'string', `${lang}: ${code}`)
      const text = tradueixMissatge(msg(code, params), t)
      assert.ok(text && !text.includes('scheduler.diagnostic.') && !/[{}]/.test(text), `${lang}: ${code}: ${text}`)
    }
  }
})

test('les llistes llargues mostren quatre noms i el recompte restant', () => {
  i18n.global.locale.value = 'ca'
  const text = tradueixMissatge(msg('fixats_mateix_dia', { index: 1, assignatures: ['A', 'B', 'C', 'D', 'E'], noms: ['A', 'B'], dia: 'Dilluns' }), t)
  assert.ok(text.includes('A, B, C, D i 1 més'), text)
  assert.ok(text.includes('Dilluns'), text)
  assert.equal(tradueixMissatge('log anterior', t), 'log anterior')
})
