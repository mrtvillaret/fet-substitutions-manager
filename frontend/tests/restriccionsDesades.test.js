import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ambElQueNoConeix } from '../src/views/scheduler/restriccionsDesades.js'

const carregades = {
  restriccions_dures: {
    no_mateix_dia: [['A', 'B']],
    combinacions_permeses: [['X', 'Y']], // la pantalla no l'edita
    assignatures_dia_fix: { A: 'Dilluns', _pes_A: 0, C: 'Dimarts', _pes_C: 50 },
    assignatures_hora_fix: { A: '09:00', _pes_A: 0 }
  },
  preferencies: { mateix_dia: [], altra: [{ assignatures: ['Z'] }] },
  pesos_optimitzacio: { restriccio_dura: 1000, pes_desconegut: 7 },
  pesos_percentatge: { x: 1 },
  costos_professors: { globals: { substitucio: 1 } }
}

test('restriccions: en desar es conserva el que la pantalla no coneix', () => {
  const noves = {
    restriccions_dures: {
      no_mateix_dia: [],
      assignatures_dia_fix: { A: 'Dilluns' }, // C ja no hi és
      assignatures_hora_fix: { A: '09:00' }
    },
    preferencies: { mateix_dia: [{ assignatures: ['A', 'B'], pes: 50 }] },
    pesos_optimitzacio: { restriccio_dura: 900 }
  }
  const r = ambElQueNoConeix(carregades, noves)
  assert.deepEqual(r.restriccions_dures.no_mateix_dia, [])
  assert.deepEqual(r.restriccions_dures.combinacions_permeses, [['X', 'Y']])
  // El pes del pin d'A es conserva; el de C, que ja no està fixat, no
  assert.deepEqual(r.restriccions_dures.assignatures_dia_fix, { A: 'Dilluns', _pes_A: 0 })
  assert.deepEqual(r.restriccions_dures.assignatures_hora_fix, { A: '09:00', _pes_A: 0 })
  assert.deepEqual(r.preferencies, { mateix_dia: [{ assignatures: ['A', 'B'], pes: 50 }], altra: [{ assignatures: ['Z'] }] })
  assert.deepEqual(r.pesos_optimitzacio, { restriccio_dura: 900, pes_desconegut: 7 })
  assert.deepEqual(r.pesos_percentatge, { x: 1 })
  assert.equal('costos_professors' in r, false)
})

test('restriccions: sense res carregat, es desa el que hi ha a la pantalla', () => {
  const noves = { restriccions_dures: { assignatures_dia_fix: {}, assignatures_hora_fix: {} }, preferencies: {}, pesos_optimitzacio: {} }
  assert.deepEqual(ambElQueNoConeix(undefined, noves), noves)
})
