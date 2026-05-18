import { matchBackendDayLine, normalizeText } from './textUtils'

const REPORT_MARKERS = {
  perSessioHeader: '📝',
  perSessioTeachers: '👥',
  dayHeader: '📅',
  slotHeader: '⏰',
  hourHeader: '⏱️',
  substitutionsTitle: 'substitucions',
  availableTitle: 'disponibles',
  releasedTitle: 'alliberats',
}

const SLOT_QUALITY_LABELS = {
  optimal: 'optimes',
  good: 'bones',
  acceptable: 'acceptables',
}

const linesFromReport = (text) => {
  if (!text) return []
  return text.split('\n').map((line) => line.trim()).filter((line) => line.length)
}

const splitOutsideBrackets = (text, delimiter = ',') => {
  const items = []
  let current = ''
  let depth = 0
  for (const ch of text || '') {
    if (ch === '[') depth += 1
    if (ch === ']') depth = Math.max(0, depth - 1)
    if (ch === delimiter && depth === 0) {
      const trimmed = current.trim()
      if (trimmed) items.push(trimmed)
      current = ''
      continue
    }
    current += ch
  }
  const trimmed = current.trim()
  if (trimmed) items.push(trimmed)
  return items
}

const parseSlotItem = (raw) => {
  const text = (raw || '').trim()
  if (!text) return { label: '', details: [] }
  const match = text.match(/^(.*?)(?:\s*\[(.+)\])?$/)
  const label = (match?.[1] || text).trim()
  const detailsRaw = (match?.[2] || '').trim()
  const details = detailsRaw ? detailsRaw.split(';').map((d) => d.trim()).filter(Boolean) : []
  return { label, details }
}

export const parsePerSessioReport = (text) => {
  const lines = linesFromReport(text)
  const sections = []
  let current = null

  const pushSection = () => {
    if (current && current.titol) sections.push(current)
  }

  for (const line of lines) {
    if (line.startsWith(REPORT_MARKERS.perSessioHeader)) {
      pushSection()
      current = { titol: line.replace(REPORT_MARKERS.perSessioHeader, '').trim(), professors: '', files: [] }
      continue
    }
    if (!current) continue
    if (line.startsWith(REPORT_MARKERS.perSessioTeachers)) {
      current.professors = line.replace('👥 Professors:', '').trim()
      continue
    }
    if (line.includes('|') && !line.startsWith('Dia')) {
      const parts = line.split('|').map((p) => p.trim())
      const first = parts[0] || ''
      const hasEmoji = first.startsWith('✅') || first.startsWith('🟡') || first.startsWith('🔶') || first.startsWith('🔴')
      const emoji = hasEmoji ? first.split(' ')[0] : ''
      const dia = hasEmoji ? first.slice(emoji.length).trim() : first
      const detalls = parts.slice(7).join(' | ').trim() || '—'
      current.files.push({
        emoji,
        dia,
        hora: parts[1] || '',
        cost: parts[2] || '',
        subs: parts[3] || '',
        abans: parts[4] || '',
        despres: parts[5] || '',
        no_treballa: parts[6] || '',
        detalls
      })
      continue
    }
    const dayLine = matchBackendDayLine(line)
    if (dayLine) {
      const dia = dayLine.day
      const rest = dayLine.rest || ''
      let parts = rest.split('\t').map((p) => p.trim()).filter(Boolean)
      if (parts.length < 6) {
        parts = rest.trim().split(/\s+/)
      }
      if (parts.length >= 6) {
        const hasCost = parts.length >= 7
        const offset = hasCost ? 1 : 0
        current.files.push({
          emoji: '',
          dia,
          hora: parts[0] || '',
          cost: hasCost ? (parts[1] || '') : '',
          subs: parts[1 + offset] || '',
          abans: parts[2 + offset] || '',
          despres: parts[3 + offset] || '',
          no_treballa: parts[4 + offset] || '',
          detalls: parts.slice(5 + offset).join(' ').trim() || '—'
        })
      }
    }
  }

  pushSection()
  return sections
}

