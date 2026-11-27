import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed, watch, nextTick } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara(){
  const idioma=ref('ca'),dependents={vigilancies:ref([{id:3,nivell:'N1',hora:'08',aula:'A2',vigilant:'Prof 1'},{id:1,nivell:'N1',hora:'09',aula:'A1',vigilant:' '},{id:2,nivell:'N2',hora:'08',aula:'A2',vigilant:''}]),aules:ref(['A10','A3','A1']),t:x=>idioma.value+':'+x}
  return {...carregaBlocVista('useFiltresVigilancies', {...dependents,dependents,ref,computed,watch}),idioma}
}
test('Filtres: intersecció, recomptes i ordre original de les files',()=>{
  const p=prepara();assert.deepEqual(p.vigilanciesFiltrades.value.map(v=>v.id),[3,1,2]);assert.equal(p.vigilanciesAssignades.value,1);assert.equal(p.vigilanciesPendents.value,2)
  p.filtreNivell.value='N1';p.filtreHora.value='09';assert.deepEqual(p.vigilanciesFiltrades.value.map(v=>v.id),[1]);assert.equal(p.filtresActius.value,true)
  p.filtreEstat.value=p.statusOptions.value[1];assert.deepEqual(p.vigilanciesFiltrades.value,[])
  assert.deepEqual(p.aulesDelFiltre.value,['A1','A2','A3','A10']) // natural (src/ordreAlfabetic.js)
})
test('Filtres: canvi d’idioma actualitza només els valors neutres',async()=>{
  const p=prepara();p.filtreAula.value='A2';p.idioma.value='es';await nextTick();assert.equal(p.filtreHora.value,p.allLabel.value);assert.equal(p.filtreAula.value,'A2');assert.equal(p.etiquetaFiltre('hour',p.allLabel.value),'es:vigilancies.filters.hourAll')
})
