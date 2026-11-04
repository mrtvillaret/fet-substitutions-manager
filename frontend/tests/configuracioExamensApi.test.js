import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as api from '../src/api/configuracioExamens.js'

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

const comprova = async (funcio, args, resposta, peticio) => {
  const fals = clientFals(resposta)
  assert.deepEqual(await funcio(fals.client, ...args), resposta)
  assert.deepEqual(fals.peticions, [peticio])
}

test('configuració mestra conserva el contracte de nivells, assignatures, grups i aules', async () => {
  await comprova(api.nivellsAmb, [], { nivells: ['ESO'] }, ['get', '/api/config/nivells'])
  await comprova(api.creaNivellAmb, [{ codi: 'ESO' }], {}, ['post', '/api/config/nivells', { codi: 'ESO' }])
  await comprova(api.assignaturesAmb, ['ESO'], { assignatures: [] }, ['get', '/api/config/assignatures/ESO'])
  await comprova(api.creaAssignaturaAmb, ['ESO', { nom: 'MAT' }], {}, ['post', '/api/config/assignatures/ESO', { nom: 'MAT' }])
  await comprova(api.esborraAssignaturaAmb, ['ESO', 'A / B'], {}, ['delete', '/api/config/assignatures/ESO/A%20%2F%20B'])
  await comprova(api.grupsAmb, ['ESO'], { grups: [] }, ['get', '/api/config/grups/ESO'])
  await comprova(api.creaGrupAmb, ['ESO', { codi: '1A' }], {}, ['post', '/api/config/grups/ESO', { codi: '1A' }])
  await comprova(api.aulesAmb, [], { aules: [] }, ['get', '/api/config/aules'])
  await comprova(api.creaAulaAmb, [{ codi: 'A1' }], {}, ['post', '/api/config/aules', { codi: 'A1' }])
  await comprova(api.esborraAulaAmb, ['A / 1'], {}, ['delete', '/api/config/aules/A%20%2F%201'])
})

test('esborrat amb assignacions i edició dinàmica conserven URL, paràmetres i cos', async () => {
  const url = '/api/config/grups/G%201'
  await comprova(api.comptaAssignacionsAmb, [url], { assignacions: 2 }, ['get', `${url}/assignacions`])
  await comprova(api.esborraElementAmb, [url, true], {}, ['delete', url, { params: { amb_assignacions: true } }])
  await comprova(api.editaElementAmb, [url, { nou_nom: 'G2' }], {}, ['put', url, { nou_nom: 'G2' }])
})

test('assignacions conserva totes les variants de lectura i escriptura', async () => {
  await comprova(api.assignacionsObsoletesAmb, [], { assignacions: [] }, ['get', '/api/config/assignacions-obsoletes'])
  await comprova(api.assignacionsAmb, [], { assignacions: [] }, ['get', '/api/config/assignacions'])
  await comprova(api.creaAssignacioAmb, [{ grup: '1A' }], { id: 3 }, ['post', '/api/config/assignacions', { grup: '1A' }])
  await comprova(api.editaAssignacioAmb, [3, { aula: 'A1' }], {}, ['put', '/api/config/assignacions/3', { aula: 'A1' }])
  await comprova(api.esborraAssignacioAmb, [3], {}, ['delete', '/api/config/assignacions/3'])
  await comprova(api.esborraAssignacionsAmb, [{ ids: [3] }], { eliminades: 1 }, [
    'delete', '/api/config/assignacions', { data: { ids: [3] } }
  ])
})

test('importacions conserva els cossos i les capçaleres multipart', async () => {
  const form = { form: true }
  const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }
  await comprova(api.previsualitzaImportacioAmb, [], { propostes: [] }, ['get', '/api/config/importar-assignacions/preview'])
  await comprova(api.simulaImportacioAmb, [{ propostes: [] }], {}, [
    'post', '/api/config/importar-assignacions/dry-run', { propostes: [] }
  ])
  await comprova(api.simulaImportacioCsvAmb, [form], {}, [
    'post', '/api/config/importar-assignacions-csv/dry-run', form, multipart
  ])
  await comprova(api.importaCsvAmb, [form], {}, [
    'post', '/api/config/importar-assignacions-csv', form, multipart
  ])
  await comprova(api.importaAmb, [{ propostes: [] }], {}, [
    'post', '/api/config/importar-assignacions', { propostes: [] }
  ])
})

test('afinitats conserva lectura, cos i retorn', async () => {
  await comprova(api.afinitatsAmb, [], { afinitats: [] }, ['get', '/api/config/afinitats'])
  await comprova(api.desaAfinitatsAmb, [{ afinitats: [] }], { afinitats: [] }, [
    'put', '/api/config/afinitats', { afinitats: [] }
  ])
})
