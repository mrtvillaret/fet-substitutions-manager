export const getExamsUnics = (examens) => {
  const vistos = new Set()
  return (examens || []).filter((exam) => {
    const clau = `${exam.assignatura}_${exam.titular}`
    if (vistos.has(clau)) return false
    vistos.add(clau)
    return true
  })
}

export const normalizeText = (value) => (value || '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .replace(/[_-]+/g, ' ')
  .replace(/[^a-zA-Z0-9\s]/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()
  .toLowerCase()

// L'ordre dels nivells a tot el planificador és el de la Configuració d'exàmens (`ordre`,
// la llista config.nivells). Un nivell que no hi és, al final.
export const comparaSegonsOrdre = (ordre = []) => {
  const posicio = (nivell) => {
    const i = ordre.indexOf(nivell)
    return i === -1 ? ordre.length : i
  }
  return (a, b) => posicio(a) - posicio(b)
}

const BACKEND_DAY_I18N_KEYS = {
  dilluns: 'scheduler.days.monday',
  dimarts: 'scheduler.days.tuesday',
  dimecres: 'scheduler.days.wednesday',
  dijous: 'scheduler.days.thursday',
  divendres: 'scheduler.days.friday',
  dissabte: 'scheduler.days.saturday',
  diumenge: 'scheduler.days.sunday',
}
export const localizeBackendDayName = (dayName, t) => {
  // «Dilluns 20/04»: el backend hi afegeix la data; es tradueix el nom del dia
  const [, nom, resta] = String(dayName || '').match(/^(\S+)(.*)$/s) || [null, dayName, '']
  const key = BACKEND_DAY_I18N_KEYS[normalizeText(nom)]
  if (!key || typeof t !== 'function') return dayName
  const translated = t(key)
  return translated ? `${translated}${resta}` : dayName
}

// Un dia del límit per professor: un nom de dia («Dilluns», tots els dilluns) o una data
// («2027-03-01» → «Dilluns 01/03»), amb el nom traduït.
const NOMS_DIES_BACKEND = ['Diumenge', 'Dilluns', 'Dimarts', 'Dimecres', 'Dijous', 'Divendres', 'Dissabte']
export const etiquetaDiaRestringit = (dia, t) => {
  const m = String(dia || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return localizeBackendDayName(dia, t)
  const nom = NOMS_DIES_BACKEND[new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).getDay()]
  return localizeBackendDayName(`${nom} ${m[3]}/${m[2]}`, t)
}
