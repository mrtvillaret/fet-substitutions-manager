import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { dataIso } from '../src/dates.js'
import { carregaBloc } from './support/carregaBlocSubstitucions.js'
const noms=['avisosEncadenades','substitucions','substitucionsFiltrades','totesAbsencies','vigilanciesCount','professors','absenciesCobertes','horesDisponibles','loading','errorCarregaSubstitucions','ordreFiles','carregarSubstitucions','carregarTotesAbsencies','carregarProfessors','carregarHores','canviaOrdre']
function prepara(api = {}, revisions = [{data:{avisos_encadenades:['Avís del backend']}}]) {
  const peticions=[], avisos=[], guardat=[]
  const deferits=[]
  const dependents={dataTreball:ref(new Date('2026-04-20T10:00:00')),locale:ref('ca'),toast:{add:m=>avisos.push(m)},t:x=>x}
  const dependencies={apiPdf:{validacions:async()=>revisions.shift() || {data:{avisos_encadenades:[]}}},...dependents,dependents,ref,computed,dataIso,ambDataTreball:()=>({params:{data:'2026-04-20'}}),localStorage:{getItem:()=>null,setItem:(...a)=>guardat.push(a)},llistaVigilancies:async()=>[{},{}],apiHorari:{professorsHorari:async()=>({professors:['Prof 2','Prof 1'],absencies_cobertes:[]}),hores:async()=>({hores:['08:00','09:00']})},apiSubstitucions:{llista:async(...a)=>{peticions.push(['llista',...a]);return [{id:1,hora:'08:00'}]},llistaTotes:async(...a)=>{peticions.push(['totes',...a]);return [{id:2,hora:'09:00'}]},disponiblesEnBloc:(...a)=>{peticions.push(['disponibles',...a]);return new Promise(resolve=>deferits.push(resolve))},...api}}
  const bloc=carregaBloc('useDadesSubstitucions',[['// State','const mostrarDialogConflicte'],['// Computed','// Mètodes'],['// Mètodes','const anarAVigilancies'],['const carregarProfessors','const obrirDialogConflicte'],['const carregarHores','const mostrarAvisos']],noms,dependencies)
  return {...bloc,peticions,avisos,guardat,deferits,dependents}
}
const torn=()=>new Promise(resolve=>setTimeout(resolve, 0))
test('dades: la llista es publica tota alhora, quan arriben els disponibles',async()=>{
  const p=prepara()
  const carrega=p.carregarSubstitucions()
  await torn()
  assert.equal(p.loading.value,true)
  assert.deepEqual(p.substitucionsFiltrades.value,[])
  p.deferits[0]({'08:00':{disponibles:[{professor:'Prof 3'}]}})
  await carrega
  assert.deepEqual(p.substitucionsFiltrades.value,[{id:1,hora:'08:00',disponibles:[{professor:'Prof 3'}]}])
  assert.equal(p.substitucions.value,p.substitucionsFiltrades.value)
  assert.equal(p.vigilanciesCount.value,2)
  assert.equal(p.loading.value,false)
  assert.deepEqual(p.peticions,[['llista','2026-04-20','curs'],['totes','2026-04-20',{silent:true}],['disponibles','2026-04-20',['08:00']]])
})
test('dades: una petició antiga no trepitja el dia nou ni n’apaga la càrrega',async()=>{
  const p=prepara()
  const primera=p.carregarSubstitucions(); await torn()
  p.dependents.dataTreball.value=new Date('2026-04-21T10:00:00')
  const segona=p.carregarSubstitucions(); await torn()
  p.deferits[0]({'08:00':{disponibles:[{professor:'antic'}]}}); await primera
  assert.equal(p.loading.value,true)
  assert.deepEqual(p.substitucions.value,[])
  p.deferits[1]({'08:00':{disponibles:[{professor:'nou'}]}}); await segona
  assert.equal(p.substitucions.value[0].disponibles[0].professor,'nou')
  assert.equal(p.loading.value,false)
})
test('dades: recorda l’ordre i carrega professors i hores sense canviar la resposta',async()=>{
  const p=prepara({disponiblesEnBloc:async()=>({})})
  p.canviaOrdre('professor'); await torn()
  assert.deepEqual(p.guardat,[['substitucions_ordre','professor']])
  assert.deepEqual(p.peticions[0],['llista','2026-04-20','professor'])
  await p.carregarProfessors(); await p.carregarHores()
  assert.deepEqual(p.professors.value,['Prof 1','Prof 2'])
  assert.deepEqual(p.horesDisponibles.value,['08:00','09:00'])
})

test('dades: publica els avisos del backend i els retira en recarregar', async () => {
  const p = prepara({ disponiblesEnBloc: async () => ({}) })
  await p.carregarSubstitucions()
  assert.deepEqual(p.avisosEncadenades.value, ['Avís del backend'])
  await p.carregarSubstitucions()
  assert.deepEqual(p.avisosEncadenades.value, [])
})
