import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed, nextTick, watch } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
import { DIALEGS, llegeixAdreca, escriuAdreca, pasHistorial, dataDeIso } from '../src/adreca.js'
import { dataIso } from '../src/dates.js'
import { dialegsInterns, registraDialegIntern, dialegInternObert, tancaDialegIntern } from '../src/dialegsInterns.js'
// Navegador de prova: adreça i historial amb entrades, «Enrere» i popstate
function navegador(adreca = '/') {
  const escoltes = {}
  const entrades = [{ state: null, url: adreca }]
  let posicio = 0
  const location = { search: '', pathname: '/', href: '', reload() {} }
  const posa = () => {
    const url = new URL(entrades[posicio].url, 'http://prova')
    location.pathname = url.pathname
    location.search = url.search
  }
  posa()
  const navega = (pas) => {
    posicio += pas
    posa()
    return Promise.all((escoltes.popstate || []).map(f => f({})))
  }
  const history = {
    get state() { return entrades[posicio].state },
    get length() { return entrades.length },
    get posicio() { return posicio },
    pushState(state, _t, url) { entrades.splice(posicio + 1); entrades.push({ state, url }); posicio += 1; posa() },
    replaceState(state, _t, url) { entrades[posicio] = { state, url }; posa() },
    back() { history.pendent = navega(-1) },
    forward() { history.pendent = navega(1) },
    entrades,
  }
  return {
    location, history,
    matchMedia: () => ({ matches: true, addEventListener() {}, removeEventListener() {} }),
    addEventListener(nom, f) { (escoltes[nom] ||= []).push(f) },
    removeEventListener(nom, f) { escoltes[nom] = (escoltes[nom] || []).filter(x => x !== f) },
  }
}

function prepara({ adreca = '/', rol = 'admin', vueWatch = () => {} } = {}) {
  const peticions=[], avisos=[], errors=[], mounted=[], unmounted=[], interceptors=[]
  const dependents={t:x=>x,toast:{add:x=>avisos.push(x)}}
  const window = navegador(adreca)
  const dataTreball = ref(new Date('2026-04-20T12:00:00'))
  const apiUsuaris={perfil:async()=>{peticions.push('perfil');return{data:{role:rol,idioma:'ca',institucio:'exemple'}}},surt:async()=>{peticions.push('sortir')},entra:async x=>{peticions.push(['login',x]);return{data:{}}},entraDelegacio:async(...x)=>peticions.push(['delegacio',...x])}
  const p=carregaBlocVista('App.vue','useAplicacio',[['const config =','</script>']],['tabActiu','grupsRef','canviaTab','autenticat','carregarConfig','cursos','cursDeLaData','carregarPerfil','isAdmin','userProfile','isMobile','ferLogin','loginUser','loginPass','ferLogout','config','diaAnterior','diaSeguent','dataSeleccionada','anarScheduler','tornarAlGestor','isSchedulerRoute','handleInstitucioCanviada','institucioKey','loginError'],{...dependents,dependents,console:{error:(...a)=>errors.push(a)},ref,computed,nextTick,watch:vueWatch,onMounted:x=>mounted.push(x),onBeforeUnmount:x=>unmounted.push(x),window,URLSearchParams,URL,setInterval,clearInterval,dataTreball,ambDataTreball:()=>({params:{data:'2026-04-20'}}),dataIso,apiUsuaris,configuracioHorari:async x=>{peticions.push(['config',x]);return{num_hores:7}},llistaCursos:async()=>[{id:1,nom:'Prova',data_inici:'2026-01-01',data_fi:null}],BASE:'/',esRutaLocal:x=>x.startsWith('/')&&!x.startsWith('//'),vigilaVersio:()=>()=>peticions.push('desmuntat'),clientHttp:{defaults:{},interceptors:{response:{use:(...x)=>interceptors.push(x)}}},setLocale:x=>peticions.push(['idioma',x]),missatgeDError:async()=> 'error',DIALEGS,llegeixAdreca,escriuAdreca,pasHistorial,dataDeIso,dialegInternObert,tancaDialegIntern})
  return{...p,peticions,avisos,errors,mounted,unmounted,interceptors,apiUsuaris,window}
}
test('App: un canvi de pestanya espera la decisió de Grups',async()=>{const p=prepara();p.tabActiu.value='grups';p.grupsRef.value={potSortir:async()=>false};assert.equal(await p.canviaTab('vigilancies'),false);assert.equal(p.tabActiu.value,'grups');p.grupsRef.value={potSortir:async()=>true};assert.equal(await p.canviaTab('vigilancies'),true)})
test('App: arrencada configura sessió, mode mòbil, perfil i curs en el mateix ordre',async()=>{const p=prepara();await p.mounted[0]();assert.equal(p.autenticat.value,true);assert.equal(p.isAdmin.value,true);assert.equal(p.isMobile.value,true);assert.equal(p.cursDeLaData.value.id,1);assert.deepEqual(p.peticions.slice(0,3),['perfil',['idioma','ca'],['config',{params:{data:'2026-04-20'}}]]);p.unmounted[0]();assert.equal(p.peticions.at(-1),'desmuntat')})
test('App: l’interceptor conserva el missatge de sessió i propaga el mateix error',async()=>{const p=prepara();await p.mounted[0]();const error={response:{status:401,data:{detail:'Sessió tancada'}}};await assert.rejects(p.interceptors[0][1](error),e=>e===error);assert.equal(p.autenticat.value,false);assert.equal(p.loginError.value,'app.login.sessionClosed');assert.equal(p.userProfile.value,null)})
test('App: login i logout conserven credencials, càrrega i neteja',async()=>{const p=prepara();p.loginUser.value='prova';p.loginPass.value='nomes-test';await p.ferLogin();assert.deepEqual(p.peticions[0],['login',{username:'prova',password:'nomes-test'}]);assert.equal(p.autenticat.value,true);p.ferLogout();assert.equal(p.config.value,null);assert.equal(p.loginPass.value,'');assert.equal(p.peticions.at(-1),'sortir')})
test('App: calendari, ruta i canvi de centre mantenen coordinació',async()=>{const p=prepara();p.diaSeguent();assert.equal(p.dataSeleccionada.value.getDate(),21);p.diaAnterior();assert.equal(p.dataSeleccionada.value.getDate(),20);p.userProfile.value={role:'admin'};p.anarScheduler();assert.equal(p.isSchedulerRoute.value,true);p.tornarAlGestor();assert.equal(p.isSchedulerRoute.value,false);p.tabActiu.value='grups';await p.handleInstitucioCanviada();assert.equal(p.tabActiu.value,'substitucions');assert.equal(p.institucioKey.value,1)})

