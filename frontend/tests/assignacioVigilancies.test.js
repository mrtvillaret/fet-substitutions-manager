import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara(){
  const peticions=[],confirmacions=[],avisos=[]
  const dependents={dataISO:ref('2026-04-20'),vigilancies:ref([]),toast:{add:x=>avisos.push(x)},t:x=>x,confirm:{require:x=>confirmacions.push(x)},confirmaEsborrar:x=>confirmacions.push(x),carregarVigilancies:async()=>peticions.push(['recarrega'])}
  const apiVigilancies={assignaTitulars:async(...a)=>{peticions.push(['titulars',...a]);return{titulars_hora_lliure:[{vigilancia_id:1,titular:'Prof 1'}],vigilancies_sense_titular:[{vigilancia_id:2}],message:'fet'}},assignaPendents:async(...a)=>{peticions.push(['pendents',...a]);return{assigned_count:1,remaining_count:2,message:'fet'}},teOrdreManual:async()=>true,ordena:async(...a)=>{peticions.push(['ordena',...a]);return{message:'fet'}},llista:async()=>[{id:2}],neteja:async(...a)=>{peticions.push(['neteja',...a]);return{message:'fet'}},edita:async(...a)=>peticions.push(['edita',...a])}
  const noms=['titularsHoraLliure','vigilanciesSenseTitular','posantTitular','assignantTitulars','assignantPendents','ordenant','posaTitularHoraLliure','assignarTitulars','assignarPendents','confirmarNetejar','ordenarPerHora']
  return {...carregaBlocVista('views/VigilanciesView.vue','useAssignacioVigilancies',[['const titularsHoraLliure','const seleccionades'],['const assignantTitulars','// State PDF'],['// Posa com a vigilant','// «Nova vigilància»'],['// Mètodes d\'assignació automàtica','// Funcions PDF']],noms,{...dependents,dependents,apiVigilancies,ref,computed,console:{error(){}}}),...dependents,peticions,confirmacions,avisos}
}
test('Assignació: titulars, avisos i assignació expressa del titular lliure',async()=>{
  const p=prepara();await p.assignarTitulars();assert.equal(p.titularsHoraLliure.value.length,1);assert.equal(p.vigilanciesSenseTitular.value.length,1);assert.equal(p.assignantTitulars.value,false);await p.posaTitularHoraLliure({vigilancia_id:1,titular:'Prof 1',hora:'08',grups:'G1'});assert.deepEqual(p.titularsHoraLliure.value,[]);assert.equal(p.posantTitular.value,null);assert.deepEqual(p.peticions.at(-2),['edita','2026-04-20',1,{vigilant:'Prof 1',updated_at:undefined}])
})
test('Assignació: dues fases, disponibles només en acceptar la confirmació',async()=>{
  const p=prepara();await p.assignarPendents();assert.deepEqual(p.peticions,[['pendents','2026-04-20',false],['recarrega']]);assert.equal(p.assignantPendents.value,false);await p.confirmacions[0].accept();assert.deepEqual(p.peticions.slice(2),[['pendents','2026-04-20',true],['recarrega']]);assert.equal(p.assignantPendents.value,false)
})
test('Assignació: ordre manual i neteja mantenen la confirmació prèvia',async()=>{
  const p=prepara();await p.ordenarPerHora();assert.deepEqual(p.peticions,[]);await p.confirmacions[0].accept();assert.deepEqual(p.vigilancies.value,[{id:2}]);assert.equal(p.ordenant.value,false);p.confirmarNetejar();await p.confirmacions[1].accept();assert.deepEqual(p.peticions.slice(-2),[['neteja','2026-04-20'],['recarrega']])
})
