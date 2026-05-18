<template src="./scheduler/SchedulerView.template.html"></template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import { useI18n } from 'vue-i18n'

import Steps from 'primevue/steps'
import Button from 'primevue/button'
import Toast from 'primevue/toast'
import Menu from 'primevue/menu'
import ConfirmDialog from 'primevue/confirmdialog'
import PublicarVigilanciesDialog from '../components/PublicarVigilanciesDialog.vue'
import SchedulerDialogs from './scheduler/steps/SchedulerDialogs.vue'
import SchedulerStepAnalysis from './scheduler/steps/SchedulerStepAnalysis.vue'
import SchedulerStepConfig from './scheduler/steps/SchedulerStepConfig.vue'
import SchedulerStepGroups from './scheduler/steps/SchedulerStepGroups.vue'
import SchedulerStepRestrictions from './scheduler/steps/SchedulerStepRestrictions.vue'
import SchedulerStepResults from './scheduler/steps/SchedulerStepResults.vue'
import { parsePerSessioReport, parsePerSlotsReport, parseProfessorsSlotReport } from './scheduler/analysisParsers'
import { getExamsUnics, normalizeText } from './scheduler/textUtils'
import { formatDateLocal, toDomId, isSameDay, parseIsoLocal as _parseIsoLocal, formatLocalDate, getWeekNumber } from './scheduler/dateUtils'
import { buildId, extreuNivell as _extreuNivell } from './scheduler/idUtils'
import { formatIncidentFull as formatIncidentFullRaw, formatIncidentShort as formatIncidentShortRaw } from './scheduler/incidentFormatters'
import { useAlliberamentsPerNivell } from './scheduler/useAlliberamentsPerNivell'
import { useSchedulerApi } from './scheduler/useSchedulerApi'
import { useSchedulerRestrictions } from './scheduler/useSchedulerRestrictions'
import { useSchedulerResults } from './scheduler/useSchedulerResults'
import { useSchedulerIncidencies } from './scheduler/useSchedulerIncidencies'
import { useSchedulerSlotsConfig } from './scheduler/useSchedulerSlotsConfig'

const toast = useToast()
const { t, locale, te } = useI18n()

// ESTAT
const pasActiu = ref(0)
const stepperContainerRef = ref(null)
const loading = ref(true), generating = ref(false), savingRestr = ref(false)
const config = ref(null), status = ref(null), selectedDates = ref([]), result = ref(null)
const modeEdicio = ref(false)
// Durades del titular i de l'examen
const duradesGrups = ref([])  // [{ id, nom, assignatures, durada, durada_examen }]
const duradaExamen = ref(1)
const editantDuradaId = ref(null)
const mostrarDialogDurada = ref(false)
const formulariDurada = ref({ nom: '', sessions: [], durada: 2, durada_examen: 1 })
const analisiLoading = ref(false), analisiResult = ref(null)
const analysisActiveIndex = ref(0)
const analysisTabInfo = computed(() => {
  const info = [
    {
      title: t('scheduler.view.analysis.tabs.perSlot.title'),
      desc: t('scheduler.view.analysis.tabs.perSlot.desc')
    },
    {
      title: t('scheduler.view.analysis.tabs.perGroup.title'),
      desc: t('scheduler.view.analysis.tabs.perGroup.desc')
    },
    {
      title: t('scheduler.view.analysis.tabs.teachersPerSlot.title'),
      desc: t('scheduler.view.analysis.tabs.teachersPerSlot.desc')
    }
  ]
  return info[analysisActiveIndex.value] || info[0]
})

