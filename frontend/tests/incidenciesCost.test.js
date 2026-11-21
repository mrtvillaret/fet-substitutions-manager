import { test } from 'node:test'
import assert from 'node:assert/strict'
import { localizeBackendDayName, comparaSegonsOrdre } from '../src/views/scheduler/textUtils.js'
import { esDeLExamen, grupIncidencia, iconaIncidencia, textCurtIncidencia, textIncidencia } from '../src/views/scheduler/incidencies.js'
import { formatIncidentShort, teCost } from '../src/views/scheduler/incidentFormatters.js'
import { tradueixMissatge } from '../src/views/scheduler/missatges.js'

// Plantilles de prova: la clau i els paràmetres, per veure què arriba a l'idioma
const t = (clau, params) => {
  if (clau === 'scheduler.days.monday') return 'Lunes'
  if (clau === 'scheduler.steps.results.incidents.short.cost') return 'coste'
  if (clau === 'scheduler.incidencies.curt.inc_substitucio') return `${params.professor}${params.ambExamens} · ${params.assignatura} · ${params.dia} ${params.hora}`
  if (clau.startsWith('scheduler.incidencies.')) return `${clau.split('.').pop()}: ${JSON.stringify(params)}`
  return clau
}

const SUBST = {
  codi: 'inc_substitucio',
  params: { professor: 'Prof 1', examens: [{ nom: 'Física (1-BAT)', curs: '1-BAT' }], assignatura: 'Mates', grup: '2-ESO-A', hora: '09:00', dia: 'Dilluns', data: '2026-04-20' },
  punts: 80
}

test('incidències: el text curt i el sencer surten de la plantilla de l\'idioma, amb el cost', () => {
  assert.equal(textCurtIncidencia(SUBST, t), '🚨 Prof 1 (Física (1-BAT))->1-BAT · Mates · Lunes 20/04 09:00 (coste: 80)')
  assert.equal(formatIncidentShort({}, SUBST, t), textCurtIncidencia(SUBST, t))
  assert.match(textIncidencia(SUBST, t), /^inc_substitucio: .*"dia":"Lunes 20\/04".* \(coste: 80\)$/)
  // Sense punts (enllaços, zona d'examen), sense «(cost: 0)»
  const enllac = { codi: 'inc_enllac', params: { professor: 'Prof 1', count: 2, nivell: 'N1', assignatures: ['A', 'B'], hora: '09:00', dia: 'Dilluns', data: null }, punts: 0 }
  assert.match(textIncidencia(enllac, t), /"assignatures":"A, B".*"dia":"Lunes"/)
  assert.doesNotMatch(textIncidencia(enllac, t), /coste/)
  assert.equal(teCost(SUBST), true)
  assert.equal(teCost(enllac), false)
  assert.equal(teCost('un avís de la configuració'), false)
  // tradueixMissatge també les tradueix
  assert.equal(tradueixMissatge(SUBST, t), textIncidencia(SUBST, t))
})

test('incidències: el grup i la icona surten del codi', () => {
  assert.deepEqual([grupIncidencia(SUBST), iconaIncidencia(SUBST)], ['substitutions', '🚨'])
  assert.deepEqual([grupIncidencia({ codi: 'inc_zona_examen' }), iconaIncidencia({ codi: 'inc_zona_examen' })], ['zoneExam', '👁️'])
  assert.deepEqual([grupIncidencia({ codi: 'inc_desconegut' }), iconaIncidencia({ codi: 'inc_desconegut' })], ['others', '⚠️'])
})

test('incidències: una incidència és de l\'examen pel titular, la data i l\'hora', () => {
  assert.equal(esDeLExamen(SUBST, 'Prof 1', { dia: 'Dilluns', data: '2026-04-20', hora: '09:00' }), true)
  // La mateixa hora una altra setmana, no
  assert.equal(esDeLExamen(SUBST, 'Prof 1', { dia: 'Dilluns', data: '2026-04-27', hora: '09:00' }), false)
  assert.equal(esDeLExamen(SUBST, 'Prof 2', { dia: 'Dilluns', data: '2026-04-20', hora: '09:00' }), false)
})

test('incidències: el dia amb data es tradueix i conserva la data', () => {
  assert.equal(localizeBackendDayName('Dilluns 20/04', t), 'Lunes 20/04')
  assert.equal(localizeBackendDayName('Dilluns', t), 'Lunes')
  assert.equal(localizeBackendDayName('2026-04-20', t), '2026-04-20')
})

test('nivells: el planificador els ordena com la Configuració d\'exàmens', () => {
  const ordre = ['1-ESO', '2-ESO', '1-BATX', '2-BATX']
  assert.deepEqual(['2-BATX', 'ALTRE', '2-ESO', '1-ESO'].sort(comparaSegonsOrdre(ordre)), ['1-ESO', '2-ESO', '2-BATX', 'ALTRE'])
  assert.deepEqual(['B', 'A'].sort(comparaSegonsOrdre(undefined)), ['B', 'A'])
})
