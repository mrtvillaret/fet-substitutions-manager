import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as pdf from '../src/api/pdf.js'

test('els PDF conserven el Blob i Content-Disposition sense transformar-los', async () => {
  const data = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
  const resposta = { data, headers: { 'content-disposition': 'attachment; filename="disponibles.pdf"' } }
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const cos = { data_inici: '2026-11-03' }
  assert.equal(await pdf.creaDisponiblesTotsDiesAmb(client, cos, { responseType: 'blob' }), resposta)
  assert.deepEqual(peticions, [['/api/pdf/disponibles-tots-dies', cos, { responseType: 'blob' }]])
})

test('els errors JSON rebuts com a Blob i la cancel·lació arriben intactes', async () => {
  for (const error of [
    { response: { data: new Blob(['{"detail":"prova"}'], { type: 'application/json' }), status: 400 } },
    { code: 'ERR_CANCELED' }
  ]) {
    const controller = new AbortController()
    controller.abort()
    const opcions = { responseType: 'blob', _silent: true, signal: controller.signal }
    const client = { get: async (url, config) => {
      assert.equal(url, '/api/informes/direccio')
      assert.equal(config, opcions)
      throw error
    } }
    await assert.rejects(pdf.descarregaAmb(client, '/api/informes/direccio', opcions), e => e === error)
  }
})