const analysisFilaClass = (fila, idx, files) => {
  const currDia = String(fila?.dia || '')
  const prevDia = idx > 0 ? String(files[idx - 1]?.dia || '') : ''
  const blockSize = Math.max(1, Number(config.value?.durada_titular || 1))
  let dayIdx = 0
  for (let i = 0; i <= idx; i += 1) {
    if (String(files[i]?.dia || '') === currDia) {
      dayIdx += 1
    }
  }
  const groupIdx = Math.floor((dayIdx - 1) / blockSize)
  const prevDayIdx = dayIdx - 1
  const prevGroupIdx = Math.floor((prevDayIdx - 1) / blockSize)
  const isDayStart = idx === 0 || prevDia !== currDia
  const isBlockStart = isDayStart || prevGroupIdx !== groupIdx
  const variant = groupIdx % 2 === 0 ? 'even' : 'odd'
  return [
    `analysis-row-${variant}`,
    isDayStart ? 'analysis-row-day-start' : '',
    isBlockStart ? 'analysis-row-block-start' : ''
  ]
}
const mostrarDialogIntents = ref(false)
const mostrarDialogIncompat = ref(false)
const incompatibilitats = ref([])
const incompatErrorMsg = ref('')
const intentsLog = ref([])
const llistaAssignatures = ref([]), llistaProfessors = ref([]), llistaGrups = ref([]), llistaSessions = ref([]), llistaHoresDisponibles = ref([]), genConfigHoresArray = ref([])

const recompteNivells = computed(() => result.value?.horari?.metadata?.recompte_nivells || {})
const recompteTotals = computed(() => {
  let esperats = 0
  let collocats = 0
  for (const info of Object.values(recompteNivells.value || {})) {
    esperats += Number(info?.esperats || 0)
    collocats += Number(info?.collocats || 0)
  }
  return { esperats, collocats }
})
const recompteTotalsText = computed(() => (
  recompteTotals.value.esperats > 0
    ? `${recompteTotals.value.collocats}/${recompteTotals.value.esperats}`
    : '—'
))
const recompteTooltip = computed(() => {
  const entries = Object.entries(recompteNivells.value || {})
  if (!entries.length) return ''
  return entries
    .map(([nivell, info]) => `${nivell}: ${info?.collocats || 0}/${info?.esperats || 0}`)
    .join('\n')
})

const passos = computed(() => ([
  { label: t('scheduler.view.steps.dates'), command: () => { pasActiu.value = 0 } },
  { label: t('scheduler.view.steps.groups'), command: () => { pasActiu.value = 1 } },
  { label: t('scheduler.view.steps.restrictions'), command: () => { pasActiu.value = 2 } },
  { label: t('scheduler.view.steps.analysis'), command: () => { pasActiu.value = 3 } },
  { label: t('scheduler.view.steps.generation'), command: () => { pasActiu.value = 4 } }
]))
// Motors i paràmetres carregats des de l'API (GET /api/scheduler/motors)
const motorsMetadata = ref([])
const i18nWithFallback = (key, fallback, params = undefined) => {
  if (typeof te === 'function' && te(key)) return t(key, params)
  const value = t(key, params)
  return value && value !== key ? value : fallback
}

const localizeMotorLabel = (motorId, fallback) => i18nWithFallback(`scheduler.motors.${motorId}`, fallback || motorId)

const localizeMotorParam = (paramKey, cfg = {}) => {
  const baseKey = `scheduler.motors.params.${paramKey}`
  const options = Array.isArray(cfg.options)
    ? cfg.options.map((opt) => ({
      ...opt,
      label: i18nWithFallback(`${baseKey}.options.${opt?.value}`, opt?.label || String(opt?.value || ''))
    }))
    : cfg.options

  return {
    ...cfg,
    label: i18nWithFallback(`${baseKey}.label`, cfg.label || paramKey),
    help: i18nWithFallback(`${baseKey}.help`, cfg.help || ''),
    options
  }
}

const motors = computed(() => motorsMetadata.value.map((m) => ({ label: localizeMotorLabel(m.id, m.label), value: m.id })))
const genConfig = ref({
  motor: 'v3',
  nivells_actius: [],
  max_dies: 5,
})

const currentMotorMeta = computed(() => motorsMetadata.value.find(m => m.id === genConfig.value.motor))
const mainParams = computed(() => {
  const meta = currentMotorMeta.value
  if (!meta?.param_labels) return []
  return Object.entries(meta.param_labels)
    .filter(([, cfg]) => cfg.main)
    .map(([key, cfg]) => ({ key, ...localizeMotorParam(key, cfg) }))
})
const advancedParams = computed(() => {
  const meta = currentMotorMeta.value
  if (!meta?.param_labels) return []
  return Object.entries(meta.param_labels)
    .filter(([, cfg]) => !cfg.main)
    .map(([key, cfg]) => ({ key, ...localizeMotorParam(key, cfg) }))
})

