// Incidències del planificador com a dades: el backend envia {codi, params, punts}
// i aquí es classifiquen i es tradueixen. Cap expressió regular sobre el text.
import { etiquetaDiaRestringit, localizeBackendDayName } from './textUtils.js'

const prefix = 'scheduler.incidencies.'

// Grup de la llista d'incidències i icona de cada codi
const GRUPS = {
  inc_substitucio: ['substitutions', '🚨'],
  inc_limit_dies_professor: ['others', '🚨'],
  inc_nivells_diferents: ['conflicts', '⚠️'],
  inc_conflicte_alumnes: ['conflicts', '⚠️'],
  inc_despres: ['stayLate', '🕐'],
  inc_abans: ['arriveEarly', '🕐'],
  inc_no_treballa: ['others', '🚫'],
  inc_enllac: ['links', '🔗'],
  inc_enllac_nivells: ['links', '🔗'],
  inc_zona_examen: ['zoneExam', '👁️'],
  inc_horari_estricte: ['others', '⛔'],
  inc_mateix_dia_obligatori: ['others', '⛔'],
}

export const esIncidencia = (m) => !!m && typeof m === 'object' && String(m.codi || '').startsWith('inc_')

export const grupIncidencia = (m) => GRUPS[m?.codi]?.[0] || 'others'

export const iconaIncidencia = (m) => GRUPS[m?.codi]?.[1] || '⚠️'

// Les que no sumen al recompte d'incidències ni pinten la casella com a avís
export const esEnllac = (m) => grupIncidencia(m) === 'links'
export const esZonaExamen = (m) => m?.codi === 'inc_zona_examen'
// Les que pinten l'examen de vermell al calendari (cal substituir o hi ha un conflicte)
export const esCritica = (m) => ['substitutions', 'conflicts'].includes(grupIncidencia(m))

// «Dilluns 20/04», amb el nom del dia traduït
export const etiquetaDia = ({ dia, data }, t) => {
  const nom = localizeBackendDayName(dia || '', t)
  return data && data.length >= 10 ? `${nom} ${data.slice(8, 10)}/${data.slice(5, 7)}`.trim() : nom
}

const llista = (valors, t) => {
  const noms = (valors || []).filter(Boolean)
  return noms.length > 4
    ? t('scheduler.diagnostic.llista_mes', { noms: noms.slice(0, 4).join(', '), count: noms.length - 4 })
    : noms.join(', ')
}

// Els exàmens on surt una incidència d'un professor: «Mates (N1)->N1»
const examens = (llistaExamens) => (llistaExamens || [])
  .map(({ nom, curs }) => (nom && curs ? `(${nom})->${curs}` : nom ? `(${nom})` : curs ? `->${curs}` : ''))
  .filter(Boolean)
  .sort()
  .join(', ')

const dataCurta = (d) => (/^\d{4}-\d{2}-\d{2}$/.test(d || '') ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : d)

// Els paràmetres preparats per a la plantilla de l'idioma
export const parametresIncidencia = (m, t) => {
  const p = { ...(m?.params || {}) }
  const out = { ...p }
  if ('dia' in p || 'data' in p) out.dia = etiquetaDia(p, t)
  for (const clau of ['amb', 'assignatures', 'examens_nivells', 'noms']) if (Array.isArray(p[clau])) out[clau] = llista(p[clau], t)
  if (Array.isArray(p.examens)) out.examens = examens(p.examens)
  out.ambExamens = out.examens ? ` ${out.examens}` : ''
  if (Array.isArray(p.dates)) out.dates = p.dates.map(dataCurta).join(', ')
  if (Array.isArray(p.dies_limit)) {
    // Els dies amb exàmens, amb quants n'hi ha; si cap, tots els del límit
    const amb = p.dies_limit.filter((d) => d.n)
    out.dies_limit = (amb.length ? amb.map((d) => `${etiquetaDiaRestringit(d.dia, t)} (${d.n})`) : p.dies_limit.map((d) => etiquetaDiaRestringit(d.dia, t))).join(', ')
  }
  if (Array.isArray(p.ubicacions)) {
    out.ubicacions = p.ubicacions.map((u) => `${llista(u.assignatures, t)} → ${etiquetaDia(u, t)} ${u.hora}`).join('; ')
  }
  return out
}

const ambCost = (text, m, t) => (m?.punts ? `${text} (${t('scheduler.steps.results.incidents.short.cost')}: ${m.punts})` : text)

// El text sencer (tooltip i llista detallada)
export const textIncidencia = (m, t) => ambCost(t(prefix + m.codi, parametresIncidencia(m, t)), m, t)

// El text curt de la llista d'incidències, amb la icona
export const textCurtIncidencia = (m, t) => {
  const clau = prefix + 'curt.' + m.codi
  const curt = t(clau, parametresIncidencia(m, t))
  const text = curt && curt !== clau ? curt : t(prefix + m.codi, parametresIncidencia(m, t))
  return `${iconaIncidencia(m)} ${ambCost(text, m, t)}`
}

// La incidència és d'aquest examen (el seu titular) en aquesta data i hora?
export const esDeLExamen = (m, titular, { dia, data, hora }) => {
  const p = m?.params || {}
  if (!titular || p.professor !== titular || p.hora !== hora) return false
  return p.data ? p.data === data : p.dia === dia
}
