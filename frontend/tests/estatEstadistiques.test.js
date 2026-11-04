import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'

function prepara() {
  const peticions = [], avisos = [], watchers = [], descarregues = []
  const props = { visible: true, curs: { id: 7, data_inici: '2026-04-01', data_fi: '2026-04-30' }, cursos: [] }
  const dependents = { props, emit: (...args) => peticions.push(args), t: x => x, toast: { add: x => avisos.push(x) } }
  const apiConfiguracio = { llegeix: async () => ({}), desa: async x => peticions.push(['settings', x]) }
  const apiEstadistiques = Object.fromEntries(['resum', 'professors', 'temporal', 'classes', 'taula', 'franges', 'professor', 'detallClasses', 'hores'].map(n => [n, async (...args) => { peticions.push([n, ...args]); return { data: n === 'hores' ? { hores: ['8h', '9h'] } : { resultat: n } } }]))
  const apiPdf = { professorsInforme: async () => ({ data: { professors: ['Prof 2', 'Prof 1'] } }), descarrega: async (...args) => { descarregues.push(args); return { data: 'PDF' } } }
  const p = carregaBlocVista('components/EstadistiquesDialog.vue', 'useEstadistiques', [['const loading =', '</script>']], [
    'dataInici', 'dataFinal', 'cursTriatId', 'inicialitzarDates', 'carregarEstadistiques', 'loading', 'resum', 'horesTriades', 'carregarFrangesHorari', 'paramsDelFiltre', 'onProfessorRowClick', 'professorDetail', 'professorDetailVisible', 'classesSeleccionades', 'carregarDetallClasses', 'classesDetailData', 'formatPercent', 'formatBarWidth', 'carregarInformeProfessors', 'informeProfessorsOpcions', 'informeProfessorSeleccionat', 'generarInformeProfessor', 'tancar'
  ], { ...dependents, dependents, ref, computed, watch: (...args) => watchers.push(args), apiConfiguracio, apiEstadistiques, apiPdf, dataTreball: ref(new Date('2026-04-20')), dataIso: d => d?.toLocaleDateString('sv-SE'), ordenaAlfabeticament: xs => [...xs].sort(), localizeBackendDayName: x => x,
    document: { createElement: () => ({ click() {} }) }, URL: { createObjectURL: () => 'blob:prova', revokeObjectURL() {} }, Blob })
  return { ...p, peticions, avisos, descarregues, watchers, props }
}
test('Estadístiques: el curs fixa el període i les cinc consultes comparteixen filtre', async () => {
  const p = prepara(); await p.inicialitzarDates(); p.horesTriades.value = ['9h']; await p.carregarEstadistiques()
  assert.equal(p.cursTriatId.value, 7); assert.equal(p.loading.value, false); assert.deepEqual(p.resum.value, { resultat: 'resum' })
  assert.equal(p.peticions.length, 6); assert.deepEqual(p.peticions[0], ['settings', { data_inici_estadistiques: '2026-04-01', data_final_estadistiques: '2026-04-30' }])
  for (const [, options] of p.peticions.slice(1)) assert.deepEqual(options.params, { data_inici: '2026-04-01', data_final: '2026-04-30', hores: ['9h'] })
  assert.equal(p.watchers.length, 3)
})
test('Estadístiques: les franges retiren només hores inexistents i els detalls conserven el filtre', async () => {
  const p = prepara(); await p.inicialitzarDates(); p.horesTriades.value = ['8h', 'inexistent']; await p.carregarFrangesHorari()
  assert.deepEqual(p.horesTriades.value, ['8h']); await p.onProfessorRowClick({ data: { professor: 'Prof 1' } })
  assert.equal(p.professorDetailVisible.value, true); assert.deepEqual(p.professorDetail.value, { resultat: 'professor' })
  p.classesSeleccionades.value = ['G1']; await p.carregarDetallClasses(); assert.deepEqual(p.classesDetailData.value, { resultat: 'detallClasses' }); assert.deepEqual(p.peticions.at(-1)[1].params.grups, ['G1'])
})
test('Estadístiques: sense grups, avís i cap consulta de detall', async () => {
  const p = prepara(); await p.carregarDetallClasses(); assert.equal(p.peticions.length, 0); assert.equal(p.avisos[0].severity, 'warn')
})
test('Estadístiques: PDF manté paràmetres, selecció vàlida i ordre alfabètic', async () => {
  const p = prepara(); await p.inicialitzarDates(); p.informeProfessorSeleccionat.value = 'retirat'; await p.carregarInformeProfessors()
  assert.equal(p.informeProfessorSeleccionat.value, null); assert.deepEqual(p.informeProfessorsOpcions.value, ['Prof 1', 'Prof 2'])
  p.informeProfessorSeleccionat.value = 'Prof 1'; await p.generarInformeProfessor(); assert.deepEqual(p.descarregues[0], ['/api/informes/professor', { params: { data_inici: '2026-04-01', data_final: '2026-04-30', mostrar_taules: false, professor: 'Prof 1' }, responseType: 'blob' }])
  p.tancar(); assert.deepEqual(p.peticions.at(-1), ['update:visible', false])
})
test('Estadístiques: percentatges i barres es limiten als extrems existents', () => {
  const p = prepara(); assert.equal(p.formatPercent(5, 0), '0%'); assert.equal(p.formatPercent(4, 3), '100%'); assert.equal(p.formatBarWidth(1, 3), '33%')
})
