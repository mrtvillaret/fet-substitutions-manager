import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed, watch, nextTick } from 'vue'
import { dataIso } from '../src/dates.js'
import { carregaBloc } from './support/carregaBlocSubstitucions.js'
const noms = ['mostrarDialogGestio','closeBtnRef','dropdownProfValue','gestioAbsencies','horesAmbClasse','horesAlCentre','horesCarregades','modeRang','dataFinalRang','professorsAmbInfo','absenciesDelDia','absenciesDelDiaAgrupades','datesDelRang','seleccionarProfessorDropdown','obrirDialogNou','editarAbsenciesProfessor','tancarDialogGestio','seleccionarProfessor','toggleHoraAbsencia','toggleHoraServei','totesTrnadesAbsencia','totesTrnadesServei','toggleTotesAbsencia','toggleTotesServei','afegirAbsenciaImmediata','confirmarEliminarAbsenciesProf']
function prepara() {
  const peticions = [], avisos = [], confirmacions = [], cos = { style: {} }
  const dependents = { dataISO: ref('2026-04-24'), professors: ref(['Prof 1', 'Prof 2']), absenciesCobertes: ref([{ professor:'Prof 3', data_final:'2026-04-30' }]), totesAbsencies: ref([{ professor_absent:'Prof 1', hora:'08:00', tipus_absencia:'ABSENCIA', updated_at:'ara' }, { professor_absent:'Prof 1', hora:'09:00', tipus_absencia:'ENCADENADA' }]), horesDisponibles: ref(['08:00','09:00','10:00']), loading: ref(false), toast: {add: m => avisos.push(m)}, t: x => x, confirmaEsborrar: c => confirmacions.push(c), obrirDialogConflicte: c => confirmacions.push(c), carregarSubstitucions: async () => peticions.push(['recarrega']), carregarTotesAbsencies: async () => {} }
  const deps = { ...dependents, dependents, ref, computed, watch, nextTick, onBeforeUnmount: () => {}, dataIso, avisaSubstitutsTrets: () => {}, document: {body: cos}, apiSubstitucions: { horesProfessor: async (...a) => {peticions.push(['hores',...a]); return {hores_amb_classe:['08:00'],hores_al_centre:['08:00','09:00']}}, desaAbsencies: async (...a) => {peticions.push(['desa',...a]); return {}} } }
  const bloc = carregaBloc('useAbsenciesSubstitucions', [['const mostrarDialogGestio = ref(false)', 'const mostrarDialogConflicte'], ['const professorsAmbInfo = computed', '// Mètodes'], ['const obrirDialogNou =', '// Les opcions del substitut'], ['// Quan les dades canvien', '// Lifecycle']], noms, deps)
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
  p.seleccionarProfessor({nom:'Prof 1'})
  p.modeRang.value=true; p.dataFinalRang.value='2026-04-27'
  await p.afegirAbsenciaImmediata()
  assert.deepEqual(p.peticions.filter(p=>p[0]==='desa'), ['2026-04-24','2026-04-27'].map(d=>['desa',d,'Prof 1',{hores_absencia:['08:00'],hores_servei:[],updated_at_map:{}}]))
  assert.equal(p.modeRang.value,false)
})
