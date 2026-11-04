import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'

function prepara() {
  const peticions = [], esdeveniments = [], avisos = [], muntatges = []
  const horariInicial = { dies: [{ data: '2026-04-20', dia: 'Dilluns', sessions: [
    { hora: '8h', sessions_simultanees: [{ nom: 'Examen A', curs: 'G1', item_id: 'a' }] },
    { hora: '9h', sessions_simultanees: [{ nom: 'Examen B', curs: 'G1', item_id: 'b' }] }
  ] }] }
  const props = { horariInicial, dataReferencia: '2026-04-20', selectedDates: ['2026-04-20'], pinnedNoms: new Set() }
  const dependents = { props, emit: (...args) => esdeveniments.push(args), t: x => x, toast: { add: x => avisos.push(x) } }
  const p = carregaBlocVista('components/HorariEditable.vue', 'useHorariEditable', [['// slotKey', 'const props ='], ['const horariLocal =', '</script>']], [
    'horariLocal', 'horariOriginal', 'costTotal', 'isValid', 'carregant', 'haCanvis', 'getItemsSlot', 'getCostSlot', 'onItemsChanged', 'itemsAparcats', 'grupsAparcats',
    'recalcularCost', 'aplicarCanvis', 'desferCanvis', 'toggleFixarItem', 'fixarTot', 'desfixarTot', 'onMoveGrup', 'parseSlotKey'
  ], {
    ...dependents, dependents, ref, computed, watch() {}, onMounted: x => muntatges.push(x), debounce: x => x,
    localizeBackendDayName: x => x,
    apiPlanificador: {
      recalculaCost: async body => { peticions.push(['cost', body]); return { data: { cost_total: 15, valid: true, slots: [{ slot_key: '2026-04-20_8h', cost: 15 }], logs: [] } } },
      pins: async body => peticions.push(['pins', body])
    }
  })
  return { ...p, props, peticions, esdeveniments, avisos, muntatges }
}

async function muntat() {
  const p = prepara()
  p.muntatges[0]()
  await p.recalcularCost()
  p.peticions.length = 0
  p.esdeveniments.length = 0
  return p
}

test('Horari editable: còpia inicial independent, identificadors i cos del recàlcul', async () => {
  const p = await muntat()
  assert.equal(p.getItemsSlot('2026-04-20', '8h')[0]._uid, 'a_G1_1')
  assert.equal(p.props.horariInicial.dies[0].sessions[0]._items, undefined)
  assert.equal(p.getCostSlot('2026-04-20', '8h').cost, 15)
  await p.recalcularCost()
  const body = p.peticions[0][1]
  assert.equal(body.data_referencia, '2026-04-20')
  assert.deepEqual(body.selected_dates, ['2026-04-20'])
  assert.equal(body.horari.dies[0].sessions[0]._items, undefined)
  assert.equal(p.carregant.value, false)
})

test('Horari editable: mou un ítem i aparca el conflictiu del mateix nivell', async () => {
  const p = await muntat()
  const item = p.getItemsSlot('2026-04-20', '8h')[0]
  await p.onItemsChanged({ type: 'added', slotKey: '2026-04-20_9h', item })
  assert.deepEqual(p.getItemsSlot('2026-04-20', '8h'), [])
  assert.deepEqual(p.getItemsSlot('2026-04-20', '9h').map(x => x.nom), ['Examen A'])
  assert.deepEqual(p.itemsAparcats.value.map(x => x.nom), ['Examen B'])
  assert.equal(p.haCanvis.value, true)
  assert.equal(p.props.horariInicial.dies[0].sessions[0].sessions_simultanees[0].nom, 'Examen A')
})

test('Horari editable: aplicar vàlid emet una còpia neta i invàlid només avisa', async () => {
  const p = await muntat()
  p.isValid.value = false
  p.aplicarCanvis()
  assert.deepEqual(p.esdeveniments, [])
  assert.equal(p.avisos.at(-1).severity, 'warn')
  p.isValid.value = true
  p.aplicarCanvis()
  const [event, horari] = p.esdeveniments.at(-1)
  assert.equal(event, 'actualitzat')
  assert.equal(horari.metadata.editat_manualment, true)
  assert.equal(horari.metadata.cost_total, 15)
  assert.equal(horari.dies[0].sessions[0]._items, undefined)
  horari.dies.length = 0
  assert.equal(p.horariLocal.value.dies.length, 1)
})

test('Horari editable: fixar, desfixar i desfer conserven peticions i esdeveniments', async () => {
  const p = await muntat()
  const item = p.getItemsSlot('2026-04-20', '8h')[0]
  await p.toggleFixarItem({ item, slotKey: '2026-04-20_8h' })
  assert.deepEqual(p.peticions.at(-1), ['pins', { pins: [{ nom: 'Examen A', dia: '2026-04-20', hora: '8h' }], unpins: [] }])
  p.props.pinnedNoms.add('Examen A')
  await p.desfixarTot()
  assert.deepEqual(p.peticions.at(-1), ['pins', { pins: [], unpins: ['Examen A'] }])
  await p.fixarTot()
  assert.equal(p.peticions.at(-1)[1].pins.length, 2)
  p.itemsAparcats.value.push(item)
  p.desferCanvis()
  assert.deepEqual(p.itemsAparcats.value, [])
  assert.deepEqual(p.grupsAparcats.value, [])
  assert.equal(p.getItemsSlot('2026-04-20', '8h')[0].nom, 'Examen A')
})