// Aplica defaults del motor seleccionat al genConfig
const aplicarDefaultsMotor = (motorId) => {
  const meta = motorsMetadata.value.find(m => m.id === motorId)
  if (!meta?.params) return
  for (const [key, val] of Object.entries(meta.params)) {
    genConfig.value[key] = val
  }
}

// Quan canvia el motor, actualitza els params amb els defaults nous
watch(() => genConfig.value.motor, (nouMotor) => {
  aplicarDefaultsMotor(nouMotor)
})

watch(() => config.value?.durada_titular, (val, prev) => {
  if (!configReady.value || val === prev) return
  scheduleConfigSave()
})

watch(duradaExamen, (val, prev) => {
  if (!configReady.value || val === prev) return
  scheduleConfigSave()
})

const mostrarParametresAvancats = ref(false)
const configReady = ref(false)
let configSaveTimer = null
let configSaveIdleId = null
const pesos = ref({
  restriccio_dura: 1000,
  preferencia_mateix_dia: -500,
  preferencia_mateix_slot: -2000,
  preferencia_dies_diferents: 500
})
const pesosInfo = computed(() => ({
  restriccio_dura: {
    label: t('scheduler.view.weights.restriccioDura.label'),
    desc: t('scheduler.view.weights.restriccioDura.desc')
  },
  preferencia_mateix_dia: {
    label: t('scheduler.view.weights.preferenciaMateixDia.label'),
    desc: t('scheduler.view.weights.preferenciaMateixDia.desc')
  },
  preferencia_mateix_slot: {
    label: t('scheduler.view.weights.preferenciaMateixSlot.label'),
    desc: t('scheduler.view.weights.preferenciaMateixSlot.desc')
  },
  preferencia_dies_diferents: {
    label: t('scheduler.view.weights.preferenciaDiesDiferents.label'),
    desc: t('scheduler.view.weights.preferenciaDiesDiferents.desc')
  }
}))

// Defaults sincronitzats amb backend (scheduler_engine/defaults.py)
const costosProfessors = ref({
  globals: { substitucio: 80, abans_jornada: 30, despres_jornada: 30, no_treballa_dia: 60 },
  individuals: {}
})
const costosInfo = computed(() => ({
  substitucio: {
    label: t('scheduler.dialogs.cost.fields.substitution'),
    desc: t('scheduler.view.costs.substitucioDesc')
  },
  abans_jornada: {
    label: t('scheduler.dialogs.cost.fields.beforeShift'),
    desc: t('scheduler.view.costs.abansJornadaDesc')
  },
  despres_jornada: {
    label: t('scheduler.dialogs.cost.fields.afterShift'),
    desc: t('scheduler.view.costs.despresJornadaDesc')
  },
  no_treballa_dia: {
    label: t('scheduler.dialogs.cost.fields.noWorkDay'),
    desc: t('scheduler.view.costs.noTreballaDiaDesc')
  }
}))
const costosProfessorsIndividuals = computed(() => {
  const globals = costosProfessors.value.globals || {}
  return Object.entries(costosProfessors.value.individuals || {}).map(([professor, data]) => ({
    professor,
    substitucio: data.substitucio ?? globals.substitucio ?? 0,
    abans_jornada: data.abans_jornada ?? globals.abans_jornada ?? 0,
    despres_jornada: data.despres_jornada ?? globals.despres_jornada ?? 0,
    no_treballa_dia: data.no_treballa_dia ?? globals.no_treballa_dia ?? 0,
  }))
})

const restriccionsProfessors = ref([])
const restriccionsDiesHores = ref([])
const restriccionsPreferencies = ref([])
const restriccionsIncompatibilitats = ref([])
const restriccionsMateixSlot = ref([])
const professorsHorariEstricte = ref([])
const preferencies = ref([])

// Pins = sessions que tenen restricció dia_fix + hora_fix (derivat de restriccionsDiesHores)
const pinnedNoms = computed(() => {
  const noms = new Set()
  for (const r of restriccionsDiesHores.value) {
    if (r.tipus === 'fixar' && r.dia && r.hora) {
      (r.assignatures || []).forEach((a) => noms.add(a))
    }
  }
  return noms
})

