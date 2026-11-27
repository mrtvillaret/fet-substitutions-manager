import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { useConflicte } from '../src/composables/useConflicte.js'
function prepara({error,resposta={updated_at:'nou'}}={}) {
  const peticions=[], confirmacions=[], avisos=[]
  const dependents={dataISO:ref('2026-04-20'),totesAbsencies:ref([{hora:'08:00',substitut:'Prof 2',professor_absent:'Prof 3'}]),substitucions:ref([]),toast:{add:m=>avisos.push(m)},t:x=>x,confirm:{require:c=>confirmacions.push(c)},carregarSubstitucions:async()=>peticions.push(['recarrega'])}
  const conflicte=useConflicte(dependents.carregarSubstitucions)
  dependents.obreSiConflicte=conflicte.obreSiConflicte
  const dependencies={...dependents,dependents,computed,console:{error:()=>{}},apiSubstitucions:{actualitza:async(...a)=>{peticions.push(['actualitza',...a]);if(error && peticions.length===1)throw error;return resposta}}}
  const bloc=carregaBlocVista('useEdicioSubstitucions', dependencies)
  return {...bloc,peticions,confirmacions,conflicte,avisos,dependents}
}
const fila=()=>({id:'1',hora:'08:00',professor_absent:'Prof 1',substitut:'Prof 2',updated_at:'abans',disponibles:[]})
test('edició: desa el substitut amb id, timestamp i mode silenciós i recarrega',async()=>{
  const p=prepara(),f=fila()
  await p.canviaCamp(f,'substitut',f.substitut)
  assert.deepEqual(p.peticions,[['actualitza','2026-04-20','08:00','Prof 1',{id:'1',substitut:'Prof 2',updated_at:'abans',moure:false},{silent:true}],['recarrega']])
  assert.equal(f.updated_at,'nou')
  assert.deepEqual(p.avisos.map(a=>[a.severity,a.detail]),[['success','substitutions.messages.substituteAssigned']])
})
test('edició: si el substitut deixa una altra fila pendent, recarrega i ho diu',async()=>{
  const p=prepara({resposta:{updated_at:'nou',alliberades:[{professor_absent:'Prof 3'}]}})
  {const f=fila();await p.canviaCamp(f,'substitut',f.substitut)}
  assert.equal(p.peticions.at(-1)[0],'recarrega')
  assert.deepEqual(p.avisos.map(a=>[a.severity,a.detail,a.life]),[['info','substitutions.messages.substituteMoved',5000]])
})
test('edició: moure un substitut ja assignat exigeix confirmació',async()=>{
  const p=prepara(),f=fila();f.disponibles=[{professor:'Prof 2',ja_assignat:true}]
  p.canviaCamp(f,'substitut',f.substitut)
  assert.deepEqual(p.peticions,[])
  await p.confirmacions[0].accept()
  assert.equal(p.peticions[0][4].moure,true)
  await p.confirmacions[0].reject()
  assert.equal(p.peticions.at(-1)[0],'recarrega')
})
test('edició: un conflicte conserva la fila i reintenta amb force i timestamp actual',async()=>{
  const p=prepara({error:{response:{status:409,data:{detail:{current_data:{updated_at:'servidor'}}}}}}),f=fila()
  await p.canviaCamp(f,'substitut',f.substitut)
  assert.equal(p.conflicte.mostrarDialogConflicte.value,true)
  await p.conflicte.executarOverwrite()
  assert.deepEqual(p.peticions.slice(1),[['actualitza','2026-04-20','08:00','Prof 1',{id:'1',substitut:'Prof 2',updated_at:'servidor',force:true,moure:false}],['recarrega']])
})
test('edició: desar observacions conserva el substitut i el control de concurrència',async()=>{
  const p=prepara(),f={...fila(),comentaris:'Text'}
  await p.canviaCamp(f,'comentaris',f.comentaris)
  assert.deepEqual(p.peticions,[['actualitza','2026-04-20','08:00','Prof 1',{id:'1',substitut:'Prof 2',comentaris:'Text',updated_at:'abans'},{silent:true}]])
  assert.equal(f.updated_at,'nou')
})
test('edició: opcions neutra i inactiva, ordre de disponibilitat i identitat per fila',()=>{
  const p=prepara(),f=fila()
  f.substitut='Prof inactiu'
  f.disponibles=[{professor:'Prof 2',categoria:1},{professor:'Prof 3',categoria:2},{professor:'Prof 4',categoria:1,de_baixa:true}] // ja en l'ordre del backend
  p.dependents.substitucions.value=[f]
  const reactiveFila=p.dependents.substitucions.value[0]
  const opcions=p.disponiblesDe(reactiveFila)
  assert.deepEqual(opcions.map(x=>x.value),['','Prof 2','Prof 3','Prof 4','Prof inactiu'])
  assert.equal(p.disponiblesDe(reactiveFila),opcions)
  assert.equal(opcions.at(-1).label,'Prof inactiu (common.inactive)')
})
test('edició: si desar el substitut falla, avisa amb el text del backend i recarrega la fila de la BD',async()=>{
  const p=prepara({error:{response:{status:400,data:{detail:'Prof 2 té classe'}}}}),f=fila()
  await p.canviaCamp(f,'substitut','Prof 2')
  assert.deepEqual(p.avisos.map(a=>[a.severity,a.detail]),[['error','Prof 2 té classe']])
  assert.deepEqual(p.peticions.at(-1),['recarrega'])
})
test('edició: si desar les observacions falla, avisa sense recarregar (el text escrit es queda)',async()=>{
  const p=prepara({error:{response:{status:500,data:{}}}}),f=fila()
  await p.canviaCamp(f,'comentaris','Text')
  assert.deepEqual(p.avisos.map(a=>[a.severity,a.detail]),[['error','substitutions.errors.saveComment']])
  assert.equal(p.peticions.length,1)
  assert.equal(f.comentaris,'Text')
})
test('edició: el desplegable de substituts manté l’ordre del backend (també el desempat natural)',()=>{
  const p=prepara(),d=(professor,categoria,extra={})=>({professor,categoria,text_display:professor,...extra})
  for (const disponibles of [
    // sense empats de nom: l'ordre de sempre (de baixa i ocupats al final, per categoria)
    [d('Prof 7',0),d('Prof 3',1),d('Prof 5',2,{ocupat:true}),d('Prof 1',0,{de_baixa:true})],
    // empat: nom natural, com el backend (noms.ordre_alfabetic)
    [d('Prof 2',1),d('Prof 10',1)]
  ]) {
    const f={...fila(),substitut:'',disponibles}
    p.dependents.substitucions.value=[f]
    assert.deepEqual(p.disponiblesDe(p.dependents.substitucions.value[0]).map(o=>o.value),['',...disponibles.map(x=>x.professor)])
  }
})
for (const [camp,valor] of [['substitut','Prof 2'],['comentaris','Text']]) test(`edició: si la fila ja no existeix (${camp}), ho diu i torna a carregar la llista`,async()=>{
  const p=prepara({error:{response:{status:404,data:{detail:'No trobada',codi:'substitucio_id_no_trobat',params:{}}}}}),f=fila()
  await p.canviaCamp(f,camp,valor)
  assert.deepEqual(p.avisos.map(a=>[a.severity,a.detail]),[['warn','common.rowGone']])
  assert.deepEqual(p.peticions.at(-1),['recarrega'])
  assert.equal(p.conflicte.mostrarDialogConflicte.value,false)
})
