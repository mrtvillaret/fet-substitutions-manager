import { computed } from 'vue'

import { normalizeText, extractHour, getAvisEmoji, getIncidentEmoji, isCriticalIncident, isZonaExamenIncident, stripIncidentDecorators, localizeIncidentText } from './textUtils'

export function useSchedulerIncidencies({ t, logsIncidencies, logsEnllacos, result }) {
  const formatWarningText = (text) => localizeIncidentText(text, t)

  const getAvisosExamen = (ex, dia, hora) => {
    const logs = logsIncidencies.value || []
    const avisos = new Set()
    const prof = normalizeText(ex?.titular || '')
    const diaNorm = normalizeText(dia)
    const horaNorm = extractHour(hora)
    if (!prof || !diaNorm || !horaNorm) return []

    logs.forEach((log) => {
      const logNorm = normalizeText(log)
      if (!logNorm.includes(prof)) return
      if (!logNorm.includes(diaNorm)) return
      // Comprovar l'hora exacta del log (el backend genera una entrada per cada hora)
      const logHour = extractHour(log)
      if (logHour !== horaNorm) return
      avisos.add(stripIncidentDecorators(log))
    })
    return Array.from(avisos)
  }

  const getEnllacosExamen = (ex, dia, hora) => {
    const logs = logsEnllacos.value || []
    const avisos = new Set()
    const prof = normalizeText(ex?.titular || '')
    const diaNorm = normalizeText(dia)
    const horaNorm = extractHour(hora)
    if (!prof || !diaNorm || !horaNorm) return []

    logs.forEach((log) => {
      const logNorm = normalizeText(log)
      if (!logNorm.includes(prof)) return
      if (!logNorm.includes(diaNorm)) return
      const logHour = extractHour(log)
      if (logHour !== horaNorm) return
      avisos.add(stripIncidentDecorators(log))
    })
    return Array.from(avisos)
  }

  const getAvisosIconsExamen = (ex, dia, hora) => {
    const avisos = getAvisosExamen(ex, dia, hora)
    const enllacos = getEnllacosExamen(ex, dia, hora)
    const order = ['🚨', '🕐', '🚫', '🔗', '👁️', '⚠️']
    const set = new Set()
    avisos.forEach((a) => set.add(getAvisEmoji(a)))
    if (enllacos.length) set.add('🔗')
    return order.filter((e) => set.has(e))
  }

  const getAvisosTitleExamen = (ex, dia, hora) => {
    const avisos = getAvisosExamen(ex, dia, hora)
    const enllacos = getEnllacosExamen(ex, dia, hora)
    return [...avisos, ...enllacos].map(formatWarningText).join('\n')
  }

  const getSessioClass = (s, dia, hora) => {
    let w = false
    let sb = false
    let ze = false
    s.examens.forEach((ex) => {
      const av = getAvisosExamen(ex, dia, hora)
      av.forEach((a) => {
        if (isCriticalIncident(a)) sb = true
        else if (isZonaExamenIncident(a)) ze = true
        else w = true
      })
    })
    return sb ? 'sessio-with-subs' : (w ? 'sessio-with-warnings' : (ze ? 'sessio-with-zona-examen' : ''))
  }

  const getIncidentIcon = (text) => getIncidentEmoji(text)

  // Obtenir classe CSS per nivell
  const getNivellClass = (nivellInfo, dia, hora) => {
    let hasWarning = false
    let hasSub = false
    let hasZona = false
    nivellInfo.examens.forEach((ex) => {
      const avisos = getAvisosExamen(ex, dia, hora)
      avisos.forEach((a) => {
        if (isCriticalIncident(a)) hasSub = true
        else if (isZonaExamenIncident(a)) hasZona = true
        else hasWarning = true
      })
    })
    return hasSub ? 'nivell-with-subs' : (hasWarning ? 'nivell-with-warnings' : (hasZona ? 'nivell-with-zona-examen' : ''))
  }

  const incidenciesDetallades = computed(() => {
    const meta = result.value?.horari?.metadata || {}
    const l = []
    if (meta.professors_slots_duplicats) {
      meta.professors_slots_duplicats.forEach((d) => l.push(`❌ SIMULTANI: ${d.professor} a ${d.dia} ${d.hora}`))
    }
    if (meta.logs) l.push(...meta.logs)
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
