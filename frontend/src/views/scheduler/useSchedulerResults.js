import { computed } from 'vue'
import { classifyIncidentKind, INCIDENT_KINDS, extractIncidentScore, isIncidentLogLine, isLinkIncident } from './textUtils'

export const useSchedulerResults = ({
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
}) => {
  const resolveLocale = () => {
    const code = locale?.value || locale || 'ca'
    if (code === 'es') return 'es-ES'
    if (code === 'en') return 'en-GB'
    return 'ca-ES'
  }

  const incidenciesAgrupades = computed(() => {
    const logs = result.value?.horari?.metadata?.logs || []
    const filtered = logs.map((line) => line.trim()).filter(isIncidentLogLine)

    const grups = {
      conflictes: { id: 'conflicts', titol: `🚨 ${t('scheduler.steps.results.incidents.groups.conflicts')}`, items: [], severity: 'error' },
      substitucions: { id: 'substitutions', titol: `🚨 ${t('scheduler.steps.results.incidents.groups.substitutions')}`, items: [], severity: 'error' },
      quedaMes: { id: 'stayLate', titol: `🕐 ${t('scheduler.steps.results.incidents.groups.stayLate')}`, items: [], severity: 'warn' },
      arribenAbans: { id: 'arriveEarly', titol: `🕐 ${t('scheduler.steps.results.incidents.groups.arriveEarly')}`, items: [], severity: 'warn' },
      zonaExamen: { id: 'zoneExam', titol: `👁️ ${t('scheduler.steps.results.incidents.groups.zoneExam')}`, items: [], severity: 'error' },
      enllacos: { id: 'links', titol: `🔗 ${t('scheduler.steps.results.incidents.groups.links')}`, items: [], severity: 'info' },
      altres: { id: 'others', titol: `📋 ${t('scheduler.steps.results.incidents.groups.others')}`, items: [], severity: 'info' }
    }

    filtered.forEach((line) => {
      const kind = classifyIncidentKind(line)
      if (kind === INCIDENT_KINDS.conflict) grups.conflictes.items.push(line)
      else if (kind === INCIDENT_KINDS.substitution) grups.substitucions.items.push(line)
      else if (kind === INCIDENT_KINDS.stayLate) grups.quedaMes.items.push(line)
      else if (kind === INCIDENT_KINDS.arriveEarly) grups.arribenAbans.items.push(line)
      else if (kind === INCIDENT_KINDS.zonaExamen) grups.zonaExamen.items.push(line)
      else if (kind === INCIDENT_KINDS.link) grups.enllacos.items.push(line)
      else grups.altres.items.push(line)
    })

    return Object.values(grups).filter((group) => group.items.length > 0)
  })

  const logsEnllacos = computed(() => {
    const logs = result.value?.horari?.metadata?.logs || []
    return logs.map((line) => line.trim()).filter(isLinkIncident)
  })

  const logsIncidencies = computed(() => {
    return incidenciesAgrupades.value
      .filter((group) => group.id !== 'links')
      .flatMap((group) => group.items)
  })

  const incidenciesCount = computed(() => logsIncidencies.value.length)

  const incidenciesStats = computed(() => {
    const logs = logsIncidencies.value || []
    let totalScore = 0
    let substitucions = 0
    let arribenAbans = 0
    logs.forEach((log) => {
      const scoreToken = extractIncidentScore(log)
      const scoreValue = scoreToken.match(/(\d+)/)?.[1]
      if (scoreValue) totalScore += Number(scoreValue)

      const kind = classifyIncidentKind(log)
      if (kind === INCIDENT_KINDS.substitution) substitucions += 1
      if (kind === INCIDENT_KINDS.arriveEarly) arribenAbans += 1
    })
    return { totalScore, substitucions, arribenAbans }
  })

  const bestIntent = computed(() => {
    const intents = intentsLog.value || []
    const valid = intents.filter((intent) => intent.valid_full)
    if (!valid.length) return null
    return valid.reduce((best, cur) => (cur.cost_total < best.cost_total ? cur : best), valid[0])
  })

  const horesExamenConfig = computed(() => llistaHoresDisponibles.value.length ? llistaHoresDisponibles.value : ['09:00', '11:30'])

  const getDuradaSessio = (nomSessio, nivell) => {
    // 1. Buscar en duradesGrups per nom de sessió — usa durada_examen per la graella
    if (nomSessio && duradesGrups?.value?.length) {
      for (const grup of duradesGrups.value) {
        if (Array.isArray(grup.assignatures) && grup.assignatures.includes(nomSessio)) {
          return Math.max(1, Number(grup.durada_examen ?? grup.durada) || 1)
        }
      }
    }
    // 2. Fallback: durada_examen global o durada_titular
    const globalExamen = duradaExamen?.value
    const durada = Number(globalExamen || config.value?.durada_examen || config.value?.durada_titular || 1)
    return Math.max(1, durada)
  }

  // Mantenim per compatibilitat (usada externament si cal)
  const getDuradaPerNivell = (nivell) => getDuradaSessio(null, nivell)

  const getHoresOcupades = (horaInici, nivell, nomSessio) => {
    const hores = llistaHoresDisponibles.value || []
    const idx = hores.indexOf(horaInici)
    const durada = getDuradaSessio(nomSessio, nivell)
    if (idx === -1) return [horaInici]
    return hores.slice(idx, Math.min(idx + durada, hores.length))
  }

  const getSlotPerHora = (dia, hora) => {
    if (!dia?.sessions?.length) return null
    const sessions = []
    const vistos = new Set()
    dia.sessions.forEach((slot) => {
      slot.sessions_simultanees.forEach((sessio) => {
        const nivell = sessio?.curs || sessio?.nivell
        const hores = getHoresOcupades(slot.hora, nivell, sessio?.nom)
        if (!hores.includes(hora)) return
        const key = `${sessio.nom}|${sessio.curs || ''}`
        if (vistos.has(key)) return
        vistos.add(key)
        sessions.push(sessio)
      })
    })
    return sessions.length ? { sessions_simultanees: sessions } : null
  }

  const horarisPerSetmana = computed(() => {
    if (!result.value?.horari?.dies || !selectedDates.value?.length) return []

    const datesSorted = [...selectedDates.value].sort((a, b) => a - b)
    const setmanes = []
    let setmanaActual = null

    datesSorted.forEach((data) => {
      const numSetmana = getWeekNumber(data)
      if (!setmanaActual || setmanaActual.numSetmana !== numSetmana) {
        setmanaActual = { numSetmana, dates: [], diesNom: {} }
        setmanes.push(setmanaActual)
      }
      setmanaActual.dates.push(data)
      const diaNom = data.toLocaleDateString('ca-ES', { weekday: 'long' })
      const diaNomCap = diaNom.charAt(0).toUpperCase() + diaNom.slice(1)
      setmanaActual.diesNom[diaNomCap] = data
    })

    // Indexar per data ISO si disponible (suporta dies repetits entre setmanes)
    const diesAmbDades = {}
    result.value.horari.dies.forEach((day) => {
      const key = day.data || day.dia
      diesAmbDades[key] = day
    })

    const formatIso = (d) => {
      if (!d) return null
      const y = d.getFullYear()
      const m = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      return `${y}-${m}-${day}`
    }

    return setmanes.map((setmana, idx) => ({
      id: idx,
      numSetmana: setmana.numSetmana,
      dies: diesSetmana.map((diaNom) => {
        const data = setmana.diesNom[diaNom]
        const isoKey = formatIso(data) || diaNom  // primer la data ISO, fallback al nom
        return {
          dia: diaNom,
          diaLabel: getDayLabel ? getDayLabel(diaNom) : diaNom,
          data: data ? data.toLocaleDateString(resolveLocale(), { day: '2-digit', month: '2-digit' }) : null,
          sessions: diesAmbDades[isoKey]?.sessions || [],
          teExamens: !!data && !!diesAmbDades[isoKey]?.sessions?.length,
          estaSeleccionat: !!data
        }
      })
    }))
  })

  const getSessionsPerNivell = (slot) => {
    if (!slot?.sessions_simultanees) return []
    const perNivell = {}
    slot.sessions_simultanees.forEach((sessio) => {
      const nivell = sessio.curs || t('scheduler.steps.results.otherLevel')
      if (!perNivell[nivell]) {
        perNivell[nivell] = { nivell, sessions: [], examens: [] }
      }
      perNivell[nivell].sessions.push(sessio)
      if (sessio.examens) {
        sessio.examens.forEach((exam) => {
          perNivell[nivell].examens.push({ ...exam, sessioNom: sessio.nom, analisi: sessio.analisi })
        })
      }
    })
    return Object.values(perNivell).sort((a, b) => b.nivell.localeCompare(a.nivell))
  }

  const onHorariActualitzat = (nouHorari) => {
    if (result.value) {
      result.value.horari = nouHorari
      toast.add({
        severity: 'info',
        summary: t('scheduler.view.messages.scheduleUpdated'),
        detail: t('scheduler.view.messages.localChangesApplied'),
        life: 2000
      })
    }
  }

  const onCostChanged = ({ cost, logs, stats }) => {
    if (!result.value?.horari) return
    result.value.horari.metadata = result.value.horari.metadata || {}
    result.value.horari.metadata.cost_total = cost
    if (Array.isArray(logs)) {
      result.value.horari.metadata.logs = logs
    }
    if (stats) {
      result.value.horari.metadata.total_substitucions = stats.total_substitucions || 0
      result.value.horari.metadata.professors_abans = stats.professors_abans || 0
      result.value.horari.metadata.professors_despres = stats.professors_despres || 0
      result.value.horari.metadata.professors_no_treballa = stats.professors_no_treballa || 0
    }
  }

  return {
    incidenciesAgrupades,
    logsEnllacos,
    logsIncidencies,
    incidenciesCount,
    incidenciesStats,
    bestIntent,
    horesExamenConfig,
    getDuradaPerNivell,
    getHoresOcupades,
    getSlotPerHora,
    horarisPerSetmana,
    getSessionsPerNivell,
    onHorariActualitzat,
    onCostChanged,
  }
}
