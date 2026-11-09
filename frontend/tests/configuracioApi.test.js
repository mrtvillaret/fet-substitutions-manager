import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as config from '../src/api/configuracio.js'
import * as cursos from '../src/api/cursos.js'
import * as baixes from '../src/api/absenciesCobertes.js'
import * as dades from '../src/api/dades.js'
import * as prioritats from '../src/api/prioritats.js'
import * as grups from '../src/api/grups.js'

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

test('configuració conserva lectures, blob, multipart i cossos', async () => {
  await comprova(config.llegeixAmb, [], { idioma: 'ca' }, ['get', '/api/settings'])
  await comprova(config.idiomesAmb, [], { idiomes: ['ca'] }, ['get', '/api/settings/idiomes'])
  await comprova(config.versionsXmlAmb, [], { versions: [] }, ['get', '/api/settings/xml-versions'])
  await comprova(config.logoAmb, [123], 'blob', [
    'get', '/api/files/logo', { responseType: 'blob', params: { ts: 123 }, _silent: [404] }
  ])
  await comprova(config.editaVersioXmlAmb, [7, { data_inici: null }], {}, [
    'put', '/api/settings/xml-versions/7', { data_inici: null }
  ])
  await comprova(config.esborraVersioXmlAmb, [7], {}, ['delete', '/api/settings/xml-versions/7'])
  const form = { form: true }
  const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }
  await comprova(config.pujaLogoAmb, [form], { path: 'logo' }, ['post', '/api/files/upload-logo', form, multipart])
  await comprova(config.desaAmb, [{ idioma: 'ca' }], { message: 'fet' }, ['put', '/api/settings', { idioma: 'ca' }])
  await comprova(config.pujaXmlAmb, [form], { path: 'xml' }, ['post', '/api/files/upload-xml', form, multipart])
})

test('cursos i absències cobertes conserven el contracte CRUD', async () => {
  await comprova(cursos.llistaAmb, [], [], ['get', '/api/cursos'])
  await comprova(cursos.validacioXmlAmb, [], [], ['get', '/api/cursos/validacio-xml'])
  await comprova(cursos.creaAmb, [{ nom: 'Curs' }], {}, ['post', '/api/cursos', { nom: 'Curs' }])
  await comprova(cursos.editaAmb, [2, { nom: 'Curs' }], {}, ['put', '/api/cursos/2', { nom: 'Curs' }])
  await comprova(cursos.esborraAmb, [2], {}, ['delete', '/api/cursos/2'])
  await comprova(baixes.llistaAmb, [], { absencies_cobertes: [] }, ['get', '/api/absencies-cobertes'])
  await comprova(baixes.creaAmb, [{ professor: 'Prof 1' }], {}, ['post', '/api/absencies-cobertes', { professor: 'Prof 1' }])
  await comprova(baixes.editaAmb, [3, { motiu: '' }], {}, ['put', '/api/absencies-cobertes/3', { motiu: '' }])
  await comprova(baixes.esborraAmb, [3], {}, ['delete', '/api/absencies-cobertes/3'])
})

test('gestió de dades conserva URL, cos i retorn', async () => {
  await comprova(dades.professorsAmb, [], { professors: [] }, ['get', '/api/dades/professors'])
  await comprova(dades.reanomenaProfessorAmb, [{ antic: 'A', nou: 'B' }], {}, [
    'post', '/api/dades/professors/reanomena', { antic: 'A', nou: 'B' }
  ])
  await comprova(dades.analitzaPurgaAmb, [{ curs_id: 1 }], {}, ['post', '/api/dades/purga/analitzar', { curs_id: 1 }])
  await comprova(dades.executaPurgaAmb, [{ curs_id: 1 }], {}, ['post', '/api/dades/purga/executar', { curs_id: 1 }])
})

test('prioritats conserva totes les rutes i codifica No substituir', async () => {
  const opcions = { params: { data: '2026-04-20' } }
  await comprova(prioritats.activitatsAlliberablesAmb, [opcions], {}, [
    'get', '/api/prioritats/activitats-alliberables', opcions
  ])
  await comprova(prioritats.desaActivitatsAlliberablesAmb, [{ activitats: [] }], {}, [
    'put', '/api/prioritats/activitats-alliberables', { activitats: [] }
  ])
  await comprova(prioritats.noSubstituirAmb, [], {}, ['get', '/api/prioritats/no-substituir'])
  await comprova(prioritats.assignaturesAmb, [], {}, ['get', '/api/prioritats/assignatures'])
  await comprova(prioritats.categoriesAmb, [], {}, ['get', '/api/prioritats/categories'])
  await comprova(prioritats.desaTotAmb, [{ pesos: {} }], {}, ['put', '/api/prioritats/desar-tot', { pesos: {} }])
  await comprova(prioritats.afegeixNoSubstituirAmb, ['Act 1'], {}, [
    'post', '/api/prioritats/no-substituir', { assignatura: 'Act 1' }
  ])
  await comprova(prioritats.esborraNoSubstituirAmb, ['Act / 1'], {}, [
    'delete', '/api/prioritats/no-substituir/Act%20%2F%201'
  ])
})

test('abreviatures de grup conserven el contracte CRUD', async () => {
  await comprova(grups.abreviaturesAmb, [], { abreviatures: [] }, ['get', '/api/config/abreviatures'])
  await comprova(grups.creaAbreviaturaAmb, [{ abreviatura: 'G' }], {}, ['post', '/api/config/abreviatures', { abreviatura: 'G' }])
  await comprova(grups.editaAbreviaturaAmb, [4, { abreviatura: 'G' }], {}, ['put', '/api/config/abreviatures/4', { abreviatura: 'G' }])
  await comprova(grups.esborraAbreviaturaAmb, [4], {}, ['delete', '/api/config/abreviatures/4'])
})
