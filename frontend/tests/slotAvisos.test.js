import { test } from 'node:test'
import assert from 'node:assert/strict'
import { avisosDelsLogs, extractHour, normalizeText } from '../src/components/slotAvisos.js'

const AVIS = 'Avís: Prof 3 té enllaç Dimarts a les 09:00'

test('els avisos dels logs són els del professor, el dia i l’hora de la casella', () => {
  const logs = [AVIS, 'Avís: Prof 3 té enllaç Dimarts a les 10:00', 'Avís: Prof 4 té enllaç Dimarts a les 09:00', 'Prof 3 Dimarts a les 09:00']
  assert.deepEqual(avisosDelsLogs(logs, ['Prof 3'], 'Dimarts', '09:00'), [AVIS])
  assert.deepEqual(avisosDelsLogs(logs, ['Prof 3'], 'Dilluns', '09:00'), [])
})

test('un avís de la configuració (dades, no text) als logs no trenca els avisos de la casella', () => {
  const logs = [
    { codi: 'grup_sense_nivell', params: { grup: 'G', assignatures: ['A'] } },
    { codi: 'nivell_sense_hores_alliberades', params: { nivell: 'N' } },
    null,
    AVIS
  ]
  assert.deepEqual(avisosDelsLogs(logs, ['Prof 3'], 'Dimarts', '09:00'), [AVIS])
})

test('normalitzar i extreure l’hora accepten qualsevol valor', () => {
  assert.equal(normalizeText('Límit DIES'), 'limit dies')
  assert.equal(normalizeText({ codi: 'x' }), '')
  assert.equal(extractHour('a les 9:30'), '9:30')
  assert.equal(extractHour({ codi: 'x' }), null)
})
