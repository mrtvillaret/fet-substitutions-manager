import axios from 'axios'

const parseAlliberamentsPerNivell = (raw) => {
  const parsed = {}
  for (const [nivell, data] of Object.entries(raw || {})) {
    const dates = (data.dates || [])
      .filter((date) => typeof date === 'string' && date.length === 10)
      .map((date) => {
        const parts = date.split('-')
        return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10))
      })
      .filter((date) => !isNaN(date.getTime()))
    parsed[nivell] = {
      durada: data.durada || 1,
      config: data.config || {},
      dates,
    }
  }
  return parsed
}

const buildDiesUtilitzar = (sortedDates) => {
  const diesUtilitzar = []
  const diesSet = new Set()
  sortedDates.forEach((date) => {
    const dia = date.toLocaleDateString('ca-ES', { weekday: 'long' })
    const diaFormat = dia.charAt(0).toUpperCase() + dia.slice(1)
    if (!diesSet.has(diaFormat)) {
      diesSet.add(diaFormat)
      diesUtilitzar.push(diaFormat)
    }
  })
  return diesUtilitzar
}

const normalizeIntents = (rawIntents, maxSessions) => {
  let bestSoFar = null
  return (rawIntents || []).map((it, idx) => {
    const cost = it.cost_total ?? it.cost ?? 0
    const totalSessions = it.total_sessions ?? it.sessions ?? it.sess ?? it.total ?? null
    const validFull = (it.valid !== false) && (maxSessions === null || totalSessions === maxSessions)
    if (validFull) {
      bestSoFar = bestSoFar === null ? cost : Math.min(bestSoFar, cost)
    }
    return {
      ...it,
      intent: it.intent ?? idx + 1,
      cost_total: cost,
      best_so_far: it.best_so_far ?? bestSoFar,
      total_sessions: totalSessions,
      total_substitucions: it.total_substitucions ?? it.substitucions ?? it.subst ?? null,
      professors_abans: it.professors_abans ?? it.abans ?? null,
      professors_despres: it.professors_despres ?? it.despres ?? null,
      valid_full: validFull,
      is_best: it.is_best ?? (validFull && cost === bestSoFar)
    }
  })
}

