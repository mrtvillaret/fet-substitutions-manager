import { test } from 'node:test'
import assert from 'node:assert/strict'
import { novesAmbGrup } from '../src/noSubstituirAmbGrup.js'

test('avisa de les activitats que s\'afegeixen a «No substituir» i tenen grup a l\'horari', () => {
  const ambGrup = ['Català', 'Tutoria', '']
  const previes = ['Guàrdia', 'Tutoria']

  // Tutoria ja hi era (no és nova); Guàrdia i Pares no tenen grup
  assert.deepEqual(novesAmbGrup(['Guàrdia', 'Tutoria', 'Català', 'Pares'], previes, ambGrup), ['Català'])
  assert.deepEqual(novesAmbGrup(['Guàrdia', 'Tutoria'], previes, ambGrup), [])
  // El buit és un nom més
  assert.deepEqual(novesAmbGrup(['', 'Català'], [], ambGrup), ['', 'Català'])
})
