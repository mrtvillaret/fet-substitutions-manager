import { avisosDeConfiguracio } from './missatges.js'
import { computed } from 'vue'
import { horesExamen } from './duradaExamen.js'
import { dataIso } from '../../dates'
import { comparaSegonsOrdre } from './textUtils'
import { esEnllac, esIncidencia, grupIncidencia } from './incidencies.js'

export const useSchedulerResults = ({
  t,
  locale,
  toast,
  result,
  selectedDates,
  llistaHoresDisponibles,
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
    const grups = {
      conflicts: { id: 'conflicts', titol: `🚨 ${t('scheduler.steps.results.incidents.groups.conflicts')}`, items: [], severity: 'error' },
      substitutions: { id: 'substitutions', titol: `🚨 ${t('scheduler.steps.results.incidents.groups.substitutions')}`, items: [], severity: 'error' },
      stayLate: { id: 'stayLate', titol: `🕐 ${t('scheduler.steps.results.incidents.groups.stayLate')}`, items: [], severity: 'warn' },
      arriveEarly: { id: 'arriveEarly', titol: `🕐 ${t('scheduler.steps.results.incidents.groups.arriveEarly')}`, items: [], severity: 'warn' },
      links: { id: 'links', titol: `🔗 ${t('scheduler.steps.results.incidents.groups.links')}`, items: [], severity: 'info' },
      others: { id: 'others', titol: `📋 ${t('scheduler.steps.results.incidents.groups.others')}`, items: [], severity: 'info' },
      zoneExam: { id: 'zoneExam', titol: `👁️ ${t('scheduler.steps.results.incidents.groups.zoneExam')}`, items: [], severity: 'error' }
    }

    // Els avisos de la configuració (grups sense nivell...), primer de tot a «Altres» (text)
    grups.others.items.push(...avisosDeConfiguracio(logs, t))
    // Les incidències, pel codi; la resta de línies (el progrés del motor) no ho són
    logs.filter(esIncidencia).forEach((m) => grups[grupIncidencia(m)].items.push(m))

    return Object.values(grups).filter((group) => group.items.length > 0)
  })

  const logsEnllacos = computed(() => (result.value?.horari?.metadata?.logs || []).filter(esEnllac))

  const logsIncidencies = computed(() => {
    return incidenciesAgrupades.value
      .filter((group) => group.id !== 'links')
      .flatMap((group) => group.items)
  })

  const incidenciesCount = computed(() => logsIncidencies.value.length)

  const bestIntent = computed(() => {
    const intents = intentsLog.value || []
    const valid = intents.filter((intent) => intent.valid_full)
    if (!valid.length) return null
    return valid.reduce((best, cur) => (cur.cost_total < best.cost_total ? cur : best), valid[0])
  })

  const horesExamenConfig = computed(() => llistaHoresDisponibles.value.length ? llistaHoresDisponibles.value : ['09:00', '11:30'])

  const getDuradaSessio = (nomSessio) =>
    horesExamen({
      nom: nomSessio,
      grups: duradesGrups?.value,
      generalExamen: duradaExamen?.value || config.value?.durada_examen,
      generalTitular: config.value?.durada_titular,
    })

  const getHoresOcupades = (horaInici, nomSessio) => {
    const hores = llistaHoresDisponibles.value || []
    const idx = hores.indexOf(horaInici)
    const durada = getDuradaSessio(nomSessio)
    if (idx === -1) return [horaInici]
    return hores.slice(idx, Math.min(idx + durada, hores.length))
  }

  const getSlotPerHora = (dia, hora) => {
    if (!dia?.sessions?.length) return null
    const sessions = []
    const vistos = new Set()
    dia.sessions.forEach((slot) => {
      slot.sessions_simultanees.forEach((sessio) => {
        const hores = getHoresOcupades(slot.hora, sessio?.nom)
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

        const formatIso = dataIso

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
          dataIso: data ? formatIso(data) : null,
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
    const compara = comparaSegonsOrdre(config.value?.nivells)
    return Object.values(perNivell).sort((a, b) => compara(a.nivell, b.nivell))
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

  const onCostChanged = ({ cost, desglossament, logs, stats }) => {
    if (!result.value?.horari) return
    result.value.horari.metadata = result.value.horari.metadata || {}
    result.value.horari.metadata.cost_total = cost
    if (Array.isArray(desglossament)) {
      result.value.horari.metadata.cost_desglossament = desglossament
    }
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
    bestIntent,
    horesExamenConfig,
    getSlotPerHora,
    horarisPerSetmana,
    getSessionsPerNivell,
    onHorariActualitzat,
    onCostChanged,
  }
}