test('App: la sessió tancada es reconeix pel codi i, sense codi, pel text', async () => {
 const casos = [
  [{ detail: 'Sessió tancada', codi: 'sessio_tancada', params: {} }, 'app.login.sessionClosed'],
  [{ detail: 'Un text qualsevol', codi: 'sessio_tancada', params: {} }, 'app.login.sessionClosed'],
  [{ detail: 'Sessió tancada', codi: 'sessio_caducada', params: {} }, 'app.login.sessionExpired'],
  [{ detail: 'Sessió caducada', codi: 'sessio_caducada', params: {} }, 'app.login.sessionExpired'],
  [{ detail: 'No autenticat', codi: 'no_autenticat', params: {} }, 'app.login.sessionExpired'],
  [{ detail: 'Sessió tancada' }, 'app.login.sessionClosed'],
  [{ detail: 'Sessió caducada' }, 'app.login.sessionExpired'],
 ]
 for (const [data, esperat] of casos) {
  const p = prepara()
  await p.mounted[0]()
  await assert.rejects(p.interceptors[0][1]({ response: { status: 401, data } }))
  assert.equal(p.loginError.value, esperat, JSON.stringify(data))
 }
})

test('App: carregarPerfil ignora el 401 a la consola i registra la resta dels errors',async()=>{
 const p=prepara()
 for(const error of [{response:{status:401}},{response:{status:500}},Error('xarxa')]){
  p.apiUsuaris.perfil=async()=>{throw error};await p.carregarPerfil()
 }
 assert.equal(p.errors.length,2)
 assert.equal(p.errors[0][1].response.status,500)
 assert.equal(p.errors[1][1].message,'xarxa')
})

for (const cas of ['global', 'pantalla', 'sessio', 'xarxa']) {
 test(`App: regla única dels avisos (${cas})`, async () => {
  const errorsAvisos = await import('../src/errorsApi.js')
  const p = prepara()
  await p.mounted[0]()
  const error = cas === 'xarxa' ? {config:{}} : {config:{_silent:cas==='pantalla'},response:{status:cas==='sessio'?401:500,data:{}}}
  await assert.rejects(p.interceptors[0][1](error), e=>e===error)
  errorsAvisos.avisaError(error,()=>p.avisos.push({detail:'local'}))
  assert.equal(p.avisos.length,cas==='sessio'?0:1)
  if(cas==='pantalla')assert.equal(p.avisos[0].detail,'local')
  else if(cas!=='sessio')assert.equal(p.avisos[0].detail,'error')
 })
}

