import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { ambDataTreball, dataTreball } from '../dataTreball'
import { dataIso } from '../dates'
import { missatgeDError, avisaError, marcaAvisat, esErrorSilencios } from '../errorsApi'
import clientHttp from '../api/client'
import * as apiUsuaris from '../api/usuaris'
import { configuracio as configuracioHorari } from '../api/horari'
import { llista as llistaCursos } from '../api/cursos'
import { BASE, esRutaLocal } from '../basePath'
import { DIALEGS, llegeixAdreca, escriuAdreca, pasHistorial, dataDeIso } from '../adreca'
import { dialegInternObert, tancaDialegIntern } from '../dialegsInterns'
import { vigilaVersio } from '../versioApp'
import { setLocale } from '../i18n'

export function useAplicacio(dependents) {
  const { t, toast } = dependents

  const config = ref(null)
  const autenticat = ref(false)
  // L'adreça amb què s'obre la pàgina (enllaç directe o recàrrega): la data es
  // posa ja; la pantalla i el diàleg, quan se sap qui ha entrat (aplicaAdreca)
  const adrecaInicial = llegeixAdreca(window.location, BASE)
  if (adrecaInicial.data) dataTreball.value = dataDeIso(adrecaInicial.data)
  const tabActiu = ref(adrecaInicial.pantalla === 'scheduler' ? 'substitucions' : adrecaInicial.pantalla)
  const grupsRef = ref(null)
  const configuracioRef = ref(null)
  const configuracioExamensRef = ref(null)

  // Canvi de pestanya: si a «Grups» hi ha canvis sense desar, primer es confirma
  const canviaTab = async (nova) => {
    if (tabActiu.value === nova) return true
    if (tabActiu.value === 'grups' && grupsRef.value && !(await grupsRef.value.potSortir())) return false
    tabActiu.value = nova
    return true
  }
  const substitucionsRef = ref(null)
  // La data del calendari és la data de treball de tota l'aplicació (dataTreball.js)
  const dataSeleccionada = dataTreball
  const mostrarConfiguracio = ref(false)
  const mostrarConfiguracioExamens = ref(false)
  const mostrarEstadistiques = ref(false)
  const mostrarAjuda = ref(false)
  const mostrarPerfil = ref(false)
  const mostrarMenuMobil = ref(false)
  // Si s'arriba des del login d'una altra instal·lació (delegació a una demo en
  // un subdomini), el nom d'usuari ja ve escrit; la contrasenya no viatja mai
  const loginUser = ref(new URLSearchParams(window.location.search).get('usuari') || '')
  const loginPass = ref('')
  const loginError = ref('')
  const loginLoading = ref(false)
  const loginRetrySeconds = ref(null)
  let loginRetryTimer = null
  const isMobile = ref(false)
  let mediaQuery = null
  const userProfile = ref(null)
  const institucioKey = ref(0)
  const isAdmin = computed(() => ['admin', 'super_admin'].includes(userProfile.value?.role || ''))
  const esDemo = computed(() => userProfile.value?.institucio === 'demo')
  // El planificador és només per als admins: per adreça tampoc no s'obre a ningú més
  const rutaScheduler = ref(adrecaInicial.pantalla === 'scheduler')
  const isSchedulerRoute = computed(() => rutaScheduler.value && isAdmin.value)

  const actualitzarModeMobil = () => {
    if (!mediaQuery) return
    isMobile.value = mediaQuery.matches
  }

  const aplicarToken = () => {
    autenticat.value = true
  }

  const netejarToken = () => {
    autenticat.value = false
    config.value = null
    userProfile.value = null
    apiUsuaris.surt().catch(() => {})
  }

  // Professors i hores de l'horari vigent a la data del calendari (capçalera)
  const carregarEstatHorari = async () => {
    config.value = await configuracioHorari(ambDataTreball())
  }

  const carregarConfig = async () => {
    await carregarEstatHorari()
    await carregarCursos()
  }

  watch(dataSeleccionada, () => {
    if (autenticat.value) carregarEstatHorari().catch(() => {})
  })

  // ===== CURSOS (per institució) =====
  // Els cursos són una seqüència contígua de rangs amb nom. NO es trien: el curs es
  // deriva de la data on treballes, igual que la versió d'XML. Aquí només es mostra.
  const cursos = ref([])

  const cursDeLaData = computed(() => {
    const iso = dataIso(dataSeleccionada.value)
    if (!iso) return null
    // Comparació lexicogràfica: les dates ISO ho permeten
    return cursos.value.find(
      c => c.data_inici <= iso && (!c.data_fi || iso <= c.data_fi)
    ) || null
  })

  const carregarCursos = async () => {
    try {
      const data = await llistaCursos()
      cursos.value = data
    } catch {
      cursos.value = []
    }
  }

  const carregarPerfil = async () => {
    try {
      const response = await apiUsuaris.perfil()
      userProfile.value = response.data
      setLocale(response.data.idioma || 'ca')
    } catch (error) {
      if (error.response?.status !== 401) console.error('Error carregant perfil:', error)
    }
  }

  // També després d'importar un XML nou (issue #1): mateixa recàrrega de dades.
  const handleInstitucioCanviada = async () => {
    await carregarPerfil()
    await carregarConfig()   // recarrega també els cursos (són per institució)
    tabActiu.value = 'substitucions'
    institucioKey.value += 1
  }

  const tornarAlGestor = () => {
    rutaScheduler.value = false
  }

  const anarScheduler = () => {
    rutaScheduler.value = true
  }

  // ===== ADREÇA (adreca.js) =====
  // La pantalla, la data i el diàleg obert són a l'adreça: «Enrere» tanca el
  // diàleg o torna a la pantalla anterior, i recarregar o un enllaç hi tornen.
  const dialegs = {
    configuracio: mostrarConfiguracio,
    'configuracio-examens': mostrarConfiguracioExamens,
    estadistiques: mostrarEstadistiques,
    perfil: mostrarPerfil,
    ajuda: mostrarAjuda,
    menu: mostrarMenuMobil,
  }
  // Diàlegs que poden tenir canvis sense desar: exposen teCanvis i tanca()
  const dialegsAmbCanvis = { configuracio: configuracioRef, 'configuracio-examens': configuracioExamensRef }
  const NOMES_ADMINS = ['configuracio', 'configuracio-examens', 'estadistiques']
  const dialegPermes = (nom) =>
    NOMES_ADMINS.includes(nom) ? isAdmin.value : nom !== 'menu' || isMobile.value

  const dialegObert = computed(() =>
    isSchedulerRoute.value ? null : DIALEGS.find(nom => dialegs[nom].value) || null)
  // Els diàlegs de dins de les pantalles (dialegsInterns.js): no van a l'adreça,
  // però tenen entrada pròpia a l'historial (history.state.intern)
  const dialegIntern = computed(() => dialegInternObert())
  const estatAdreca = computed(() => ({
    pantalla: isSchedulerRoute.value ? 'scheduler' : tabActiu.value,
    data: dataIso(dataSeleccionada.value),
    obert: dialegObert.value,
    intern: dialegIntern.value,
  }))

  const avui = () => dataIso(new Date())
  const internDeLHistorial = () => window.history.state?.intern || null
  const adrecaActual = () => {
    const adreca = llegeixAdreca(window.location, BASE)
    return { ...adreca, data: adreca.data || avui(), intern: internDeLHistorial() }
  }
  const estatHistorial = (estat) => ({ dialeg: Boolean(estat.obert || estat.intern), intern: estat.intern || null })

  // Escriu l'estat a l'adreça (pasHistorial decideix si és una entrada nova)
  const sincronitzaAdreca = ({ substitueix = false } = {}) => {
    if (!autenticat.value) return
    const nou = estatAdreca.value
    const url = escriuAdreca(nou, BASE, avui())
    if (url === window.location.pathname + window.location.search && nou.intern === internDeLHistorial()) return
    // 'res': la mateixa adreça escrita d'una altra manera (/, valors desconeguts...)
    const actual = adrecaActual()
    const pas = pasHistorial(actual, nou, Boolean(window.history.state?.dialeg))
    if (pas === 'enrere' && !substitueix) window.history.back()
    else if (pas === 'afegeix' && !substitueix) window.history.pushState(estatHistorial(nou), '', url)
    else {
      // L'entrada continua sent del diàleg si només canvia la data o el diàleg;
      // si ha canviat la pantalla (p. ex. un altre centre des del Perfil), en
      // tancar-lo no s'ha de tornar a la pantalla d'abans
      const delDialeg = Boolean(nou.obert || nou.intern) && actual.pantalla === nou.pantalla
      const estat = delDialeg ? { ...window.history.state, intern: nou.intern || null } : null
      window.history.replaceState(estat, '', url)
    }
  }
  watch(estatAdreca, () => sincronitzaAdreca())

  // Porta la pantalla a l'adreça (en entrar i amb «Enrere»/«Endavant»). La data
  // de treball no torna enrere: és la de tota l'aplicació.
  const aplicaAdreca = (desti) => {
    // Un diàleg de dins de la pantalla es tanca com amb la creu; no es reobre
    // («Endavant»), perquè no se'n sap el context
    if (dialegIntern.value && dialegIntern.value !== desti.intern) tancaDialegIntern(dialegIntern.value)
    rutaScheduler.value = desti.pantalla === 'scheduler'
    if (desti.pantalla !== 'scheduler') tabActiu.value = desti.pantalla
    for (const [nom, visible] of Object.entries(dialegs)) {
      visible.value = nom === desti.obert && dialegPermes(nom)
    }
    sincronitzaAdreca({ substitueix: true })
  }

  const entraAAdreca = () => aplicaAdreca(llegeixAdreca(window.location, BASE))

  // «Enrere»/«Endavant». Amb canvis sense desar, es torna a posar l'adreça
  // d'on se surt i es pregunta com en tancar (diàleg) o en canviar de pestanya (Grups).
  let grupsJaDecidit = false
  const enNavegar = async () => {
    if (!autenticat.value) return
    const desti = { ...llegeixAdreca(window.location, BASE), intern: internDeLHistorial() }
    const obert = dialegObert.value
    const dialeg = obert && obert !== desti.obert ? dialegsAmbCanvis[obert]?.value : null
    const tornaAOnEra = () => window.history.pushState(
      estatHistorial(estatAdreca.value), '', escriuAdreca(estatAdreca.value, BASE, avui()))
    if (dialeg?.teCanvis) {
      tornaAOnEra()
      dialeg.tanca()   // si es tanca, sincronitzaAdreca torna enrere
      return
    }
    const surtDeGrups = estatAdreca.value.pantalla === 'grups' && desti.pantalla !== 'grups'
    if (surtDeGrups && !grupsJaDecidit && grupsRef.value?.teCanvis) {
      tornaAOnEra()
      if (await grupsRef.value.potSortir()) {
        grupsJaDecidit = true
        window.history.back()
      }
      return
    }
    grupsJaDecidit = false
    aplicaAdreca(desti)
  }

  const versioNova = ref(false)
  const recarregaPagina = () => window.location.reload()
  let deixaDeVigilarVersio = null

  onMounted(async () => {
    deixaDeVigilarVersio = vigilaVersio(() => { versioNova.value = true })
    clientHttp.defaults.withCredentials = true
    // Les crides '/api/...' van a la instal·lació on s'ha obert la pàgina ('' o '/demo')
    clientHttp.defaults.baseURL = BASE.replace(/\/$/, '')
    mediaQuery = window.matchMedia('(max-width: 720px)')
    actualitzarModeMobil()
    mediaQuery.addEventListener('change', actualitzarModeMobil)
    window.addEventListener('popstate', enNavegar)
    window.addEventListener('obre-configuracio-examens', obreConfiguracioExamensDesDeVista)

    clientHttp.interceptors.response.use(
      (response) => response,
      async (error) => {
        const status = error?.response?.status
        if (status === 401) {
          // Si hi havia una sessió oberta, diu per què s'ha de tornar a entrar
          // (sense activitat el navegador ja ha esborrat la cookie: «No autenticat»).
          // Pel codi de l'error; el text, només si la resposta no en porta.
          if (autenticat.value) {
            const dades = error.response?.data
            const tancada = dades?.codi ? dades.codi === 'sessio_tancada' : dades?.detail === 'Sessió tancada'
            loginError.value = tancada ? t('app.login.sessionClosed') : t('app.login.sessionExpired')
          }
          const esEntrada = String(error.config?.url || '').split('?')[0].endsWith('/api/login')
          if (autenticat.value || !esEntrada) marcaAvisat(error)
          netejarToken()
          return Promise.reject(error)
        }
        if (!esErrorSilencios(error)) {
          const msg = await missatgeDError(error, t)
          avisaError(error, () => toast.add({ severity: 'error', summary: t('app.errors.title'), detail: msg, life: 5000 }))
        }
        return Promise.reject(error)
      }
    )

    try {
      await carregarPerfil()
      await carregarConfig()
      aplicarToken()
      entraAAdreca()
    } catch {
      // Cookie absent o expirada — es queda a la pantalla de login
    }
  })

  onBeforeUnmount(() => {
    deixaDeVigilarVersio?.()
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', actualitzarModeMobil)
    }
    window.removeEventListener('popstate', enNavegar)
    window.removeEventListener('obre-configuracio-examens', obreConfiguracioExamensDesDeVista)
    if (loginRetryTimer) {
      clearInterval(loginRetryTimer)
    }
  })

  const ferLogin = async () => {
    loginError.value = ''
    loginLoading.value = true
    try {
      const credencials = { username: loginUser.value, password: loginPass.value }
      const response = await apiUsuaris.entra(credencials, { _silent: true })
      const delegacio = response.data?.redirect
      if (delegacio && esRutaLocal(delegacio)) {
        // L'usuari és d'una altra instal·lació del mateix domini (p.ex. la demo a
        // /demo/): s'hi entra amb les mateixes credencials i s'hi va.
        await apiUsuaris.entraDelegacio(delegacio, credencials, { baseURL: '', _silent: true })
        window.location.href = delegacio
        return
      }
      if (delegacio && delegacio.startsWith('https://')) {
        // Instal·lació en un altre (sub)domini: s'hi porta l'usuari amb el nom ja
        // escrit, però la contrasenya no s'envia a un altre lloc.
        const desti = new URL(delegacio)
        desti.searchParams.set('usuari', credencials.username)
        window.location.href = desti.toString()
        return
      }
      aplicarToken()
      // Només es redirigeix dins del mateix domini: un ?redirect=https://... extern
      // portaria l'usuari fora just després d'entrar.
      const redirectUrl = new URLSearchParams(window.location.search).get('redirect')
      if (redirectUrl && esRutaLocal(redirectUrl)) { window.location.href = redirectUrl; return; }
      await carregarPerfil()
      entraAAdreca()
      await carregarConfig()
    } catch (error) {
      avisaError(error, () => {
        const status = error.response?.status
        if (status === 429) {
          const retryAfter = parseInt(error.response?.headers?.['retry-after'], 10)
          loginRetrySeconds.value = Number.isFinite(retryAfter) ? retryAfter : 60
          loginError.value = t('app.login.rateLimitWithWait', { seconds: loginRetrySeconds.value })

          if (loginRetryTimer) {
            clearInterval(loginRetryTimer)
          }

          loginRetryTimer = setInterval(() => {
            if (loginRetrySeconds.value === null) return
            loginRetrySeconds.value -= 1
            if (loginRetrySeconds.value <= 0) {
              clearInterval(loginRetryTimer)
              loginRetryTimer = null
              loginRetrySeconds.value = null
              loginError.value = ''
              return
            }
            loginError.value = t('app.login.rateLimitWithWait', { seconds: loginRetrySeconds.value })
          }, 1000)
        } else {
          loginError.value = t('app.login.error')
        }
      })
    } finally {
      loginLoading.value = false
    }
  }

  const ferLogout = () => {
    // Es tanquen els diàlegs: en tornar a entrar no es reobren des de l'adreça
    for (const visible of Object.values(dialegs)) visible.value = false
    sincronitzaAdreca({ substitueix: true })
    netejarToken()
    loginPass.value = ''
  }

  const obrirConfiguracio = () => {
    mostrarConfiguracio.value = true
  }

  const obrirConfiguracioExamens = () => {
    mostrarConfiguracioExamens.value = true
  }

  // Des d'una pantalla (p. ex. l'avís de vigilàncies sense titular): només per als admins
  const obreConfiguracioExamensDesDeVista = () => {
    if (isAdmin.value) obrirConfiguracioExamens()
  }

  const obrirEstadistiques = () => {
    mostrarEstadistiques.value = true
  }

  const obrirPerfil = () => {
    mostrarPerfil.value = true
  }

  const obrirAjuda = () => {
    mostrarAjuda.value = true
  }

  const obrirPdfDia = async () => {
    if (!(await canviaTab('substitucions'))) return
    await nextTick()
    substitucionsRef.value?.mostrarDialegPDF?.()
  }

  const diaAnterior = () => {
    const novaData = new Date(dataSeleccionada.value)
    novaData.setDate(novaData.getDate() - 1)
    dataSeleccionada.value = novaData
  }

  const diaSeguent = () => {
    const novaData = new Date(dataSeleccionada.value)
    novaData.setDate(novaData.getDate() + 1)
    dataSeleccionada.value = novaData
  }

  return {
    config,
    autenticat,
    tabActiu,
    grupsRef,
    configuracioRef,
    configuracioExamensRef,
    canviaTab,
    substitucionsRef,
    dataSeleccionada,
    mostrarConfiguracio,
    mostrarConfiguracioExamens,
    mostrarEstadistiques,
    mostrarAjuda,
    mostrarPerfil,
    mostrarMenuMobil,
    loginUser,
    loginPass,
    loginError,
    loginLoading,
    loginRetrySeconds,
    loginRetryTimer,
    isMobile,
    mediaQuery,
    userProfile,
    institucioKey,
    isAdmin,
    esDemo,
    isSchedulerRoute,
    actualitzarModeMobil,
    estatAdreca,
    sincronitzaAdreca,
    aplicaAdreca,
    enNavegar,
    aplicarToken,
    netejarToken,
    carregarEstatHorari,
    carregarConfig,
    cursos,
    cursDeLaData,
    carregarCursos,
    carregarPerfil,
    handleInstitucioCanviada,
    tornarAlGestor,
    anarScheduler,
    versioNova,
    recarregaPagina,
    deixaDeVigilarVersio,
    ferLogin,
    ferLogout,
    obrirConfiguracio,
    obrirConfiguracioExamens,
    obreConfiguracioExamensDesDeVista,
    obrirEstadistiques,
    obrirPerfil,
    obrirAjuda,
    obrirPdfDia,
    diaAnterior,
    diaSeguent,
  }
}
