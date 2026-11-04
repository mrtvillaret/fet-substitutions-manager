import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ajudaVigilantAmb,
  assignaPendentsAmb,
  assignaTitularsAmb,
  configuracioAmb,
  creaAmb,
  desaOrdreAmb,
  disponiblesAmb,
  disponiblesEnBlocAmb,
  editaAmb,
  esborraAmb,
  llistaAmb,
  netejaAmb,
  ordenaAmb,
  teOrdreManualAmb
} from '../src/api/vigilancies.js'

const clientFals = (resposta = {}) => {
  const peticions = []
  const client = {}
  for (const metode of ['get', 'post', 'put', 'delete']) {
    client[metode] = async (...args) => {
      peticions.push([metode, ...args])
      return { data: resposta }
    }
  }
  return { client, peticions }
}

test('llista i transforma les vigilàncies del dia', async () => {
  const { client, peticions } = clientFals([{ id: 1 }])
  assert.deepEqual(await llistaAmb(client, '2026-04-20'), [{ id: 1 }])
  assert.deepEqual(peticions, [['get', '/api/vigilancies/2026-04-20']])
})

test('crea i retorna la vigilància creada', async () => {
  const { client, peticions } = clientFals({ vigilancia: { id: 7 } })
  assert.deepEqual(await creaAmb(client, '2026-04-20', { hora: '08:00' }), { id: 7 })
  assert.deepEqual(peticions, [[
    'post', '/api/vigilancies/2026-04-20', { hora: '08:00' }
  ]])
})

test('edita i retorna la resposta completa', async () => {
  const { client, peticions } = clientFals({ updated_at: 'ara' })
  assert.deepEqual(await editaAmb(client, '2026-04-20', 7, { aula: 'A1' }), { updated_at: 'ara' })
  assert.deepEqual(peticions, [[
    'put', '/api/vigilancies/2026-04-20/7', { aula: 'A1' }
  ]])
})

test('esborra amb els paràmetres de concurrència i força', async () => {
  const { client, peticions } = clientFals()
  assert.equal(await esborraAmb(client, '2026-04-20', 7, { updatedAt: 'ara', force: true }), undefined)
  assert.deepEqual(peticions, [[
    'delete', '/api/vigilancies/2026-04-20/7',
    { params: { updated_at: 'ara', force: true } }
  ]])
})

test('demana disponibles amb els mateixos paràmetres opcionals a la URL', async () => {
  const { client, peticions } = clientFals([{ value: 'Prof 1' }])
  const resultat = await disponiblesAmb(client, '2026-04-20', '08:00', {
    tipus: 'Ordinari', grups: 'Grup A', aula: 'A 1'
  })
  assert.deepEqual(resultat, [{ value: 'Prof 1' }])
  assert.deepEqual(peticions, [[
    'get',
    '/api/vigilancies/2026-04-20/08:00/disponibles?tipus=Ordinari&grups=Grup+A&aula=A+1'
  ]])
})

test('demana disponibles en bloc i conserva el fallback buit', async () => {
  const queries = [{ hora: '08:00' }]
  const { client, peticions } = clientFals({ results: { clau: ['Prof 1'] } })
  assert.deepEqual(await disponiblesEnBlocAmb(client, '2026-04-20', queries), { clau: ['Prof 1'] })
  assert.deepEqual(peticions, [[
    'post', '/api/vigilancies/2026-04-20/disponibles-batch', { queries }
  ]])
})

test('demana l’ajuda del vigilant en silenci', async () => {
  const { client, peticions } = clientFals({ activitats: [] })
  assert.deepEqual(await ajudaVigilantAmb(client, '2026-04-20', '08:00', 'Prof 1'), { activitats: [] })
  assert.deepEqual(peticions, [[
    'get', '/api/vigilancies/2026-04-20/08:00/professor',
    { params: { nom: 'Prof 1' }, _silent: true }
  ]])
})

test('carrega la configuració amb les opcions rebudes', async () => {
  const opcions = { params: { data: '2026-04-20' } }
  const { client, peticions } = clientFals({ hores: ['08:00'] })
  assert.deepEqual(await configuracioAmb(client, opcions), { hores: ['08:00'] })
  assert.deepEqual(peticions, [['get', '/api/vigilancies/config', opcions]])
})

test('consulta i desa l’ordre', async () => {
  const consulta = clientFals({ ordre_manual: true })
  assert.equal(await teOrdreManualAmb(consulta.client, '2026-04-20'), true)
  assert.deepEqual(consulta.peticions, [['get', '/api/vigilancies/2026-04-20/ordre']])

  const desat = clientFals()
  assert.equal(await desaOrdreAmb(desat.client, '2026-04-20', '08:00', [3, 1]), undefined)
  assert.deepEqual(desat.peticions, [[
    'put', '/api/vigilancies/2026-04-20/ordre', { hora: '08:00', ids: [3, 1] }
  ]])
})

test('ordena, assigna i neteja retornant la resposta del servidor', async () => {
  const casos = [
    [ordenaAmb, ['2026-04-20'], '/api/vigilancies/2026-04-20/sort'],
    [assignaTitularsAmb, ['2026-04-20'], '/api/vigilancies/2026-04-20/assign/titulars'],
    [assignaPendentsAmb, ['2026-04-20', false], '/api/vigilancies/2026-04-20/assign/pendents?disponibles=false'],
    [netejaAmb, ['2026-04-20'], '/api/vigilancies/2026-04-20/clear']
  ]
  for (const [funcio, args, url] of casos) {
    const { client, peticions } = clientFals({ message: 'fet' })
    assert.deepEqual(await funcio(client, ...args), { message: 'fet' })
    assert.deepEqual(peticions, [['post', url]])
  }
})
