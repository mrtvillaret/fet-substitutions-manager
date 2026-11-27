import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed, watch, nextTick } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../src/pdfOpcions.js'
import { SENSE_NIVELL, opcionsNivellsPdf, parametresNivellsPdf, seleccioInicialNivellsPdf } from '../src/vigilanciesPdf.js'
import { dataIso } from '../src/dates.js'
function prepara(validacio = { conflicts: [], warnings: [], informatius: [], total: 0, has_critical: false }) {
  const peticions=[], links=[], avisos=[]
  const dependents={dataISO:ref('2026-04-20'),dataTreball:ref(new Date(2026,3,20)),nivells:ref(['N1']),toast:{add:x=>avisos.push(x)},t:x=>x}
  let senseNivell=2
  const apiPdf={preferencies:async(...a)=>{peticions.push(['preferencies',...a]);return{data:{vigilancies:{showHours:true}}}},desaPreferencies:async(...a)=>peticions.push(['desa',...a]),comptesSenseNivell:async(...a)=>{peticions.push(['comptes',...a]);return{data:{sense_nivell:senseNivell}}},validacions:async(...a)=>{peticions.push(['validacions',...a]);return{data:validacio}},vigilanciesDelDia:async(...a)=>{peticions.push(['pdf',...a]);return{data:'PDF'}},vigilanciesInterval:async(...a)=>{peticions.push(['interval',...a]);return{data:'PDF'}}}
  const dependencies={...dependents,dependents,ref,computed,watch,aplicaPreferencies,midaPerDefecte,parametresComuns,SENSE_NIVELL,opcionsNivellsPdf,parametresNivellsPdf,seleccioInicialNivellsPdf,dataIso,apiPdf,jaAvisat:()=>false,desaPdf:(_dades,nom)=>links.push(nom)}
  return {...carregaBlocVista('usePdfVigilancies', dependencies),peticions,links,avisos,setSenseNivell:n=>{senseNivell=n}}
}
test('PDF vigilàncies: opcions de nivell, preferències i revisió dels nivells triats', async()=>{
  const p=prepara({conflicts:['Aula ocupada'],warnings:[],informatius:['Vigilant amb classe'],total:2,has_critical:true})
  await p.mostrarDialegPDF();assert.deepEqual(p.pdfConfig.value.nivells,['N1',SENSE_NIVELL]);assert.equal(p.pdfConfig.value.showHours,true)
  await p.generarPDF();assert.deepEqual(p.peticions.find(x=>x[0]==='validacions').slice(1),['2026-04-20',{params:{nivells:'N1',inclou_sense_nivell:true}}])
  assert.equal(p.mostrarDialogValidacionsVig.value,true)
  p.cancelarPDFVig();assert.equal(p.mostrarDialogPDF.value,true);assert.deepEqual(p.links,[])
})
test('PDF vigilàncies: descàrrega del dia amb nom i paràmetres originals',async()=>{
  const p=prepara();await p.mostrarDialegPDF();await p.generarPDF()
  assert.deepEqual(p.links,['vigilancies_2026-04-20.pdf']);assert.equal(p.mostrarDialogPDF.value,false);assert.equal(p.generantPDF.value,false)
  assert.deepEqual(p.peticions.find(x=>x[0]==='pdf').slice(1),['2026-04-20',{format:'hores',mida_lletra:1.2,show_comments:true,show_hours:true,compress:false,nivells:'N1',inclou_sense_nivell:true,include_substitucions:false}])
  assert.equal(p.peticions.at(-1)[1].vigilancies.showHours,true)
})
test('PDF interval: dates requerides, selecció sense nivell i nom de descàrrega',async()=>{
  const p=prepara();await p.generarPDFInterval();assert.equal(p.avisos[0].severity,'warn');assert.deepEqual(p.peticions,[])
  await p.mostrarDialegInterval();await nextTick();await p.generarPDFInterval()
  assert.deepEqual(p.links,['vigilancies_interval_2026-04-20_a_2026-04-20.pdf']);assert.equal(p.generantPDFInterval.value,false)
  assert.equal(p.peticions.find(x=>x[0]==='interval')[1].inclou_sense_nivell,true)
  p.setSenseNivell(0);p.intervalConfig.value.dataFinal=new Date(2026,3,21);p.mostrarDialogInterval.value=true;await nextTick();await nextTick();assert.deepEqual(p.intervalConfig.value.nivells,['N1'])
})
test('PDF amb importants exigeix confirmar, i cada revisió reinicia la confirmació',async()=>{
 const p=prepara({conflicts:['Vigilant sense cobertura'],warnings:[],informatius:[],has_critical:true,total:1})
 await p.mostrarDialegPDF();await p.generarPDF();await p.continuarPDFVig()
 assert.deepEqual(p.links,[])
 p.confirmacioImportants.value=true;await p.continuarPDFVig()
 assert.equal(p.links.length,1)
 await p.mostrarDialegPDF();await p.generarPDF()
 assert.equal(p.confirmacioImportants.value,false)
 await p.continuarPDFVig();assert.equal(p.links.length,1)
})

test('PDF vigilàncies: només informatius també obre la revisió i permet continuar', async () => {
  const informatius = Array.from({length: 21}, (_, i) => `Informatiu ${i}`)
  const p = prepara({conflicts:[], warnings:[], informatius, total:21, has_critical:false})
  await p.mostrarDialegPDF();await p.generarPDF()
  assert.equal(p.mostrarDialogValidacionsVig.value, true)
  assert.deepEqual(p.links, [])
  await p.continuarPDFVig()
  assert.equal(p.links.length, 1)
})