test('App: un 401 d’entrada mostra les credencials errònies una sola vegada', async () => {
 const p=prepara()
 await p.mounted[0]()
 p.autenticat.value=false
 p.apiUsuaris.entra=async()=>p.interceptors[0][1]({config:{_silent:true,url:'/api/login'},response:{status:401,data:{}}})
 await p.ferLogin()
 assert.equal(p.loginError.value,'app.login.error')
 assert.equal(p.avisos.length,0)
})

test('App: el 429 d’entrada conserva l’avís concret i el temporitzador sense toast', async () => {
 const p=prepara()
 await p.mounted[0]()
 p.autenticat.value=false
 p.apiUsuaris.entra=async()=>p.interceptors[0][1]({config:{_silent:true,url:'/api/login'},response:{status:429,headers:{'retry-after':'7'},data:{}}})
 await p.ferLogin()
 assert.equal(p.loginError.value,'app.login.rateLimitWithWait')
 assert.equal(p.loginRetrySeconds.value,7)
 assert.equal(p.avisos.length,0)
 p.unmounted[0]()
})

test('App: peticions pendents amb 401 no afegeixen toasts a la pantalla d’entrada', async () => {
 const errorsAvisos=await import('../src/errorsApi.js'),p=prepara()
 await p.mounted[0]()
 p.autenticat.value=false
 const error={config:{url:'/api/vigilancies/2026-04-20'},response:{status:401,data:{}}}
 await assert.rejects(p.interceptors[0][1](error))
 errorsAvisos.avisaError(error,()=>p.avisos.push({detail:'duplicat'}))
 assert.equal(p.avisos.length,0)
})

// ===== Adreça: pantalla, data i diàleg (adreca.js) =====
const adrecaDe = (p) => p.window.location.pathname + p.window.location.search
const entra = async (opcions) => {
  const p = prepara({ vueWatch: watch, ...opcions })
  await p.mounted[0]()
  await nextTick()
  return p
}

test('Adreça: un enllaç directe obre pantalla, data i diàleg després d’entrar', async () => {
  const p = prepara({ vueWatch: watch, adreca: '/vigilancies?data=2026-05-04&obert=estadistiques' })
  assert.equal(dataIso(p.dataSeleccionada.value), '2026-05-04')
  assert.equal(p.estatAdreca.value.obert, null)   // encara no se sap qui entra
  await p.mounted[0]()
  assert.equal(p.tabActiu.value, 'vigilancies')
  assert.equal(p.estatAdreca.value.obert, 'estadistiques')
  assert.equal(adrecaDe(p), '/vigilancies?data=2026-05-04&obert=estadistiques')
  assert.equal(p.window.history.length, 1)
})

test('Adreça: el que el rol no permet no s’obre i l’adreça queda neta', async () => {
  const p = await entra({ rol: 'user', adreca: '/grups?data=2026-05-04&obert=configuracio' })
  assert.equal(p.tabActiu.value, 'grups')
  assert.equal(p.estatAdreca.value.obert, null)
  assert.equal(adrecaDe(p), '/grups?data=2026-05-04')
  const q = await entra({ rol: 'user', adreca: '/scheduler' })
  assert.equal(q.isSchedulerRoute.value, false)
  assert.equal(adrecaDe(q), '/substitucions?data=2026-04-20')
  const r = await entra({ adreca: '/pantalla-inexistent?data=dema&obert=x' })
  assert.equal(r.tabActiu.value, 'substitucions')
  assert.equal(adrecaDe(r), '/substitucions?data=2026-04-20')
})

test('Adreça: «Enrere» tanca primer el diàleg i després torna a la pantalla anterior', async () => {
  const p = await entra()
  const h = p.window.history
  await p.canviaTab('vigilancies'); await nextTick()
  p.diaSeguent(); await nextTick()
  assert.equal(adrecaDe(p), '/vigilancies?data=2026-04-21')
  assert.equal(h.length, 2)                        // la data no afegeix entrades
  p.obrirEstadistiques(); await nextTick()
  assert.equal(adrecaDe(p), '/vigilancies?data=2026-04-21&obert=estadistiques')
  h.back(); await h.pendent; await nextTick()
  assert.equal(p.estatAdreca.value.obert, null)
  assert.equal(p.tabActiu.value, 'vigilancies')
  h.back(); await h.pendent; await nextTick()
  assert.equal(p.tabActiu.value, 'substitucions')
  assert.equal(dataIso(p.dataSeleccionada.value), '2026-04-21')   // la data no torna enrere
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-21')
  assert.equal(p.autenticat.value, true)
})

