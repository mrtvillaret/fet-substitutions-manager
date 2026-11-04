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
  if (typeof params.dies === 'string') {
    params.dies = params.dies.split(', ').map(d => localizeBackendDayName(d, t)).join(', ')
  }
  for (const [key, unitat, desti] of [['count', 'examens', 'examens'], ['hores', 'hores', 'horesText'], ['dies', 'dies', 'diesText']]) {
    if (typeof params[key] === 'number') params[desti] = t(prefix + 'unitats.' + unitat, { count: params[key] }, params[key])
  }
  return t(prefix + missatge.codi, params)
}
