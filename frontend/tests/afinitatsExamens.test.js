import { test } from 'node:test'
import assert from 'node:assert/strict'
import { computed, ref } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara(){
  const peticions=[],avisos=[],dependents={t:x=>x,toast:{add:x=>avisos.push(x)}}
  const apiExamens={afinitats:async()=>({afinitats:[{base:'N1',ordre:['N2','N3']}]}),desaAfinitats:async x=>{peticions.push(x);return{afinitats:x.afinitats}}}
  return {...carregaBlocVista('components/ConfiguracioExamensDialog.vue','useAfinitatsExamens',[['const afinitats =',['watch(allLabel','// Assignacions amb grups']],['const carregarAfinitats','// ===== FUNCIONS REANOMENAR']],['afinitats','teCanvis','carregarAfinitats','afegirFilaAfinitat','eliminarFilaAfinitat','desarAfinitats'],{...dependents,dependents,ref,computed,apiExamens}),peticions,avisos}
}
test('Afinitats: lectura, edició i desat mantenen normalització i ordre',async()=>{
  const p=prepara();await p.carregarAfinitats();assert.deepEqual(p.afinitats.value,[{base:'N1',ordreText:'N2,N3'}]);p.afegirFilaAfinitat();p.afinitats.value.push({base:' N2 ',ordreText:' N3, ,N1 '});await p.desarAfinitats();assert.deepEqual(p.peticions,[{afinitats:[{base:'N1',ordre:['N2','N3']},{base:'N2',ordre:['N3','N1']}]}]);p.eliminarFilaAfinitat(0);assert.deepEqual(p.afinitats.value,[{base:'N2',ordreText:'N3,N1'}]);assert.equal(p.avisos[0].severity,'success')
})

test('Afinitats: canvis sense desar des de la càrrega fins al desat', async () => {
  const p = prepara()
  await p.carregarAfinitats()
  assert.equal(p.teCanvis.value, false)
  p.afinitats.value[0].ordreText = 'N3'
  assert.equal(p.teCanvis.value, true)
  await p.desarAfinitats()
  assert.equal(p.teCanvis.value, false)
  p.afegirFilaAfinitat()
  assert.equal(p.teCanvis.value, true)
})
