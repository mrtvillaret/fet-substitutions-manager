import { test } from 'node:test'
import assert from 'node:assert/strict'

// Arguments HTTP de prova que les funcions de src/api/ han de passar tal qual
export const LECTURA = [{ params: { hores: ['08:00', '09:00'] }, responseType: 'blob', _silent: true, signal: null }]
export const COS = [{ valor: 7 }, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000, baseURL: '' }]
export const ESBORRA = [{ data: { ids: [7] }, params: { amb_assignacions: true } }]

// Per a cada fila [funció …Amb(client, ...), mètode, arguments, URL, arguments HTTP]:
// fa una sola petició amb el mètode i la URL, hi passa els arguments HTTP tal
// qual, retorna la resposta sencera i deixa passar l'error original.
export const provaCrides = (files) => {
  for (const [funcio, metode, args, url, argumentsHttp] of files) {
    test(`${funcio.name.replace(/Amb$/, '')}: URL, mètode, arguments, resposta i errors intactes`, async () => {
      const resposta = { data: { resultat: true }, headers: { 'content-disposition': 'filename="prova.pdf"' } }
      const peticions = []
      const client = { [metode]: async (...a) => { peticions.push(a); return resposta } }
      assert.equal(await funcio(client, ...args, ...argumentsHttp), resposta)
      assert.deepEqual(peticions, [[url, ...argumentsHttp]])
      const error = new Error('error original')
      client[metode] = async () => { throw error }
      await assert.rejects(funcio(client, ...args, ...argumentsHttp), e => e === error)
    })
  }
}

// Un client HTTP fals: desa cada petició ([mètode, ...arguments]) i respon `{ data: resposta }`
export const clientFals = (resposta = {}) => {
  const peticions = []
  const client = {}
  for (const metode of ['get', 'post', 'put', 'patch', 'delete']) {
    client[metode] = async (...args) => {
      peticions.push([metode, ...args])
      return { data: resposta }
    }
  }
  return { client, peticions }
}
