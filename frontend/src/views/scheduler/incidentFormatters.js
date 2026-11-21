// Text de cada línia de la llista d'incidències: les incidències són dades i es
// tradueixen pel codi; els avisos de la configuració ja arriben traduïts (text).
import { esIncidencia, textCurtIncidencia, textIncidencia } from './incidencies.js'

export const formatIncidentFull = (_group, incident, t) =>
  esIncidencia(incident) ? textIncidencia(incident, t) : String(incident || '')

export const formatIncidentShort = (_group, incident, t) =>
  esIncidencia(incident) ? textCurtIncidencia(incident, t) : String(incident || '')

export const teCost = (incident) => esIncidencia(incident) && !!incident.punts
