import { computed, ref } from 'vue'
import axios from 'axios'

export const useSchedulerRestrictions = ({
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
  extreuNivell,
}) => {
  const ALL_LEVELS_FILTER = '__all__'

  const mostrarDialogProfessor = ref(false)
  const professorEditantId = ref(null)
  const formulariProfessor = ref({ professor: '', assignatures: [], dies: [], max_examens: 1, pes: 50 })

  const mostrarDialogDiaHora = ref(false)
  const diaHoraEditantId = ref(null)
  const formulariDiaHora = ref({ tipus: 'fixar', assignatures: [], dia: '', hora: '', teDia: false, teHora: false })

  const mostrarDialogPreferenciaDia = ref(false)
  const preferenciaEditantId = ref(null)
  const formulariPreferencia = ref({ assignatures: [], tipus: 'mateix_dia', pes: 50 })
  const tipusPreferenciaDia = computed(() => ([
    { label: `📅 ${t('scheduler.steps.restrictions.dayPreferences.type.sameDay')}`, value: 'mateix_dia' },
    { label: `↔️ ${t('scheduler.steps.restrictions.dayPreferences.type.differentDays')}`, value: 'dies_diferents' },
    { label: `🔗 ${t('scheduler.steps.restrictions.dayPreferences.type.sameSlot')}`, value: 'mateix_slot' }
  ]))

  const mostrarDialogIncompatibilitat = ref(false)
  const incompatEditantId = ref(null)
  const formulariIncompat = ref({ nom: '', assignatures: [], pes: 100 })

  const mostrarDialogAgrupacio = ref(false)
  const agrupacioEditantId = ref(null)
  const formulariAgrupacio = ref({ nom: '', assignatures: [] })

  const mostrarDialogCostProfessor = ref(false)
  const costProfessorEditantId = ref(null)
  const formulariCostProfessor = ref({ professor: '', substitucio: 0, abans_jornada: 0, despres_jornada: 0, no_treballa_dia: 0 })

  const filtreNivellAgrupacio = ref(ALL_LEVELS_FILTER)

  const nivellsFiltreOptions = computed(() => {
    const base = genConfig.value?.nivells_actius?.length
      ? genConfig.value.nivells_actius
      : (config.value?.nivells || [])
    return [
      { label: t('common.all'), value: ALL_LEVELS_FILTER },
      ...Array.from(new Set(base || [])).map((level) => ({ label: level, value: level }))
    ]
  })

  const sessionsFiltrades = computed(() => {
    if (filtreNivellAgrupacio.value === ALL_LEVELS_FILTER) return llistaSessions.value
    const nivell = filtreNivellAgrupacio.value
    return llistaSessions.value.filter((session) => extreuNivell(session) === nivell)
  })

  const agrupacionsFiltrades = computed(() => {
    if (filtreNivellAgrupacio.value === ALL_LEVELS_FILTER) return restriccionsMateixSlot.value
    const nivell = filtreNivellAgrupacio.value
    return restriccionsMateixSlot.value.filter((group) =>
      (group.assignatures || []).some((subject) => extreuNivell(subject) === nivell)
    )
  })

  const sessionsSoltes = computed(() => {
    const agrupades = new Set()
    restriccionsMateixSlot.value.forEach((group) => (group.assignatures || []).forEach((subject) => agrupades.add(subject)))
    return sessionsFiltrades.value.filter((session) => !agrupades.has(session))
  })

  const resetProfessorForm = () => {
    formulariProfessor.value = { professor: '', assignatures: [], dies: [], max_examens: 1, pes: 50 }
    professorEditantId.value = null
  }

  const obrirDialogProfessor = (item = null) => {
    if (item) {
      professorEditantId.value = item.id
      formulariProfessor.value = {
        professor: item.professor,
        assignatures: [...(item.assignatures || [])],
        dies: [...(item.dies || [])],
        max_examens: item.max_examens ?? 1,
        pes: item.pes ?? 50
      }
    } else resetProfessorForm()
    mostrarDialogProfessor.value = true
  }

  const desarDialogProfessor = () => {
    const form = formulariProfessor.value
    if (!form.professor) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectTeacher') })
    if (!form.assignatures?.length) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectSubjects') })
    const payload = {
      id: professorEditantId.value || buildId(),
      professor: form.professor,
      assignatures: form.assignatures,
      dies: form.dies,
      max_examens: form.max_examens ?? 0,
      pes: form.pes ?? 0
    }
    if (professorEditantId.value) {
      restriccionsProfessors.value = restriccionsProfessors.value.map((row) => row.id === professorEditantId.value ? payload : row)
    } else {
      restriccionsProfessors.value.push(payload)
    }
    mostrarDialogProfessor.value = false
    resetProfessorForm()
  }

  const resetDiaHoraForm = () => {
    formulariDiaHora.value = { tipus: 'fixar', assignatures: [], dia: '', hora: '', teDia: false, teHora: false }
    diaHoraEditantId.value = null
  }

  const obrirDialogDiaHora = (item = null) => {
    if (item) {
      diaHoraEditantId.value = item.id
      formulariDiaHora.value = {
        tipus: item.tipus || 'fixar',
        assignatures: [...(item.assignatures || [])],
        dia: item.dia || '',
        hora: item.hora || '',
        teDia: !!item.dia,
        teHora: !!item.hora
      }
    } else resetDiaHoraForm()
    mostrarDialogDiaHora.value = true
  }

  const desarDialogDiaHora = () => {
    const form = formulariDiaHora.value
    if (!form.assignatures?.length) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectSubject') })
    if (!form.teDia && !form.teHora) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectDayOrHour') })
    if (form.teDia && !form.dia) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectDay') })
    if (form.teHora && !form.hora) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectHour') })
    const payload = {
      id: diaHoraEditantId.value || buildId(),
      tipus: form.tipus || 'fixar',
      assignatures: form.assignatures,
      dia: form.teDia ? form.dia : '',
      hora: form.teHora ? form.hora : '',
      teDia: form.teDia,
      teHora: form.teHora
    }
    if (diaHoraEditantId.value) {
      restriccionsDiesHores.value = restriccionsDiesHores.value.map((row) => row.id === diaHoraEditantId.value ? payload : row)
    } else {
      restriccionsDiesHores.value.push(payload)
    }
    mostrarDialogDiaHora.value = false
    resetDiaHoraForm()
  }

  const resetPreferenciaForm = () => {
    formulariPreferencia.value = { assignatures: [], tipus: 'dies_diferents', pes: 75 }
    preferenciaEditantId.value = null
  }

  const obrirDialogPreferenciaDia = (item = null) => {
    if (item) {
      preferenciaEditantId.value = item.id
      formulariPreferencia.value = {
        assignatures: [...(item.assignatures || [])],
        tipus: item.tipus === 'no_mateix_dia' ? 'dies_diferents' : item.tipus,
        pes: item.pes ?? 0
      }
    } else resetPreferenciaForm()
    mostrarDialogPreferenciaDia.value = true
  }

  const desarDialogPreferenciaDia = () => {
    const form = formulariPreferencia.value
    if (!form.assignatures || form.assignatures.length < 2) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectAtLeastTwoSubjects') })
    const payload = {
      id: preferenciaEditantId.value || buildId(),
      assignatures: form.assignatures,
      tipus: form.tipus,
      pes: form.pes ?? 0
    }
    if (preferenciaEditantId.value) {
      restriccionsPreferencies.value = restriccionsPreferencies.value.map((row) => row.id === preferenciaEditantId.value ? payload : row)
    } else {
      restriccionsPreferencies.value.push(payload)
    }
    mostrarDialogPreferenciaDia.value = false
    resetPreferenciaForm()
  }

  const resetIncompatForm = () => {
    formulariIncompat.value = { nom: '', assignatures: [], pes: 100 }
    incompatEditantId.value = null
  }

  const obrirDialogIncompatibilitat = (item = null) => {
    if (item) {
      incompatEditantId.value = item.id
      formulariIncompat.value = { nom: item.nom, assignatures: [...(item.assignatures || [])], pes: item.pes ?? 100 }
    } else resetIncompatForm()
    mostrarDialogIncompatibilitat.value = true
  }

  const desarDialogIncompatibilitat = () => {
    const form = formulariIncompat.value
    if (!form.nom) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.writeGroupName') })
    if (!form.assignatures || form.assignatures.length < 2) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectAtLeastTwoSubjects') })
    const payload = { id: incompatEditantId.value || buildId(), nom: form.nom, assignatures: form.assignatures, pes: form.pes ?? 100 }
    if (incompatEditantId.value) {
      restriccionsIncompatibilitats.value = restriccionsIncompatibilitats.value.map((row) => row.id === incompatEditantId.value ? payload : row)
    } else {
      restriccionsIncompatibilitats.value.push(payload)
    }
    mostrarDialogIncompatibilitat.value = false
    resetIncompatForm()
  }

  const resetAgrupacioForm = () => {
    formulariAgrupacio.value = { nom: '', assignatures: [] }
    agrupacioEditantId.value = null
  }

  const obrirDialogAgrupacio = (item = null) => {
    if (item) {
      agrupacioEditantId.value = item.id
      formulariAgrupacio.value = {
        nom: item.nom || '',
        assignatures: [...(item.assignatures || [])]
      }
    } else resetAgrupacioForm()
    mostrarDialogAgrupacio.value = true
  }

  const desarDialogAgrupacio = () => {
    const form = formulariAgrupacio.value
    if (!form.assignatures || form.assignatures.length < 1) {
      return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectAtLeastOneSubject') })
    }

    const payload = {
      id: agrupacioEditantId.value || buildId(),
      nom: form.nom || t('scheduler.view.defaults.groupName', { index: restriccionsMateixSlot.value.length + 1 }),
      assignatures: form.assignatures
    }

    if (agrupacioEditantId.value) {
      restriccionsMateixSlot.value = restriccionsMateixSlot.value.map((row) => row.id === agrupacioEditantId.value ? payload : row)
    } else {
      restriccionsMateixSlot.value.push(payload)
    }

    mostrarDialogAgrupacio.value = false
    resetAgrupacioForm()
  }

  const eliminarAgrupacio = (id) => {
    restriccionsMateixSlot.value = restriccionsMateixSlot.value.filter((row) => row.id !== id)
  }

  const resetCostProfessorForm = () => {
    const globals = costosProfessors.value.globals || {}
    formulariCostProfessor.value = {
      professor: '',
      substitucio: globals.substitucio ?? 0,
      abans_jornada: globals.abans_jornada ?? 0,
      despres_jornada: globals.despres_jornada ?? 0,
      no_treballa_dia: globals.no_treballa_dia ?? 0
    }
    costProfessorEditantId.value = null
  }

  const obrirDialogCostProfessor = (item = null) => {
    const globals = costosProfessors.value.globals || {}
    if (item?.professor) {
      costProfessorEditantId.value = item.professor
      const override = costosProfessors.value.individuals?.[item.professor] || {}
      formulariCostProfessor.value = {
        professor: item.professor,
        substitucio: override.substitucio ?? item.substitucio ?? globals.substitucio ?? 0,
        abans_jornada: override.abans_jornada ?? item.abans_jornada ?? globals.abans_jornada ?? 0,
        despres_jornada: override.despres_jornada ?? item.despres_jornada ?? globals.despres_jornada ?? 0,
        no_treballa_dia: override.no_treballa_dia ?? item.no_treballa_dia ?? globals.no_treballa_dia ?? 0
      }
    } else {
      resetCostProfessorForm()
    }
    mostrarDialogCostProfessor.value = true
  }

  const desarDialogCostProfessor = () => {
    const form = formulariCostProfessor.value
    if (!form.professor) return toast.add({ severity: 'warn', summary: t('scheduler.view.validations.selectTeacher') })
    if (!costosProfessors.value.individuals) costosProfessors.value.individuals = {}
    costosProfessors.value.individuals[form.professor] = {
      substitucio: form.substitucio ?? 0,
      abans_jornada: form.abans_jornada ?? 0,
      despres_jornada: form.despres_jornada ?? 0,
      no_treballa_dia: form.no_treballa_dia ?? 0
    }
    mostrarDialogCostProfessor.value = false
    resetCostProfessorForm()
  }

  const eliminarCostProfessor = (professor) => {
    const individuals = { ...(costosProfessors.value.individuals || {}) }
    if (professor in individuals) {
      delete individuals[professor]
      costosProfessors.value.individuals = individuals
    }
  }

  const desarTotAlBackend = async (opts = {}) => {
    const { silent = false } = opts
    savingRestr.value = true
    try {
      await flushPendingConfigSave()
      await desarDates()
      const dures = {
        no_mateix_dia: [],
        no_mateix_slot: {},
        mateix_slot: [],
        assignatures_dia_fix: {},
        assignatures_hora_fix: {},
        assignatures_slot_prohibit: [],
        professors_horari_estricte: [...professorsHorariEstricte.value],
        professors_limit_dies_especifics: {},
        slots_valids_per_nivell: serialitzarSlotsValidsPerNivell(),
        combinacions_permeses: [],
        assignatures_dies_exclosos: []
      }
      const prefs = { mateix_dia: [], dies_diferents: [], mateix_slot: [] }

      restriccionsDiesHores.value.forEach((row) => {
        if (row.tipus === 'prohibir') {
          dures.assignatures_slot_prohibit.push({
            assignatures: row.assignatures || [],
            dia: row.dia || '',
            hora: row.hora || ''
          })
        } else {
          // tipus === 'fixar' (o legacy sense tipus)
          for (const ass of (row.assignatures || [])) {
            if (row.dia) dures.assignatures_dia_fix[ass] = row.dia
            if (row.hora) dures.assignatures_hora_fix[ass] = row.hora
          }
        }
      })

      restriccionsIncompatibilitats.value.forEach((row) => {
        dures.no_mateix_slot[row.nom] = row.assignatures || []
        dures.no_mateix_slot[`_pes_${row.nom}`] = row.pes ?? 100
      })

      dures.mateix_slot = restriccionsMateixSlot.value
        .map((row) => ({
          nom: row.nom || '',
          assignatures: row.assignatures || []
        }))
        .filter((row) => (row.assignatures || []).length >= 1)

      restriccionsProfessors.value.forEach((row) => {
        dures.professors_limit_dies_especifics[row.professor] = {
          assignatures: row.assignatures || [],
          dies_restringits: row.dies || [],
          max_examens: row.max_examens ?? 0,
          pes_penalitzacio: row.pes ?? 0
        }
      })

      restriccionsPreferencies.value.forEach((row) => {
        const assignatures = row.assignatures || []
        if (!assignatures.length) return
        const pes = row.pes ?? 75
        if (row.tipus === 'mateix_dia') {
          prefs.mateix_dia.push({ assignatures, pes })
          return
        }
        if (row.tipus === 'dies_diferents') {
          if (pes >= 100) dures.no_mateix_dia.push(assignatures)
          else prefs.dies_diferents.push({ assignatures, pes })
          return
        }
        if (row.tipus === 'mateix_slot') {
          prefs.mateix_slot.push({ assignatures, pes })
          return
        }
        if (row.tipus === 'no_mateix_dia') dures.no_mateix_dia.push(assignatures)
      })

      await axios.put('/api/scheduler/restriccions', {
        restriccions: {
          restriccions_dures: dures,
          preferencies: prefs,
          pesos_optimitzacio: pesos.value
        }
      })
      await axios.put('/api/scheduler/costos-professors', costosProfessors.value)
      if (!silent) toast.add({ severity: 'success', summary: t('common.saved') })
    } catch (error) {
      toast.add({ severity: 'error', summary: t('common.error') })
    } finally {
      savingRestr.value = false
    }
  }

  return {
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
  }
}
