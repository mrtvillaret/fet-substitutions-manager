import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed, watch, nextTick } from 'vue'
import { dataIso } from '../src/dates.js'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara() {
  const peticions = [], avisos = [], confirmacions = [], cos = { style: {} }
  const dependents = { dataISO: ref('2026-04-24'), professors: ref(['Prof 1', 'Prof 2']), absenciesCobertes: ref([{ professor:'Prof 3', data_final:'2026-04-30' }]), totesAbsencies: ref([{ professor_absent:'Prof 1', hora:'08:00', tipus_absencia:'ABSENCIA', updated_at:'ara' }, { professor_absent:'Prof 1', hora:'09:00', tipus_absencia:'ENCADENADA' }]), horesDisponibles: ref(['08:00','09:00','10:00']), loading: ref(false), toast: {add: m => avisos.push(m)}, t: x => x, confirmaEsborrar: c => confirmacions.push(c), obreSiConflicte: () => false, carregarSubstitucions: async () => peticions.push(['recarrega']), carregarTotesAbsencies: async () => {} }
  const deps = { ...dependents, dependents, ref, computed, watch, nextTick, onBeforeUnmount: () => {}, dataIso, avisaSubstitutsTrets: () => {}, document: {body: cos}, apiSubstitucions: { horesProfessor: async (...a) => {peticions.push(['hores',...a]); return {hores_amb_classe:['08:00'],hores_al_centre:['08:00','09:00']}}, desaAbsencies: async (...a) => {peticions.push(['desa',...a]); return {}} } }
  const bloc = carregaBlocVista('useAbsenciesSubstitucions', deps)
  return {...bloc, peticions, avisos, confirmacions, cos, dependents}
}
test('absències: professor cobert al final i encadenades fora dels recomptes reals', () => {
  const p=prepara()
  assert.deepEqual(p.professorsAmbInfo.value, [{nom:'Prof 1',teAbsencies:true,numHores:1,coberta:false},{nom:'Prof 2',teAbsencies:false,numHores:0,coberta:false},{nom:'Prof 3',teAbsencies:false,numHores:0,coberta:true,finsA:'30/04'}])
  assert.deepEqual(p.absenciesDelDiaAgrupades.value, [{professor:'Prof 1',horesAbsencia:['08:00'],horesServei:[]}])
})
test('absències: selecció, hores excloents, rang sense caps de setmana i reinici en tancar', async () => {
  const p=prepara()
  p.obrirDialogNou()
  assert.equal(p.cos.style.overflow,'hidden')
  await p.editarAbsenciesProfessor({professor_absent:'Prof 1'})
  await nextTick()
  assert.deepEqual(p.gestioAbsencies.value.horesAbsencia,['08:00'])
  assert.deepEqual(p.horesAlCentre.value,['08:00','09:00'])
  p.toggleTotesServei()
  assert.deepEqual(p.gestioAbsencies.value.horesServei,['09:00','10:00'])
  p.toggleTotesAbsencia()
  assert.deepEqual(p.gestioAbsencies.value.horesAbsencia,[])
  p.modeRang.value=true; p.dataFinalRang.value='2026-04-27'
  assert.deepEqual(p.datesDelRang.value,['2026-04-24','2026-04-27'])
  p.tancarDialogGestio()
  assert.equal(p.cos.style.overflow,'')
  assert.equal(p.modeRang.value,false)
  assert.equal(p.dropdownProfValue.value,null)
})
test('absències: desat diari amb updated_at_map, recàrrega i confirmació abans de buidar', async () => {
  const p=prepara()
  await p.editarAbsenciesProfessor({professor_absent:'Prof 1'})
  await p.afegirAbsenciaImmediata()
  assert.deepEqual(p.peticions.slice(1), [['desa','2026-04-24','Prof 1',{hores_absencia:['08:00'],hores_servei:[],updated_at_map:{'08:00':'ara'}},{silent:true}],['recarrega']])
  p.confirmarEliminarAbsenciesProf('Prof 1')
  assert.equal(p.confirmacions.length,1)
  assert.equal(p.peticions.length,3)
})
test('absències: el rang desa cada dia amb mapa buit i torna al mode diari', async () => {
  const p=prepara()
  p.seleccionarProfessorDropdown({value:{nom:'Prof 1'}})
  p.modeRang.value=true; p.dataFinalRang.value='2026-04-27'
  await p.afegirAbsenciaImmediata()
  assert.deepEqual(p.peticions.filter(p=>p[0]==='desa'), ['2026-04-24','2026-04-27'].map(d=>['desa',d,'Prof 1',{hores_absencia:['08:00'],hores_servei:[],updated_at_map:{}},{silent:true}]))
  assert.equal(p.modeRang.value,false)
})
test('absències: una sola regla de quines files són absències del professor (recompte, edició i selecció)', async () => {
  const p=prepara()
  p.dependents.totesAbsencies.value = [
    { professor_absent:'Prof 1', hora:'10:00', tipus_absencia:'ABSENCIA' },
    { professor_absent:'Prof 1', hora:'09:00', tipus_absencia:'SERVEI' },
    { professor_absent:'Prof 1', hora:'08:00', tipus_absencia:'VIGILANCIA_ABSENT' },
    { professor_absent:'Prof 1', hora:'08:00', tipus_absencia:'VIGILANCIA' },
    { professor_absent:'Prof 1', hora:'09:00', tipus_absencia:'ENCADENADA' }
  ]
  assert.equal(p.professorsAmbInfo.value[0].numHores, 3)
  const hores = () => [[...p.gestioAbsencies.value.horesAbsencia].sort(), p.gestioAbsencies.value.horesServei]
  await p.editarAbsenciesProfessor({professor_absent:'Prof 1'})
  assert.deepEqual(hores(), [['08:00','10:00'],['09:00']])
  p.tancarDialogGestio()
  p.seleccionarProfessorDropdown({value:{nom:'Prof 1'}})
  assert.deepEqual(hores(), [['08:00','10:00'],['09:00']])
})
test('absències: un conflicte (409) obre el diàleg i sobreescriure desa amb force i recarrega', async () => {
  const { useConflicte } = await import('../src/composables/useConflicte.js')
  const p=prepara()
  const conflicte=useConflicte(p.dependents.carregarSubstitucions)
  p.dependents.obreSiConflicte=conflicte.obreSiConflicte
  const bloc=carregaBlocVista('useAbsenciesSubstitucions', { ...p.dependents, dependents: p.dependents, ref, computed, watch, onBeforeUnmount: () => {}, dataIso, avisaSubstitutsTrets: () => {}, document: {body: p.cos},
    apiSubstitucions: { desaAbsencies: async (...a) => { p.peticions.push(['desa',...a]); if (!a[2].force) throw { response: { status: 409, data: { detail: { current_data: [] } } } }; return {} } } })
  bloc.confirmarEliminarAbsenciesProf('Prof 1')
  await p.confirmacions[0].accept()
  assert.equal(conflicte.mostrarDialogConflicte.value, true)
  await conflicte.executarOverwrite()
  assert.deepEqual(p.peticions.slice(1), [['desa','2026-04-24','Prof 1',{hores_absencia:[],hores_servei:[],force:true}],['recarrega']])
})
test('absències: un rang amb un dia que falla desa la resta, recarrega i diu quins dies han fallat', async () => {
  const p=prepara()
  const tAmb=(clau, params) => params ? `${clau} ${JSON.stringify(params)}` : clau
  const bloc=carregaBlocVista('useAbsenciesSubstitucions', { ...p.dependents, dependents: { ...p.dependents, t: tAmb }, ref, computed, watch, onBeforeUnmount: () => {}, dataIso, avisaSubstitutsTrets: () => {}, document: {body: p.cos},
    apiSubstitucions: { horesProfessor: async () => ({hores_amb_classe:[],hores_al_centre:[]}), desaAbsencies: async (...a) => {
      p.peticions.push(['desa',...a])
      if (a[0] === '2026-04-27') throw { response: { status: 400, data: { detail: 'Prof 1 té una absència coberta' } } }
      return {}
    } } })
  bloc.seleccionarProfessorDropdown({value:{nom:'Prof 1'}})
  bloc.modeRang.value=true; bloc.dataFinalRang.value='2026-04-28'
  await bloc.afegirAbsenciaImmediata()
  assert.deepEqual(p.peticions.filter(x=>x[0]==='desa').map(x=>[x[1], x[4]]), [['2026-04-24',{silent:true}],['2026-04-27',{silent:true}],['2026-04-28',{silent:true}]])
  assert.deepEqual(p.peticions.at(-1), ['recarrega'])
  const avis = p.avisos.at(-1)
  assert.equal(avis.severity, 'error')
  assert.equal(avis.detail, 'substitutions.range.partial {"desats":"24/04, 28/04","fallats":"27/04 (Prof 1 té una absència coberta)"}')
  assert.equal(bloc.modeRang.value, true) // es pot tornar a provar
})
