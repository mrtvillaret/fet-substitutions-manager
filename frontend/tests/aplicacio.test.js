import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed, nextTick } from 'vue'
import { carregaBlocVista } from './support/carregaBlocVista.js'
function prepara() {
  const peticions=[], avisos=[], errors=[], mounted=[], unmounted=[], interceptors=[]
  const dependents={t:x=>x,toast:{add:x=>avisos.push(x)}}
  const window={location:{search:'',pathname:'/',href:'',reload(){}},history:{pushState(_a,_b,path){window.location.pathname=path}},matchMedia:()=>({matches:true,addEventListener(){},removeEventListener(){}}),addEventListener(){},removeEventListener(){}}
  const apiUsuaris={perfil:async()=>{peticions.push('perfil');return{data:{role:'admin',idioma:'ca',institucio:'exemple'}}},surt:async()=>{peticions.push('sortir')},entra:async x=>{peticions.push(['login',x]);return{data:{}}},entraDelegacio:async(...x)=>peticions.push(['delegacio',...x])}
  const p=carregaBlocVista('App.vue','useAplicacio',[['const config =','</script>']],['tabActiu','grupsRef','canviaTab','autenticat','carregarConfig','cursos','cursDeLaData','carregarPerfil','isAdmin','userProfile','isMobile','ferLogin','loginUser','loginPass','ferLogout','config','diaAnterior','diaSeguent','dataSeleccionada','anarScheduler','tornarAlGestor','isSchedulerRoute','handleInstitucioCanviada','institucioKey','loginError'],{...dependents,dependents,console:{error:(...a)=>errors.push(a)},ref,computed,nextTick,watch(){},onMounted:x=>mounted.push(x),onBeforeUnmount:x=>unmounted.push(x),window,URLSearchParams,URL,setInterval,clearInterval,dataTreball:ref(new Date('2026-04-20T12:00:00')),ambDataTreball:()=>({params:{data:'2026-04-20'}}),dataIso:d=>d.toLocaleDateString('sv-SE'),apiUsuaris,configuracioHorari:async x=>{peticions.push(['config',x]);return{num_hores:7}},llistaCursos:async()=>[{id:1,nom:'Prova',data_inici:'2026-01-01',data_fi:null}],BASE:'/',ruta:(x='')=>'/'+x,esRutaLocal:x=>x.startsWith('/')&&!x.startsWith('//'),vigilaVersio:()=>()=>peticions.push('desmuntat'),clientHttp:{defaults:{},interceptors:{response:{use:(...x)=>interceptors.push(x)}}},setLocale:x=>peticions.push(['idioma',x]),missatgeDError:async()=> 'error'})
  return{...p,peticions,avisos,errors,mounted,unmounted,interceptors,apiUsuaris,window}
}
test('App: un canvi de pestanya espera la decisió de Grups',async()=>{const p=prepara();p.tabActiu.value='grups';p.grupsRef.value={potSortir:async()=>false};assert.equal(await p.canviaTab('vigilancies'),false);assert.equal(p.tabActiu.value,'grups');p.grupsRef.value={potSortir:async()=>true};assert.equal(await p.canviaTab('vigilancies'),true)})
test('App: arrencada configura sessió, mode mòbil, perfil i curs en el mateix ordre',async()=>{const p=prepara();await p.mounted[0]();assert.equal(p.autenticat.value,true);assert.equal(p.isAdmin.value,true);assert.equal(p.isMobile.value,true);assert.equal(p.cursDeLaData.value.id,1);assert.deepEqual(p.peticions.slice(0,3),['perfil',['idioma','ca'],['config',{params:{data:'2026-04-20'}}]]);p.unmounted[0]();assert.equal(p.peticions.at(-1),'desmuntat')})
test('App: l’interceptor conserva el missatge de sessió i propaga el mateix error',async()=>{const p=prepara();await p.mounted[0]();const error={response:{status:401,data:{detail:'Sessió tancada'}}};await assert.rejects(p.interceptors[0][1](error),e=>e===error);assert.equal(p.autenticat.value,false);assert.equal(p.loginError.value,'app.login.sessionClosed');assert.equal(p.userProfile.value,null)})
test('App: login i logout conserven credencials, càrrega i neteja',async()=>{const p=prepara();p.loginUser.value='prova';p.loginPass.value='nomes-test';await p.ferLogin();assert.deepEqual(p.peticions[0],['login',{username:'prova',password:'nomes-test'}]);assert.equal(p.autenticat.value,true);p.ferLogout();assert.equal(p.config.value,null);assert.equal(p.loginPass.value,'');assert.equal(p.peticions.at(-1),'sortir')})
test('App: calendari, ruta i canvi de centre mantenen coordinació',async()=>{const p=prepara();p.diaSeguent();assert.equal(p.dataSeleccionada.value.getDate(),21);p.diaAnterior();assert.equal(p.dataSeleccionada.value.getDate(),20);p.anarScheduler();assert.equal(p.isSchedulerRoute.value,true);p.tornarAlGestor();assert.equal(p.isSchedulerRoute.value,false);p.tabActiu.value='grups';await p.handleInstitucioCanviada();assert.equal(p.tabActiu.value,'substitucions');assert.equal(p.institucioKey.value,1)})

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
