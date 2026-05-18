import { getIncidentEmoji, removeIncidentScore, extractIncidentScore, stripIncidentDecorators, localizeIncidentText } from './textUtils'

const translate = (t, key, fallback) => {
  if (typeof t !== 'function') return fallback
  const value = t(key)
  return value || fallback
}

export const formatIncidentFull = (group, incident, t) => {
  const cleaned = localizeIncidentText(incident, t)
  if (group?.id === 'links') return `🔗 ${cleaned}`
  return cleaned
}

export const formatIncidentShort = (group, incident, t) => {
  const scoreToken = extractIncidentScore(incident)
  const scoreValue = scoreToken.match(/(\d+)/)?.[1]
  const score = scoreValue && Number(scoreValue) > 0 ? ` (${translate(t, 'scheduler.steps.results.incidents.short.cost', 'cost')}: ${scoreValue})` : ''
  const noScore = removeIncidentScore(incident)
  const emojiMatch = noScore.match(/^(🚨|🕐|⚠️|📋|🔗|🚫|❌|ℹ️|👁️)/u)
  const cleanedNoEmoji = stripIncidentDecorators(noScore)
  const emoji = emojiMatch ? `${emojiMatch[0]} ` : `${getIncidentEmoji(cleanedNoEmoji)} `
  const cleaned = cleanedNoEmoji

  let shortText = cleaned

  let match = cleaned.match(/^(.+?)\s+→\s+ha de ser SUBSTITUÏT a\s+(.+?)\s+amb\s+(.+?)\s+a les\s+(\d{2}:\d{2})\s+el\s+(.+)$/i)
  if (match) {
    const [, prof, assig, grupText, hora, dia] = match
    shortText = `${prof} · ${assig} · ${grupText} · ${dia} ${hora}`
  }

  if (!match) {
    match = cleaned.match(/^(.+?)\s+→\s+arriba abans a\s+(\d{2}:\d{2})\s+el\s+(.+?)\s+\(primera hora:\s*([^)]+)\)$/i)
    if (match) {
      const [, prof, hora, dia, primera] = match
      shortText = `${prof} · ${translate(t, 'scheduler.steps.results.incidents.short.before', 'before')} ${dia} ${hora} · ${translate(t, 'scheduler.steps.results.incidents.short.first', 'first')} ${primera}`
    }
  }

  if (!match) {
    match = cleaned.match(/^(.+?)\s+→\s+queda més estona a\s+(\d{2}:\d{2})\s+el\s+(.+?)\s+\(última hora:\s*([^)]+)\)$/i)
    if (match) {
      const [, prof, hora, dia, ultima] = match
      shortText = `${prof} · ${translate(t, 'scheduler.steps.results.incidents.short.after', 'after')} ${dia} ${hora} · ${translate(t, 'scheduler.steps.results.incidents.short.last', 'last')} ${ultima}`
    }
  }

  if (!match) {
    match = cleaned.match(/^(.+?)\s+→\s+no treballa aquest dia a les\s+(\d{2}:\d{2})\s+el\s+(.+)$/i)
    if (match) {
      const [, prof, hora, dia] = match
      shortText = `${prof} · ${translate(t, 'scheduler.steps.results.incidents.short.noWork', 'no work')} ${dia} ${hora}`
    }
  }

  if (!match) {
    match = cleaned.match(/^(.+?)\s+→\s+en zona examen a\s+(.+?)\s+amb\s+(.+?)\s+a les\s+(\d{2}:\d{2})\s+el\s+(.+)$/i)
    if (match) {
      const [, prof, assig, grupText, hora, dia] = match
      shortText = `${prof} · ${assig} · ${grupText} · ${dia} ${hora}`
    }
  }

  const localizedShort = localizeIncidentText(shortText, t)
  return `${emoji}${localizedShort}${score}`.trim()
}
