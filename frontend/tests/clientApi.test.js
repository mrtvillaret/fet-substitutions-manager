import { test } from 'node:test'
import assert from 'node:assert/strict'
import axios from 'axios'
import client from '../src/api/client.js'
import { descarrega } from '../src/api/pdf.js'
import { genera, horari } from '../src/api/planificador.js'
import { entraDelegacio } from '../src/api/usuaris.js'

test('el client únic conserva Blob, capçaleres, paràmetres, _silent, timeout i baseURL', async () => {
  assert.equal(client, axios)
  const adapterOriginal = client.defaults.adapter
  const peticions = []
  const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
  const controller = new AbortController()
  client.defaults.adapter = async config => {
    peticions.push(config)
    return { data: blob, headers: { 'content-disposition': 'attachment; filename="prova.pdf"' }, config, status: 200, statusText: 'OK' }
  }
  try {
    const params = { hores: ['08:00', '09:00'], data: '2026-11-03' }
    const resposta = await descarrega('/api/pdf/complete/2026-11-03', {
      params, _silent: true, responseType: 'blob', signal: controller.signal
    })
    assert.equal(resposta.data, blob)
    assert.equal(resposta.headers['content-disposition'], 'attachment; filename="prova.pdf"')
    assert.deepEqual(peticions[0].params, params)
    assert.equal(peticions[0]._silent, true)
    assert.equal(peticions[0].responseType, 'blob')
    assert.equal(peticions[0].signal, controller.signal)
    await genera({ selected_dates: ['2026-11-03'] }, { timeout: 300000 })
    assert.equal(peticions[1].timeout, 300000)
    assert.deepEqual(JSON.parse(peticions[1].data), { selected_dates: ['2026-11-03'] })
    await entraDelegacio('/demo/', { username: 'prova', password: 'inventada' }, { baseURL: '' })
    assert.equal(peticions[2].url, '/demo/api/login')
    assert.equal(peticions[2].baseURL, '')
    await horari()
    assert.equal(peticions[3].params, undefined)
  } finally {
    client.defaults.adapter = adapterOriginal
  }
})

test('el client conserva el rebuig original i la cancel·lació evita la petició', async () => {
  const adapterOriginal = client.defaults.adapter
  const error = new Error('error original')
  error.response = { status: 400, data: new Blob(['{"detail":"prova"}'], { type: 'application/json' }) }
  let crides = 0
  client.defaults.adapter = async () => { crides++; throw error }
  try {
    await assert.rejects(descarrega('/api/pdf/prova', { responseType: 'blob' }), e => e === error)
    const controller = new AbortController()
    controller.abort()
    await assert.rejects(descarrega('/api/pdf/prova', { signal: controller.signal }), e => e.code === 'ERR_CANCELED')
    assert.equal(crides, 1)
  } finally {
    client.defaults.adapter = adapterOriginal
  }
})
