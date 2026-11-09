import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'
import * as errors from '../src/errorsApi.js'

const errorApi = (status = 500, silent = false) => ({ isAxiosError: true, config: { _silent: silent }, response: { status } })

test('un error Axios encara no mostrat no consta com a avisat', () => {
  assert.equal(errors.jaAvisat(errorApi()), false)
})

test('el mateix error només es mostra un cop en propagar-se per diverses capes', () => {
  const error = errorApi(), avisos = []
  errors.avisaError(error, () => avisos.push('global'))
  errors.avisaError(error, () => avisos.push('pantalla'))
  errors.avisaError(error, () => avisos.push('exterior'))
  assert.deepEqual(avisos, ['global'])
  assert.equal(errors.jaAvisat(error), true)
})

test('dos errors amb el mateix text són dues incidències diferents', () => {
  const avisos = []
  for (const error of [errorApi(), errorApi()]) errors.avisaError(error, () => avisos.push('avís'))
  assert.equal(avisos.length, 2)
})

test('una pantalla pot mostrar el seu error gestionat una sola vegada', () => {
  const error = errorApi(409, true), avisos = []
  assert.equal(errors.esErrorSilencios(error), true)
  errors.avisaError(error, () => avisos.push('conflicte'))
  errors.avisaError(error, () => avisos.push('duplicat'))
  assert.deepEqual(avisos, ['conflicte'])
})

test('la sessió tancada ja té avís a la pantalla d’entrada', () => {
  const error = errorApi(401), avisos = []
  errors.marcaAvisat(error)
  errors.avisaError(error, () => avisos.push('duplicat'))
  assert.deepEqual(avisos, [])
})

test('el logo opcional només silencia el 404, la resta dels errors s’avisen', () => {
  assert.equal(errors.esErrorSilencios(errorApi(404, [404])), true)
  for (const status of [400, 401, 403, 422, 429, 500, 503]) {
    assert.equal(errors.esErrorSilencios(errorApi(status, [404])), false)
  }
  assert.equal(errors.esErrorSilencios({ config: { _silent: [404] } }), false)
  assert.equal(errors.esErrorSilencios(errorApi(500)), false)
})

const eslint = new ESLint({ cwd: fileURLToPath(new URL('..', import.meta.url)) })
const guardia = async (codi, filePath = 'src/prova.js') =>
  (await eslint.lintText(codi, { filePath })).flatMap(r => r.messages).filter(m => m.ruleId === 'avisos/error-unic')

for (const [nom, codi] of [
  ['toast', "try { crida() } catch (error) { toast.add({severity:'error'}) }"],
  ['sense paràmetre', "try { crida() } catch { toast.add({severity:'error'}) }"],
  ['avís condicional', "try { crida() } catch (error) { toast.add({severity: error.response.status === 409 ? 'warn' : 'error'}) }"],
  ['error equivocat', "try { crida() } catch (error) { avisaError(unAltre, () => toast.add({severity:'error'})) }"],
  ['missatge en línia', "try { crida() } catch (error) { errorMessage.value = t('error') }"],
]) test(`guardià: impedeix avisar sense la regla única (${nom})`, async () => {
  assert.equal((await guardia(codi)).length, 1)
})

test('guardià: accepta la regla única i les validacions locals', async () => {
  assert.deepEqual(await guardia("try { crida() } catch (error) { avisaError(error, () => toast.add({severity:'error'})) }"), [])
  assert.deepEqual(await guardia("if (!nom) toast.add({severity:'error'})"), [])
})

test('guardià: també s’aplica als components Vue', async () => {
  const codi = "<template><div /></template><script setup>try { crida() } catch (error) { toast.add({severity:'error'}) }</script>"
  assert.equal((await guardia(codi, 'src/prova.vue')).length, 1)
})

test('la regla també admet errors congelats sense modificar-los', () => {
  const error = Object.freeze(errorApi()), avisos = []
  errors.avisaError(error, () => avisos.push('avís'))
  errors.avisaError(error, () => avisos.push('duplicat'))
  assert.equal(avisos.length, 1)
})

test('les crides amb avís local transmeten la gestió explícita sense alterar dades', async () => {
  const vigilancies = await import('../src/api/vigilancies.js')
  const grups = await import('../src/api/grups.js')
  const substitucions = await import('../src/api/substitucions.js')
  const peticions = [], opcions = { _silent: true }, cos = { aula: 'A1' }
  const client = Object.fromEntries(['get', 'post', 'put', 'delete'].map(verb => [verb, async (...args) => {
    peticions.push([verb, ...args]); return { data: { results: {} } }
  }]))
  await vigilancies.llistaAmb(client, '2026-04-20', opcions)
  await vigilancies.analisiAmb(client, '2026-04-20', opcions)
  await vigilancies.disponiblesEnBlocAmb(client, '2026-04-20', [], opcions)
  await vigilancies.editaAmb(client, '2026-04-20', 2, cos, opcions)
  await grups.llistaAmb(client, '2026-04-20', opcions)
  await substitucions.llistaSimpleAmb(client, '2026-04-20', opcions)
  assert.ok(peticions.every(p => p.at(-1) === opcions))
  assert.equal(peticions[3][2], cos)
  await vigilancies.esborraAmb(client, '2026-04-20', 2, { updatedAt: 'versio', silent: true })
  assert.deepEqual(peticions.at(-1), ['delete', '/api/vigilancies/2026-04-20/2', { params: { updated_at: 'versio' }, _silent: true }])
})
