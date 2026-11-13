import { test } from 'node:test'
import assert from 'node:assert/strict'
import { extractIncidentScore, isIncidentLogLine, localizeBackendDayName, localizeIncidentText, removeIncidentScore } from '../src/views/scheduler/textUtils.js'
import { formatIncidentShort } from '../src/views/scheduler/incidentFormatters.js'

const t = (clau, params) => ({
  'scheduler.days.monday': 'Lunes',
  'scheduler.steps.results.incidents.short.cost': 'coste',
  'scheduler.steps.results.incidents.full.noWork': `${params?.teacher} → no trabaja ${params?.hour} ${params?.day}`,
}[clau] || clau)

test('incidències: els punts negatius (bonificacions) també es llegeixen', () => {
  const linia = '⚠️ MATEIX DIA: Català (1-BAT) → el mateix dia que Filosofia (1-BAT) (el Dilluns 20/04) (punt: -120)'
  assert.equal(extractIncidentScore(linia), '(punt: -120)')
  assert.equal(removeIncidentScore(linia).endsWith('(el Dilluns 20/04)'), true)
  assert.match(formatIncidentShort({ id: 'others' }, linia, t), /\(coste: -120\)$/)
})

test('incidències: les restriccions toves es veuen (porten «→»)', () => {
  assert.equal(isIncidentLogLine('⚠️ NO AL MATEIX MOMENT: Anglès (1-BAT) → coincideix amb Anglès (2-BAT) a 09:00 el Dilluns 20/04 (punt: 3000)'), true)
})

test('incidències: el dia amb data es tradueix i conserva la data', () => {
  assert.equal(localizeBackendDayName('Dilluns 20/04', t), 'Lunes 20/04')
  assert.equal(localizeBackendDayName('Dilluns', t), 'Lunes')
  assert.equal(localizeBackendDayName('2026-04-20', t), '2026-04-20')
  assert.equal(
    localizeIncidentText('🚫 Prof 1 → no treballa aquest dia a les 09:00 el Dilluns 20/04 (punt: 90)', t),
    'Prof 1 → no trabaja 09:00 Lunes 20/04 (coste: 90)'
  )
})
