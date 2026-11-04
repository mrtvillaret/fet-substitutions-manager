import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref,computed,watch } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara(){
  const peticions=[],confirmacions=[],avisos=[]
  const dependents={assignacions:ref([]),aules:ref(['A1']),toast:{add:x=>avisos.push(x)},t:x=>x,confirmaEsborrar:x=>confirmacions.push(x)}
  const apiExamens={assignacionsObsoletes:async()=>({assignacions:[]}),assignacions:async()=>({assignacions:[{id:1,assignatura:'Prova',grup:'N1A',titular:'Prof 1',aula:'A1'},{id:2,assignatura:'Prova',grup:'G1',titular:'',aula:'A2'}]}),creaAssignacio:async x=>{peticions.push(['crea',x]);return{id:7}},editaAssignacio:async(...a)=>peticions.push(['edita',...a]),esborraAssignacions:async x=>{peticions.push(['esborra',x]);return{eliminades:1}}}
  const noms=['assignacions','assignacionsFiltrades','filtreNivellAssignacions','filtreAssignaturaAssignacions','filtreAulaAssignacions','assignaturesUniques','aulesDelFiltre','carregarAssignacions','filtrarAssignacions','afegirFilaAssignacio','onCellEditComplete','eliminarAssignacio','eliminarAssignacionsFiltrades']
  // L'estat auxiliar dels catàlegs s'injecta quan ja s'ha extret el seu composable.
  const dependencies={...dependents,dependents,ref,computed,watch,apiExamens,console:{error(){}}}
  return {...dependents,...carregaBlocVista('components/ConfiguracioExamensDialog.vue','useAssignacionsExamens',[['// Assignacions Professor',['const totesAssignatures','const assignaturesUniques']],['const assignaturesUniques',['const professors =','const nextTempId']],['const nextTempId','const afinitats'],['watch(allLabel',['const carregarNivells','// Assignacions amb grups']],['// Assignacions amb grups','// ===== Importar des de']],noms,dependencies),peticions,confirmacions,avisos}
}
test('Assignacions: manté el filtre existent per prefix i intersecció d’aula i assignatura',async()=>{
  const p=prepara();await p.carregarAssignacions();assert.deepEqual(p.aulesDelFiltre.value,['A1','A2']);assert.deepEqual(p.assignaturesUniques.value,['Prova']);p.filtreNivellAssignacions.value='N1';p.filtrarAssignacions();assert.deepEqual(p.assignacionsFiltrades.value.map(a=>a.id),[1]);p.filtreAulaAssignacions.value='A2';p.filtrarAssignacions();assert.deepEqual(p.assignacionsFiltrades.value,[])
})
test('Assignacions: alta temporal només es desa quan té assignatura i grup',async()=>{
  const p=prepara();p.afegirFilaAssignacio();const fila=p.assignacions.value[0];assert.equal(fila.id,-1);await p.onCellEditComplete({data:fila,field:'assignatura',newValue:'Prova'});assert.deepEqual(p.peticions,[]);await p.onCellEditComplete({data:fila,field:'grup',newValue:'G1'});assert.equal(fila.id,7);assert.equal(fila._isNew,undefined);assert.deepEqual(p.peticions,[['crea',{assignatura:'Prova',grup:'G1',titular:'',aula:''}]])
})
test('Assignacions: esborrat local sense API i massiu només després de confirmar',async()=>{
  const p=prepara();p.afegirFilaAssignacio();await p.eliminarAssignacio(-1);assert.deepEqual(p.peticions,[]);await p.carregarAssignacions();p.eliminarAssignacionsFiltrades();assert.deepEqual(p.peticions,[]);await p.confirmacions[0].accept();assert.deepEqual(p.peticions,[['esborra',{ids:[1,2]}]])
})