test('Adreça: tancar el diàleg amb la creu treu la seva entrada; «Endavant» el reobre', async () => {
  const p = await entra()
  const h = p.window.history
  p.obrirAjuda(); await nextTick()
  assert.equal(h.length, 2)
  assert.equal(h.state.dialeg, true)
  p.mostrarAjuda.value = false; await nextTick()   // la creu del diàleg (v-model)
  await h.pendent; await nextTick()
  assert.equal(h.posicio, 0)
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20')
  h.forward(); await h.pendent; await nextTick()
  assert.equal(p.mostrarAjuda.value, true)
})

test('Adreça: un diàleg obert per enllaç directe es tanca sense sortir de l’aplicació', async () => {
  const p = await entra({ adreca: '/grups?obert=perfil' })
  assert.equal(p.mostrarPerfil.value, true)
  p.mostrarPerfil.value = false; await nextTick()
  assert.equal(p.window.history.length, 1)
  assert.equal(adrecaDe(p), '/grups?data=2026-04-20')
})

test('Adreça: del menú del mòbil a una altra pantalla, «Enrere» no reobre el menú', async () => {
  const p = await entra()
  p.mostrarMenuMobil.value = true; await nextTick()
  p.anarScheduler(); p.mostrarMenuMobil.value = false; await nextTick()
  assert.equal(adrecaDe(p), '/scheduler?data=2026-04-20')
  assert.equal(p.window.history.length, 2)
  p.window.history.back(); await p.window.history.pendent; await nextTick()
  assert.equal(p.isSchedulerRoute.value, false)
  assert.equal(p.mostrarMenuMobil.value, false)
})

test('Adreça: «Enrere» amb canvis sense desar en un diàleg pregunta i no el tanca', async () => {
  const p = await entra()
  const h = p.window.history
  const peticionsTancar = []
  p.configuracioRef.value = { teCanvis: true, tanca: () => peticionsTancar.push('tanca') }
  p.obrirConfiguracio(); await nextTick()
  h.back(); await h.pendent; await nextTick()
  assert.deepEqual(peticionsTancar, ['tanca'])
  assert.equal(p.mostrarConfiguracio.value, true)
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20&obert=configuracio')
  assert.equal(h.length, 2)
  // Si l'usuari ho accepta, el diàleg es tanca i l'adreça torna enrere
  p.mostrarConfiguracio.value = false; await nextTick(); await h.pendent; await nextTick()
  assert.equal(h.posicio, 0)
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20')
})

test('Adreça: «Enrere» des de Grups amb canvis sense desar espera la decisió', async () => {
  const p = await entra()
  const h = p.window.history
  await p.canviaTab('grups'); await nextTick()
  let resposta = false
  const preguntes = []
  p.grupsRef.value = { teCanvis: true, potSortir: async () => { preguntes.push(resposta); return resposta } }
  h.back(); await h.pendent; await nextTick()
  assert.equal(p.tabActiu.value, 'grups')
  assert.equal(adrecaDe(p), '/grups?data=2026-04-20')
  resposta = true
  h.back(); await h.pendent; await h.pendent; await nextTick()
  assert.deepEqual(preguntes, [false, true])
  assert.equal(p.tabActiu.value, 'substitucions')
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20')
})

test('Adreça: sortir tanca els diàlegs i no es reobren en tornar a entrar', async () => {
  const p = await entra()
  p.obrirPerfil(); await nextTick()
  p.ferLogout(); await nextTick()
  assert.equal(p.mostrarPerfil.value, false)
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20')
})

test('Adreça: canviar de centre amb el Perfil obert no fa tornar a la pantalla d’abans en tancar-lo', async () => {
  const p = await entra()
  const h = p.window.history
  await p.canviaTab('vigilancies'); await nextTick()
  p.obrirPerfil(); await nextTick()
  await p.handleInstitucioCanviada(); await nextTick()
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20&obert=perfil')
  p.mostrarPerfil.value = false; await nextTick(); await h.pendent; await nextTick()
  assert.equal(p.tabActiu.value, 'substitucions')
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20')
})

