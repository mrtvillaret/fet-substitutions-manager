import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { adaptaVigilanciaAlNivell } from '../src/vigilanciesNivell.js'
function prepara({conflicte=false}={}){
  const peticions=[],avisos=[],confirmacions=[]
  const dependents={dataISO:ref('2026-04-20'),vigilancies:ref([]),seleccionades:ref([]),vigilanciesFiltrades:ref([]),hores:ref(['08']),opcionsFiles:ref({}),t:x=>x,toast:{add:x=>avisos.push(x)},confirmaEsborrar:x=>confirmacions.push(x),oblidaAjudes:()=>peticions.push(['oblida']),ressalta:x=>peticions.push(['ressalta',x]),carregarVigilancies:async()=>peticions.push(['recarrega']),carregarSubstitucionsCount:async()=>peticions.push(['recompte']),refrescarDisponiblesHora:async h=>peticions.push(['disponibles',h]),carregarDisponibles:async()=>[],getDisponiblesPerHora:()=>[]}
  const apiVigilancies={edita:async(...a)=>{peticions.push(['edita',...a]);if(conflicte&&!a[2].force)throw {response:{status:409,data:{detail:{current_data:{updated_at:'nou'}}}}};return{updated_at:'nou'}},llista:async()=>{peticions.push(['llista']);return dependents.vigilancies.value},crea:async(...a)=>{peticions.push(['crea',...a]);return{id:7}},esborra:async(...a)=>peticions.push(['esborra',...a]),desaOrdre:async(...a)=>peticions.push(['ordre',...a])}
  const noms=['mostrarDialogConflicte','canviaCamp','actualitzarVigilancia','executarOverwrite','gestionarConflicte','confirmarEliminar','confirmarEliminarSeleccionades','mostrarFormulariNova','propostaNova','afegirNovaVigilancia','creaVigilancia','afegirVigilanciaDesprés','mouFiles']
  return {...carregaBlocVista('views/VigilanciesView.vue','useEdicioVigilancies',[['const mostrarDialogConflicte','// State PDF'],['const obrirDialogConflicte','// Posa com a vigilant'],['// «Nova vigilància»','// Mètodes d\'assignació automàtica']],noms,{...dependents,dependents,apiVigilancies,adaptaVigilanciaAlNivell,ref,console:{error(){}}}),...dependents,peticions,avisos,confirmacions,apiVigilancies}
}
test('Edició vigilàncies: canvi d’hora recarrega i refresca amb ordre i ressalta',async()=>{
  const p=prepara(),fila={id:2,hora:'09',nivell:'N1',tipus:'--',grups:'G1',aula:'A1',vigilant:'',updated_at:'vell'}
  p.vigilancies.value=[fila];await p.actualitzarVigilancia(fila,{horaAbans:'08'});assert.equal(p.peticions[0][3].tipus,'');assert.equal(fila.updated_at,'nou');assert.deepEqual(p.peticions.slice(1),[['oblida'],['llista'],['disponibles','08'],['disponibles','09'],['ressalta',2],['recompte']])
})
test('Edició vigilàncies: conflicte conserva sobreescriptura amb timestamp actual',async()=>{
  const p=prepara({conflicte:true});await p.actualitzarVigilancia({id:2,hora:'08',nivell:'N1',tipus:'Prova',grups:'G1',aula:'A1'});assert.equal(p.mostrarDialogConflicte.value,true);await p.executarOverwrite();assert.equal(p.peticions[1][3].force,true);assert.equal(p.peticions[1][3].updated_at,'nou');assert.deepEqual(p.peticions.at(-1),['recarrega'])
})
test('Edició vigilàncies: proposta, alta i còpia mantenen ordre i camps',async()=>{
  const p=prepara();p.vigilanciesFiltrades.value=[{hora:'09',nivell:'N1',tipus:'Prova'}];p.afegirNovaVigilancia();assert.deepEqual(p.propostaNova.value,{hora:'09',nivell:'N1',tipus:'Prova'});await p.creaVigilancia(p.propostaNova.value);assert.equal(p.mostrarFormulariNova.value,false);assert.deepEqual(p.peticions.at(-1),['ressalta',7]);await p.afegirVigilanciaDesprés({id:3,hora:'09',nivell:'N1',tipus:'Prova',grups:'G1',aula:'A1'});assert.equal(p.peticions.at(-3)[2].despres_de,'3');assert.equal(p.peticions.at(-3)[2].vigilant,'')
})
test('Edició vigilàncies: esborrat seleccionat necessita confirmació i manté timestamps',async()=>{
  const p=prepara();p.seleccionades.value=[{id:1,updated_at:'a'},{id:2,updated_at:'b'}];p.confirmarEliminarSeleccionades();assert.deepEqual(p.peticions,[]);await p.confirmacions[0].accept();assert.deepEqual(p.peticions,[['esborra','2026-04-20',1,{updatedAt:'a',silent:true}],['esborra','2026-04-20',2,{updatedAt:'b',silent:true}],['recarrega']]);assert.deepEqual(p.seleccionades.value,[])
})

test('Edició vigilàncies: un esborrat parcial mostra un únic resum local',async()=>{
 const p=prepara(),peticions=[]
 p.apiVigilancies.esborra=async(...args)=>{peticions.push(args);throw Error('fallada')}
 p.seleccionades.value=[{id:1,updated_at:'a'},{id:2,updated_at:'b'}]
 p.confirmarEliminarSeleccionades()
 await p.confirmacions[0].accept()
 assert.equal(p.avisos.length,1)
 assert.equal(p.avisos[0].severity,'warn')
 assert.ok(peticions.every(p=>p[2].silent===true))
})
