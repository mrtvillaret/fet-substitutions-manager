import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  actualitzaAmb,
  desaAbsenciesAmb,
  disponiblesEnBlocAmb,
  generaAmb,
  horesProfessorAmb,
  llistaAmb,
  llistaSimpleAmb,
  llistaTotesAmb,
  reassignaProblematiquesAmb
} from '../src/api/substitucions.js'

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

test('llista les substitucions amb les variants exactes de la pantalla', async () => {
  const ordenada = clientFals([{ id: 1 }])
  assert.deepEqual(await llistaAmb(ordenada.client, '2026-04-20', 'curs'), [{ id: 1 }])
  assert.deepEqual(ordenada.peticions, [[
    'get', '/api/substitucions/2026-04-20', { params: { ordre: 'curs' }, _silent: true }
  ]])

  const simple = clientFals([])
  assert.deepEqual(await llistaSimpleAmb(simple.client, '2026-04-20'), [])
  assert.deepEqual(simple.peticions, [['get', '/api/substitucions/2026-04-20']])

  const totes = clientFals([{ id: 2 }])
  assert.deepEqual(await llistaTotesAmb(totes.client, '2026-04-20', { silent: true }), [{ id: 2 }])
  assert.deepEqual(totes.peticions, [[
    'get', '/api/substitucions/2026-04-20?include_all=true', { _silent: true }
  ]])
})

test('genera pendents o regenera tot i retorna el resultat', async () => {
  const { client, peticions } = clientFals({ generated: 2 })
  assert.deepEqual(await generaAmb(client, '2026-04-20', true), { generated: 2 })
  assert.deepEqual(peticions, [[
    'post', '/api/substitucions/2026-04-20/generar?regenerar_tot=true'
  ]])
})

test('actualitza una fila conservant el mode silenciós', async () => {
  const cos = { id: 3, substitut: 'Prof 1' }
  const { client, peticions } = clientFals({ updated_at: 'ara' })
  assert.deepEqual(
    await actualitzaAmb(client, '2026-04-20', '08:00', 'Prof absent', cos, { silent: true }),
    { updated_at: 'ara' }
  )
  assert.deepEqual(peticions, [[
    'put', '/api/substitucions/2026-04-20/08:00/Prof absent', cos, { _silent: true }
  ]])
})

test('desa les absències codificant només el professor', async () => {
  const cos = { hores_absencia: ['08:00'], hores_servei: [] }
  const { client, peticions } = clientFals({ substituts_trets: [] })
  assert.deepEqual(
    await desaAbsenciesAmb(client, '2026-04-20', 'Prof / 1', cos, { silent: true }),
    { substituts_trets: [] }
  )
  assert.deepEqual(peticions, [[
    'put', '/api/substitucions/2026-04-20/absencies/Prof%20%2F%201', cos, { _silent: true }
  ]])
})

test('carrega les hores del professor i reassigna les problemàtiques', async () => {
  const hores = clientFals({ hores_amb_classe: ['08:00'] })
  assert.deepEqual(await horesProfessorAmb(hores.client, '2026-04-20', 'Prof 1'), { hores_amb_classe: ['08:00'] })
  assert.deepEqual(hores.peticions, [[
    'get', '/api/substitucions/2026-04-20/hores-professor/Prof%201'
  ]])

  const reassigna = clientFals({ changes: [] })
  assert.deepEqual(await reassignaProblematiquesAmb(reassigna.client, '2026-04-20'), { changes: [] })
  assert.deepEqual(reassigna.peticions, [[
    'post', '/api/substitucions/2026-04-20/reassign-problematics'
  ]])
})

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