// ===== Diàlegs de dins de les pantalles (dialegsInterns.js) =====
const dialegIntern = (nom) => {
  const obert = ref(false), tancaments = []
  const treu = registraDialegIntern(nom, { obert: () => obert.value, tanca: () => { tancaments.push(nom); obert.value = false } })
  return { obert, tancaments, treu }
}

test('Diàlegs interns: obrir-ne un afegeix una entrada sense canviar l’adreça; «Enrere» el tanca', async () => {
  const p = await entra()
  const h = p.window.history
  await p.canviaTab('vigilancies'); await nextTick()
  const pdf = dialegIntern('vigilancies-pdf')
  pdf.obert.value = true; await nextTick()
  assert.equal(adrecaDe(p), '/vigilancies?data=2026-04-20')
  assert.equal(h.length, 3)
  assert.deepEqual(h.state, { dialeg: true, intern: 'vigilancies-pdf' })
  h.back(); await h.pendent; await nextTick()
  assert.deepEqual(pdf.tancaments, ['vigilancies-pdf'])
  assert.equal(pdf.obert.value, false)
  assert.equal(p.tabActiu.value, 'vigilancies')
  assert.equal(adrecaDe(p), '/vigilancies?data=2026-04-20')
  // El segon «Enrere» ja torna a la pantalla anterior
  h.back(); await h.pendent; await nextTick()
  assert.equal(p.tabActiu.value, 'substitucions')
  pdf.treu()
})

test('Diàlegs interns: la creu treu la seva entrada i «Endavant» no el reobre', async () => {
  const p = await entra()
  const h = p.window.history
  const fitxa = dialegIntern('substitucions-absencies')
  fitxa.obert.value = true; await nextTick()
  assert.equal(h.posicio, 1)
  fitxa.obert.value = false; await nextTick(); await h.pendent; await nextTick()
  assert.equal(h.posicio, 0)
  assert.deepEqual(fitxa.tancaments, [])   // l'ha tancat la creu, no «Enrere»
  h.forward(); await h.pendent; await nextTick()
  assert.equal(fitxa.obert.value, false)
  assert.equal(h.state, null)              // l'entrada ja no és d'un diàleg
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20')
  fitxa.treu()
})

test('Diàlegs interns: del menú del mòbil al PDF, en tancar-lo es torna a abans del menú', async () => {
  const p = await entra()
  const h = p.window.history
  const pdf = dialegIntern('substitucions-pdf')
  p.mostrarMenuMobil.value = true; await nextTick()
  assert.equal(h.length, 2)
  p.mostrarMenuMobil.value = false; pdf.obert.value = true; await nextTick()
  assert.equal(adrecaDe(p), '/substitucions?data=2026-04-20')
  assert.equal(h.length, 2)
  assert.deepEqual(h.state, { dialeg: true, intern: 'substitucions-pdf' })
  h.back(); await h.pendent; await nextTick()
  assert.equal(pdf.obert.value, false)
  assert.equal(p.mostrarMenuMobil.value, false)
  assert.equal(h.posicio, 0)
  pdf.treu()
})

test('Diàlegs interns: a Grups amb canvis sense desar, «Enrere» tanca el diàleg sense preguntar', async () => {
  const p = await entra()
  const h = p.window.history
  await p.canviaTab('grups'); await nextTick()
  const preguntes = []
  p.grupsRef.value = { teCanvis: true, potSortir: async () => { preguntes.push('pregunta'); return false } }
  const reforc = dialegIntern('grups-reforc')
  reforc.obert.value = true; await nextTick()
  h.back(); await h.pendent; await nextTick()
  assert.deepEqual(reforc.tancaments, ['grups-reforc'])
  assert.deepEqual(preguntes, [])
  assert.equal(p.tabActiu.value, 'grups')
  assert.equal(adrecaDe(p), '/grups?data=2026-04-20')
  reforc.treu()
})

test('Diàlegs interns: el registre només treu el diàleg que hi ha posat', () => {
  const primer = registraDialegIntern('prova', { obert: () => true, tanca() {} })
  const segon = registraDialegIntern('prova', { obert: () => false, tanca() {} })
  primer()
  assert.equal(dialegsInterns.has('prova'), true)
  assert.equal(dialegInternObert(), null)
  segon()
  assert.equal(dialegsInterns.has('prova'), false)
})
