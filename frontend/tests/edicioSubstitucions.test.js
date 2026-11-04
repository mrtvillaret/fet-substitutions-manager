import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBloc } from './support/carregaBlocSubstitucions.js'
const noms=['actualitzarSubstitut','actualitzarComentari','formatDisponibles','disponiblesDe','canviaCamp']
function prepara({error,resposta={updated_at:'nou'}}={}) {
  const peticions=[], confirmacions=[], conflictes=[], avisos=[]
  const dependents={dataISO:ref('2026-04-20'),totesAbsencies:ref([{hora:'08:00',substitut:'Prof 2',professor_absent:'Prof 3'}]),substitucionsFiltrades:ref([]),collator:ref(new Intl.Collator('ca')),toast:{add:m=>avisos.push(m)},t:x=>x,confirm:{require:c=>confirmacions.push(c)},obrirDialogConflicte:c=>conflictes.push(c),mostrarAvisos:x=>avisos.push(x),carregarSubstitucions:async()=>peticions.push(['recarrega'])}
  const dependencies={...dependents,dependents,computed,console:{error:()=>{}},apiSubstitucions:{actualitza:async(...a)=>{peticions.push(['actualitza',...a]);if(error && peticions.length===1)throw error;return resposta}}}
  const bloc=carregaBloc('useEdicioSubstitucions',[['// Si el professor triat ja substitueix','// Esborrar des de la fila']],noms,dependencies)
  return {...bloc,peticions,confirmacions,conflictes,avisos,dependents}
}
const fila=()=>({id:'1',hora:'08:00',professor_absent:'Prof 1',substitut:'Prof 2',updated_at:'abans',disponibles:[]})
test('edició: desa el substitut amb id, timestamp i mode silenciós i recarrega',async()=>{
  const p=prepara(),f=fila()
  await p.actualitzarSubstitut(f)
  assert.deepEqual(p.peticions,[['actualitza','2026-04-20','08:00','Prof 1',{id:'1',substitut:'Prof 2',updated_at:'abans',moure:false},{silent:true}],['recarrega']])
  assert.equal(f.updated_at,'nou')
  assert.equal(f.estat,'assignada')
})
test('edició: moure un substitut ja assignat exigeix confirmació',async()=>{
  const p=prepara(),f=fila();f.disponibles=[{professor:'Prof 2',ja_assignat:true}]
  p.actualitzarSubstitut(f)
  assert.deepEqual(p.peticions,[])
  await p.confirmacions[0].accept()
  assert.equal(p.peticions[0][4].moure,true)
  await p.confirmacions[0].reject()
  assert.equal(p.peticions.at(-1)[0],'recarrega')
})
test('edició: un conflicte conserva la fila i reintenta amb force i timestamp actual',async()=>{
  const p=prepara({error:{response:{status:409,data:{detail:{current_data:{updated_at:'servidor'}}}}}}),f=fila()
  await p.actualitzarSubstitut(f)
  assert.equal(p.conflictes.length,1)
  await p.conflictes[0]()
  assert.deepEqual(p.peticions[1],['actualitza','2026-04-20','08:00','Prof 1',{id:'1',substitut:'Prof 2',updated_at:'servidor',force:true,moure:false}])
})
test('edició: desar observacions conserva el substitut i el control de concurrència',async()=>{
  const p=prepara(),f={...fila(),comentaris:'Text'}
  await p.actualitzarComentari(f)
  assert.deepEqual(p.peticions,[['actualitza','2026-04-20','08:00','Prof 1',{id:'1',substitut:'Prof 2',comentaris:'Text',updated_at:'abans'},{silent:true}]])
  assert.equal(f.updated_at,'nou')
})
test('edició: opcions neutra i inactiva, ordre de disponibilitat i identitat per fila',()=>{
  const p=prepara(),f=fila()
  f.substitut='Prof inactiu'
  f.disponibles=[{professor:'Prof 4',categoria:1,de_baixa:true},{professor:'Prof 3',categoria:2},{professor:'Prof 2',categoria:1}]
  p.dependents.substitucionsFiltrades.value=[f]
  const reactiveFila=p.dependents.substitucionsFiltrades.value[0]
  const opcions=p.disponiblesDe(reactiveFila)
  assert.deepEqual(opcions.map(x=>x.value),['','Prof 2','Prof 3','Prof 4','Prof inactiu'])
  assert.equal(p.disponiblesDe(reactiveFila),opcions)
  assert.equal(opcions.at(-1).label,'Prof inactiu (common.inactive)')
})
