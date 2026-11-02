// node --test tests/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parametresDelMotor } from '../src/views/scheduler/motors.js'

const V3 = {
  id: 'v3',
  params: { temperatura_inicial: 100, max_iteracions: 200000, intents_solucio_inicial: 50 },
  param_labels: { temperatura_inicial: { label: 'Temperatura inicial' }, max_iteracions: { label: 'Límit' } }
}

test('només els paràmetres que la pantalla deixa canviar (amb etiqueta)', () => {
  assert.deepEqual(parametresDelMotor(V3), { temperatura_inicial: 100, max_iteracions: 200000 })
})

test('un motor sense etiquetes no envia cap paràmetre', () => {
  assert.deepEqual(parametresDelMotor({ params: { a: 1 } }), {})
  assert.deepEqual(parametresDelMotor(undefined), {})
})
