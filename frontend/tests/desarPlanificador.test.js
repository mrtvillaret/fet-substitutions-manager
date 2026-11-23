import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, ref } from 'vue'
import { ambElQueNoConeix } from '../src/views/scheduler/restriccionsDesades.js'

// El composable real, amb l'API i els avisos com a dobles (com carregaBlocVista)
const codi = readFileSync(new URL('../src/views/scheduler/useSchedulerRestrictions.js', import.meta.url), 'utf8')
  .replace(/^import .*\n/gm, '')
  .replace('export const useSchedulerRestrictions', 'const useSchedulerRestrictions')

function prepara(configReady) {
  const crides = []
  const avisos = []
  const apiPlanificador = new Proxy({}, {
    get: (_, nom) => async () => { crides.push(nom); return { data: {} } }
  })
  const crea = new Function(
    'computed', 'ref', 'apiPlanificador', 'ambElQueNoConeix', 'avisaError', 'detallDError',
    `${codi}; return useSchedulerRestrictions`
  )(computed, ref, apiPlanificador, ambElQueNoConeix, (_e, avisa) => avisa(), () => null)
  let configDesada = 0
  const { desarTotAlBackend } = crea({
    t: (clau) => clau,
    toast: { add: (avis) => avisos.push(avis) },
    config: ref({}),
    genConfig: ref({ nivells_actius: [] }),
    llistaSessions: ref([]),
    restriccionsProfessors: ref([]),
    restriccionsDiesHores: ref([]),
    restriccionsPreferencies: ref([]),
    restriccionsIncompatibilitats: ref([]),
    restriccionsMateixSlot: ref([]),
    professorsHorariEstricte: ref([]),
    costosProfessors: ref({ globals: {}, individuals: {} }),
    pesos: ref({}),
    restriccionsCarregades: ref({}),
    savingRestr: ref(false),
    configReady: ref(configReady),
    flushPendingConfigSave: async () => { configDesada++ },
    serialitzarSlotsValidsPerNivell: () => ({}),
    buildId: () => 'id',
    extreuNivell: () => ''
  })
  return { desarTotAlBackend, crides, avisos, configDesada: () => configDesada }
}

test('planificador: si la càrrega ha fallat, «Desa» no escriu res, avisa i torna false (generar no continua)', async () => {
  const { desarTotAlBackend, crides, avisos, configDesada } = prepara(false)

  assert.equal(await desarTotAlBackend(), false)
  assert.equal(await desarTotAlBackend({ silent: true }), false) // el que crida «Genera»

  assert.deepEqual(crides, [])
  assert.equal(configDesada(), 0)
  assert.equal(avisos.length, 2)
  assert.ok(avisos.every((a) => a.severity === 'error' && a.summary === 'scheduler.view.loadFailed'))
})

test('planificador: amb la configuració carregada, «Desa» desa configuració, restriccions i costos', async () => {
  const { desarTotAlBackend, crides, configDesada } = prepara(true)

  assert.equal(await desarTotAlBackend({ silent: true }), true)

  assert.equal(configDesada(), 1)
  assert.deepEqual(crides, ['desaRestriccions', 'desaCostosProfessors'])
})
