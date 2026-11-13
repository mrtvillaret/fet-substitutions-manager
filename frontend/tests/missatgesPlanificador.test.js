import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createI18n } from 'vue-i18n'
import { avisosDeConfiguracio, avisosDeGrupsSenseNivell, tradueixMissatge } from '../src/views/scheduler/missatges.js'

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
  const files = ['planificador/config.py', 'planificador/diagnostic.py', 'planificador/generacio.py', 'scheduler_engine/core/diagnostic.py', 'scheduler_engine/generators/v2_intents.py', 'scheduler_engine/generators/v2_backtrack.py', 'scheduler_engine/generators/v3_sa.py']
  const codes = new Set(files.flatMap(file => [...readFileSync(new URL(`../../backend/${file}`, import.meta.url), 'utf8').matchAll(/missatge\("([^"]+)"/g)].map(m => m[1])))
  const params = { nivell: 'N', nom: 'A', altre: 'B', count: 3, hores: 2, dies: 2, causa: 'dia_hora_fix', assignatures: ['A', 'B'], noms: ['A', 'B'], grup: 'G', index: 1, dia: 'Dilluns', hora: '09:00', collocats: 1, esperats: 3, segons: 20, nodes: 1000, professor: 'P', max: 1 }
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

test('examen fixat: la franja és el dia (traduït) i l’hora que hi hagi', () => {
  i18n.global.locale.value = 'ca'
  assert.equal(
    tradueixMissatge(msg('fixat_a_hora_sense_inici', { nom: 'Fil', nivell: '1-BAT', dia: 'Dilluns', hora: '11:30' }), t),
    '«Fil» està fixat a Dilluns 11:30, però 1-BAT no hi té marcat l’inici d’un examen'
  )
  assert.equal(
    tradueixMissatge(msg('fixat_fora_de_dates', { nom: 'Fil', dia: 'Dijous', hora: '' }), t),
    '«Fil» està fixat a Dijous, que no és entre les dates i hores planificades'
  )
  i18n.global.locale.value = 'en'
  const text = tradueixMissatge(msg('fixat_a_franja_prohibida', { nom: 'Fil', dia: '', hora: '09:00' }), t)
  assert.ok(text.includes('pinned to 09:00,'), text)
})

test('límit per professor: el màxim, els dies i els exàmens amb singular i plural', () => {
  const m = msg('limit_professor_insuficient', { professor: 'P', max: 1, count: 2, noms: ['A', 'B'], dies: 'Dilluns, Dimarts' })
  i18n.global.locale.value = 'ca'
  assert.equal(
    tradueixMissatge(m, t),
    'P: com a màxim 1 els dies Dilluns, Dimarts, i aquests dies són els únics possibles per a 2 exàmens: A, B'
  )
  i18n.global.locale.value = 'en'
  const un = tradueixMissatge(msg('limit_professor_insuficient', { professor: 'P', max: 0, count: 1, noms: ['A'], dies: 'Dilluns' }), t)
  assert.equal(un, 'P: at most 0 on Monday, and those are the only possible days for 1 exam: A')
})

test('l’avís d’un grup sense nivell es tradueix i va a les incidències en els quatre idiomes', () => {
  const avis = msg('grup_sense_nivell', { grup: '1-BAT-Z', assignatures: ['Filosofia'] })
  for (const lang of ['ca', 'es', 'en', 'it']) {
    i18n.global.locale.value = lang
    const text = tradueixMissatge(avis, t)
    assert.ok(text.includes('1-BAT-Z') && text.includes('Filosofia') && !text.includes('grup_sense_nivell'), text)
    // Es reconeix pel codi, no per si el text diu «avís» en aquell idioma
    assert.deepEqual(avisosDeConfiguracio([avis, 'una línia qualsevol', msg('examens_pendents')], t), [text])
  }
})

test('l’avís d’un nivell sense hores alliberades es tradueix i va a les incidències', () => {
  const avis = msg('nivell_sense_hores_alliberades', { nivell: '1-BAT' })
  const esperats = {
    ca: 'El nivell 1-BAT no té hores alliberades: es considera tot el dia lliure; comproveu-les',
    es: 'El nivel 1-BAT no tiene horas liberadas: se considera todo el día libre; compruébelas',
    en: 'Level 1-BAT has no released hours: the whole day is considered free; please check them',
    it: 'Il livello 1-BAT non ha ore liberate: si considera libera tutta la giornata; controllatele',
  }
  for (const [lang, text] of Object.entries(esperats)) {
    i18n.global.locale.value = lang
    assert.equal(tradueixMissatge(avis, t), text)
    assert.deepEqual(avisosDeConfiguracio([avis], t), [text])
  }
})

test('l’avís d’un nivell amb alliberaments però cap hora disponible es tradueix i va a les incidències', () => {
  const avis = msg('nivell_alliberaments_sense_hores', { nivell: '1-BAT' })
  const esperats = {
    ca: 'El nivell 1-BAT té alliberaments, però cap hora disponible per als exàmens; comproveu-los',
    es: 'El nivel 1-BAT tiene horas liberadas configuradas, pero ninguna hora disponible para los exámenes; compruébelas',
    en: 'Level 1-BAT has released hours set up, but no hour available for exams; please check them',
    it: 'Il livello 1-BAT ha ore liberate configurate, ma nessuna ora disponibile per gli esami; controllatele',
  }
  for (const [lang, text] of Object.entries(esperats)) {
    i18n.global.locale.value = lang
    assert.equal(tradueixMissatge(avis, t), text)
    assert.deepEqual(avisosDeConfiguracio([avis], t), [text])
  }
})

test('el diàleg de no viable i l’anàlisi només mostren els grups sense nivell', () => {
  const grup = msg('grup_sense_nivell', { grup: '1-BAT-Z', assignatures: ['Filosofia'] })
  const logs = [msg('nivell_sense_hores_alliberades', { nivell: '1-BAT' }), 'una línia qualsevol', grup, null]
  i18n.global.locale.value = 'ca'
  assert.deepEqual(avisosDeGrupsSenseNivell(logs, t), [tradueixMissatge(grup, t)])
  assert.deepEqual(avisosDeGrupsSenseNivell(undefined, t), [])
})
