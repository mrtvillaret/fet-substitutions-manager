import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed, watch } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../src/pdfOpcions.js'
import { SENSE_NIVELL, opcionsNivellsPdf, parametresNivellsPdf, seleccioInicialNivellsPdf } from '../src/vigilanciesPdf.js'
import { dataIso } from '../src/dates.js'

test('l’interval descarrega directament i deixa els problemes a dins del PDF', async () => {
  const peticions = []
  const dependents = { dataISO: ref('2026-04-20'), dataTreball: ref(new Date(2026, 3, 20)), nivells: ref([]), vigilancies: ref([]), t: x => x, toast: { add() {} } }
  const apiPdf = {
    validacions: () => assert.fail('l’interval no ha de fer revisió prèvia'),
    vigilanciesInterval: async params => { peticions.push(params); return { data: 'PDF' } },
    desaPreferencies: async () => {},
  }
  const deps = { dependents, ref, computed, watch, apiPdf, aplicaPreferencies, midaPerDefecte, parametresComuns, SENSE_NIVELL, opcionsNivellsPdf, parametresNivellsPdf, seleccioInicialNivellsPdf, dataIso, jaAvisat: () => false, desaPdf: () => {} }
  const p = carregaBlocVista('usePdfVigilancies', deps)
  p.intervalConfig.value.dataInici = new Date(2026, 3, 20)
  p.intervalConfig.value.dataFinal = new Date(2026, 3, 21)
  await p.generarPDFInterval()
  assert.equal(peticions.length, 1)
  assert.deepEqual([peticions[0].data_inici, peticions[0].data_final], ['2026-04-20', '2026-04-21'])
  assert.equal(p.mostrarDialogValidacionsVig.value, false)
  assert.equal(p.generantPDFInterval.value, false)
})
