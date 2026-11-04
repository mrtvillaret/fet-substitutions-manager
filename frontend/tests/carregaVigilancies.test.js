import { setImmediate } from 'node:timers'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, watch } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara() {
  const lots=[],llistes=[],configs=[],avisos=[]
  const pendent=llista=>()=>new Promise((resolve,reject)=>llista.push({resolve,reject}))
  const dependents={dataISO:ref('2026-04-20'),loading:ref(false),error:ref(null),vigilancies:ref([]),seleccionades:ref([]),substitucionsCount:ref(0),problemes:ref([]),carregarDisponiblesPerLlista:async(files,{vigent,alhora})=>{await new Promise((resolve,reject)=>lots.push({resolve,reject}));if(vigent())alhora()},publicaConfig:c=>configs.push(c),oblidaAjudes:()=>{},t:x=>x}
  const deps={dependents,watch,apiVigilancies:{configuracio:async()=>({}),analisi:async()=>[{tipus:"prova",files:["2"],missatge:"Avís"}],llista:pendent(llistes)},llistaSubstitucions:async()=>[],console:{error:(...a)=>avisos.push(a)}}
  return {...dependents,...carregaBlocVista('', 'useCarregaVigilancies',[],[],deps),lots,llistes,configs,avisos}
}
const tick=()=>new Promise(r=>setImmediate(r))
test('Vigilàncies: una resposta antiga de llista o disponibles no publica ni acaba la càrrega nova',async()=>{
 const p=prepara(),a=p.carregarVigilancies();p.llistes[0].resolve([{id:1}]);await tick()
 p.dataISO.value='2026-04-21';const b=p.carregarVigilancies();p.lots[0].resolve();await a
 assert.equal(p.loading.value,true);assert.deepEqual(p.vigilancies.value,[])
 p.llistes[1].resolve([{id:2}]);await tick();p.lots[1].resolve();await b
 assert.deepEqual(p.vigilancies.value,[{id:2}]);assert.equal(p.problemes.value[0].tipus,'prova');assert.equal(p.configs.length,1);assert.equal(p.loading.value,false)
 const c=p.carregarVigilancies();p.dataISO.value='2026-04-22';p.llistes[2].reject(Error('vell'));await c
 assert.equal(p.error.value,null);assert.equal(p.avisos.length,0)
})
test('Vigilàncies: error de disponibles deixa un sol avís i permet reintentar',async()=>{
 const p=prepara(),a=p.carregarVigilancies();p.llistes[0].resolve([{id:1}]);await tick();p.lots[0].reject(Error('prova'));await a
 assert.equal(p.error.value,'vigilancies.errors.load');assert.equal(p.avisos.length,1);assert.equal(p.loading.value,false)
 const b=p.carregarVigilancies();assert.equal(p.error.value,null);p.llistes[1].resolve([{id:2}]);await tick();p.lots[1].resolve();await b
 assert.deepEqual(p.vigilancies.value,[{id:2}]);assert.equal(p.error.value,null)
})
test('Vigilàncies: files i problemes es publiquen junts i no es mostren avisos antics després d’un error',async()=>{
 const p=prepara()
 p.problemes.value=[{tipus:'antic'}]
 const inici=p.carregarVigilancies();p.llistes[0].reject(Error('sense anàlisi'));await inici
 assert.deepEqual(p.problemes.value,[])
 assert.equal(p.error.value,'vigilancies.errors.load')
})
