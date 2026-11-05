import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'

function prepara(batch = null) {
  const peticions = [], avisos = [], watchers = [], descarregues = []
  const props = { visible: true, curs: { id: 7, data_inici: '2026-04-01', data_fi: '2026-04-30' }, cursos: [] }
  const dependents = { props, emit: (...args) => peticions.push(args), t: x => x, toast: { add: x => avisos.push(x) } }
  const apiConfiguracio = { llegeix: async () => ({}), desa: async x => peticions.push(['settings', x]) }
  const apiEstadistiques = Object.fromEntries(['resum', 'professors', 'temporal', 'classes', 'taula', 'franges', 'professor', 'detallClasses', 'hores'].map(n => [n, async (...args) => { peticions.push([n, ...args]); return { data: n === 'hores' ? { hores: ['8h', '9h'] } : { resultat: n } } }]))
  apiEstadistiques.batch = batch || (async (...args) => {
    peticions.push(['batch', ...args])
    const triades = (args[0]?.params.hores || []).filter(h => ['8h', '9h'].includes(h))
    return { data: {
      ...Object.fromEntries(['resum', 'professors', 'temporal', 'classes', 'taula'].map(n => [n, { resultat: n }])),
      hores: ['8h', '9h'], hores_triades: triades, professors_informe: ['Prof 2', 'Prof 1']
    } }
  })
  const apiPdf = { professorsInforme: async () => ({ data: { professors: ['Prof 2', 'Prof 1'] } }), descarrega: async (...args) => { descarregues.push(args); return { data: 'PDF' } } }
  const p = carregaBlocVista('components/EstadistiquesDialog.vue', 'useEstadistiques', [['const loading =', '</script>']], [
    'dataInici', 'dataFinal', 'cursTriatId', 'inicialitzarDates', 'carregarEstadistiques', 'loading', 'resum', 'horesTriades', 'carregarFrangesHorari', 'paramsDelFiltre', 'onProfessorRowClick', 'professorDetail', 'professorDetailVisible', 'classesSeleccionades', 'carregarDetallClasses', 'classesDetailData', 'formatPercent', 'formatBarWidth', 'carregarInformeProfessors', 'informeProfessorsOpcions', 'informeProfessorSeleccionat', 'generarInformeProfessor', 'tancar'
  ], { ...dependents, dependents, ref, computed, watch: (...args) => watchers.push(args), apiConfiguracio, apiEstadistiques, apiPdf, dataTreball: ref(new Date('2026-04-20')), dataIso: d => d?.toLocaleDateString('sv-SE'), ordenaAlfabeticament: xs => [...xs].sort(), localizeBackendDayName: x => x,
    document: { createElement: () => ({ click() {} }) }, URL: { createObjectURL: () => 'blob:prova', revokeObjectURL() {} }, Blob })
  return { ...p, peticions, avisos, descarregues, watchers, props }
}
test('Estadístiques: el curs fixa el període i una sola consulta conté tots els recomptes i el filtre', async () => {
  const p = prepara(); await p.inicialitzarDates(); p.horesTriades.value = ['9h']; await p.carregarEstadistiques()
  assert.equal(p.cursTriatId.value, 7); assert.equal(p.loading.value, false); assert.deepEqual(p.resum.value, { resultat: 'resum' })
  assert.equal(p.peticions.length, 2); assert.deepEqual(p.peticions[0], ['settings', { data_inici_estadistiques: '2026-04-01', data_final_estadistiques: '2026-04-30' }])
  assert.equal(p.peticions[1][0], 'batch')
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


test('Estadístiques: obertura i canvi de dates comparteixen el lot en curs', async () => {
  const p = prepara()
  p.watchers[0][1](true)
  await Promise.resolve()
  p.watchers[1][1]([p.dataInici.value, p.dataFinal.value])
  await p.carregarEstadistiques()
  assert.equal(p.peticions.filter(([n]) => n === 'batch').length, 1)
  await p.carregarEstadistiques()
  assert.equal(p.peticions.filter(([n]) => n === 'batch').length, 2)
})

test('Estadístiques: una resposta antiga no trepitja el nou interval', async () => {
  const pendents = []
  const p = prepara(() => new Promise(resolve => pendents.push(resolve)))
  await p.inicialitzarDates()
  const antiga = p.carregarEstadistiques()
  await Promise.resolve()
  await Promise.resolve()
  p.dataFinal.value = new Date('2026-05-31')
  const nova = p.carregarEstadistiques()
  await Promise.resolve()
  await Promise.resolve()
  const dada = resultat => ({ data: { resum: { resultat }, professors: {}, temporal: {}, classes: {}, taula: {}, hores: [], hores_triades: [], professors_informe: [] } })
  pendents[1](dada('nou')); await nova
  pendents[0](dada('antic')); await antiga
  assert.deepEqual(p.resum.value, { resultat: 'nou' })
})

test('Estadístiques: fallada del lot conserva dades i permet reintentar', async () => {
  let intents = 0
  const p = prepara(async () => {
    if (++intents === 1) throw new Error('fallada de prova')
    return { data: { resum: { correcte: true }, professors: {}, temporal: {}, classes: {}, taula: {}, hores: [], hores_triades: [], professors_informe: [] } }
  })
  await p.inicialitzarDates()
  await p.carregarEstadistiques()
  assert.equal(p.avisos.length, 1); assert.equal(p.loading.value, false)
  await p.carregarEstadistiques()
  assert.deepEqual(p.resum.value, { correcte: true })
})


test('Estadístiques: editar dates només actualitza auxiliars fins a prémer Actualitza', async () => {
  const p = prepara()
  await p.inicialitzarDates(); await p.carregarEstadistiques()
  const resum = p.resum.value
  p.dataFinal.value = new Date('2026-05-31')
  p.watchers[1][1]([p.dataInici.value, p.dataFinal.value])
  await p.carregarFrangesHorari()
  assert.equal(p.resum.value, resum)
  assert.equal(p.peticions.filter(([n]) => n === 'settings').length, 1)
  await p.carregarEstadistiques()
  assert.equal(p.peticions.filter(([n]) => n === 'settings').length, 2)
})
