import assert from 'node:assert/strict'
import test from 'node:test'

import {
  SENSE_NIVELL,
  opcionsNivellsPdf,
  parametresNivellsPdf,
  seleccioInicialNivellsPdf
} from '../src/vigilanciesPdf.js'

test('afegeix Sense nivell amb recompte només quan n’hi ha i el marca per defecte', () => {
  const ambAntigues = opcionsNivellsPdf(['1-ESO', '2-ESO'], 3, (n) => `Sense nivell (${n})`)
  const senseAntigues = opcionsNivellsPdf(['1-ESO'], 0, (n) => `Sense nivell (${n})`)

  assert.deepEqual(ambAntigues, [
    { valor: '1-ESO', etiqueta: '1-ESO' },
    { valor: '2-ESO', etiqueta: '2-ESO' },
    { valor: SENSE_NIVELL, etiqueta: 'Sense nivell (3)' }
  ])
  assert.deepEqual(seleccioInicialNivellsPdf(ambAntigues), ['1-ESO', '2-ESO', SENSE_NIVELL])
  assert.deepEqual(senseAntigues, [{ valor: '1-ESO', etiqueta: '1-ESO' }])
})

test('separa els nivells reals de la tria de les vigilàncies sense nivell', () => {
  assert.deepEqual(parametresNivellsPdf(['1-ESO', SENSE_NIVELL]), {
    nivells: '1-ESO',
    inclou_sense_nivell: true
  })
  assert.deepEqual(parametresNivellsPdf(['1-ESO']), {
    nivells: '1-ESO',
    inclou_sense_nivell: false
  })
})
