import { test } from 'node:test'
import assert from 'node:assert/strict'
import { horesExamen, horesExamenDelGrup, iniciSenseCabuda } from '../src/views/scheduler/duradaExamen.js'

// La durada d'examen de la pantalla segueix la mateixa regla que el backend.
test("durada d'examen: general, pròpia, últim grup i mai menys que la vigilància", () => {
  const nom = 'A (1-BAT)'
  assert.equal(horesExamen({ nom, generalExamen: 2, generalTitular: 1 }), 2)
  assert.equal(horesExamen({ nom, grups: [{ assignatures: [nom], durada: 1, durada_examen: 3 }], generalExamen: 2, generalTitular: 1 }), 3)
  assert.equal(horesExamen({ nom, grups: [{ assignatures: [nom], durada: 3, durada_examen: 1 }], generalExamen: 2, generalTitular: 1 }), 3)
  const dosGrups = [
    { assignatures: [nom], durada: 1, durada_examen: 1 },
    { assignatures: [nom], durada: 2, durada_examen: 2 },
  ]
  assert.equal(horesExamen({ nom, grups: dosGrups, generalExamen: 1, generalTitular: 1 }), 2)
  assert.equal(horesExamen({ nom: 'B (1-BAT)', generalExamen: 1, generalTitular: 2 }), 2)
  assert.equal(horesExamen({ nom }), 1)
})

test("una marca d'inici on no hi cap cap examen del nivell", () => {
  const hores = ['09:00', '10:00', '11:00']
  const examens = ['A (1-BAT)', 'B (1-BAT)', 'C (2-BAT)']
  const base = { hores, examens, generalExamen: 2, generalTitular: 1 }
  assert.equal(iniciSenseCabuda({ ...base, nivell: '1-BAT', hora: '11:00' }), 2)
  assert.equal(iniciSenseCabuda({ ...base, nivell: '1-BAT', hora: '10:00' }), 0)
  // Un examen del nivell d'una hora hi cap: la marca es pot fer servir
  const grups = [{ assignatures: ['B (1-BAT)'], durada: 1, durada_examen: 1 }]
  assert.equal(iniciSenseCabuda({ ...base, grups, nivell: '1-BAT', hora: '11:00' }), 0)
  assert.equal(iniciSenseCabuda({ ...base, nivell: '1-BAT', hora: '12:00' }), 0)
})

// La columna «durada d'examen» de la taula de grups de durada mostra la que es fa servir:
// mai menys que la vigilància, i sense durada d'examen (buida o nul·la), la del grup.
test("durada d'examen d'un grup de durada", () => {
  assert.equal(horesExamenDelGrup({ durada: 3, durada_examen: 1 }), 3)
  assert.equal(horesExamenDelGrup({ durada: 1, durada_examen: 2 }), 2)
  assert.equal(horesExamenDelGrup({ durada: 3, durada_examen: null }, 4, 1), 3)
  assert.equal(horesExamenDelGrup({ durada: 3 }, 4, 1), 3)
})
