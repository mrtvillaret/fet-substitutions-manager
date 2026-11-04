import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { ambDataTreball, dataTreball } from '../dataTreball'
import { dataIso } from '../dates'
import { missatgeDError } from '../errorsApi'
import clientHttp from '../api/client'
import * as apiUsuaris from '../api/usuaris'
import { configuracio as configuracioHorari } from '../api/horari'
import { llista as llistaCursos } from '../api/cursos'
import { BASE, ruta, esRutaLocal } from '../basePath'
import { vigilaVersio } from '../versioApp'
import { setLocale } from '../i18n'

export function useAplicacio(dependents) {
  const { t, toast } = dependents

  const config = ref(null)
  const autenticat = ref(false)
  const tabActiu = ref('substitucions')
  const grupsRef = ref(null)

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
  const isSchedulerRoute = ref(window.location.pathname === ruta('scheduler'))

  const actualitzarModeMobil = () => {
    if (!mediaQuery) return
    isMobile.value = mediaQuery.matches
  }

  const actualitzarRuta = () => {
    isSchedulerRoute.value = window.location.pathname === ruta('scheduler')
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
    window.history.pushState({}, '', ruta())
    actualitzarRuta()
  }

  const anarScheduler = () => {
    window.history.pushState({}, '', ruta('scheduler'))
    actualitzarRuta()
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
    window.addEventListener('popstate', actualitzarRuta)
    window.addEventListener('obre-configuracio-examens', obreConfiguracioExamensDesDeVista)

    clientHttp.interceptors.response.use(
      (response) => response,
      async (error) => {
        const status = error?.response?.status
        if (status === 401) {
          // Si hi havia una sessió oberta, diu per què s'ha de tornar a entrar
          // (sense activitat el navegador ja ha esborrat la cookie: «No autenticat»).
          if (autenticat.value) {
            loginError.value = error.response?.data?.detail === 'Sessió tancada'
              ? t('app.login.sessionClosed') : t('app.login.sessionExpired')
          }
          netejarToken()
          return Promise.reject(error)
        }
        if (!error.config?._silent) {
          const msg = await missatgeDError(error, t)
          toast.add({ severity: 'error', summary: t('app.errors.title'), detail: msg, life: 5000 })
        }
        return Promise.reject(error)
      }
    )

    try {
      await carregarPerfil()
      await carregarConfig()
      aplicarToken()
    } catch {
      // Cookie absent o expirada — es queda a la pantalla de login
    }
  })

  onBeforeUnmount(() => {
    deixaDeVigilarVersio?.()
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', actualitzarModeMobil)
    }
    window.removeEventListener('popstate', actualitzarRuta)
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
      const response = await apiUsuaris.entra(credencials)
      const delegacio = response.data?.redirect
      if (delegacio && esRutaLocal(delegacio)) {
        // L'usuari és d'una altra instal·lació del mateix domini (p.ex. la demo a
        // /demo/): s'hi entra amb les mateixes credencials i s'hi va.
        await apiUsuaris.entraDelegacio(delegacio, credencials, { baseURL: '' })
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
      await carregarConfig()
    } catch (error) {
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
    } finally {
      loginLoading.value = false
    }
  }

  const ferLogout = () => {
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
    actualitzarRuta,
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
