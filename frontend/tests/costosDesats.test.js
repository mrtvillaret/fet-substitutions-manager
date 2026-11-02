// node --test tests/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { costosDesats } from '../src/views/scheduler/costos.js'

const PER_DEFECTE = { globals: { substitucio: 80, abans_jornada: 30, despres_jornada: 30, no_treballa_dia: 60 }, individuals: {} }

test('la pantalla mostra els costos desats (resposta del backend)', () => {
  const resposta = {
    costos_professors: {
      globals: { substitucio: 50, abans_jornada: 10, despres_jornada: 20, no_treballa_dia: 90 },
      individuals: { 'Prof 48': { abans_jornada: 90 } }
    }
  }
  assert.deepEqual(costosDesats(resposta, PER_DEFECTE), resposta.costos_professors)
})

test('els globals que no hi són es queden amb el valor de la pantalla', () => {
  const resposta = { costos_professors: { globals: { substitucio: 50 }, individuals: {} } }
  assert.deepEqual(costosDesats(resposta, PER_DEFECTE).globals, { ...PER_DEFECTE.globals, substitucio: 50 })
})

test('sense resposta, els de la pantalla', () => {
  assert.deepEqual(costosDesats(undefined, PER_DEFECTE), PER_DEFECTE)
})
