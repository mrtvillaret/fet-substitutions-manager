import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as api from '../src/api/estadistiques.js'

test('franges: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.frangesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/franges", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.frangesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('professor: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = ["A / B"]
  assert.equal(await api.professorAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/professor/A%20%2F%20B", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.professorAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('detallClasses: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.detallClassesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/classes/detall", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.detallClassesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

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
