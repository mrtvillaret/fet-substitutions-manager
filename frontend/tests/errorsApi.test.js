// node --test tests/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { missatgeDError } from '../src/errorsApi.js'

const t = (clau) => clau

const error = (status, data) => ({ response: { status, data } })

test('el detail del backend', async () => {
  assert.equal(await missatgeDError(error(400, { detail: 'Interval invertit' }), t), 'Interval invertit')
})

test('el detail també quan la resposta esperada era un fitxer (blob)', async () => {
  const cos = new Blob([JSON.stringify({ detail: 'Interval invertit' })], { type: 'application/json' })
  assert.equal(await missatgeDError(error(400, cos), t), 'Interval invertit')
})

test('un blob 5xx amb la referència', async () => {
  const cos = new Blob([JSON.stringify({ error_ref: 'abc123' })], { type: 'application/json' })
  assert.equal(await missatgeDError(error(500, cos), t), 'app.errors.server (ref. abc123)')
})

test('un blob que no és JSON no trenca res', async () => {
  const cos = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
  assert.equal(await missatgeDError(error(400, cos), t), 'app.errors.unexpected')
})

test('sense resposta, error de connexió', async () => {
  assert.equal(await missatgeDError({}, t), 'app.errors.connection')
})

test("jaAvisat reflecteix un avís real, també per als errors de xarxa", async () => {
  const { jaAvisat, marcaAvisat } = await import('../src/errorsApi.js')
  const error = { isAxiosError: true, config: {} }
  assert.equal(jaAvisat(error), false)
  marcaAvisat(error)
  assert.equal(jaAvisat(error), true)
  assert.equal(jaAvisat(new TypeError('URL.createObjectURL')), false)
})
