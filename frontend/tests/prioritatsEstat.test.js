import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'

function prepara() {
  const peticions = [], avisos = [], confirmacions = []
  const dependents = { t: x => x, locale: ref('ca'), toast: { add: x => avisos.push(x) }, confirmaEsborrar: x => confirmacions.push(x) }
  const apiPrioritats = {
    assignatures: async () => ({ assignatures: [{ assignatura: 'Guàrdia', categoria_id: 2, ordre: 1, pes: 3, auto_assignada: true }, { assignatura: 'Reforç', categoria_id: 1, ordre: 1, pes: 2, auto_assignada: false }] }),
    categories: async () => ({ categories: [{ id: 1, activa: false, ordre: 2 }, { id: 2, activa: true, ordre: 1 }] }),
    desaTot: async body => { peticions.push(['desa', body]); return { message: 'fet' } },
    noSubstituir: async () => ({ assignatures: [''] }),
    afegeixNoSubstituir: async x => peticions.push(['afegeix', x]),
    esborraNoSubstituir: async x => peticions.push(['treu', x]),
    desaActivitatsAlliberables: async body => { peticions.push(['activitats', body]); return body }
  }
  const p = carregaBlocVista('components/config/PrioritatsTab.vue', 'usePrioritats', [['// Data en format ISO', '</script>']], [
    'carregarPrioritats', 'ordreCategories', 'pesos', 'teCanvisPrioritats', 'categoriaSeleccionadaIndex', 'moureCategoriaAmunt', 'moureCategoriaAvall',
    'afegirAssignaturaCategoria', 'assignaturesSeleccionades', 'desarAssignaturaCategoria', 'desarPrioitats', 'eliminarCategoria',
    'noSubstituir', 'novesNoSubstituir', 'desarNoSubstituir', 'activitatsAlliberables', 'activitatsPerDefecte', 'desarActivitatsAlliberables', 'opcionsNoSubst'
  ], {
    ...dependents, dependents, ref, computed, watch() {}, onMounted() {}, apiPrioritats,
    dataTreball: ref(new Date('2026-04-20T12:00:00')), dataIso: () => '2026-04-20', ambDataTreball: () => ({ params: { data: '2026-04-20' } }),
    detectaAssignatures: async () => ({ assignatures: ['Guàrdia'], te_buits: true }), novesAmbGrup: () => []
  })
  return { ...p, peticions, avisos, confirmacions }
}

test('Prioritats: conserva ordre per id, pesos i activació de les assignatures', async () => {
  const p = prepara()
  await p.carregarPrioritats()
  assert.deepEqual(p.ordreCategories.value, [{ categories: ['Reforç'], activa: false }, { categories: ['Guàrdia'], activa: true }])
  assert.deepEqual(p.pesos.value, { Guàrdia: 3, Reforç: 2 })
  assert.equal(p.teCanvisPrioritats.value, false)
  p.categoriaSeleccionadaIndex.value = 1
  p.moureCategoriaAmunt()
  assert.equal(p.categoriaSeleccionadaIndex.value, 0)
  assert.equal(p.teCanvisPrioritats.value, true)
  p.moureCategoriaAvall()
  assert.equal(p.teCanvisPrioritats.value, false)
})

test('Prioritats: selecció de categoria manté ordre existent i afegeix pes per defecte', async () => {
  const p = prepara()
  await p.carregarPrioritats()
  await p.afegirAssignaturaCategoria(0)
  p.assignaturesSeleccionades.value = ['alliberat', 'Reforç']
  p.desarAssignaturaCategoria()
  assert.deepEqual(p.ordreCategories.value[0].categories, ['Reforç', 'alliberat'])
  assert.equal(p.pesos.value.alliberat, 1)
  await p.desarPrioitats()
  assert.deepEqual(p.peticions[0], ['desa', { ordre_categories: [['Reforç', 'alliberat'], ['Guàrdia']], pesos: { Guàrdia: 3, Reforç: 2, alliberat: 1 }, categories_actives: [false, true] }])
  assert.equal(p.teCanvisPrioritats.value, false)
})

test('Prioritats: eliminar exigeix confirmació i conserva els pesos', async () => {
  const p = prepara()
  await p.carregarPrioritats()
  p.categoriaSeleccionadaIndex.value = 0
  p.eliminarCategoria()
  assert.equal(p.ordreCategories.value.length, 2)
  p.confirmacions[0].accept()
  assert.deepEqual(p.ordreCategories.value, [{ categories: ['Guàrdia'], activa: true }])
  assert.equal(p.pesos.value.Reforç, 2)
})

test('Prioritats: no substituir afegeix abans de treure i les activitats filtren per defecte', async () => {
  const p = prepara()
  p.noSubstituir.value = ['']
  p.novesNoSubstituir.value = ['Guàrdia']
  await p.desarNoSubstituir()
  assert.deepEqual(p.peticions, [['afegeix', 'Guàrdia'], ['treu', '']])
  assert(p.opcionsNoSubst.value.some(x => x.value === '' && x.label === 'common.empty'))
  p.activitatsAlliberables.value = ['Reforç']
  p.activitatsPerDefecte.value = ['Reforç', 'Antic']
  await p.desarActivitatsAlliberables()
  assert.deepEqual(p.peticions.at(-1), ['activitats', { activitats: ['Reforç'], per_defecte: ['Reforç'] }])
})
