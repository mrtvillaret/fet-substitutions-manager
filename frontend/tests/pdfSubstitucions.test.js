import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBloc } from './support/carregaBlocSubstitucions.js'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../src/pdfOpcions.js'

const noms = ['mostrarDialogPDF', 'mostrarDialogValidacions', 'generantPDF', 'reassignantProblematics', 'reassignChanges', 'validacions', 'warningsFiltrats', 'totalIssuesFiltrats', 'pdfConfig', 'mostrarDialegPDF', 'carregarPreferenciesPdf', 'generarPDFComplet', 'continuarPDF', 'cancelarPDF', 'reassignarProblematics']
function prepara({ validacio = { conflicts: [], warnings: [], total: 0 }, changes = [] } = {}) {
  const peticions = [], avisos = [], links = []
  const apiPdf = {
    preferencies: async (...args) => { peticions.push(['preferencies', ...args]); return { data: { substitucions: { format: 'dies', blankRows: true } } } },
    validacions: async (...args) => { peticions.push(['validacions', ...args]); return { data: validacio } },
    descarrega: async (...args) => { peticions.push(['descarrega', ...args]); return { data: 'PDF' } },
    desaPreferencies: async (...args) => { peticions.push(['desaPreferencies', ...args]) }
  }
  const dependents = { dataISO: ref('2026-04-20'), ordreFiles: ref('professor'), horesDisponibles: ref(['09:00','08:00']), collator: ref(new Intl.Collator('ca')), toast: { add: m => avisos.push(m) }, t: x => x, mostrarAvisos: x => avisos.push(x), carregarSubstitucions: async () => peticions.push(['recarrega']) }
  const dependencies = { ...dependents, dependents, ref, computed, aplicaPreferencies, midaPerDefecte, parametresComuns, apiPdf, jaAvisat: () => false, apiSubstitucions: { reassignaProblematiques: async (...args) => { peticions.push(['reassigna', ...args]); return { changes, cleared: changes.length } } }, URLSearchParams, Blob, window: { URL: { createObjectURL: () => 'blob:prova', revokeObjectURL: x => peticions.push(['revoca', x]) } }, document: { createElement: () => { const link = { click: () => links.push([link.href, link.download]) }; return link }, body: { appendChild() {}, removeChild() {} } } }
  const bloc = carregaBloc('usePdfSubstitucions', [['// PDF export', '// Computed'], ['// PDF Functions', '// Watch per canvis de data']], noms, dependencies)
  return { ...bloc, peticions, avisos, links }
}
test('PDF: preferències, filtratge dels avisos i retorn del diàleg de validació', async () => {
  const p = prepara({ validacio: { conflicts: ['conflicte'], warnings: ['⚠️ prioritat X', 'avís útil'], total: 3, has_critical: true } })
  await p.mostrarDialegPDF()
  assert.equal(p.pdfConfig.value.format, 'dies')
  assert.equal(p.mostrarDialogPDF.value, true)
  await p.generarPDFComplet()
  assert.equal(p.mostrarDialogValidacions.value, true)
  assert.equal(p.generantPDF.value, false)
  assert.deepEqual(p.warningsFiltrats.value, ['avís útil'])
  assert.equal(p.totalIssuesFiltrats.value, 2)
  assert.deepEqual(p.peticions, [['preferencies'], ['validacions', '2026-04-20']])
  p.cancelarPDF()
  assert.equal(p.mostrarDialogPDF.value, true)
  assert.equal(p.mostrarDialogValidacions.value, false)
})
test('PDF: descàrrega amb ordre de pantalla, nom, opcions i desat posterior', async () => {
  const p = prepara()
  await p.generarPDFComplet()
  assert.deepEqual(p.links, [['blob:prova', 'complet_2026-04-20.pdf']])
  assert.equal(p.peticions[1][1], '/api/pdf/complete/2026-04-20?format=hores&mida_lletra=1.2&show_comments=true&show_hours=false&compress=false&include_substitutions=true&include_vigilancies=true&show_conflicts=true&blank_rows=false&ordre=professor')
  assert.deepEqual(p.peticions[1][2], { responseType: 'blob' })
  assert.equal(p.peticions[3][0], 'desaPreferencies')
  assert.equal(p.peticions[3][1].substitucions.includeVigilancies, true)
  assert.equal(p.generantPDF.value, false)
})
test('PDF: sense contingut no es fa cap petició', async () => {
  const p = prepara()
  p.pdfConfig.value.includeSubstitutions = false
  p.pdfConfig.value.includeVigilancies = false
  await p.generarPDFComplet()
  assert.deepEqual(p.peticions, [])
  assert.equal(p.avisos[0].severity, 'warn')
})
test('PDF: reassignació, recàrrega i canvis en ordre de les hores de l’XML', async () => {
  const p = prepara({ changes: [{ hora:'08:00', professor_absent:'Prof 1', abans:'', despres:'Prof 2' }, { hora:'09:00', professor_absent:'Prof 3', abans:'Prof 4', despres:'' }] })
  await p.reassignarProblematics()
  assert.deepEqual(p.peticions.slice(0,3), [['reassigna','2026-04-20'],['recarrega'],['validacions','2026-04-20']])
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


test('PDF complet: informatius separats dels avisos per gravetat', async () => {
  const p = prepara({ validacio: {conflicts: [], warnings: ['Classe coberta', 'Avís útil'], total: 2,
    problemes_vigilancies: [{gravetat: 'informacio', missatge: 'Classe coberta'}]} })
  await p.generarPDFComplet()
  assert.deepEqual(p.warningsFiltrats.value, ['Avís útil'])
  assert.deepEqual(p.informatiusFiltrats.value, ['Classe coberta'])
  assert.equal(p.totalIssuesFiltrats.value, 2)
  assert.equal(p.mostrarDialogValidacions.value, true)
})

test('PDF complet: només informatius també obre la revisió i permet continuar', async () => {
  const p = prepara({validacio:{conflicts:[], warnings:['Activitat sense grup'], total:1,
    problemes_vigilancies:[{gravetat:'informacio',missatge:'Activitat sense grup'}]}})
  await p.generarPDFComplet()
  assert.deepEqual(p.warningsFiltrats.value, [])
  assert.deepEqual(p.informatiusFiltrats.value, ['Activitat sense grup'])
  assert.equal(p.totalIssuesFiltrats.value, 1)
  assert.equal(p.mostrarDialogValidacions.value, true)
  await p.continuarPDF()
  assert.equal(p.links.length, 1)
})
