import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { CONCEPTES_COST, filesDesglossament } from '../src/views/scheduler/costDesglossament.js'

const arrel = new URL('..', import.meta.url)
const locale = (codi) => JSON.parse(readFileSync(new URL(`src/locales/${codi}.json`, arrel), 'utf8'))
const t = (clau) => clau.split('.').reduce((o, k) => o?.[k], locale('ca')) ?? clau

test('desglossament del cost: quantitat × pes, només conceptes amb punts, i el total', () => {
  const { files, total, text } = filesDesglossament([
    { concepte: 'abans_jornada', quantitat: 2, pes: 30, punts: 60 },
    { concepte: 'substitucio', quantitat: 2, pes: 80, punts: 160 },
    { concepte: 'substitucio', quantitat: 1, pes: 10, punts: 10 },
    { concepte: 'zona_examen', quantitat: 3, pes: 0, punts: 0 },
    { concepte: 'preferencia_mateix_dia', quantitat: 1, pes: -120, punts: -120 },
    { concepte: 'limit_dies_professor', quantitat: 1, pes: 12000, punts: 12000 },
  ], t, 'ca-ES')
  assert.deepEqual(files.map((f) => [f.etiqueta, f.calcul, f.punts]), [
    ['Substitucions', '2 × 80 + 1 × 10', 170],
    ['Arriben abans', '2 × 30', 60],
    ['Preferència mateix dia', '1 × -120', -120],
    ["Límit d'exàmens per professor", '1 × 12.000', 12000],
  ])
  assert.equal(total, 12110)
  assert.equal(text(total), '12.110')
})

test('desglossament del cost: sense punts no hi ha files (la icona no surt)', () => {
  assert.deepEqual(filesDesglossament([], t).files, [])
  assert.deepEqual(filesDesglossament(undefined, t).files, [])
})

test('desglossament del cost: els conceptes del backend tenen text als quatre idiomes', () => {
  const punts = readFileSync(new URL('../backend/scheduler_engine/core/punts.py', arrel), 'utf8')
  const bloc = punts.match(/CONCEPTES = \(([\s\S]*?)\n\)/)[1]
  const delBackend = [...bloc.matchAll(/"([a-z_]+)"/g)].map((m) => m[1])
  assert.deepEqual(CONCEPTES_COST, delBackend)
  for (const codi of ['ca', 'es', 'en', 'it']) {
    const textos = locale(codi).scheduler.steps.results.costBreakdown
    for (const concepte of delBackend) assert.ok(textos.concepts[concepte], `${codi}: ${concepte}`)
    for (const clau of ['open', 'title', 'total']) assert.ok(textos[clau], `${codi}: ${clau}`)
  }
})
