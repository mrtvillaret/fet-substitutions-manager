import { test } from 'node:test'
import assert from 'node:assert/strict'
import { provaCrides, LECTURA } from './support/crides.js'
import * as api from '../src/api/estadistiques.js'

// Cada funció: [funció, mètode HTTP, arguments, URL, arguments HTTP que passen tal qual]
provaCrides([
  [api.frangesAmb, 'get', [], '/api/estadistiques/franges', LECTURA],
  [api.professorAmb, 'get', ['A / B'], '/api/estadistiques/professor/A%20%2F%20B', LECTURA],
  [api.detallClassesAmb, 'get', [], '/api/estadistiques/classes/detall', LECTURA]
])

test('batch: una petició amb dates i hores, resposta i errors originals', async () => {
  const params = { data_inici: '2026-01-01', data_final: '2026-12-31', hores: ['08:00'] }
  const resposta = { data: { resum: {}, professors_informe: [] } }
  const client = { get: async (...args) => {
    assert.deepEqual(args, ['/api/estadistiques/batch', { params }])
    return resposta
  } }
  assert.equal(await api.batchAmb(client, { params }), resposta)
  const error = new Error('error del lot')
  client.get = async () => { throw error }
  await assert.rejects(api.batchAmb(client, { params }), e => e === error)
})