const onPinChanged = async () => {
  try {
    const { data } = await axios.get('/api/scheduler/restriccions')
    aplicarRestriccions(data.restriccions)
  } catch (err) {
    console.error('Error recarregant restriccions:', err)
  }
}

const clearAllPins = async () => {
  const unpins = Array.from(pinnedNoms.value)
  if (!unpins.length) return
  try {
    await axios.post('/api/scheduler/restriccions/pin', { pins: [], unpins })
    await onPinChanged()
  } catch (err) {
    console.error('Error desfixant tot:', err)
  }
}

// Dies de la setmana (font única)
const diesSetmana = ['Dilluns', 'Dimarts', 'Dimecres', 'Dijous', 'Divendres']
const diesCurts = diesSetmana.map(nom => ({ curt: nom.slice(0, 2), nom }))
const dayLabels = computed(() => ({
  Dilluns: t('scheduler.days.monday'),
  Dimarts: t('scheduler.days.tuesday'),
  Dimecres: t('scheduler.days.wednesday'),
  Dijous: t('scheduler.days.thursday'),
  Divendres: t('scheduler.days.friday'),
  Dissabte: t('scheduler.days.saturday'),
  Diumenge: t('scheduler.days.sunday'),
}))
const getDayLabel = (dayName) => dayLabels.value[dayName] || dayName
const slotsValidsPerNivell = ref({})
const horesPerNivell = ref({}) // Format: { "1-BATX": ["09:00", "11:30"], ... }

const {
  alliberamentsPerNivell,
  datesPerNivellModel,
  sincronitzarDatesGlobals,
  onDatesChange,
  getDatesPerNivellOrdenades,
  formatDataCurta,
  isAlliberat,
  isIniciExamen,
  toggleAlliberat,
  toggleIniciExamen,
  menuFila,
  menuColumna,
  menuFilaItems,
  menuColumnaItems,
  mostrarMenuFila,
  mostrarMenuColumna,
} = useAlliberamentsPerNivell({
  t,
  locale,
  genConfig,
  config,
  selectedDates,
  configReady,
  scheduleConfigSave,
  llistaHoresDisponibles,
  formatDateLocal,
  parseIsoLocal: _parseIsoLocal,
  isSameDay,
})

// Model per al MultiSelect d'hores per nivell (mostra buit si usa globals)
const horesPerNivellModel = computed(() => {
  const result = {}
  for (const nivell of (genConfig.value?.nivells_actius || [])) {
    result[nivell] = horesPerNivell.value[nivell] || []
  }
  return result
})

// Hores úniques per la graella global (ordenades segons l'ordre del XML)
const horesGraella = computed(() => {
  const seleccionades = new Set(genConfigHoresArray.value || [])
  return llistaHoresDisponibles.value.filter(h => seleccionades.has(h))
})
const {
  getHoresGraellaPerNivell,
  onHoresNivellChange,
  resetHoresNivell,
  isSlotEnabledPerNivell,
  toggleNivellSlot,
  resetNivellSlots,
  serialitzarSlotsValidsPerNivell,
} = useSchedulerSlotsConfig({
  horesPerNivell,
  horesPerNivellModel,
  slotsValidsPerNivell,
  horesGraella,
  llistaHoresDisponibles,
  diesSetmana,
})

const imprimirAnalisi = () => {
  window.print()
}

const imprimirHorari = async () => {
  const prevMode = modeEdicio.value
  if (prevMode) modeEdicio.value = false
  await nextTick()
  window.print()
  if (prevMode) {
    setTimeout(() => { modeEdicio.value = true }, 0)
  }
}

const perSessioParsed = computed(() => parsePerSessioReport(analisiResult.value?.per_sessio))
const perSlotsParsed = computed(() => parsePerSlotsReport(analisiResult.value?.per_slots))
const professorsSlotParsed = computed(() => parseProfessorsSlotReport(analisiResult.value?.professors_slot))

