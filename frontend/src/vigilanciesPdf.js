export const SENSE_NIVELL = '__sense_nivell__'

export const opcionsNivellsPdf = (nivells, senseNivell, etiquetaSenseNivell) => {
  const opcions = nivells.map((nivell) => ({ valor: nivell, etiqueta: nivell }))
  if (senseNivell > 0) {
    opcions.push({ valor: SENSE_NIVELL, etiqueta: etiquetaSenseNivell(senseNivell) })
  }
  return opcions
}

export const seleccioInicialNivellsPdf = (opcions) => opcions.map((opcio) => opcio.valor)

export const parametresNivellsPdf = (seleccio = []) => ({
  nivells: seleccio.filter((nivell) => nivell !== SENSE_NIVELL).join(','),
  inclou_sense_nivell: seleccio.includes(SENSE_NIVELL)
})
