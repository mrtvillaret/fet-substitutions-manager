import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara(){
  const peticions=[],avisos=[],confirmacions=[]
  const dependents={toast:{add:x=>avisos.push(x)},t:x=>x,confirmaEsborrar:x=>confirmacions.push(x),assignacions:ref([{id:1,assignatura:'Prova',grup:'G1',aula:'A1'}]),carregarAssignacions:async()=>peticions.push(['assignacions']),filtrarAssignacions:()=>peticions.push(['filtra'])}
  let quantes=2
  const apiExamens={nivells:async()=>({nivells:['N1']}),assignatures:async n=>{peticions.push(['assignatures',n]);return{assignatures:['Prova']}},grups:async n=>{peticions.push(['grups',n]);return{grups:['G1']}},aules:async()=>({aules:['A1']}),creaNivell:async x=>peticions.push(['nivell',x]),creaAssignatura:async(...a)=>peticions.push(['assignatura',...a]),creaGrup:async(...a)=>peticions.push(['grup',...a]),creaAula:async x=>peticions.push(['aula',x]),comptaAssignacions:async()=>({assignacions:quantes}),esborraElement:async(...a)=>{peticions.push(['esborra',...a]);return{assignacions_esborrades:a[1],assignacions:quantes}},editaElement:async(...a)=>peticions.push(['renom',...a])}
  const noms=['nivells','nouNivell','novaAssignatura','nouGrup','novaAula','nivellSeleccionat','nivellSeleccionatGrups','afegirNivell','afegirAssignatura','afegirGrup','afegirAula','esborrantAmbAssignacions','eliminarNivell','esborra','prepararRenomAssignatura','renomValor','reanomenarItem','mostrarDialogRenomItem','carregarProfessors','professors','horariPlanificacio']
  const dependencies={...dependents,dependents,ref,apiExamens,apiPlanificador:{horari:async()=>({data:{data_referencia:'2026-04-20'}})},carregaProfessorsHorari:async(...a)=>{peticions.push(['professors',...a]);return{professors:['Prof 1']}},console:{error(){}}}
  return {...carregaBlocVista('components/ConfiguracioExamensDialog.vue','useCatalegsExamens',[['const nivells =','// Assignacions Professor'],['const totesAssignatures','const assignaturesUniques'],['const professors =','const nextTempId'],['const carregarNivells','// Assignacions amb grups'],['const prepararRenomAssignatura','const carregarTot']],noms,dependencies),...dependents,peticions,avisos,confirmacions,setQuantes:x=>{quantes=x}}
}
test('Catàlegs: altes conserven majúscules només on correspon i el nivell seleccionat',async()=>{
  const p=prepara();p.nouNivell.value=' n2 ';await p.afegirNivell();p.nivellSeleccionat.value='N1';p.novaAssignatura.value=' prova ';await p.afegirAssignatura();p.nivellSeleccionatGrups.value='N1';p.nouGrup.value=' g2 ';await p.afegirGrup();p.novaAula.value=' a2 ';await p.afegirAula()
  assert(p.peticions.some(x=>x[0]==='nivell'&&x[1].codi==='N2'));assert(p.peticions.some(x=>x[0]==='assignatura'&&x[2].nom==='PROVA'));assert(p.peticions.some(x=>x[0]==='grup'&&x[2].codi==='g2'));assert(p.peticions.some(x=>x[0]==='aula'&&x[1].codi==='a2'))
})
test('Catàlegs: esborrat amb dependències espera la decisió i recarrega assignacions si cal',async()=>{
  const p=prepara();await p.eliminarNivell('N1');assert.deepEqual(p.esborrantAmbAssignacions.value,{tipus:'nivell',codi:'N1',quantes:2});assert.deepEqual(p.peticions,[]);await p.esborra('nivell','N1',true);assert.deepEqual(p.peticions.slice(0,2),[['esborra','/api/config/nivells/N1',true],['assignacions']]);p.setQuantes(0);await p.eliminarNivell('N1');assert.equal(p.confirmacions.length,1)
})
test('Catàlegs: renom propaga localment i refresca les llistes i els filtres',async()=>{
  const p=prepara();p.nivellSeleccionat.value='N1';p.prepararRenomAssignatura('Prova');p.renomValor.value=' Nova ';await p.reanomenarItem();assert.equal(p.assignacions.value[0].assignatura,'Nova');assert.deepEqual(p.peticions[0],['renom','/api/config/assignatures/N1/Prova',{nou_nom:'Nova'}]);assert.equal(p.mostrarDialogRenomItem.value,false);assert.deepEqual(p.peticions.slice(-2),[['assignacions'],['filtra']])
})
test('Catàlegs: professors de la data del planificador',async()=>{
  const p=prepara();await p.carregarProfessors();assert.deepEqual(p.peticions,[['professors',{params:{data:'2026-04-20'}}]]);assert.deepEqual(p.professors.value,['Prof 1'])
})
