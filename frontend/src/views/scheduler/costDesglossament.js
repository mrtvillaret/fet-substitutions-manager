// Desglossament del cost total del planificador (cost_desglossament del
// backend: [{concepte, quantitat, pes, punts}], només els conceptes amb punts).
// Una fila per concepte; si un concepte té pesos diferents (p. ex. costos
// individuals de professors), «2 × 80 + 1 × 10».

const CONCEPTES = [
  'substitucio',
  'abans_jornada',
  'despres_jornada',
  'no_treballa_dia',
  'preferencia_mateix_dia',
  'preferencia_dies_diferents',
  'preferencia_mateix_slot',
  'no_mateix_slot',
  'no_mateix_dia',
  'combinacio_no_permesa',
  'dia_hora_fix',
  'assignatures_dies_exclosos',
  'limit_dies_professor',
  'professor_estricte',
]

export const CONCEPTES_COST = CONCEPTES

const nombre = (valor, locale) => Number(valor).toLocaleString(locale)

export const filesDesglossament = (desglossament, t, locale = 'ca-ES') => {
  const perConcepte = new Map()
  for (const fila of desglossament || []) {
    if (!fila || !Number(fila.punts)) continue
    if (!perConcepte.has(fila.concepte)) perConcepte.set(fila.concepte, [])
    perConcepte.get(fila.concepte).push(fila)
  }
  const ordre = (c) => (CONCEPTES.includes(c) ? CONCEPTES.indexOf(c) : CONCEPTES.length)
  const files = [...perConcepte.entries()]
    .sort(([a], [b]) => ordre(a) - ordre(b))
    .map(([concepte, grups]) => {
      const clau = `scheduler.steps.results.costBreakdown.concepts.${concepte}`
      const etiqueta = t(clau)
      return {
        concepte,
        etiqueta: etiqueta && etiqueta !== clau ? etiqueta : concepte,
        calcul: grups.map((g) => `${nombre(g.quantitat, locale)} × ${nombre(g.pes, locale)}`).join(' + '),
        punts: grups.reduce((suma, g) => suma + Number(g.punts), 0),
      }
    })
  const total = files.reduce((suma, f) => suma + f.punts, 0)
  return { files, total, text: (punts) => nombre(punts, locale) }
}
