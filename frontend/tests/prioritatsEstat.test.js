import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { dataAmbAny, dataIso } from '../src/dates.js'

function prepara(apiDiferent = () => ({})) {
  const peticions = [], avisos = [], confirmacions = []
  const dependents = { t: x => x, locale: ref('ca'), toast: { add: x => avisos.push(x) }, confirmaEsborrar: x => confirmacions.push(x) }
  const apiPrioritats = {
    assignatures: async () => ({ assignatures: [{ assignatura: 'Guàrdia', categoria_id: 2, ordre: 1, pes: 3, auto_assignada: true }, { assignatura: 'Reforç', categoria_id: 1, ordre: 1, pes: 2, auto_assignada: false }] }),
    categories: async () => ({ categories: [{ id: 1, activa: false, ordre: 2 }, { id: 2, activa: true, ordre: 1 }] }),
    desaTot: async body => { peticions.push(['desa', body]); return { message: 'fet' } },
    noSubstituir: async () => ({ assignatures: [''], entrades: [] }),
    afegeixNoSubstituir: async (x, data) => peticions.push(['afegeix', x, data]),
    esborraNoSubstituir: async (x, data) => peticions.push(['treu', x, data]),
    desaActivitatsAlliberables: async body => { peticions.push(['activitats', body]); return body },
    ...apiDiferent(peticions)
  }
  const p = carregaBlocVista('components/config/PrioritatsTab.vue', 'usePrioritats', [['// Data en format ISO', '</script>']], [
    'carregarPrioritats', 'ordreCategories', 'pesos', 'teCanvisPrioritats', 'categoriaSeleccionadaIndex', 'moureCategoriaAmunt', 'moureCategoriaAvall',
    'afegirAssignaturaCategoria', 'assignaturesSeleccionades', 'desarAssignaturaCategoria', 'desarPrioitats', 'eliminarCategoria',
    'noSubstituir', 'novesNoSubstituir', 'desarNoSubstituir', 'activitatsAlliberables', 'activitatsPerDefecte', 'desarActivitatsAlliberables', 'opcionsNoSubst',
    'entradesNoSubstituir', 'dataCanvisNoSubst', 'dataCanvisNoSubstPassada', 'fiNoSubstituir', 'futuresNoSubstituir', 'eliminarNoSubstituir',
    'obrirDialogNoSubstituir', 'mostrarDialogNoSubstituir'
  ], {
    ...dependents, dependents, ref, computed, watch() {}, onMounted() {}, apiPrioritats,
    dataTreball: ref(new Date('2026-04-20T12:00:00')), dataIso, dataAmbAny, detallDError: error => error?.response?.data?.detail, ambDataTreball: () => ({ params: { data: '2026-04-20' } }),
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
  const avui = dataIso(new Date())
  assert.deepEqual(p.peticions, [['afegeix', 'Guàrdia', avui], ['treu', '', avui]])
  assert(p.opcionsNoSubst.value.some(x => x.value === '' && x.label === 'common.empty'))
  p.activitatsAlliberables.value = ['Reforç']
  p.activitatsPerDefecte.value = ['Reforç', 'Antic']
  await p.desarActivitatsAlliberables()
  assert.deepEqual(p.peticions.at(-1), ['activitats', { activitats: ['Reforç'], per_defecte: ['Reforç'] }])
})

test('Prioritats: no substituir desa amb la data triada i avisa si és passada', async () => {
  const p = prepara()
  p.noSubstituir.value = ['Guàrdia']
  p.novesNoSubstituir.value = ['Pares']
  assert.equal(p.dataCanvisNoSubstPassada.value, false)
  p.dataCanvisNoSubst.value = new Date('2025-09-01T12:00:00')
  assert.equal(p.dataCanvisNoSubstPassada.value, true)
  await p.desarNoSubstituir()
  assert.deepEqual(p.peticions, [['afegeix', 'Pares', '2025-09-01'], ['treu', 'Guàrdia', '2025-09-01']])
})

test('Prioritats: les dates de fi i les activitats que comencen més endavant', () => {
  const p = prepara()
  p.noSubstituir.value = ['Guàrdia', 'Pati']
  p.entradesNoSubstituir.value = [
    { assignatura: 'Guàrdia', vigent_des_de: null, vigent_fins_a: '2999-01-31' },
    { assignatura: 'Pati', vigent_des_de: null, vigent_fins_a: null },
    { assignatura: 'Pares', vigent_des_de: '2999-02-01', vigent_fins_a: null }
  ]
  assert.deepEqual(p.fiNoSubstituir.value, { Guàrdia: '31/01/2999' })
  assert.deepEqual(p.futuresNoSubstituir.value.map(e => e.assignatura), ['Pares'])
})

test('Prioritats: anul·lar una activitat futura la treu des de la seva data d\'inici', async () => {
  const p = prepara()
  await p.eliminarNoSubstituir('Pares', '2999-02-01')
  assert.deepEqual(p.peticions, [['treu', 'Pares', '2999-02-01']])
})

test('Prioritats: un error a mig desar recarrega la llista i no torna a enviar el que ja s\'ha desat', async () => {
  let falla = true, lectures = 0
  const p = prepara(peticions => ({
    noSubstituir: async () => { lectures++; return { assignatures: ['Guàrdia'], entrades: [] } },
    afegeixNoSubstituir: async (x, data) => {
      if (x === 'Reunió' && falla) throw { response: { status: 409, data: { detail: 'solapada', codi: 'no_substituir_solapada' } } }
      peticions.push(['afegeix', x, data])
    }
  }))
  p.noSubstituir.value = ['Guàrdia']
  p.obrirDialogNoSubstituir()
  // Una data futura: el que s'hi afegeix no surt a la llista d'avui
  p.dataCanvisNoSubst.value = new Date('2999-01-01T12:00:00')
  p.novesNoSubstituir.value = ['Pares', 'Reunió']
  await p.desarNoSubstituir()
  assert.deepEqual(p.peticions, [['afegeix', 'Pares', '2999-01-01']])
  assert.equal(lectures, 1)
  assert.equal(p.avisos.at(-1).severity, 'error')
  // El diàleg continua obert amb la mateixa selecció i la mateixa data
  assert.equal(p.mostrarDialogNoSubstituir.value, true)
  assert.deepEqual(p.novesNoSubstituir.value, ['Pares', 'Reunió'])

  falla = false
  await p.desarNoSubstituir()
  assert.deepEqual(p.peticions, [
    ['afegeix', 'Pares', '2999-01-01'], ['afegeix', 'Reunió', '2999-01-01'], ['treu', 'Guàrdia', '2999-01-01']
  ])
  assert.equal(p.mostrarDialogNoSubstituir.value, false)
})
