import { test } from 'node:test'
import assert from 'node:assert/strict'
import { etiquetaDiaRestringit } from '../src/views/scheduler/textUtils.js'

// El límit per professor admet noms de dia (tots els d'aquell nom) i dates concretes.
test('etiqueta dels dies restringits: nom de dia o data amb el seu dia de la setmana', () => {
  assert.equal(etiquetaDiaRestringit('2027-03-01', undefined), 'Dilluns 01/03')
  assert.equal(etiquetaDiaRestringit('2027-03-09', undefined), 'Dimarts 09/03')
  assert.equal(etiquetaDiaRestringit('Dilluns', undefined), 'Dilluns')
})
