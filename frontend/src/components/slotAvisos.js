// Avisos d'un ítem de l'horari editable que surten dels logs globals de l'horari (les
// incidències són dades {codi, params, punts}). Només els globals: enllaços, exàmens de
// nivells diferents alhora i el límit per professor; la resta ja són a l'ítem (item_avisos).
import { esEnllac, esIncidencia } from '../views/scheduler/incidencies.js'

const GLOBALS = new Set(['inc_nivells_diferents', 'inc_limit_dies_professor'])
const NOMS_DIES = ['Diumenge', 'Dilluns', 'Dimarts', 'Dimecres', 'Dijous', 'Divendres', 'Dissabte']

// «09:00» i «9:00» són la mateixa hora
const hora = (h) => String(h || '').replace(/^0(\d:)/, '$1')

// El nom del dia d'una clau de casella (una data ISO o ja un nom de dia)
const nomDelDia = (clau) => (/^\d{4}-\d{2}-\d{2}$/.test(clau) ? NOMS_DIES[new Date(`${clau}T12:00:00`).getDay()] : clau)

const delDia = (p, clau) => (p.data ? p.data === clau : p.dia === clau || p.dia === nomDelDia(clau))

export function avisosDelsLogs(logs, professors, clauDia, horaCasella) {
  const profs = new Set(professors)
  return (logs || []).filter((m) => {
    if (!esIncidencia(m) || !(esEnllac(m) || GLOBALS.has(m.codi))) return false
    const p = m.params || {}
    if (!profs.has(p.professor)) return false
    if (m.codi === 'inc_limit_dies_professor') {
      // Als dies restringits del límit (dates o noms de dia)
      return (p.dies_limit || []).some((d) => d.dia === clauDia || d.dia === nomDelDia(clauDia))
    }
    return delDia(p, clauDia) && hora(p.hora) === hora(horaCasella)
  })
}
