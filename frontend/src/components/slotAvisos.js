// Avisos d'un ítem de l'horari editable que surten dels logs globals de l'horari.

// Text sense accents i en minúscules
export const normalizeText = (t) => (typeof t === 'string' ? t : '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

// L'hora d'un log (patró «a les HH:MM»)
export const extractHour = (text) => {
  const m = (typeof text === 'string' ? text : '').match(/a(?: les)? (\d{1,2}:\d{2})/)
  return m ? m[1] : null
}

// Les línies de text dels logs que parlen d'algun dels professors a aquell dia
// i hora i són avisos globals (enllaç, avisos, límit de dies). Els avisos de la
// configuració arriben com a dades ({codi, params}), no com a text: no són de
// cap casella i es deixen fora.
export function avisosDelsLogs(logs, professors, dia, hora) {
  const profsNorm = professors.map(normalizeText)
  const diaNorm = normalizeText(dia)
  return (logs || []).filter(log => {
    if (typeof log !== 'string') return false
    const logNorm = normalizeText(log)
    const logHour = extractHour(log)
    if (!profsNorm.some(prof => logNorm.includes(prof))) return false
    if (!logNorm.includes(diaNorm)) return false
    if (logHour && logHour !== hora) return false
    return logNorm.includes('enllac') || logNorm.includes('avis') || logNorm.includes('limit dies')
  })
}
