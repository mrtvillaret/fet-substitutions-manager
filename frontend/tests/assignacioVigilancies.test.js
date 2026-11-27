import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { useConflicte } from '../src/composables/useConflicte.js'
function prepara(){
  const peticions=[],confirmacions=[],avisos=[]
  const dependents={dataISO:ref('2026-04-20'),vigilancies:ref([]),toast:{add:x=>avisos.push(x)},t:x=>x,confirm:{require:x=>confirmacions.push(x)},confirmaEsborrar:x=>confirmacions.push(x),carregarVigilancies:async()=>peticions.push(['recarrega'])}
  const apiVigilancies={assignaTitulars:async(...a)=>{peticions.push(['titulars',...a]);return{titulars_hora_lliure:[{vigilancia_id:1,titular:'Prof 1'}],vigilancies_sense_titular:[{vigilancia_id:2}],message:'fet'}},assignaPendents:async(...a)=>{peticions.push(['pendents',...a]);return{assigned_count:1,remaining_count:2,message:'fet'}},teOrdreManual:async()=>true,ordena:async(...a)=>{peticions.push(['ordena',...a]);return{message:'fet'}},llista:async()=>[{id:2}],neteja:async(...a)=>{peticions.push(['neteja',...a]);return{message:'fet'}},edita:async(...a)=>peticions.push(['edita',...a])}
  // El llistat es torna a llegir amb la funció real de l'edició (la que descarta un dia antic),
  // i el 404 d'una fila esborrada, amb la de l'edició (avís i recàrrega)
  const { recarregaLlistat, siJaNoExisteix }=carregaBlocVista('useEdicioVigilancies', {dependents,apiVigilancies,useConflicte,ref,adaptaVigilanciaAlNivell:null})
  return {...carregaBlocVista('useAssignacioVigilancies', {...dependents,dependents:{...dependents,recarregaLlistat,siJaNoExisteix},apiVigilancies,ref,computed,console:{error(){}}}),...dependents,peticions,confirmacions,avisos,apiVigilancies}
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
test('Assignació: el llistat ordenat que arriba d’un dia que ja no és a la pantalla no es publica',async()=>{
  const p=prepara()
  let resol
  p.apiVigilancies.llista=()=>new Promise(r=>{resol=r})
  p.apiVigilancies.teOrdreManual=async()=>false
  const ordre=p.ordenarPerHora()
  await new Promise(r=>setTimeout(r,0))
  p.dataISO.value='2026-04-21'
  resol([{id:99}]); await ordre
  assert.deepEqual(p.vigilancies.value,[])
  assert.equal(p.ordenant.value,false)
})
test('Assignació: si la vigilància del titular lliure ja no existeix, ho diu i torna a carregar',async()=>{
  const p=prepara()
  p.apiVigilancies.edita=async()=>{throw {response:{status:404,data:{detail:'Vigilància no trobada',codi:'vigilancia_no_trobada',params:{}}}}}
  p.titularsHoraLliure.value=[{vigilancia_id:1,titular:'Prof 1',hora:'08',grups:'G1'}]
  await p.posaTitularHoraLliure(p.titularsHoraLliure.value[0])
  assert.deepEqual(p.avisos.map(a=>[a.severity,a.detail]),[['warn','common.rowGone']])
  assert.deepEqual(p.peticions,[['recarrega']])
  assert.deepEqual(p.titularsHoraLliure.value,[])
  assert.equal(p.posantTitular.value,null)
})
