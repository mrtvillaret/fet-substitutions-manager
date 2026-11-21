// Hores que dura un examen, amb la mateixa regla que el backend (planificador/motor/durades.py):
// la pròpia (l'últim grup de durada que el conté) o la general d'examen, i mai
// menys que la vigilància (la pròpia del grup o la general del titular).
const positiu = (valor) => (Number(valor) > 0 ? Number(valor) : null)

// Les hores d'examen d'un grup de durada (o, sense grup, les generals).
export const horesExamenDelGrup = (grup, generalExamen, generalTitular) => {
  const titular = positiu(generalTitular) || 1
  const vigilancia = positiu(grup?.durada) || titular
  const examen = positiu(grup?.durada_examen ?? grup?.durada) || positiu(generalExamen) || titular
  return Math.max(examen, vigilancia)
}

export const horesExamen = ({ nom, grups = [], generalExamen, generalTitular }) => {
  let grup = null
  for (const g of grups || []) {
    if (nom && Array.isArray(g.assignatures) && g.assignatures.includes(nom)) grup = g
  }
  return horesExamenDelGrup(grup, generalExamen, generalTitular)
}

// Una marca d'inici on no hi cap sencer cap examen del nivell (fins a l'última
// hora de la graella). Torna les hores de l'examen més curt del nivell si no hi
// cap, o 0 si hi cap (o l'hora no és a la graella).
export const iniciSenseCabuda = ({ nivell, hora, hores = [], examens = [], grups, generalExamen, generalTitular }) => {
  const idx = hores.indexOf(hora)
  if (idx < 0) return 0
  const delNivell = examens.filter((nom) => String(nom).endsWith(`(${nivell})`))
  const durades = (delNivell.length ? delNivell : [null]).map((nom) =>
    horesExamen({ nom, grups, generalExamen, generalTitular }))
  const minima = Math.min(...durades)
  return idx + minima > hores.length ? minima : 0
}
