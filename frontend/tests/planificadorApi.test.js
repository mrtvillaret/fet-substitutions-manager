import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as api from '../src/api/planificador.js'

test('horari: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.horariAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/horari", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.horariAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('pins: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.pinsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/restriccions/pin", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.pinsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('recalculaCost: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.recalculaCostAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/recalcular-cost", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.recalculaCostAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('publica: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.publicaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/publicar", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.publicaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('restriccions: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.restriccionsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/restriccions", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.restriccionsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('treuInexistents: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.treuInexistentsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/restriccions/treure-inexistents", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.treuInexistentsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('ultimResultat: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.ultimResultatAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/ultim-resultat", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.ultimResultatAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('cursDates: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.cursDatesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/curs-dates", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.cursDatesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('desaConfiguracio: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { put: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.desaConfiguracioAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/config", ...argumentsHttp]])
  const error = new Error('error original')
  client.put = async () => { throw error }
  await assert.rejects(api.desaConfiguracioAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('desaDates: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { put: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.desaDatesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/dates", ...argumentsHttp]])
  const error = new Error('error original')
  client.put = async () => { throw error }
  await assert.rejects(api.desaDatesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('sessionsInfo: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = ["ESO,BATX"]
  assert.equal(await api.sessionsInfoAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/sessions-info?nivells=ESO,BATX", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.sessionsInfoAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('configuracio: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.configuracioAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/config", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.configuracioAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('dates: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.datesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/dates", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.datesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('assignaturesActives: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.assignaturesActivesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/assignatures-actives", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.assignaturesActivesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('motors: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.motorsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/motors", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.motorsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('costosProfessors: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.costosProfessorsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/costos-professors", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.costosProfessorsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('genera: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.generaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/generate", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.generaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('analisi: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.analisiAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/analisi", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.analisiAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('desaRestriccions: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { put: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.desaRestriccionsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/restriccions", ...argumentsHttp]])
  const error = new Error('error original')
  client.put = async () => { throw error }
  await assert.rejects(api.desaRestriccionsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('desaCostosProfessors: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { put: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.desaCostosProfessorsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/scheduler/costos-professors", ...argumentsHttp]])
  const error = new Error('error original')
  client.put = async () => { throw error }
  await assert.rejects(api.desaCostosProfessorsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

