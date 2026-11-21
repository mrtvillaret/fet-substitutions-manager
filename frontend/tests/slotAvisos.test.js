import { test } from 'node:test'
import assert from 'node:assert/strict'
import { avisosDelsLogs } from '../src/components/slotAvisos.js'

const enllac = (professor, dia, data, hora) => ({
  codi: 'inc_enllac', params: { professor, count: 2, nivell: 'N1', assignatures: ['A', 'B'], hora, dia, data }, punts: 0
})
const ENLLAC = enllac('Prof 3', 'Dimarts', '2027-03-02', '09:00')

test('els avisos dels logs són els del professor, la data i l’hora de la casella', () => {
  const logs = [ENLLAC, enllac('Prof 3', 'Dimarts', '2027-03-02', '10:00'), enllac('Prof 4', 'Dimarts', '2027-03-02', '09:00'),
    { codi: 'inc_substitucio', params: { professor: 'Prof 3', hora: '09:00', dia: 'Dimarts', data: '2027-03-02' }, punts: 80 }]
  assert.deepEqual(avisosDelsLogs(logs, ['Prof 3'], '2027-03-02', '09:00'), [ENLLAC])
  assert.deepEqual(avisosDelsLogs(logs, ['Prof 3'], '2027-03-02', '9:00'), [ENLLAC])
  assert.deepEqual(avisosDelsLogs(logs, ['Prof 3'], '2027-03-09', '09:00'), [])
  // Un horari sense dates (casella pel nom del dia)
  const senseData = enllac('Prof 3', 'Dimarts', null, '09:00')
  assert.deepEqual(avisosDelsLogs([senseData], ['Prof 3'], 'Dimarts', '09:00'), [senseData])
})

test('el límit per professor surt als seus dies restringits (data o nom de dia)', () => {
  const limit = { codi: 'inc_limit_dies_professor', params: { professor: 'Prof 3', count: 2, dies_limit: [{ dia: 'Dimarts', n: 2 }], max: 1, pes: 50 }, punts: 5000 }
  assert.deepEqual(avisosDelsLogs([limit], ['Prof 3'], '2027-03-02', '09:00'), [limit])
  assert.deepEqual(avisosDelsLogs([limit], ['Prof 3'], '2027-03-03', '09:00'), [])
})

test('els avisos de la configuració, el text del motor i els buits no hi surten', () => {
  const logs = [{ codi: 'grup_sense_nivell', params: { grup: 'G', assignatures: ['A'] } }, null, '🔍 Pre-calculant…', ENLLAC]
  assert.deepEqual(avisosDelsLogs(logs, ['Prof 3'], '2027-03-02', '09:00'), [ENLLAC])
})
