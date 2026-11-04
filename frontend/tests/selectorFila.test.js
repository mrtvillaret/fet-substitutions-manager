import {test} from 'node:test'
import assert from 'node:assert/strict'
import {ref,watch} from 'vue'
import {carregaBlocVista} from './support/carregaBlocVista.js'

test('les opcions de dues files idèntiques es guarden separades i exclouen només la pròpia',async()=>{
 const consultes=[]
 const dependents={dataISO:ref('2026-04-20'),professors:ref(['Prof 21']),vigilancies:ref([]),locale:ref('ca'),collator:ref(new Intl.Collator('ca')),t:x=>x}
 const apiVigilancies={disponiblesEnBloc:async(data,queries)=>{
   consultes.push(...queries)
   return Object.fromEntries(queries.map(q=>[q.tipus?`${q.hora}|${q.tipus}|${q.grups}|${q.aula}${q.vigilancia_id?'|fila:'+q.vigilancia_id:''}`:q.hora,[{value:'Prof 21',label:q.vigilancia_id==='1'?'Prof 21':'Prof 21 [JA ASSIGNAT]',ja_assignat:q.vigilancia_id!=='1',ordre_tipus:2}]]))
 }}
 const p=carregaBlocVista('','useDisponiblesVigilancies',[],[],{dependents,ref,watch,apiVigilancies})
 const files=['1','2'].map(id=>({id,hora:'10:00',tipus:'Prova',grups:'G1',aula:'A1'}))
 await p.carregarDisponiblesPerLlista(files)
 assert.deepEqual(consultes.filter(q=>q.tipus).map(q=>q.vigilancia_id),['1','2'])
 const de=id=>p.getDisponiblesPerHora('10:00','Prova','G1','A1',id).find(p=>p.value==='Prof 21')
 assert.equal(de('1').ja_assignat,false)
 assert.equal(de('2').ja_assignat,true)
 assert.equal(p.getVigilantLabel('10:00','Prof 21','Prova','G1','A1','1'),'Prof 21')
})
