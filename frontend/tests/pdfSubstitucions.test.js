import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../src/pdfOpcions.js'

function prepara({ validacio = { conflicts: [], warnings: [], informatius: [], total: 0 }, changes = [] } = {}) {
  const peticions = [], avisos = [], links = []
  const apiPdf = {
    preferencies: async (...args) => { peticions.push(['preferencies', ...args]); return { data: { substitucions: { format: 'dies', blankRows: true } } } },
    validacions: async (...args) => { peticions.push(['validacions', ...args]); return { data: validacio } },
    complet: async (...args) => { peticions.push(['complet', ...args]); return { data: 'PDF' } },
    desaPreferencies: async (...args) => { peticions.push(['desaPreferencies', ...args]) }
  }
  const dependents = { dataISO: ref('2026-04-20'), ordreFiles: ref('professor'), horesDisponibles: ref(['09:00','08:00']), toast: { add: m => avisos.push(m) }, t: x => x, mostrarAvisos: x => avisos.push(x), carregarSubstitucions: async () => peticions.push(['recarrega']) }
  const dependencies = { ...dependents, dependents, ref, computed, aplicaPreferencies, midaPerDefecte, parametresComuns, apiPdf, jaAvisat: () => false, apiSubstitucions: { reassignaProblematiques: async (...args) => { peticions.push(['reassigna', ...args]); return { changes, cleared: changes.length } } }, desaPdf: (...args) => links.push(args) }
  const bloc = carregaBlocVista('usePdfSubstitucions', dependencies)
  return { ...bloc, peticions, avisos, links }
}
const SECCIONS = { params: { include_substitutions: true, include_vigilancies: true } }
test('PDF: preferències, avisos tal com arriben del backend i retorn del diàleg de validació', async () => {
  // Cap filtre per text: «prioritat» dins del nom d'una assignatura no amaga l'avís
  const ambPrioritat = '⚠️ 10:00: Substitut Prof 2 té classe (Prioritat, 1-ESO-A)'
  const p = prepara({ validacio: { conflicts: ['conflicte'], warnings: [ambPrioritat, 'avís útil'], informatius: [], total: 3, has_critical: true } })
  await p.mostrarDialegPDF()
  assert.equal(p.pdfConfig.value.format, 'dies')
  assert.equal(p.mostrarDialogPDF.value, true)
  await p.generarPDFComplet()
  assert.equal(p.mostrarDialogValidacions.value, true)
  assert.equal(p.generantPDF.value, false)
  assert.deepEqual(p.validacions.value.warnings, [ambPrioritat, 'avís útil'])
  assert.equal(p.validacions.value.total, 3)
  assert.deepEqual(p.peticions, [['preferencies'], ['validacions', '2026-04-20', SECCIONS]])
  p.cancelarPDF()
  assert.equal(p.mostrarDialogPDF.value, true)
  assert.equal(p.mostrarDialogValidacions.value, false)
})
test('PDF: descàrrega amb ordre de pantalla, nom, opcions i desat posterior', async () => {
  const p = prepara()
  await p.generarPDFComplet()
  assert.deepEqual(p.links, [['PDF', 'complet_2026-04-20.pdf']])
  assert.deepEqual(p.peticions[1], ['complet', '2026-04-20', { format: 'hores', mida_lletra: 1.2, show_comments: true, show_hours: false, compress: false, include_substitutions: true, include_vigilancies: true, show_conflicts: true, blank_rows: false, ordre: 'professor' }])
  assert.equal(p.peticions[2][0], 'desaPreferencies')
  assert.equal(p.peticions[2][1].substitucions.includeVigilancies, true)
  assert.equal(p.generantPDF.value, false)
})
test('PDF: sense contingut no es fa cap petició, i la revisió demana els avisos de les seccions triades', async () => {
  const p = prepara()
  p.pdfConfig.value.includeSubstitutions = false
  p.pdfConfig.value.includeVigilancies = false
  await p.generarPDFComplet()
  assert.deepEqual(p.peticions, [])
  assert.equal(p.avisos[0].severity, 'warn')
  p.pdfConfig.value.includeSubstitutions = true
  await p.generarPDFComplet()
  assert.deepEqual(p.peticions[0], ['validacions', '2026-04-20', { params: { include_substitutions: true, include_vigilancies: false } }])
})
test('PDF: reassignació, recàrrega i canvis en ordre de les hores de l’XML', async () => {
  const p = prepara({ changes: [{ hora:'08:00', professor_absent:'Prof 1', abans:'', despres:'Prof 2' }, { hora:'09:00', professor_absent:'Prof 3', abans:'Prof 4', despres:'' }] })
  await p.reassignarProblematics()
  assert.deepEqual(p.peticions.slice(0,3), [['reassigna','2026-04-20'],['recarrega'],['validacions','2026-04-20',SECCIONS]])
  assert.deepEqual(p.reassignChanges.value, ['SUB 09:00 Prof 3: Prof 4 → —', 'SUB 08:00 Prof 1: — → Prof 2'])
  assert.equal(p.mostrarDialogValidacions.value, true)
  assert.equal(p.reassignantProblematics.value, false)
})
test('PDF complet amb importants exigeix confirmar abans de descarregar',async()=>{
 const p=prepara({validacio:{conflicts:['Problema important'],warnings:[],has_critical:true,total:1}})
 await p.generarPDFComplet();await p.continuarPDF()
 assert.deepEqual(p.links,[])
 p.confirmacioImportants.value=true;await p.continuarPDF()
 assert.equal(p.links.length,1)
 await p.generarPDFComplet();assert.equal(p.confirmacioImportants.value,false)
 await p.continuarPDF();assert.equal(p.links.length,1)
})


test('PDF complet: només informatius també obre la revisió i permet continuar', async () => {
  // Els informatius arriben separats del backend (pdf/validacions.py)
  const p = prepara({validacio:{conflicts:[], warnings:[], informatius:['Activitat sense grup'], total:1}})
  await p.generarPDFComplet()
  assert.equal(p.mostrarDialogValidacions.value, true)
  await p.continuarPDF()
  assert.equal(p.links.length, 1)
})
