import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  configuracioAmb,
  detectaAssignaturesAmb,
  detectaGrupsAmb,
  horesAmb,
  professorsAmb,
  professorsHorariAmb,
  professorsTotsAmb
} from '../src/api/horari.js'
import {
  amagatsAmb,
  desaAmb,
  desaAmagatsAmb,
  desaPeriodeAmb,
  llistaAmb,
  reforcAmb
} from '../src/api/grups.js'

const clientFals = (resposta = {}) => {
  const peticions = []
  const client = {}
  for (const metode of ['get', 'post', 'put']) {
    client[metode] = async (...args) => {
      peticions.push([metode, ...args])
      return { data: resposta }
    }
  }
  return { client, peticions }
}

test('les lectures de l’horari conserven URL, paràmetres i retorn', async () => {
  const opcions = { params: { data: '2026-04-20' } }
  const casos = [
    [configuracioAmb, '/api/config'],
    [professorsAmb, '/api/professors'],
    [professorsHorariAmb, '/api/horari/professors'],
    [professorsTotsAmb, '/api/horari/professors/all'],
    [horesAmb, '/api/hores'],
    [detectaGrupsAmb, '/api/horari/grups/detectar'],
    [detectaAssignaturesAmb, '/api/horari/assignatures/detectar']
  ]
  for (const [funcio, url] of casos) {
    const { client, peticions } = clientFals({ marca: url })
    assert.deepEqual(await funcio(client, opcions), { marca: url })
    assert.deepEqual(peticions, [['get', url, opcions]])
  }
})

test('carrega un reforç codificant l’activitat i passant la data', async () => {
  const { client, peticions } = clientFals({ dies: ['dilluns'] })
  assert.deepEqual(await reforcAmb(client, 'Act / 1', '2026-04-20'), { dies: ['dilluns'] })
  assert.deepEqual(peticions, [[
    'get', '/api/grups/reforcos/Act%20%2F%201', { params: { data: '2026-04-20' } }
  ]])
})

test('les operacions de grups conserven el cos i retornen les dades', async () => {
  const cos = { grups: { '08:00': ['Grup 1'] } }
  const casos = [
    [desaPeriodeAmb, ['/api/grups/periode', cos], 'post', [cos]],
    [llistaAmb, ['/api/grups/2026-04-20'], 'get', ['2026-04-20']],
    [desaAmb, ['/api/grups/2026-04-20', cos], 'put', ['2026-04-20', cos]],
    [amagatsAmb, ['/api/grups-amagats'], 'get', []],
    [desaAmagatsAmb, ['/api/grups-amagats', { grups: ['Grup 1'] }], 'put', [['Grup 1']]]
  ]
  for (const [funcio, peticio, metode, args] of casos) {
    const { client, peticions } = clientFals({ ok: true })
    assert.deepEqual(await funcio(client, ...args), { ok: true })
    assert.deepEqual(peticions, [[metode, ...peticio]])
  }
})
