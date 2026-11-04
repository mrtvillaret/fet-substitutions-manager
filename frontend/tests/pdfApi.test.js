import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as api from '../src/api/pdf.js'

test('descarrega: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = ["/api/pdf/complete/2026-11-03?format=A4"]
  assert.equal(await api.descarregaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/pdf/complete/2026-11-03?format=A4", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.descarregaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('professorsInforme: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.professorsInformeAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/informes/professors-llista", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.professorsInformeAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('creaDisponiblesTotsDies: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { post: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.creaDisponiblesTotsDiesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/pdf/disponibles-tots-dies", ...argumentsHttp]])
  const error = new Error('error original')
  client.post = async () => { throw error }
  await assert.rejects(api.creaDisponiblesTotsDiesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('preferencies: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.preferenciesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/pdf/preferences", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.preferenciesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('desaPreferencies: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"valor":7},{"headers":{"Content-Type":"multipart/form-data"},"timeout":300000,"baseURL":""}]
  const peticions = []
  const client = { put: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.desaPreferenciesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/pdf/preferences", ...argumentsHttp]])
  const error = new Error('error original')
  client.put = async () => { throw error }
  await assert.rejects(api.desaPreferenciesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('validacions: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = ["2026-11-03"]
  assert.equal(await api.validacionsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/pdf/2026-11-03/validacions", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.validacionsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('comptesSenseNivell: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.comptesSenseNivellAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/pdf/vigilancies/comptes-sense-nivell", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.comptesSenseNivellAmb(client, ...args, ...argumentsHttp), e => e === error)
})

