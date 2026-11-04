import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref,computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara(){
  const peticions=[],confirmacions=[],listeners=[],dependents={t:x=>x,toast:{add(){}},confirm:{require:x=>confirmacions.push(x)},carregarAssignacions:async()=>peticions.push(['recarrega'])}
  const propostes=[{nivell:'N1',assignatura:'Prova',grup:'G1',titular:'Prof 1'},{nivell:'N2',assignatura:'Prova',grup:'G2',titular:'Prof 2',descartada:true},{nivell:'N1',assignatura:'Prova',grup:'G3',ja_existeix:true}]
  const apiExamens={previsualitzaImportacio:async()=>({propostes}),simulaImportacio:async x=>{peticions.push(['simula',x]);return{nivells_creats:[]}},importa:async x=>{peticions.push(['importa',x]);return{nivells_creats:[]}},simulaImportacioCsv:async x=>{peticions.push(['csv-simula',x.get('overwrite')]);return{}},importaCsv:async x=>{peticions.push(['csv-importa',x.get('overwrite')]);return{}}}
  const window={addEventListener:(...a)=>listeners.push(a),removeEventListener(){},open:(...a)=>peticions.push(['obre',...a])}
  const noms=['propostes','propostesSeleccionades','propostesFiltrades','filtreNivellImport','dragSelectAssignacions','obrirImportacio','previsualitzarImportacio','confirmarImportacioDefinitiva','mostrarResumPrevi','mostrarResumFinal','mostrarDialegImport','onFitxerCsvSeleccionat','exportarAssignacionsCsv']
  return {...carregaBlocVista('components/ConfiguracioExamensDialog.vue','useImportacioExamens',[['function useDragSelect','const props ='],['// ===== Importar des de','const carregarAfinitats']],noms,{...dependents,dependents,ref,computed,apiExamens,window,FormData,ruta:x=>'/'+x,onMounted:f=>f(),onUnmounted:()=>{}}),peticions,confirmacions,listeners}
}
test('Importació XML: preselecció, filtres i selecció per rang conserven descartades',async()=>{
  const p=prepara();await p.obrirImportacio();assert.deepEqual(p.propostesSeleccionades.value.map(x=>x._key),[0]);p.dragSelectAssignacions.onMouseDown(p.propostes.value[0],{});p.dragSelectAssignacions.onMouseDown(p.propostes.value[2],{shiftKey:true});assert.deepEqual(p.propostesSeleccionades.value.map(x=>x._key),[0,1,2]);p.filtreNivellImport.value=['N2'];p.dragSelectAssignacions.toggleAll(false);assert.deepEqual(p.propostesSeleccionades.value.map(x=>x._key),[0,2]);assert.equal(p.listeners[0][0],'mouseup')
})
test('Importació XML: simulació abans de confirmar, payload net i descartades',async()=>{
  const p=prepara();await p.obrirImportacio();await p.previsualitzarImportacio();assert.equal(p.mostrarResumPrevi.value,true);assert.deepEqual(p.peticions,[['simula',{propostes:[{nivell:'N1',assignatura:'Prova',grup:'G1',titular:'Prof 1'}],overwrite:false}]]);await p.confirmarImportacioDefinitiva();assert.deepEqual(p.peticions[1][1].descartades,[{assignatura:'Prova',grup:'G2',titular:'Prof 2'}]);assert.equal(p.mostrarDialegImport.value,false);assert.equal(p.mostrarResumFinal.value,true);assert.deepEqual(p.peticions.at(-1),['recarrega'])
})
test('Importació CSV: tria entre unir i sobreescriure, simulació i confirmació',async()=>{
  const p=prepara(),event={target:{files:[new Blob(['prova'])],value:'fitxer'}};p.onFitxerCsvSeleccionat(event);assert.equal(event.target.value,'');assert.deepEqual(p.peticions,[]);await p.confirmacions[0].reject();assert.deepEqual(p.peticions,[['csv-simula','false']]);await p.confirmarImportacioDefinitiva();assert.deepEqual(p.peticions.slice(1),[['csv-importa','false'],['recarrega']]);p.exportarAssignacionsCsv();assert.deepEqual(p.peticions.at(-1),['obre','/api/config/exportar-assignacions-csv','_blank'])
})
