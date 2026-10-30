import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ordenaAlfabeticament } from '../src/ordreAlfabetic.js'

test('ordre alfabètic natural i en català (el mateix que noms.ordre_alfabetic del backend)', () => {
  // La mateixa llista que backend/tests/test_noms.py
  const noms = ['Prof 10', 'prof 2', 'Èric', 'Prof 6', 'Zoe', 'Esteve', 'Àlex', 'Andreu', 'Prof 1',
    'Mariana', 'Mª Àngels', 'Maria']

  assert.deepEqual(ordenaAlfabeticament(noms), [
    'Àlex', 'Andreu', 'Èric', 'Esteve', 'Mª Àngels', 'Maria', 'Mariana', 'Prof 1', 'prof 2', 'Prof 6', 'Prof 10', 'Zoe',
  ])
})

test('no modifica la llista original', () => {
  const noms = ['Prof 10', 'Prof 6']
  ordenaAlfabeticament(noms)
  assert.deepEqual(noms, ['Prof 10', 'Prof 6'])
})
