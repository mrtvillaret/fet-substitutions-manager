import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as vue from 'vue'
import { parse, compileScript } from '@vue/compiler-sfc'

// Compila la plantilla real: els tests activen els mateixos handlers que els
// controls PrimeVue, sense substituir la lògica dels formularis.
const source = readFileSync(new URL('../src/views/scheduler/steps/SchedulerDialogs.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const compiled = compileScript(descriptor, { id: 'caracteritzacio', inlineTemplate: true }).content
const dependencies = { ...vue, useI18n: () => ({ t: x => x }), localizeBackendDayName: x => x }
const code = compiled.replace(/import\s+([\s\S]*?)\s+from ['"]([^'"]+)['"];?/g, (_all, names, from) => {
  if (names.trim().startsWith('{')) {
    return `const ${names.replace(/\bas\b/g, ':')} = dependencies;`
  }
  return `const ${names.trim()} = { name: ${JSON.stringify(from)} };`
}).replace('export default', 'return')
const component = new Function('dependencies', code)(dependencies)
const defaults = {
  formulariDurada: { nom: '', sessions: [], durada: 2, durada_examen: 1 },
  formulariProfessor: { professor: '', assignatures: [], dies: [], max_examens: 1, pes: 50 },
  formulariDiaHora: { tipus: 'fixar', assignatures: [], teDia: false, dia: '', teHora: false, hora: '' },
  formulariPreferencia: { assignatures: [], tipus: 'dies_diferents', pes: 75 },
  formulariIncompat: { nom: '', assignatures: [], pes: 100 },
  formulariAgrupacio: { nom: '', assignatures: [] },
  formulariCostProfessor: { professor: '', substitucio: 0, abans_jornada: 0, despres_jornada: 0, no_treballa_dia: 0 }
}

function prepara() {
  const events = [], saved = []
  const props = vue.reactive(Object.fromEntries(Object.entries(component.props).map(([nom, spec]) => [nom, typeof spec.default === 'function' ? spec.default() : spec.default])))
  Object.assign(props, JSON.parse(JSON.stringify(defaults)))
  props.diesSetmana = ['Dilluns']
  props.llistaSessions = ['Examen A', 'Examen B']
  props.llistaProfessors = ['Prof 1', 'Prof 2']
  const noms = ['Durada', 'Professor', 'DiaHora', 'PreferenciaDia', 'Incompatibilitat', 'Agrupacio', 'CostProfessor']
  for (const [i, nom] of noms.entries()) {
    props['desarDialog' + nom] = () => saved.push(JSON.parse(JSON.stringify(props[Object.keys(defaults)[i]])))
  }
  const scope = vue.effectScope()
  const render = scope.run(() => component.setup(props, {
    expose() {},
    emit(nom, valor) { events.push([nom, valor]); props[nom.slice(7)] = valor }
  }))
  const dialogs = () => render({}, []).children.filter(node => node.type?.name === 'primevue/dialog')
  const controls = index => {
    const nodes = []
    const visit = node => {
      if (Array.isArray(node)) return node.forEach(visit)
      if (!node || typeof node !== 'object') return
      if (node.props?.['onUpdate:modelValue']) nodes.push(node)
      if (Array.isArray(node.children)) visit(node.children)
      else if (node.children?.default) visit(node.children.default())
    }
    visit(dialogs()[index].children.default())
    return nodes
  }
  const update = (index, field, value) => {
    const handler = controls(index)[field].props['onUpdate:modelValue']
    for (const fn of [handler].flat()) fn(value)
  }
  return { props, events, saved, dialogs, controls, update, scope }
}

test('SchedulerDialogs: tots els controls transmeten cada camp abans de desar', () => {
  const p = prepara()
  try {
    const values = [
      ['Durada nova', ['Examen A'], 3, 2],
      ['Prof 2', ['Examen B'], ['Dilluns'], 4, 25],
      ['prohibir', ['Examen B'], true, 'Dilluns', true, '9h'],
      [['Examen B'], 'mateix_dia', 35],
      ['Conflicte', ['Examen A', 'Examen B'], 80],
      ['Agrupació', ['Examen B']],
      ['Prof 2', 10, 20, 30, 40]
    ]
    const expected = [
      { nom: 'Durada nova', sessions: ['Examen A'], durada: 3, durada_examen: 2 },
      { professor: 'Prof 2', assignatures: ['Examen B'], dies: ['Dilluns'], max_examens: 4, pes: 25 },
      { tipus: 'prohibir', assignatures: ['Examen B'], teDia: true, dia: 'Dilluns', teHora: true, hora: '9h' },
      { assignatures: ['Examen B'], tipus: 'mateix_dia', pes: 35 },
      { nom: 'Conflicte', assignatures: ['Examen A', 'Examen B'], pes: 80 },
      { nom: 'Agrupació', assignatures: ['Examen B'] },
      { professor: 'Prof 2', substitucio: 10, abans_jornada: 20, despres_jornada: 30, no_treballa_dia: 40 }
    ]
    values.forEach((fields, index) => {
      assert.equal(p.controls(index).length, fields.length)
      fields.forEach((value, field) => p.update(index, field, value))
      assert.deepEqual(p.props[Object.keys(defaults)[index]], expected[index])
      const save = p.dialogs()[index].children.footer().at(-1)
      save.props.onClick()
      assert.deepEqual(p.saved.at(-1), expected[index])
    })
    assert.equal(values.flat().length, 28)
  } finally { p.scope.stop() }
})

test('SchedulerDialogs: cancel·lar i reobrir mantenen els camps del pare', () => {
  const p = prepara()
  try {
    p.update(0, 0, 'Encara sense desar')
    p.dialogs()[0].children.footer()[0].props.onClick()
    assert.equal(p.props.mostrarDialogDurada, false)
    assert.equal(p.props.formulariDurada.nom, 'Encara sense desar')
    p.props.mostrarDialogDurada = true
    assert.equal(p.controls(0)[0].props.modelValue, 'Encara sense desar')
  } finally { p.scope.stop() }
})

test('SchedulerDialogs: reemplaçar i editar el formulari al pare actualitza els controls', () => {
  const p = prepara()
  try {
    p.props.formulariDurada = { nom: 'Editat', sessions: ['Examen B'], durada: 4, durada_examen: 3 }
    assert.equal(p.controls(0)[0].props.modelValue, 'Editat')
    p.props.formulariDurada.durada = 5
    assert.equal(p.controls(0)[2].props.modelValue, 5)
    p.update(0, 0, 'Editat després')
    assert.equal(p.props.formulariDurada.durada, 5)
  } finally { p.scope.stop() }
})

test('SchedulerDialogs: emet còpies sense modificar els objectes o arrays rebuts', () => {
  const p = prepara()
  try {
    const original = p.props.formulariDurada
    const originalSessions = original.sessions
    p.update(0, 0, 'Nou nom')
    assert.equal(original.nom, '')
    assert.equal(p.props.formulariDurada.nom, 'Nou nom')
    assert.notEqual(p.props.formulariDurada, original)
    assert.equal(p.events[0][0], 'update:formulariDurada')
    const seleccio = ['Examen A']
    p.update(0, 1, seleccio)
    seleccio.push('Examen B')
    assert.deepEqual(originalSessions, [])
    assert.deepEqual(p.props.formulariDurada.sessions, ['Examen A'])
    assert.notEqual(p.controls(0)[1].props.modelValue, p.props.formulariDurada.sessions)
  } finally { p.scope.stop() }
})
