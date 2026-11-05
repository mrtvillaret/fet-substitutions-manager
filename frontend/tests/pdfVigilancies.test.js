import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed, watch, nextTick } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../src/pdfOpcions.js'
import { SENSE_NIVELL, opcionsNivellsPdf, parametresNivellsPdf, seleccioInicialNivellsPdf } from '../src/vigilanciesPdf.js'
import { dataIso } from '../src/dates.js'
const noms = ['mostrarDialogPDF','mostrarDialogInterval','generantPDF','generantPDFInterval','mostrarDialogValidacionsVig','validacionsVig','conflictesVigFiltrats','warningsVigFiltrats','pdfConfig','intervalConfig','senseNivellInterval','mostrarDialegPDF','mostrarDialegInterval','generarPDF','continuarPDFVig','cancelarPDFVig','generarPDFInterval']
function prepara(validacio = { conflicts: [], warnings: [] }) {
  const peticions=[], links=[], avisos=[]
  const dependents={dataISO:ref('2026-04-20'),dataTreball:ref(new Date(2026,3,20)),nivells:ref(['N1']),vigilancies:ref([{id:'1',nivell:'N1'}]),toast:{add:x=>avisos.push(x)},t:x=>x}
  let senseNivell=2
  const apiPdf={preferencies:async(...a)=>{peticions.push(['preferencies',...a]);return{data:{vigilancies:{showHours:true}}}},desaPreferencies:async(...a)=>peticions.push(['desa',...a]),comptesSenseNivell:async(...a)=>{peticions.push(['comptes',...a]);return{data:{sense_nivell:senseNivell}}},validacions:async(...a)=>{peticions.push(['validacions',...a]);return{data:validacio}},descarrega:async(...a)=>{peticions.push(['pdf',...a]);return{data:'PDF'}}}
  const dependencies={...dependents,dependents,ref,computed,watch,aplicaPreferencies,midaPerDefecte,parametresComuns,SENSE_NIVELL,opcionsNivellsPdf,parametresNivellsPdf,seleccioInicialNivellsPdf,dataIso,apiPdf,jaAvisat:()=>false,Blob,URLSearchParams,window:{URL:{createObjectURL:()=> 'blob:prova',revokeObjectURL(){}}},document:{createElement:()=>{const l={click:()=>links.push(l.download)};return l},body:{appendChild(){},removeChild(){}}}}
  return {...carregaBlocVista('views/VigilanciesView.vue','usePdfVigilancies', [['// State PDF','// Configuració'],['const senseNivellDia','// Sense cap nivell configurat'],['// Funcions PDF','// Watch per canvis de data']],noms,dependencies),peticions,links,avisos,setSenseNivell:n=>{senseNivell=n}}
}
test('PDF vigilàncies: opcions de nivell, preferències i retorn de validacions filtrades', async()=>{
  const p=prepara({conflicts:['Aula ocupada','Absent'],warnings:['Vigilant amb classe','Altre'],problemes_vigilancies:[{tipus:'sense_aula',gravetat:'important',files:['1'],missatge:'Aula ocupada'},{tipus:'classe_coberta',gravetat:'informacio',files:['1'],missatge:'Vigilant amb classe'}]})
  await p.mostrarDialegPDF();assert.deepEqual(p.pdfConfig.value.nivells,['N1',SENSE_NIVELL]);assert.equal(p.pdfConfig.value.showHours,true)
  await p.generarPDF();assert.deepEqual(p.conflictesVigFiltrats.value,['Aula ocupada']);assert.deepEqual(p.warningsVigFiltrats.value,[]);assert.deepEqual(p.informatiusVigFiltrats.value,['Vigilant amb classe']);assert.equal(p.mostrarDialogValidacionsVig.value,true)
  p.cancelarPDFVig();assert.equal(p.mostrarDialogPDF.value,true);assert.deepEqual(p.links,[])
})
test('PDF vigilàncies: descàrrega del dia amb nom i paràmetres originals',async()=>{
  const p=prepara();await p.mostrarDialegPDF();await p.generarPDF()
  assert.deepEqual(p.links,['vigilancies_2026-04-20.pdf']);assert.equal(p.mostrarDialogPDF.value,false);assert.equal(p.generantPDF.value,false)
  assert.equal(p.peticions.find(x=>x[0]==='pdf')[1],'/api/pdf/vigilancies/2026-04-20?format=hores&mida_lletra=1.2&show_comments=true&show_hours=true&compress=false&nivells=N1&inclou_sense_nivell=true&include_substitucions=false')
  assert.equal(p.peticions.at(-1)[1].vigilancies.showHours,true)
})
test('PDF interval: dates requerides, selecció sense nivell i nom de descàrrega',async()=>{
  const p=prepara();await p.generarPDFInterval();assert.equal(p.avisos[0].severity,'warn');assert.deepEqual(p.peticions,[])
  await p.mostrarDialegInterval();await nextTick();await p.generarPDFInterval()
  assert.deepEqual(p.links,['vigilancies_interval_2026-04-20_a_2026-04-20.pdf']);assert.equal(p.generantPDFInterval.value,false)
  assert(p.peticions.find(x=>x[0]==='pdf')[1].includes('inclou_sense_nivell=true'))
  p.setSenseNivell(0);p.intervalConfig.value.dataFinal=new Date(2026,3,21);p.mostrarDialogInterval.value=true;await nextTick();await nextTick();assert.deepEqual(p.intervalConfig.value.nivells,['N1'])
})
for (const missatge of ['Duplicate invigilator','Vigilante repetido','Sorvegliante duplicato']) test(`PDF filtra per tipus: ${missatge}`,async()=>{
 const p=prepara({conflicts:['Problema aliè'],warnings:[missatge],has_critical:true,problemes_vigilancies:[
  {tipus:'vigilant_repetit',gravetat:'avis',files:['1','exclosa'],missatge},
  {tipus:'sense_vigilant',gravetat:'important',files:['exclosa'],missatge:'No incloure'}
 ]})
 await p.mostrarDialegPDF();await p.generarPDF()
 assert.deepEqual(p.warningsVigFiltrats.value,[missatge]);assert.deepEqual(p.conflictesVigFiltrats.value,[])
 assert.equal(p.validacionsVig.value.has_critical,false);assert.equal(p.mostrarDialogValidacionsVig.value,true)
 assert.deepEqual(p.links,[])
})
test('PDF amb importants exigeix confirmar, i cada revisió reinicia la confirmació',async()=>{
 const p=prepara({conflicts:['Vigilant sense cobertura'],warnings:[],has_critical:true,total:1,problemes_vigilancies:[{tipus:'vigilant_absent_sense_cobertura',gravetat:'important',files:['1'],missatge:'Vigilant sense cobertura'}]})
 await p.mostrarDialegPDF();await p.generarPDF();await p.continuarPDFVig()
 assert.deepEqual(p.links,[])
 p.confirmacioImportants.value=true;await p.continuarPDFVig()
 assert.equal(p.links.length,1)
 await p.mostrarDialegPDF();await p.generarPDF()
 assert.equal(p.confirmacioImportants.value,false)
 await p.continuarPDFVig();assert.equal(p.links.length,1)
})

test('PDF vigilàncies: només informatius, sense límit i filtrats pels nivells triats', async () => {
  const problemes = Array.from({length: 21}, (_, i) => ({tipus:'activitat_sense_grup', gravetat:'informacio', files:['1'], missatge:`Informatiu ${i}`}))
  problemes.push({tipus:'classe_coberta', gravetat:'informacio', files:['exclosa'], missatge:'No incloure'})
  const p = prepara({conflicts:[], warnings:problemes.map(p => p.missatge), problemes_vigilancies:problemes})
  await p.mostrarDialegPDF();await p.generarPDF()
  assert.equal(p.informatiusVigFiltrats.value.length, 21)
  assert.deepEqual(p.warningsVigFiltrats.value, [])
  assert.deepEqual(p.conflictesVigFiltrats.value, [])
  assert.equal(p.validacionsVig.value.has_critical, false)
  assert.equal(p.mostrarDialogValidacionsVig.value, true)
  assert.deepEqual(p.links, [])
  await p.continuarPDFVig()
  assert.equal(p.links.length, 1)
})
