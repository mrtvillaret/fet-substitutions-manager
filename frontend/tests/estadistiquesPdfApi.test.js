import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as pdf from '../src/api/pdf.js'
import { desaPdf } from '../src/desaPdf.js'

test('els PDF conserven el Blob i Content-Disposition sense transformar-los', async () => {
  const data = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
  const resposta = { data, headers: { 'content-disposition': 'attachment; filename="disponibles.pdf"' } }
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const cos = { data_inici: '2026-11-03' }
  assert.equal(await pdf.creaDisponiblesTotsDiesAmb(client, cos, { responseType: 'blob' }), resposta)
  assert.deepEqual(peticions, [['/api/pdf/disponibles-tots-dies', cos, { responseType: 'blob' }]])
})

test('els informes en PDF: Blob amb els paràmetres; els errors JSON rebuts com a Blob i la cancel·lació arriben intactes', async () => {
  for (const error of [
    { response: { data: new Blob(['{"detail":"prova"}'], { type: 'application/json' }), status: 400 } },
    { code: 'ERR_CANCELED' }
  ]) {
    const params = { data_inici: '2026-11-03', hores: ['08:00'] }
    const client = { get: async (url, config) => {
      assert.equal(url, '/api/informes/direccio')
      assert.deepEqual(config, { params, responseType: 'blob' })
      throw error
    } }
    await assert.rejects(pdf.informeDireccioAmb(client, params), e => e === error)
  }
})

test('desaPdf: un enllaç temporal amb el nom, un clic i l’adreça alliberada', () => {
  const fets = []
  const enllac = { click: () => fets.push(['clic', enllac.href, enllac.download]) }
  const original = { document: globalThis.document, crea: URL.createObjectURL, allibera: URL.revokeObjectURL }
  globalThis.document = { createElement: () => enllac, body: { appendChild: e => fets.push(['posa', e === enllac]), removeChild: e => fets.push(['treu', e === enllac]) } }
  URL.createObjectURL = blob => { fets.push(['blob', blob.type]); return 'blob:prova' }
  URL.revokeObjectURL = url => fets.push(['allibera', url])
  try {
    desaPdf('%PDF-1.4', 'prova.pdf')
  } finally {
    globalThis.document = original.document
    URL.createObjectURL = original.crea
    URL.revokeObjectURL = original.allibera
  }
  assert.deepEqual(fets, [['blob', 'application/pdf'], ['posa', true], ['clic', 'blob:prova', 'prova.pdf'], ['treu', true], ['allibera', 'blob:prova']])
})
