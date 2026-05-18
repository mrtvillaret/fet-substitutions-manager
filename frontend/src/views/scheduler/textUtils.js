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
  .replace(/[_\-]+/g, ' ')
  .replace(/[^a-zA-Z0-9\s]/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()
  .toLowerCase()

export const extractHour = (value) => {
  const match = String(value || '').match(/(\d{1,2}):(\d{2})/)
  if (!match) return ''
  return `${parseInt(match[1], 10)}:${match[2]}`
}

const INCIDENT_EMOJI_PREFIX_RE = /^(?:(?:🚨|🕐|⚠️|📋|🔗|🚫|❌|ℹ️|👁️)\s*)+/u
const INCIDENT_TEXT_PREFIX_RE = /^(CONFLICTE|SUBSTITUÏT|SUBSTITUIT|ENLLAÇ|ENLLAC):\s*/i
const INCIDENT_SCORE_RE = /\(punt:\s*\d+\)/i

const INCIDENT_KIND = {
  conflict: 'conflict',
  substitution: 'substitution',
  arriveEarly: 'arrive_early',
  stayLate: 'stay_late',
  noWorkDay: 'no_work_day',
  link: 'link',
  warning: 'warning',
  zonaExamen: 'zona_examen',
  other: 'other',
}

const INCIDENT_RULES = [
  { kind: INCIDENT_KIND.link, includes: ['enllac'] },
  { kind: INCIDENT_KIND.conflict, includes: ['conflicte', 'simultani'] },
  { kind: INCIDENT_KIND.substitution, includes: ['substitu'] },
  { kind: INCIDENT_KIND.arriveEarly, includes: ['arriba abans'] },
  { kind: INCIDENT_KIND.stayLate, includes: ['queda mes estona'] },
  { kind: INCIDENT_KIND.noWorkDay, includes: ['no treballa'] },
  { kind: INCIDENT_KIND.zonaExamen, includes: ['zona examen'] },
  { kind: INCIDENT_KIND.warning, includes: ['avis'] },
]

export const INCIDENT_KINDS = INCIDENT_KIND

export const stripIncidentDecorators = (text) => String(text || '')
  .replace(INCIDENT_EMOJI_PREFIX_RE, '')
  .replace(INCIDENT_TEXT_PREFIX_RE, '')
  .trim()

export const removeIncidentScore = (text) => String(text || '').replace(/\s*\(punt:\s*\d+\)\s*$/i, '')

export const extractIncidentScore = (text) => String(text || '').match(INCIDENT_SCORE_RE)?.[0] || ''

export const classifyIncidentKind = (text) => {
  const normalized = normalizeText(text)
  for (const rule of INCIDENT_RULES) {
    if (rule.includes.some((token) => normalized.includes(token))) {
      return rule.kind
    }
  }
  return INCIDENT_KIND.other
}

export const isCriticalIncident = (text) => {
  const kind = classifyIncidentKind(text)
  return kind === INCIDENT_KIND.conflict || kind === INCIDENT_KIND.substitution
}

export const isZonaExamenIncident = (text) => classifyIncidentKind(text) === INCIDENT_KIND.zonaExamen

export const isLinkIncident = (text) => classifyIncidentKind(text) === INCIDENT_KIND.link

export const isIncidentLogLine = (text) => {
  const raw = String(text || '').trim()
  if (!raw) return false
  if (raw.includes('→') || raw.includes('->')) return true
  return classifyIncidentKind(raw) !== INCIDENT_KIND.other
}

export const getAvisEmoji = (text) => {
  const match = String(text || '').match(/^(🚨|🕐|⚠️|📋|🔗|🚫|❌|ℹ️)/u)
  if (match) return match[0]
  const kind = classifyIncidentKind(text)
  if (kind === INCIDENT_KIND.conflict || kind === INCIDENT_KIND.substitution) return '🚨'
  if (kind === INCIDENT_KIND.arriveEarly || kind === INCIDENT_KIND.stayLate) return '🕐'
  if (kind === INCIDENT_KIND.noWorkDay) return '🚫'
  if (kind === INCIDENT_KIND.link) return '🔗'
  if (kind === INCIDENT_KIND.zonaExamen) return '👁️'
  return '⚠️'
}

export const getIncidentEmoji = getAvisEmoji

const BACKEND_DAY_NAMES = ['Dilluns', 'Dimarts', 'Dimecres', 'Dijous', 'Divendres', 'Dissabte', 'Diumenge']
const BACKEND_DAY_NAMES_NORM = new Set(BACKEND_DAY_NAMES.map(normalizeText))
const BACKEND_DAY_I18N_KEYS = {
  dilluns: 'scheduler.days.monday',
  dimarts: 'scheduler.days.tuesday',
  dimecres: 'scheduler.days.wednesday',
  dijous: 'scheduler.days.thursday',
  divendres: 'scheduler.days.friday',
  dissabte: 'scheduler.days.saturday',
  diumenge: 'scheduler.days.sunday',
}
const BACKEND_DAY_NAMES_RE = /\b(Dilluns|Dimarts|Dimecres|Dijous|Divendres|Dissabte|Diumenge)\b/gi

export const localizeBackendDayName = (dayName, t) => {
  const norm = normalizeText(dayName)
  const key = BACKEND_DAY_I18N_KEYS[norm]
  if (!key || typeof t !== 'function') return dayName
  const translated = t(key)
  return translated || dayName
}

export const localizeBackendDayNames = (text, t) => String(text || '')
  .replace(BACKEND_DAY_NAMES_RE, (match) => localizeBackendDayName(match, t))

export const localizeIncidentText = (text, t) => {
  const costLabel = typeof t === 'function' ? t('scheduler.steps.results.incidents.short.cost') : 'cost'
  const examsLabel = typeof t === 'function' ? t('scheduler.steps.results.incidents.short.exams') : 'exams'
  const tr = (key, fallback, params = undefined) => {
    if (typeof t !== 'function') return fallback
    const value = t(key, params)
    return value && value !== key ? value : fallback
  }

  const cleaned = stripIncidentDecorators(text)
  const scoreValue = cleaned.match(/\(punt:\s*(\d+)\)/i)?.[1]
  const rawNoScore = cleaned.replace(/\s*\(punt:\s*\d+\)\s*$/i, '').trim()
  let body = rawNoScore

  let match = rawNoScore.match(/^(.+?)\s+→\s+ha de ser SUBSTITU[ÏI]T a\s+(.+?)\s+amb\s+(.+?)\s+a les\s+(\d{2}:\d{2})\s+el\s+(.+)$/i)
  if (match) {
    const [, teacher, subject, group, hour, day] = match
    body = tr('scheduler.steps.results.incidents.full.substitution', `${teacher} → must be substituted in ${subject} with ${group} at ${hour} on ${localizeBackendDayName(day, t)}`, {
      teacher, subject, group, hour, day: localizeBackendDayName(day, t)
    })
  }

  if (!match) {
    match = rawNoScore.match(/^(.+?)\s+→\s+gestiona\s+(\d+)\s+ex[àa]mens?\s+de\s+(.+?)\s+a\s+(\d{2}:\d{2})\s+el\s+(.+?):\s+(.+)$/i)
    if (match) {
      const [, teacher, count, level, hour, day, subject] = match
      body = tr('scheduler.steps.results.incidents.full.manage', `${teacher} → handles ${count} exams for ${level} at ${hour} on ${localizeBackendDayName(day, t)}: ${subject}`, {
        teacher,
        count,
        exams: examsLabel,
        level,
        hour,
        day: localizeBackendDayName(day, t),
        subject
      })
    }
  }

  if (!match) {
    match = rawNoScore.match(/^(.+?)\s+→\s+arriba abans a\s+(\d{2}:\d{2})\s+el\s+(.+?)\s+\(primera hora:\s*([^)]+)\)$/i)
    if (match) {
      const [, teacher, hour, day, firstHour] = match
      body = tr('scheduler.steps.results.incidents.full.arriveEarly', `${teacher} → arrives early at ${hour} on ${localizeBackendDayName(day, t)} (first hour: ${firstHour})`, {
        teacher,
        hour,
        day: localizeBackendDayName(day, t),
        firstHour
      })
    }
  }

  if (!match) {
    match = rawNoScore.match(/^(.+?)\s+→\s+queda més estona a\s+(\d{2}:\d{2})\s+el\s+(.+?)\s+\(última hora:\s*([^)]+)\)$/i)
    if (match) {
      const [, teacher, hour, day, lastHour] = match
      body = tr('scheduler.steps.results.incidents.full.stayLate', `${teacher} → stays later at ${hour} on ${localizeBackendDayName(day, t)} (last hour: ${lastHour})`, {
        teacher,
        hour,
        day: localizeBackendDayName(day, t),
        lastHour
      })
    }
  }

  if (!match) {
    match = rawNoScore.match(/^(.+?)\s+→\s+no treballa aquest dia a les\s+(\d{2}:\d{2})\s+el\s+(.+)$/i)
    if (match) {
      const [, teacher, hour, day] = match
      body = tr('scheduler.steps.results.incidents.full.noWork', `${teacher} → does not work that day at ${hour} on ${localizeBackendDayName(day, t)}`, {
        teacher,
        hour,
        day: localizeBackendDayName(day, t)
      })
    }
  }

  if (!match) {
    body = localizeBackendDayNames(rawNoScore, t)
      .replace(/\bex[àa]mens?\b/gi, examsLabel)
  }

  return scoreValue ? `${body} (${costLabel}: ${scoreValue})` : body
}

export const matchBackendDayLine = (line) => {
  const text = String(line || '').trim()
  if (!text) return null
  const firstWord = text.split(/\s+/)[0]
  if (!BACKEND_DAY_NAMES_NORM.has(normalizeText(firstWord))) return null
  return {
    day: firstWord,
    rest: text.slice(firstWord.length).trim()
  }
}
