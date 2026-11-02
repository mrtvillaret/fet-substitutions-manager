import { test } from 'node:test'
import assert from 'node:assert/strict'
import { disponiblesEnBlocAmb } from '../src/api/substitucions.js'

test('carrega els disponibles de totes les hores amb una sola petició', async () => {
  const peticions = []
  const client = {
    post: async (...args) => {
      peticions.push(args)
      return { data: { results: { '08:00': {}, '09:00': {}, '10:00': {} } } }
    }
  }

  const hores = ['08:00', '09:00', '10:00']
  const resultat = await disponiblesEnBlocAmb(client, '2026-04-20', hores)

  assert.equal(peticions.length, 1)
  assert.deepEqual(peticions[0], [
    '/api/substitucions/2026-04-20/disponibles-batch',
    { hores },
    { _silent: true }
  ])
  assert.deepEqual(Object.keys(resultat), hores)
})