const aplicarRestriccions = (r) => {
  const dures = r.restriccions_dures || {}

  const profMap = dures.professors_limit_dies_especifics || {}
  restriccionsProfessors.value = Object.entries(profMap)
    .filter(([professor]) => !String(professor).startsWith('_pes_'))
    .map(([professor, data]) => ({
      id: buildId(),
      professor,
      assignatures: data?.assignatures || [],
      dies: data?.dies_restringits || [],
      max_examens: data?.max_examens ?? 0,
      pes: data?.pes_penalitzacio ?? 0
    }))

  professorsHorariEstricte.value = Array.isArray(dures.professors_horari_estricte) ? [...dures.professors_horari_estricte] : []

  const diesFix = dures.assignatures_dia_fix || {}
  const horesFix = dures.assignatures_hora_fix || {}
  const claus = new Set(
    [...Object.keys(diesFix), ...Object.keys(horesFix)].filter((clau) => !String(clau).startsWith('_pes_'))
  )
  const entresFixar = Array.from(claus).map((clau) => ({
    id: buildId(),
    tipus: 'fixar',
    assignatures: [clau],
    dia: diesFix[clau] || '',
    hora: horesFix[clau] || '',
    teDia: !!diesFix[clau],
    teHora: !!horesFix[clau]
  }))
  const entresProhibir = (dures.assignatures_slot_prohibit || []).map((p) => ({
    id: buildId(),
    tipus: 'prohibir',
    assignatures: p.assignatures || [],
    dia: p.dia || '',
    hora: p.hora || '',
    teDia: !!p.dia,
    teHora: !!p.hora
  }))
  restriccionsDiesHores.value = [...entresFixar, ...entresProhibir]

  const incompat = dures.no_mateix_slot || {}
  restriccionsIncompatibilitats.value = Object.entries(incompat)
    .filter(([nom]) => !String(nom).startsWith('_pes_'))
    .map(([nom, assignatures]) => {
      const pesRaw = incompat[`_pes_${nom}`]
      const pes = Array.isArray(pesRaw) ? (pesRaw[0] ?? 100) : (pesRaw ?? 100)
      return ({
        id: buildId(),
        nom,
        assignatures: Array.isArray(assignatures) ? assignatures : [assignatures].filter(Boolean),
        pes
      })
    })

  const mateixSlot = Array.isArray(dures.mateix_slot) ? dures.mateix_slot : []
  restriccionsMateixSlot.value = mateixSlot.map((item, idx) => {
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      return {
        id: buildId(),
        nom: item.nom || t('scheduler.view.defaults.groupName', { index: idx + 1 }),
        assignatures: Array.isArray(item.assignatures) ? item.assignatures : []
      }
    }
    return {
      id: buildId(),
      nom: t('scheduler.view.defaults.groupName', { index: idx + 1 }),
      assignatures: Array.isArray(item) ? item : [item].filter(Boolean)
    }
  })

  const prefs = []
  const prefMateix = r.preferencies?.mateix_dia || []
  const prefDif = r.preferencies?.dies_diferents || []
  const prefSlot = r.preferencies?.mateix_slot || []
  prefMateix.forEach(item => prefs.push({ id: buildId(), tipus: 'mateix_dia', assignatures: item.assignatures || [], pes: item.pes ?? 50 }))
  prefDif.forEach(item => prefs.push({ id: buildId(), tipus: 'dies_diferents', assignatures: item.assignatures || [], pes: item.pes ?? 75 }))
  prefSlot.forEach(item => prefs.push({ id: buildId(), tipus: 'mateix_slot', assignatures: item.assignatures || [], pes: item.pes ?? 100 }))

  const noMateixDia = dures.no_mateix_dia || []
  noMateixDia.forEach(item => {
    const assignatures = Array.isArray(item) ? item : [item].filter(Boolean)
    prefs.push({ id: buildId(), tipus: 'no_mateix_dia', assignatures, pes: 100 })  // 100% = obligatori
  })

  restriccionsPreferencies.value = prefs
  preferencies.value = prefs.map((item, idx) => ({ ...item, __id: `${item.tipus}-${idx}` }))

  const slotsValidsData = dures.slots_valids_per_nivell || {}
  const perNivell = {}
  Object.entries(slotsValidsData).forEach(([nivell, perDia]) => {
    const set = new Set()
    Object.entries(perDia || {}).forEach(([dia, hores]) => {
      (hores || []).forEach((hora) => set.add(`${dia}-${hora}`))
    })
    perNivell[nivell] = set
  })
  slotsValidsPerNivell.value = perNivell

  // Nota: combinacions permeses i dies exclosos es gestionaran fora d'aquest flux simplificat.
}

