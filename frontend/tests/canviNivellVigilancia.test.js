import assert from 'node:assert/strict'
import test from 'node:test'

import { adaptaVigilanciaAlNivell } from '../src/vigilanciesNivell.js'

const fila = {
  nivell: '1-ESO',
  tipus: 'Matemàtiques',
  grups: '1-ESO-A',
  aula: 'A1',
  vigilant: 'Prof 1',
  comentaris: 'Porta calculadora'
}

test('manté el tipus i el grup si són vàlids al nivell nou', () => {
  const resultat = adaptaVigilanciaAlNivell(fila, '2-ESO', {
    tipusDe: () => ['Matemàtiques', 'Català'],
    grupsDe: () => ['2-ESO-A', '1-ESO-A']
  })

  assert.deepEqual(resultat, { ...fila, nivell: '2-ESO' })
})

test('esborra només el tipus o el grup que no és vàlid al nivell nou', () => {
  const senseTipus = adaptaVigilanciaAlNivell(fila, '2-ESO', {
    tipusDe: () => ['Català'],
    grupsDe: () => ['1-ESO-A']
  })
  const senseGrup = adaptaVigilanciaAlNivell(fila, '2-ESO', {
    tipusDe: () => ['Matemàtiques'],
    grupsDe: () => ['2-ESO-A']
  })

  assert.deepEqual(senseTipus, { ...fila, nivell: '2-ESO', tipus: '' })
  assert.deepEqual(senseGrup, { ...fila, nivell: '2-ESO', grups: '' })
})

test('manté sempre aula, vigilant i comentaris', () => {
  const resultat = adaptaVigilanciaAlNivell(fila, 'GENERAL', {
    tipusDe: () => [],
    grupsDe: () => []
  })

  assert.equal(resultat.aula, 'A1')
  assert.equal(resultat.vigilant, 'Prof 1')
  assert.equal(resultat.comentaris, 'Porta calculadora')
})
