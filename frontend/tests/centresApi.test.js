import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as api from '../src/api/centres.js'

test('llista: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.llistaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/settings/institucions", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.llistaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('edita: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { put: async (...args) => { peticions.push(args); return resposta } }
  const args = ["7"]
  assert.equal(await api.editaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/settings/institucions/7", ...argumentsHttp]])
  const error = new Error('error original')
  client.put = async () => { throw error }
  await assert.rejects(api.editaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('crea: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.creaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/settings/institucions", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.creaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('estat: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { put: async (...args) => { peticions.push(args); return resposta } }
  const args = ["7"]
  assert.equal(await api.estatAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/settings/institucions/7/status", ...argumentsHttp]])
  const error = new Error('error original')
  client.put = async () => { throw error }
  await assert.rejects(api.estatAmb(client, ...args, ...argumentsHttp), e => e === error)
})