// Serialitzar alliberaments per enviar al backend (dates a string YYYY-MM-DD local)
const serializeAlliberaments = () => {
  const result = {}
  for (const [nivell, data] of Object.entries(alliberamentsPerNivell.value || {})) {
    result[nivell] = {
      durada: data.durada || 1,
      dates: (data.dates || []).map(d => formatDateLocal(d)).filter(d => d !== null),
      config: data.config || {}
    }
  }
  return result
}

const obrirDialogDurada = () => {
  editantDuradaId.value = null
  formulariDurada.value = { nom: '', sessions: [], durada: config.value?.durada_titular || 1, durada_examen: duradaExamen.value }
  mostrarDialogDurada.value = true
}

const obrirEditarDuradaGrup = (grup) => {
  editantDuradaId.value = grup.id
  formulariDurada.value = { nom: grup.nom || '', sessions: [...(grup.assignatures || [])], durada: grup.durada || 1, durada_examen: grup.durada_examen ?? duradaExamen.value }
  mostrarDialogDurada.value = true
}

const desarDialogDurada = () => {
  const { nom, sessions, durada, durada_examen } = formulariDurada.value
  if (editantDuradaId.value !== null) {
    const idx = duradesGrups.value.findIndex(g => g.id === editantDuradaId.value)
    if (idx !== -1) {
      duradesGrups.value[idx] = { ...duradesGrups.value[idx], nom, assignatures: sessions, durada, durada_examen }
    }
  } else {
    duradesGrups.value.push({ id: Date.now(), nom, assignatures: sessions, durada, durada_examen })
  }
  mostrarDialogDurada.value = false
  scheduleConfigSave()
}

const eliminarDuradaGrup = (id) => {
  duradesGrups.value = duradesGrups.value.filter(g => g.id !== id)
  scheduleConfigSave()
}

const desarMotorConfig = async (opts = {}) => {
  if (!config.value) return
  const { silent = false } = opts || {}
  try {
    sincronitzarDatesGlobals()
    // Desar hores tal qual (format XML) + hores per nivell + alliberaments + durades per grups
    await axios.put('/api/scheduler/config', {
      durada_titular: config.value.durada_titular,
      durada_examen: duradaExamen.value,
      durades_grups: duradesGrups.value.map(({ id, ...rest }) => rest),
      nivells_actius: genConfig.value.nivells_actius,
      alliberaments_per_nivell: serializeAlliberaments()
    })
    await desarDates()
    if (!silent) {
      toast.add({ severity: 'success', summary: t('scheduler.view.messages.configSaved') })
    }
  } catch (e) { console.error(e) }
}

function scheduleConfigSave() {
  if (!configReady.value) return
  if (configSaveTimer) clearTimeout(configSaveTimer)
  if (configSaveIdleId && typeof window !== 'undefined' && typeof window.cancelIdleCallback === 'function') {
    window.cancelIdleCallback(configSaveIdleId)
    configSaveIdleId = null
  }
  configSaveTimer = setTimeout(() => {
    configSaveTimer = null
    const runSave = () => {
      configSaveIdleId = null
      desarMotorConfig({ silent: true })
    }
    if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
      configSaveIdleId = window.requestIdleCallback(runSave, { timeout: 800 })
      return
    }
    runSave()
  }, 400)
}

const flushPendingConfigSave = async () => {
  if (!configReady.value) return
  if (configSaveTimer) {
    clearTimeout(configSaveTimer)
    configSaveTimer = null
  }
  if (configSaveIdleId && typeof window !== 'undefined' && typeof window.cancelIdleCallback === 'function') {
    window.cancelIdleCallback(configSaveIdleId)
    configSaveIdleId = null
  }
  await desarMotorConfig({ silent: true })
}

const desarDates = async () => {
  try {
    const dates = selectedDates.value.map(formatLocalDate)
    await axios.put('/api/scheduler/dates', { selected_dates: dates })
  } catch (e) {
    console.error(e)
  }
}

// Ref indirecta per desarTotAlBackend (es resol després de useSchedulerRestrictions)
const _desarTotAlBackendRef = ref(null)

