import { tradueixMissatge } from './missatges.js'
import { computed } from 'vue'

import { esCritica, esDeLExamen, esEnllac, esIncidencia, esZonaExamen, iconaIncidencia, textCurtIncidencia, textIncidencia } from './incidencies.js'

// Hores comparables («09:00» i «9:00» són la mateixa)
const hora = (h) => String(h || '').replace(/^0(\d:)/, '$1')

// Les incidències del calendari: pel titular de l'examen, la data i l'hora de la fila
export function useSchedulerIncidencies({ t, logsIncidencies, logsEnllacos, result }) {
  const deLExamen = (llista, ex, dia, horaFila) => (llista || []).filter((m) => esIncidencia(m) && esDeLExamen(
    { ...m, params: { ...m.params, hora: hora(m.params?.hora) } },
    ex?.titular,
    { dia: dia?.dia, data: dia?.dataIso, hora: hora(horaFila) }
  ))

  const getAvisosExamen = (ex, dia, horaFila) => deLExamen(logsIncidencies.value, ex, dia, horaFila)
  const getEnllacosExamen = (ex, dia, horaFila) => deLExamen(logsEnllacos.value, ex, dia, horaFila)

  // La zona d'examen (sense cost), l'última
  const ORDRE = ['🚨', '🕐', '🚫', '🔗', '⚠️', '⛔', '👁️']

  const getAvisosIconsExamen = (ex, dia, horaFila) => {
    const icones = new Set([...getAvisosExamen(ex, dia, horaFila), ...getEnllacosExamen(ex, dia, horaFila)].map(iconaIncidencia))
    return ORDRE.filter((e) => icones.has(e))
  }

  // Primer els avisos amb cost, després els enllaços i, al final, la zona d'examen
  const getAvisosTitleExamen = (ex, dia, horaFila) => {
    const avisos = getAvisosExamen(ex, dia, horaFila)
    return [...avisos.filter((m) => !esZonaExamen(m)), ...getEnllacosExamen(ex, dia, horaFila), ...avisos.filter(esZonaExamen)]
      .map((m) => textIncidencia(m, t))
      .join('\n')
  }

  const classe = (examens, dia, horaFila, prefix) => {
    const avisos = examens.flatMap((ex) => getAvisosExamen(ex, dia, horaFila)).filter((m) => !esEnllac(m))
    if (avisos.some(esCritica)) return `${prefix}-with-subs`
    if (avisos.some((m) => !esZonaExamen(m))) return `${prefix}-with-warnings`
    return avisos.length ? `${prefix}-with-zona-examen` : ''
  }

  const getSessioClass = (s, dia, horaFila) => classe(s.examens || [], dia, horaFila, 'sessio')
  const getNivellClass = (nivellInfo, dia, horaFila) => classe(nivellInfo.examens || [], dia, horaFila, 'nivell')

  const getIncidentIcon = (m) => iconaIncidencia(m)

  const incidenciesDetallades = computed(() => {
    const meta = result.value?.horari?.metadata || {}
    const l = []
    if (meta.professors_slots_duplicats) {
      meta.professors_slots_duplicats.forEach((d) => l.push(`❌ SIMULTANI: ${d.professor} a ${d.dia} ${d.hora}`))
    }
    if (meta.logs) l.push(...meta.logs.map((m) => (esIncidencia(m) ? textCurtIncidencia(m, t) : tradueixMissatge(m, t))))
    return l
  })

  return {
    getAvisosExamen,
    getEnllacosExamen,
    getAvisosIconsExamen,
    getAvisosTitleExamen,
    getSessioClass,
    getIncidentIcon,
    getNivellClass,
    incidenciesDetallades,
  }
}
