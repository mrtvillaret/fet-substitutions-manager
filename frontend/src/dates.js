// Una data (Date) com a AAAA-MM-DD, en hora local: el format de les dates de
// l'API. (toISOString() faria servir l'hora UTC i podria canviar de dia.)
export const dataIso = (d) => {
  if (!d) return null
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

// "2026-10-19" → "19/10/2026"
export const dataAmbAny = (iso) => {
  const [any, mes, dia] = (iso || '').split('-')
  return any && mes && dia ? `${dia}/${mes}/${any}` : iso
}