export const parsePerSlotsReport = (text) => {
  const lines = linesFromReport(text)
  const days = []
  let currentDay = null
  let currentSlot = null
  let currentLevel = null

  const pushDay = () => {
    if (currentDay) days.push(currentDay)
  }

  for (const line of lines) {
    if (line.startsWith(REPORT_MARKERS.dayHeader)) {
      pushDay()
      currentDay = { dia: line.replace(REPORT_MARKERS.dayHeader, '').trim(), slots: [] }
      currentSlot = null
      currentLevel = null
      continue
    }
    if (!currentDay) continue
    if (line.startsWith(REPORT_MARKERS.slotHeader)) {
      currentSlot = { hora: line.replace(REPORT_MARKERS.slotHeader, '').trim(), nivells: [], substitucions: [] }
      currentDay.slots.push(currentSlot)
      currentLevel = null
      continue
    }
    if (!currentSlot) continue
    if (line.endsWith(':') && !line.startsWith('✅') && !line.startsWith('🟡') && !line.startsWith('🔶') && !line.startsWith('🔴')) {
      currentLevel = { nivell: line.replace(':', '').trim(), optimes: [], bones: [], acceptables: [] }
      currentSlot.nivells.push(currentLevel)
      continue
    }
    if (!currentLevel) continue
    if (normalizeText(line).includes(REPORT_MARKERS.substitutionsTitle)) {
      currentLevel = null
      continue
    }
    if (line.startsWith('✅') || line.startsWith('🟡') || line.startsWith('🔶') || line.startsWith('🔴')) {
      const splitIdx = line.indexOf(':')
      if (splitIdx === -1) continue
      const label = line.slice(0, splitIdx) || ''
      const listPart = line.slice(splitIdx + 1)
      const itemsRaw = listPart ? splitOutsideBrackets(listPart) : []
      const items = itemsRaw.map(parseSlotItem).filter((item) => item.label)
      const normalizedLabel = normalizeText(label)
      if (normalizedLabel.includes(SLOT_QUALITY_LABELS.optimal)) currentLevel.optimes.push(...items)
      else if (normalizedLabel.includes(SLOT_QUALITY_LABELS.good)) currentLevel.bones.push(...items)
      else if (normalizedLabel.includes(SLOT_QUALITY_LABELS.acceptable)) currentLevel.acceptables.push(...items)
      continue
    }
    if (line.startsWith('•')) {
      const entry = line.replace('•', '').trim()
      if (currentSlot && entry) {
        currentSlot.substitucions.push(entry)
      }
    }
  }

  pushDay()
  return days
}

export const parseProfessorsSlotReport = (text) => {
  const lines = linesFromReport(text)
  const days = []
  let currentDay = null
  let currentSlot = null
  let currentHour = null
  let currentList = null

  const pushDay = () => {
    if (currentDay) days.push(currentDay)
  }

  for (const line of lines) {
    if (line.startsWith(REPORT_MARKERS.dayHeader)) {
      pushDay()
      currentDay = { dia: line.replace(REPORT_MARKERS.dayHeader, '').trim(), slots: [] }
      currentSlot = null
      currentHour = null
      currentList = null
      continue
    }
    if (!currentDay) continue
    if (line.startsWith(REPORT_MARKERS.slotHeader)) {
      currentSlot = { horaLabel: line.replace(REPORT_MARKERS.slotHeader, '').trim(), hores: [] }
      currentHour = { hora: null, disponibles: [], alliberats: [], substitucions: [] }
      currentSlot.hores.push(currentHour)
      currentDay.slots.push(currentSlot)
      currentList = null
      continue
    }
    if (!currentSlot) continue
    if (line.startsWith(REPORT_MARKERS.hourHeader)) {
      currentHour = { hora: line.replace(REPORT_MARKERS.hourHeader, '').replace('Hora', '').trim(), disponibles: [], alliberats: [], substitucions: [] }
      currentSlot.hores.push(currentHour)
      currentList = null
      continue
    }
    const normalizedLine = normalizeText(line)
    if (normalizedLine.includes(REPORT_MARKERS.availableTitle)) {
      currentList = 'disponibles'
      continue
    }
    if (normalizedLine.includes(REPORT_MARKERS.releasedTitle)) {
      currentList = 'alliberats'
      continue
    }
    if (normalizedLine.includes(REPORT_MARKERS.substitutionsTitle)) {
      currentList = 'substitucions'
      continue
    }
    if (line.startsWith('•')) {
      const entry = line.replace('•', '').trim()
      if (currentHour && currentList && entry) {
        currentHour[currentList].push(entry)
      }
    }
  }

  pushDay()
  return days
}
