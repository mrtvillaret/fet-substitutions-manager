import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as api from '../src/api/usuaris.js'

test('surt: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.surtAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/logout", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.surtAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('perfil: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.perfilAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/users/profile", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.perfilAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('entra: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.entraAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/login", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.entraAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('entraDelegacio: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = ["/demo/"]
  assert.equal(await api.entraDelegacioAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/demo/api/login", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.entraDelegacioAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('canviaContrasenya: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { put: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.canviaContrasenyaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/users/profile/password", ...argumentsHttp]])
  const error = new Error('error original')
  client.put = async () => { throw error }
  await assert.rejects(api.canviaContrasenyaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('tancaAltresSessions: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.tancaAltresSessionsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/users/profile/tancar-altres-sessions", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.tancaAltresSessionsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('canviaCentre: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.canviaCentreAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/users/profile/institucio", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.canviaCentreAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('llista: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.llistaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/users", ...argumentsHttp]])
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
  assert.deepEqual(peticions, [["/api/users/7", ...argumentsHttp]])
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
  assert.deepEqual(peticions, [["/api/users", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.creaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('desactiva: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"data":{"ids":[7]},"params":{"amb_assignacions":true}}]
  const peticions = []
  const client = { delete: async (...args) => { peticions.push(args); return resposta } }
  const args = ["7"]
  assert.equal(await api.desactivaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/users/7", ...argumentsHttp]])
  const error = new Error('error original')
  client.delete = async () => { throw error }
  await assert.rejects(api.desactivaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('esborra: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"data":{"ids":[7]},"params":{"amb_assignacions":true}}]
  const peticions = []
  const client = { delete: async (...args) => { peticions.push(args); return resposta } }
  const args = ["7"]
  assert.equal(await api.esborraAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/users/7/hard", ...argumentsHttp]])
  const error = new Error('error original')
  client.delete = async () => { throw error }
  await assert.rejects(api.esborraAmb(client, ...args, ...argumentsHttp), e => e === error)
})