const {
  carregarDades,
  carregarSessions,
  onNivellsChange,
  generarHorari,
  recalcularCostVisualitzacio,
  analitzarDisponibilitat,
} = useSchedulerApi({
  t,
  toast,
  loading,
  generating,
  analisiLoading,
  analisiResult,
  result,
  status,
  config,
  configReady,
  motorsMetadata,
  genConfig,
  genConfigHoresArray,
  selectedDates,
  llistaHoresDisponibles,
  llistaAssignatures,
  llistaProfessors,
  llistaGrups,
  llistaSessions,
  horesPerNivell,
  alliberamentsPerNivell,
  duradesGrups,
  duradaExamen,
  costosProfessors,
  pesos,
  intentsLog,
  incompatibilitats,
  incompatErrorMsg,
  mostrarDialogIncompat,
  mostrarDialogIntents,
  pasActiu,
  getDataReferenciaScheduler: () => dataReferenciaScheduler.value,
  aplicarDefaultsMotor,
  sincronitzarDatesGlobals,
  aplicarRestriccions,
  serializeAlliberaments,
  desarMotorConfig,
  flushPendingConfigSave,
  desarTotAlBackend: (...args) => _desarTotAlBackendRef.value?.(...args),
  formatLocalDate,
})

const {
  mostrarDialogProfessor,
  professorEditantId,
  formulariProfessor,
  mostrarDialogDiaHora,
  diaHoraEditantId,
  formulariDiaHora,
  mostrarDialogPreferenciaDia,
  preferenciaEditantId,
  formulariPreferencia,
  tipusPreferenciaDia,
  mostrarDialogIncompatibilitat,
  incompatEditantId,
  formulariIncompat,
  mostrarDialogAgrupacio,
  agrupacioEditantId,
  formulariAgrupacio,
  mostrarDialogCostProfessor,
  costProfessorEditantId,
  formulariCostProfessor,
  filtreNivellAgrupacio,
  nivellsFiltreOptions,
  sessionsFiltrades,
  agrupacionsFiltrades,
  sessionsSoltes,
  obrirDialogProfessor,
  desarDialogProfessor,
  obrirDialogDiaHora,
  desarDialogDiaHora,
  obrirDialogPreferenciaDia,
  desarDialogPreferenciaDia,
  obrirDialogIncompatibilitat,
  desarDialogIncompatibilitat,
  obrirDialogAgrupacio,
  desarDialogAgrupacio,
  eliminarAgrupacio,
  obrirDialogCostProfessor,
  desarDialogCostProfessor,
  eliminarCostProfessor,
  desarTotAlBackend,
} = useSchedulerRestrictions({
  t,
  toast,
  config,
  genConfig,
  llistaSessions,
  llistaProfessors,
  restriccionsProfessors,
  restriccionsDiesHores,
  restriccionsPreferencies,
  restriccionsIncompatibilitats,
  restriccionsMateixSlot,
  professorsHorariEstricte,
  costosProfessors,
  pesos,
  savingRestr,
  flushPendingConfigSave,
  desarDates,
  serialitzarSlotsValidsPerNivell,
  buildId,
  extreuNivell: _extreuNivell,
})
_desarTotAlBackendRef.value = desarTotAlBackend

const showSessioTitle = (sessio) => {
  if (!sessio?.nom) return false
  if (!Array.isArray(sessio.examens) || sessio.examens.length !== 1) return true
  const sessioNom = normalizeText(sessio.nom)
  const examNom = normalizeText(sessio.examens[0]?.assignatura || '')
  return sessioNom !== examNom
}

const formatIncidentFull = (group, incident) => formatIncidentFullRaw(group, incident, t)
const formatIncidentShort = (group, incident) => formatIncidentShortRaw(group, incident, t)

const tornarGestor = () => { window.history.pushState({}, '', '/'); window.dispatchEvent(new PopStateEvent('popstate')) }
const mostrarPublicarDialog = ref(false)
const publicarSetmanes = ref([])