export const useSchedulerApi = ({
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
  getDataReferenciaScheduler,
  aplicarDefaultsMotor,
  sincronitzarDatesGlobals,
  aplicarRestriccions,
  serializeAlliberaments,
  desarMotorConfig,
  flushPendingConfigSave,
  desarTotAlBackend,
  formatLocalDate,
}) => {
  const carregarSessions = async () => {
    if (!genConfig.value.nivells_actius.length) return
    try {
      const nivells = genConfig.value.nivells_actius.join(',')
      const response = await axios.get(`/api/scheduler/sessions-info?nivells=${nivells}`)
      llistaSessions.value = response.data || []
    } catch (error) {
      console.error(error)
    }
  }

  const carregarDades = async () => {
    loading.value = true
    try {
      const [st, cfg, dt, re, act, pr, gr, hr, mt, cp] = await Promise.all([
        axios.get('/api/scheduler/status'),
        axios.get('/api/scheduler/config'),
        axios.get('/api/scheduler/dates'),
        axios.get('/api/scheduler/restriccions'),
        axios.get('/api/scheduler/assignatures-actives'),
        axios.get('/api/professors'),
        axios.get('/api/horari/grups/detectar'),
        axios.get('/api/hores'),
        axios.get('/api/scheduler/motors').catch(() => ({ data: { motors: [] } })),
        axios.get('/api/scheduler/costos-professors').catch(() => ({ data: { globals: {}, individuals: {} } })),
      ])

      status.value = st.data
      config.value = cfg.data

      if (mt.data?.motors?.length) {
        motorsMetadata.value = mt.data.motors
        aplicarDefaultsMotor(genConfig.value.motor)
      }

      llistaHoresDisponibles.value = [...new Set(hr.data?.hores || [])]
      genConfigHoresArray.value = config.value?.hores_examen || []
      selectedDates.value = (dt.data?.selected_dates || []).map((date) => new Date(`${date}T00:00:00`))

      genConfig.value.nivells_actius = config.value?.nivells_seleccionats || []
      if (!genConfig.value.nivells_actius.length && config.value?.nivells) {
        genConfig.value.nivells_actius = config.value.nivells.filter((n) => n.includes('BAC') || n.includes('BAT')).slice(0, 2)
      }

      horesPerNivell.value = config.value?.hores_per_nivell || {}
      alliberamentsPerNivell.value = parseAlliberamentsPerNivell(config.value?.alliberaments_per_nivell || {})
      duradesGrups.value = (config.value?.durades_grups || []).map(g => ({ ...g, durada_examen: g.durada_examen ?? g.durada ?? 1, id: Date.now() + Math.random() }))
      duradaExamen.value = config.value?.durada_examen ?? config.value?.durada_titular ?? 1
      sincronitzarDatesGlobals()

      llistaAssignatures.value = act.data || []
      llistaProfessors.value = pr.data.professors || []
      llistaGrups.value = (gr.data.grups_raw || []).map((g) => ({ nom: g, codi: g }))
      await carregarSessions()

      const restriccions = re.data?.restriccions || {}
      aplicarRestriccions(restriccions)
      if (restriccions.pesos_optimitzacio) {
        const filtrats = {}
        for (const key of Object.keys(pesos.value)) {
          if (restriccions.pesos_optimitzacio[key] !== undefined) filtrats[key] = restriccions.pesos_optimitzacio[key]
        }
        pesos.value = { ...pesos.value, ...filtrats }
      }

      if (cp?.data) {
        const globals = cp.data?.globals || {}
        const individuals = cp.data?.individuals || {}
        costosProfessors.value = {
          globals: { ...costosProfessors.value.globals, ...globals },
          individuals: { ...individuals }
        }
      }

      configReady.value = true
    } catch (error) {
      toast.add({ severity: 'error', summary: t('common.error') })
    } finally {
      loading.value = false
    }
  }

  const onNivellsChange = async () => {
    sincronitzarDatesGlobals()
    await carregarSessions()
    await desarMotorConfig()
  }

  const recalcularCostVisualitzacio = async () => {
    if (!result.value?.horari?.dies?.length) return
    try {
      const horariPerEnviar = JSON.parse(JSON.stringify(result.value.horari))
      for (const dia of horariPerEnviar.dies || []) {
        for (const slot of dia.sessions || []) {
          delete slot._items
        }
      }
      const { data } = await axios.post('/api/scheduler/recalcular-cost', {
        horari: horariPerEnviar,
        data_referencia: getDataReferenciaScheduler(),
        selected_dates: selectedDates.value.map(formatLocalDate)
      })
      result.value.horari.metadata = result.value.horari.metadata || {}
      result.value.horari.metadata.cost_total = data.cost_total
      result.value.horari.metadata.logs = data.logs || []
      result.value.horari.metadata.total_substitucions = data.stats?.total_substitucions || 0
      result.value.horari.metadata.professors_abans = data.stats?.professors_abans || 0
      result.value.horari.metadata.professors_despres = data.stats?.professors_despres || 0
      result.value.horari.metadata.professors_no_treballa = data.stats?.professors_no_treballa || 0
    } catch (error) {
      // Silenciem errors per no bloquejar la UI
    }
  }

  const generarHorari = async () => {
    if (!selectedDates.value.length) {
      pasActiu.value = 0
      return
    }
    generating.value = true
    result.value = null
    try {
      await desarTotAlBackend({ silent: true })
      const dSorted = [...selectedDates.value].sort((a, b) => a - b)
      const payload = {
        data_inici: formatLocalDate(dSorted[0]),
        data_final: formatLocalDate(dSorted[dSorted.length - 1]),
        selected_dates: dSorted.map(formatLocalDate),
        dies_utilitzar: buildDiesUtilitzar(dSorted),
        ...genConfig.value
      }
      const response = await axios.post('/api/scheduler/generate', payload, { timeout: 300000 })
      result.value = response.data

      const meta = response.data?.horari?.metadata
      if (meta?.viable === false) {
        const errorMsg = meta?.error || t('scheduler.dialogs.incompatibilities.defaultMessage')
        incompatibilitats.value = meta?.incompatibilitats || []
        incompatErrorMsg.value = errorMsg
        mostrarDialogIncompat.value = true
        if (!incompatibilitats.value.length) {
          const slots = meta?.slots_disponibles || '?'
          const items = meta?.items_necessaris || '?'
          toast.add({
            severity: 'warn',
            summary: t('scheduler.view.messages.notViable'),
            detail: t('scheduler.view.messages.notViableDetail', { message: errorMsg, items, slots }),
            life: 10000
          })
        }
      } else {
        const rawIntents = result.value?.horari?.metadata?.intents || []
        const maxSessions = result.value?.horari?.metadata?.total_sessions ?? null
        intentsLog.value = normalizeIntents(rawIntents, maxSessions)
        if (intentsLog.value.length) mostrarDialogIntents.value = true
      }

      if (meta?.viable !== false) {
        await recalcularCostVisualitzacio()
      }
    } catch (error) {
      toast.add({ severity: 'error', summary: t('common.error') })
    } finally {
      generating.value = false
    }
  }

  const analitzarDisponibilitat = async () => {
    if (!selectedDates.value.length) {
      pasActiu.value = 0
      return
    }
    analisiLoading.value = true
    analisiResult.value = null
    try {
      const dSorted = [...selectedDates.value].sort((a, b) => a - b)
      const payload = {
        data_inici: formatLocalDate(dSorted[0]),
        data_final: formatLocalDate(dSorted[dSorted.length - 1]),
        dies_utilitzar: buildDiesUtilitzar(dSorted),
        nivells_actius: genConfig.value.nivells_actius
      }
      const response = await axios.post('/api/scheduler/analisi', payload, { timeout: 300000 })
      analisiResult.value = response.data
    } catch (error) {
      toast.add({ severity: 'error', summary: t('common.error') })
    } finally {
      analisiLoading.value = false
    }
  }

  return {
    carregarDades,
    carregarSessions,
    onNivellsChange,
    generarHorari,
    recalcularCostVisualitzacio,
    analitzarDisponibilitat,
  }
}
