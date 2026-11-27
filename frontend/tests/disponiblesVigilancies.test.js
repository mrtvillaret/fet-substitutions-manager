import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, watch } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara({fallarLot=false,fallarIndividual=false}={}) {
  const peticions=[],errors=[]
  const dependents={dataISO:ref('2026-04-20'),professors:ref(['Prof 1']),vigilancies:ref([]),locale:ref('ca'),t:x=>x}
  const apiVigilancies={disponibles:async(...a)=>{peticions.push(['individual',...a]);if(fallarIndividual)throw Error('prova');return [{value:'Prof 2',label:'2',ordre_tipus:2}]},disponiblesEnBloc:async(...a)=>{peticions.push(['lot',...a]);if(fallarLot)throw Error('prova');return {'08|Prova|G1|A1':[{value:'Prof 2',label:'2',ordre_tipus:1},{value:'Prof 3',label:'3',ordre_tipus:2}],'08':[{value:'Prof 4',label:'4',ordre_tipus:1}],'09':[]}}}
  const dependencies={...dependents,dependents,ref,watch,apiVigilancies,console:{error:(...a)=>errors.push(a)}}
  return {...carregaBlocVista('useDisponiblesVigilancies', dependencies),...dependents,peticions,errors}
}
test('Disponibles: claus normalitzades, cache específica i genèrica i opcions estables',async()=>{
  const p=prepara();await p.carregarDisponibles(' 08 ',' Prova ','G1',' A1 ');await p.carregarDisponibles('08','Prova','G1','A1');assert.equal(p.peticions.length,1)
  assert.equal(p.getVigilantLabel('08','Prof 2','Prova','G1','A1'),'2')
  const opcions=p.getDisponiblesPerHora('08','Prova','G1','A1');assert.equal(opcions[0].value,'');assert.equal(p.getDisponiblesPerHora('08','Prova','G1','A1'),opcions)
  p.locale.value='es';assert.notEqual(p.getDisponiblesPerHora('08','Prova','G1','A1'),opcions)
  // Guardià: la resposta d'una fila no omple la clau genèrica de l'hora
  assert.equal(p.disponiblesPerHora.value['08'],undefined);assert.deepEqual(p.getDisponiblesPerHora('08').map(x=>x.value),[''])
})
test('Disponibles: lot deduplicat, substitució de cache i publicació conjunta',async()=>{
  const p=prepara();let moment
  p.disponiblesPerHora.value={vella:[]}
  const files=[{hora:'08',tipus:'Prova',grups:'G1',aula:'A1'},{hora:'08',tipus:'Prova',grups:'G1',aula:'A1'}]
  await p.carregarDisponiblesPerLlista(files,{substitueix:true,alhora:()=>{moment=Object.keys(p.disponiblesPerHora.value)}})
  assert.deepEqual(moment,['vella']);assert.deepEqual(p.peticions[0],['lot','2026-04-20',[{hora:'08',tipus:'Prova',grups:'G1',aula:'A1'},{hora:'08',tipus:null,grups:null,aula:null}]])
  assert.equal(p.disponiblesPerHora.value.vella,undefined);assert.deepEqual(p.getDisponiblesPerHora('08','Prova','G1','A1').map(x=>x.value),['','Prof 2','Prof 3']);assert.deepEqual(p.getDisponiblesPerHora('08').map(x=>x.value),['','Prof 4'])
  await p.carregarDisponiblesPerLlista([],{substitueix:true,alhora:()=>{}});assert.deepEqual(p.disponiblesPerHora.value,{})
})
test('Disponibles: error de lot es propaga sense publicar ni fer crides individuals',async()=>{
  const p=prepara({fallarLot:true});let publicacions=0
  await assert.rejects(p.carregarDisponiblesPerLlista([{hora:'08'}],{substitueix:true,alhora:()=>publicacions++}))
  assert.equal(publicacions,0);assert.equal(p.peticions.length,1)
  assert.deepEqual(p.disponiblesPerHora.value,{})
})
test('Disponibles: descarta un lot del dia anterior i buida la cache',async()=>{
  const p=prepara();p.disponiblesPerHora.value={vella:[]}
  const carrega=p.carregarDisponiblesPerLlista([{hora:'08'}],{substitueix:true,alhora:()=>assert.fail('publicació antiga')})
  p.dataISO.value='2026-04-21';await carrega
  assert.deepEqual(p.disponiblesPerHora.value,{})
})
test('Disponibles: refrescar una hora preserva les opcions de les altres',async()=>{
  const p=prepara();p.disponiblesPerHora.value={'08':[],'08|X||':[],'10':[{value:'Prof 1'}]};p.vigilancies.value=[{hora:'08'}]
  const altres=p.getDisponiblesPerHora('10');await p.refrescarDisponiblesHora('08');assert.equal(p.getDisponiblesPerHora('10'),altres);assert.equal(p.disponiblesPerHora.value['08|X||'],undefined)
})
test('Disponibles: el desplegable de vigilants manté l’ordre del backend (també el desempat natural)',()=>{
  const p=prepara()
  const d=(value,ordre_tipus,categoria)=>({value,label:value,ordre_tipus,categoria})
  p.disponiblesPerHora.value={'08':[d('Prof 9',0,3),d('Prof 1',2,0),d('Prof 2',2,1),d('Prof 10',2,1)]}
  assert.deepEqual(p.getDisponiblesPerHora('08').map(x=>x.value),['','Prof 9','Prof 1','Prof 2','Prof 10'])
})
