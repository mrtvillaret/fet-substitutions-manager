import { localizeBackendDayName } from './textUtils.js'

const prefix = 'scheduler.diagnostic.'

export function tradueixMissatge(missatge, t) {
  // Compatible amb resultats anteriors; els nous missatges són codi + paràmetres.
  if (!missatge || typeof missatge === 'string') return missatge || ''
  const params = { ...missatge.params }
  for (const key of ['assignatures', 'noms']) {
    if (!Array.isArray(params[key])) continue
    const noms = params[key].slice(0, 4).join(', ')
    params[key] = params[key].length > 4
      ? t(prefix + 'llista_mes', { noms, count: params[key].length - 4 })
      : noms
  }
  if ('nom' in params && !params.nom) params.nom = t(prefix + 'sense_nom')
  if ('nivell' in params && !params.nivell) params.nivell = t(prefix + 'nivell_desconegut')
  if (params.causa) params.causa = t(prefix + 'causes.' + params.causa)
  if (params.dia) params.dia = localizeBackendDayName(params.dia, t)
  // Franja fixada d'un examen: el dia (o la data) i l'hora, el que hi hagi
  if ('dia' in params && 'hora' in params) params.franja = [params.dia, params.hora].filter(Boolean).join(' ')
  if (typeof params.dies === 'string') {
    params.dies = params.dies.split(', ').map(d => localizeBackendDayName(d, t)).join(', ')
  }
  for (const [key, unitat, desti] of [['count', 'examens', 'examens'], ['hores', 'hores', 'horesText'], ['dies', 'dies', 'diesText']]) {
    if (typeof params[key] === 'number') params[desti] = t(prefix + 'unitats.' + unitat, { count: params[key] }, params[key])
  }
  return t(prefix + missatge.codi, params)
}

// Avisos de la configuració que el backend posa als logs del resultat.
// Es reconeixen pel codi: el text no sempre diu «avís» en cada idioma.
const CODIS_AVIS_CONFIGURACIO = new Set(['grup_sense_nivell', 'nivell_sense_hores_alliberades', 'nivell_alliberaments_sense_hores'])

export const esAvisDeConfiguracio = (missatge) => CODIS_AVIS_CONFIGURACIO.has(missatge?.codi)

export function avisosDeConfiguracio(logs, t) {
  return (logs || []).filter(esAvisDeConfiguracio).map((m) => tradueixMissatge(m, t).trim())
}

// Grups de les assignacions que no són a cap nivell: al diàleg de no
// viable (dels logs del resultat) i a l'anàlisi prèvia (dels seus avisos)
export function avisosDeGrupsSenseNivell(logs, t) {
  return (logs || []).filter((m) => m?.codi === 'grup_sense_nivell').map((m) => tradueixMissatge(m, t).trim())
}
