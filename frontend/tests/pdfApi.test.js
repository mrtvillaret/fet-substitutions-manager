import { test } from 'node:test'
import assert from 'node:assert/strict'
import { provaCrides, COS, LECTURA } from './support/crides.js'
import * as api from '../src/api/pdf.js'

for (const [funcio, args, url] of [
  ['completAmb', ['2026-11-03'], '/api/pdf/complete/2026-11-03'],
  ['vigilanciesDelDiaAmb', ['2026-11-03'], '/api/pdf/vigilancies/2026-11-03'],
  ['vigilanciesIntervalAmb', [], '/api/pdf/vigilancies/interval'],
  ['informeDireccioAmb', [], '/api/informes/direccio'],
  ['informeProfessorAmb', [], '/api/informes/professor']
]) test(`${funcio}: URL, Blob amb els paràmetres, resposta i errors intactes`, async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const params = { format: 'hores', ordre: 'curs' }
  const peticions = []
  const client = { get: async (...a) => { peticions.push(a); return resposta } }
  assert.equal(await api[funcio](client, ...args, params), resposta)
  assert.deepEqual(peticions, [[url, { params, responseType: 'blob' }]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api[funcio](client, ...args, params), e => e === error)
})

// Cada funció: [funció, mètode HTTP, arguments, URL, arguments HTTP que passen tal qual]
provaCrides([
  [api.creaDisponiblesTotsDiesAmb, 'post', [], '/api/pdf/disponibles-tots-dies', COS],
  [api.preferenciesAmb, 'get', [], '/api/pdf/preferences', LECTURA],
  [api.desaPreferenciesAmb, 'put', [], '/api/pdf/preferences', COS],
  [api.validacionsAmb, 'get', ['2026-11-03'], '/api/pdf/2026-11-03/validacions', LECTURA],
  [api.comptesSenseNivellAmb, 'get', [], '/api/pdf/vigilancies/comptes-sense-nivell', LECTURA]
])
