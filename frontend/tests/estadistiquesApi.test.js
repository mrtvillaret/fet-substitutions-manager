import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as api from '../src/api/estadistiques.js'

test('resum: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.resumAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/resum", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.resumAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('professors: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.professorsAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/professors", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.professorsAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('temporal: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.temporalAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/temporal", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.temporalAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('classes: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.classesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/classes", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.classesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

test('taula: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.taulaAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/taula", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.taulaAmb(client, ...args, ...argumentsHttp), e => e === error)
})

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

test('hores: URL, mètode, arguments, resposta i errors intactes', async () => {
  const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
  const argumentsHttp = [{"params":{"hores":["08:00","09:00"]},"responseType":"blob","_silent":true,"signal":null}]
  const peticions = []
  const client = { get: async (...args) => { peticions.push(args); return resposta } }
  const args = []
  assert.equal(await api.horesAmb(client, ...args, ...argumentsHttp), resposta)
  assert.deepEqual(peticions, [["/api/estadistiques/hores", ...argumentsHttp]])
  const error = new Error('error original')
  client.get = async () => { throw error }
  await assert.rejects(api.horesAmb(client, ...args, ...argumentsHttp), e => e === error)
})