const publicarVigilancies = () => {
  if (!result.value?.horari || !selectedDates.value?.length) return
  // Construir setmanes des de horarisPerSetmana: [{Dilluns: "2026-02-02", ...}, ...]
  const datesSorted = [...selectedDates.value].sort((a, b) => a - b)
  const setmanesMap = []
  let setmanaActual = null
  datesSorted.forEach(data => {
    const numSetmana = getWeekNumber(data)
    if (!setmanaActual || setmanaActual._num !== numSetmana) {
      setmanaActual = { _num: numSetmana }
      setmanesMap.push(setmanaActual)
    }
    const diaNom = data.toLocaleDateString('ca-ES', { weekday: 'long' })
    const diaNomCap = diaNom.charAt(0).toUpperCase() + diaNom.slice(1)
    setmanaActual[diaNomCap] = formatLocalDate(data)
  })
  // Netejar _num intern
  publicarSetmanes.value = setmanesMap.map(s => {
    const { _num, ...rest } = s
    return rest
  })
  mostrarPublicarDialog.value = true
}

const onPublicat = (data) => {
  toast.add({
    severity: 'success',
    summary: t('scheduler.view.messages.vigilanciesPublished', { count: data.vigilancies_creades }),
    life: 5000,
  })
}
const eliminarRestriccio = (tipus, id) => {
  if (tipus === 'professors') restriccionsProfessors.value = restriccionsProfessors.value.filter(r => r.id !== id)
  else if (tipus === 'diesHores') restriccionsDiesHores.value = restriccionsDiesHores.value.filter(r => r.id !== id)
  else if (tipus === 'incompatibilitats') restriccionsIncompatibilitats.value = restriccionsIncompatibilitats.value.filter(r => r.id !== id)
  else if (tipus === 'mateixSlot') restriccionsMateixSlot.value = restriccionsMateixSlot.value.filter(r => r.id !== id)
}

const eliminarPreferencia = (id) => {
  restriccionsPreferencies.value = restriccionsPreferencies.value.filter(r => r.id !== id)
}
const pasSeguent = () => pasActiu.value++
const pasAnterior = () => pasActiu.value--

const centerActiveStep = (behavior = 'smooth') => {
  const container = stepperContainerRef.value
  if (!container) return
  const activeItem = container.querySelector('.p-steps-item.p-highlight')
  if (!activeItem) return
  const maxScroll = container.scrollWidth - container.clientWidth
  if (maxScroll <= 0) return

  const containerRect = container.getBoundingClientRect()
  const itemRect = activeItem.getBoundingClientRect()
  const current = container.scrollLeft
  const itemCenter = current + (itemRect.left - containerRect.left) + (itemRect.width / 2)
  const target = Math.max(0, Math.min(maxScroll, itemCenter - (container.clientWidth / 2)))
  container.scrollTo({ left: target, behavior })
}

watch(pasActiu, async () => {
  await nextTick()
  requestAnimationFrame(() => centerActiveStep('smooth'))
})

const onStepperResize = () => {
  centerActiveStep('auto')
}
const dataReferenciaScheduler = computed(() => {
  if (!selectedDates.value?.length) return null
  const datesSorted = [...selectedDates.value].sort((a, b) => a - b)
  const d = datesSorted[0]
  if (d instanceof Date) {
    return d.toISOString().split('T')[0]
  }
  return null
})

const {
  incidenciesAgrupades,
  logsEnllacos,
  logsIncidencies,
  incidenciesCount,
  incidenciesStats,
  bestIntent,
  horesExamenConfig,
  getSlotPerHora,
  horarisPerSetmana,
  getSessionsPerNivell,
  onHorariActualitzat,
  onCostChanged,
} = useSchedulerResults({
  t,
  locale,
  toast,
  result,
  selectedDates,
  llistaHoresDisponibles,
  alliberamentsPerNivell,
  duradesGrups,
  duradaExamen,
  config,
  intentsLog,
  diesSetmana,
  getWeekNumber,
  getDayLabel,
})
const {
  getAvisosExamen,
  getEnllacosExamen,
  getAvisosIconsExamen,
  getAvisosTitleExamen,
  getSessioClass,
  getIncidentIcon,
  getNivellClass,
  incidenciesDetallades,
} = useSchedulerIncidencies({
  t,
  logsIncidencies,
  logsEnllacos,
  result,
})

onMounted(() => {
  carregarDades()
  nextTick(() => requestAnimationFrame(() => centerActiveStep('auto')))
  window.addEventListener('resize', onStepperResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onStepperResize)
})
</script>

<style src="./scheduler/SchedulerView.css"></style>
