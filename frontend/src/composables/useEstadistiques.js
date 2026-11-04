import { ref, watch, computed } from 'vue'
import * as apiConfiguracio from '../api/configuracio'
import * as apiEstadistiques from '../api/estadistiques'
import * as apiPdf from '../api/pdf'
import { dataTreball } from '../dataTreball'
import { dataIso } from '../dates'
import { ordenaAlfabeticament } from '../ordreAlfabetic'
import { localizeBackendDayName } from '../views/scheduler/textUtils'

export function useEstadistiques(dependents) {
  const { props, emit, t, toast } = dependents

  const loading = ref(false)
  const dataInici = ref(null)
  const dataFinal = ref(null)
  const resum = ref(null)
  const professorsStats = ref({
    professors_absents: [],
    top_substituts: []
  })
  const temporalStats = ref(null)
  const classesStats = ref({ classes: [] })
  const professorsResum = ref({ professors: [] })
  const professorDetailVisible = ref(false)
  const professorDetail = ref(null)
  const detailLoading = ref(false)
  const frangesVisible = ref(false)
  const frangesLoading = ref(false)
  const frangesData = ref(null)
  const frangesDia = ref('')
  const frangesHora = ref('')
  const classesDetailVisible = ref(false)
  const classesDetailLoading = ref(false)
  const classesDetailData = ref(null)
  const classesSeleccionades = ref([])

  // Informes PDF
  const generantDireccio = ref(false)
  const generantProfessor = ref(false)
  const informeProfessorSeleccionat = ref(null)
  const informeMostrarTaules = ref(false)
  const informeProfessorsOpcions = ref([])

  // Filtre per hores: les franges de l'horari de l'interval i les triades
  const frangesHorari = ref([])
  const horesTriades = ref([])

  const diesDisponibles = computed(() => (temporalStats.value?.dies || []).map((d) => d.dia))
  // El backend anomena els dies en català; a la pantalla, en l'idioma triat
  const diesOpcions = computed(() => diesDisponibles.value.map((d) => ({ label: localizeBackendDayName(d, t), value: d })))
  const horesDisponibles = computed(() => (temporalStats.value?.hores || []).map((h) => h.hora))

  const topAbsents = computed(() => (professorsStats.value.professors_absents || []).slice(0, 5))
  const topSubstituts = computed(() => (professorsStats.value.top_substituts || []).slice(0, 5))
  const topAbsentsMax = computed(() => Math.max(0, ...topAbsents.value.map(p => p.total || 0)))
  const topSubstitutsMax = computed(() => Math.max(0, ...topSubstituts.value.map(p => p.total || 0)))
  // Per ordre alfabètic natural («1-ESO-B» abans de «1-ESO-C», «2-BAT» abans de «10-...»)
  const classesDisponibles = computed(() =>
    ordenaAlfabeticament((classesStats.value?.classes || []).map((c) => c.grup)).map((grup) => ({
      label: grup,
      value: grup
    }))
  )

  // Curs triat al selector del diàleg (null = rang personalitzat)
  const cursTriatId = ref(null)

  // Aplica el rang d'un curs. L'últim curs és obert (data_fi = null): el tanquem amb la
  // data més tardana entre avui, l'inici i la data de treball — així no queda un rang
  // invertit quan es preparen dades d'un curs que encara no ha començat.
  const aplicarRangCurs = (curs) => {
    if (!curs?.data_inici) return false
    const inici = new Date(curs.data_inici)
    let fi
    if (curs.data_fi) {
      fi = new Date(curs.data_fi)
    } else {
      const candidats = [Date.now(), inici.getTime()]
      // la data de treball, per acotar el final d'un curs encara obert
      candidats.push(dataTreball.value.getTime())
      fi = new Date(Math.max(...candidats))
    }
    dataInici.value = inici
    dataFinal.value = fi
    return true
  }

  const onCursTriat = () => {
    const curs = props.cursos.find(c => c.id === cursTriatId.value)
    if (curs && aplicarRangCurs(curs)) carregarEstadistiques()
  }

  // Inicialitzar dates: el curs de la data de treball mana; si no n'hi ha, la BD o
  // últims 30 dies. Les dates es poden ajustar lliurement (un rang pot creuar cursos).
  const inicialitzarDates = async () => {
    cursTriatId.value = props.curs?.id ?? null
    if (aplicarRangCurs(props.curs)) return

    try {
      const response = await apiConfiguracio.llegeix()
      const cfg = response || {}
      const dataIniciCfg = cfg.data_inici_estadistiques
      const dataFinalCfg = cfg.data_final_estadistiques

      if (dataIniciCfg && dataFinalCfg) {
        dataInici.value = new Date(dataIniciCfg)
        dataFinal.value = new Date(dataFinalCfg)
        return
      }
    } catch (error) {
      console.error('Error carregant configuració estadístiques:', error)
    }

    // Dates per defecte: últims 30 dies
    const avui = new Date()
    dataFinal.value = avui

    const fa30Dies = new Date()
    fa30Dies.setDate(avui.getDate() - 30)
    dataInici.value = fa30Dies
  }

  const formatDate = dataIso

  // El període i el filtre per hores de tots els recomptes (sense hores triades, totes)
  const paramsDelFiltre = () => ({
    data_inici: formatDate(dataInici.value),
    data_final: formatDate(dataFinal.value),
    ...(horesTriades.value.length ? { hores: horesTriades.value } : {})
  })

  // Les hores amb què s'han carregat les estadístiques: en tancar el selector,
  // només es recarrega si han canviat (també la llista de professors dels
  // informes, que fan servir el mateix filtre)
  let horesCarregades = []
  const recarregaSiCanviaElFiltre = () => {
    const ara = [...horesTriades.value].sort()
    if (ara.join('|') !== [...horesCarregades].sort().join('|')) {
      carregarEstadistiques()
      carregarInformeProfessors()
    }
  }

  const carregarEstadistiques = async () => {
    loading.value = true
    try {
      const params = paramsDelFiltre()
      horesCarregades = [...horesTriades.value]

      // Guardar dates a la BD per institució (les hores, no)
      await apiConfiguracio.desa({
        data_inici_estadistiques: params.data_inici,
        data_final_estadistiques: params.data_final
      })

      const [resumResp, professorsResp, temporalResp, classesResp, taulaResp] = await Promise.all([
        apiEstadistiques.resum({ params }),
        apiEstadistiques.professors({ params }),
        apiEstadistiques.temporal({ params }),
        apiEstadistiques.classes({ params }),
        apiEstadistiques.taula({ params })
      ])

      resum.value = resumResp.data
      professorsStats.value = professorsResp.data
      temporalStats.value = temporalResp.data
      classesStats.value = classesResp.data
      professorsResum.value = taulaResp.data
    } catch (error) {
      console.error('Error carregant estadístiques:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('stats.errors.load'),
        life: 3000
      })
    } finally {
      loading.value = false
    }
  }

  // El tipus de fila de substitució (ABSENCIA, SERVEI...), en l'idioma triat
  const nomTipusFila = (tipus) => (tipus ? t(`stats.detail.types.${tipus}`) : '')

  const formatPercent = (value, total) => {
    if (!total || total <= 0) return '0%'
    const percent = Math.min(100, Math.round((value / total) * 100))
    return `${percent}%`
  }

  const formatBarWidth = (value, maxValue) => {
    if (!maxValue || maxValue <= 0) return '0%'
    const percent = Math.min(100, Math.round((value / maxValue) * 100))
    return `${percent}%`
  }

  const formatProfessors = (professors) => {
    if (!professors || professors.length === 0) return '-'
    return professors.map((p) => `${p.professor} (${p.total})`).join(', ')
  }

  const obrirResumFranges = () => {
    if (!frangesDia.value) {
      frangesDia.value = diesDisponibles.value[0] || ''
    }
    if (!frangesHora.value) {
      frangesHora.value = horesDisponibles.value[0] || ''
    }
    frangesVisible.value = true
    if (frangesDia.value && frangesHora.value) {
      carregarFranges()
    }
  }

  const carregarFranges = async () => {
    if (!frangesDia.value || !frangesHora.value) return
    frangesLoading.value = true
    try {
      const params = {
        ...paramsDelFiltre(),
        dia: frangesDia.value,
        hora: frangesHora.value
      }
      const resp = await apiEstadistiques.franges({ params })
      frangesData.value = resp.data
    } catch (error) {
      console.error('Error carregant franges:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('stats.errors.slots'),
        life: 3000
      })
    } finally {
      frangesLoading.value = false
    }
  }

  const onProfessorRowClick = async (event) => {
    const prof = event?.data?.professor
    if (!prof) return
    detailLoading.value = true
    professorDetailVisible.value = true
    try {
      const params = paramsDelFiltre()
      const resp = await apiEstadistiques.professor(prof, { params })
      professorDetail.value = resp.data
    } catch (error) {
      console.error('Error carregant detall professor:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('stats.errors.teacherDetail'),
        life: 3000
      })
    } finally {
      detailLoading.value = false
    }
  }

  const obrirDetallClasses = (grup = null) => {
    if (grup) {
      classesSeleccionades.value = [grup]
    } else if (!classesSeleccionades.value.length && classesDisponibles.value.length) {
      classesSeleccionades.value = [classesDisponibles.value[0].value]
    }
    classesDetailVisible.value = true
  }

  const onClasseRowClick = (event) => {
    const grup = event?.data?.grup
    if (!grup) return
    obrirDetallClasses(grup)
    carregarDetallClasses()
  }

  const carregarDetallClasses = async () => {
    if (!classesSeleccionades.value.length) {
      toast.add({
        severity: 'warn',
        summary: t('stats.classes.selectionRequired'),
        detail: t('stats.classes.selectAtLeastOne'),
        life: 2500
      })
      return
    }

    classesDetailLoading.value = true
    try {
      const params = {
        ...paramsDelFiltre(),
        grups: classesSeleccionades.value
      }
      const resp = await apiEstadistiques.detallClasses({ params })
      classesDetailData.value = resp.data
    } catch (error) {
      console.error('Error carregant detall classes:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('stats.errors.classesDetail'),
        life: 3000
      })
    } finally {
      classesDetailLoading.value = false
    }
  }

  const tancar = () => {
    emit('update:visible', false)
  }

  const _descarregarPdf = async (url, params, nomFitxer, refLoading) => {
    refLoading.value = true
    try {
      const resp = await apiPdf.descarrega(url, { params, responseType: 'blob' })
      const blob = new Blob([resp.data], { type: 'application/pdf' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = nomFitxer
      link.click()
      URL.revokeObjectURL(link.href)
    } catch (error) {
      // L'avís amb el missatge del backend (detail) el mostra l'interceptor
      // d'App.vue, que també el llegeix del blob
      console.error('Error generant informe:', error)
    } finally {
      refLoading.value = false
    }
  }

  const generarInformeDireccio = async () => {
    const params = paramsDelFiltre()
    const nom = `informe_direccio_${params.data_inici}_${params.data_final}.pdf`
    await _descarregarPdf('/api/informes/direccio', params, nom, generantDireccio)
  }

  const generarInformeProfessor = async () => {
    const params = {
      ...paramsDelFiltre(),
      mostrar_taules: informeMostrarTaules.value,
    }
    if (informeProfessorSeleccionat.value) {
      params.professor = informeProfessorSeleccionat.value
    }
    const nom = informeProfessorSeleccionat.value
      ? `informe_${informeProfessorSeleccionat.value}_${params.data_inici}_${params.data_final}.pdf`
      : `informe_professors_${params.data_inici}_${params.data_final}.pdf`
    await _descarregarPdf('/api/informes/professor', params, nom, generantProfessor)
  }

  const carregarInformeProfessors = async () => {
    try {
      const resp = await apiPdf.professorsInforme({ params: paramsDelFiltre() })
      informeProfessorsOpcions.value = ordenaAlfabeticament(resp.data.professors || [])
      // El professor triat potser no té res al nou interval
      if (!informeProfessorsOpcions.value.includes(informeProfessorSeleccionat.value)) {
        informeProfessorSeleccionat.value = null
      }
    } catch (error) {
      console.error('Error carregant llista professors:', error)
    }
  }

  // Les franges de l'horari de l'interval, per al filtre per hores. Si una
  // hora triada ja no hi és (un altre horari), es treu del filtre.
  const carregarFrangesHorari = async () => {
    try {
      const params = {
        data_inici: formatDate(dataInici.value),
        data_final: formatDate(dataFinal.value)
      }
      const resp = await apiEstadistiques.hores({ params })
      frangesHorari.value = resp.data.hores || []
      horesTriades.value = horesTriades.value.filter((h) => frangesHorari.value.includes(h))
    } catch (error) {
      console.error('Error carregant les franges de l\'horari:', error)
    }
  }

  // Carregar quan s'obre el diàleg
  watch(() => props.visible, (newVal) => {
    if (newVal) {
      inicialitzarDates().then(async () => {
        await carregarFrangesHorari()
        carregarEstadistiques()
        carregarInformeProfessors()
      })
    }
  })

  // La llista de professors i les franges són les de l'interval: es refan
  // quan canvien les dates (la llista, després de treure del filtre les hores
  // que ja no hi són)
  watch([dataInici, dataFinal], async ([inici, final]) => {
    if (props.visible && inici && final) {
      await carregarFrangesHorari()
      carregarInformeProfessors()
    }
  })

  // Si canvia la data de treball (i per tant el seu curs) amb el diàleg obert,
  // reescopa les estadístiques al nou curs
  watch(() => props.curs?.id, (nou, antic) => {
    if (!props.visible || nou === antic || !nou) return
    cursTriatId.value = nou
    if (aplicarRangCurs(props.curs)) carregarEstadistiques()
  })

  return {
    loading,
    dataInici,
    dataFinal,
    resum,
    professorsStats,
    temporalStats,
    classesStats,
    professorsResum,
    professorDetailVisible,
    professorDetail,
    detailLoading,
    frangesVisible,
    frangesLoading,
    frangesData,
    frangesDia,
    frangesHora,
    classesDetailVisible,
    classesDetailLoading,
    classesDetailData,
    classesSeleccionades,
    generantDireccio,
    generantProfessor,
    informeProfessorSeleccionat,
    informeMostrarTaules,
    informeProfessorsOpcions,
    frangesHorari,
    horesTriades,
    diesDisponibles,
    diesOpcions,
    horesDisponibles,
    topAbsents,
    topSubstituts,
    topAbsentsMax,
    topSubstitutsMax,
    classesDisponibles,
    cursTriatId,
    aplicarRangCurs,
    onCursTriat,
    inicialitzarDates,
    formatDate,
    paramsDelFiltre,
    horesCarregades,
    recarregaSiCanviaElFiltre,
    carregarEstadistiques,
    nomTipusFila,
    formatPercent,
    formatBarWidth,
    formatProfessors,
    obrirResumFranges,
    carregarFranges,
    onProfessorRowClick,
    obrirDetallClasses,
    onClasseRowClick,
    carregarDetallClasses,
    tancar,
    _descarregarPdf,
    generarInformeDireccio,
    generarInformeProfessor,
    carregarInformeProfessors,
    carregarFrangesHorari,
  }
}
