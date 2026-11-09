import { avisaError } from '../errorsApi.js'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import * as apiExamens from '../api/configuracioExamens.js'
import { ruta } from '../basePath.js'

// Extret de la vista: es preserven estat, efectes i ordre de les operacions.
export function useImportacioExamens({ toast, t, confirm, carregarAssignacions }) {
  function useDragSelect(itemsRef, selectedRef) {
    // lastIndex es la POSICIÓ dins itemsRef.value (no un _key absolut), perquè
    // el rang de Maj+clic funcioni bé encara que itemsRef estigui filtrat.
    const lastIndex = ref(null)
    const dragging = ref(false)
    const dragValue = ref(true)

    const isSelected = (item) => selectedRef.value.some(s => s._key === item._key)

    const setSelected = (item, value) => {
      const ja = isSelected(item)
      if (value && !ja) selectedRef.value = [...selectedRef.value, item]
      else if (!value && ja) selectedRef.value = selectedRef.value.filter(s => s._key !== item._key)
    }

    const onMouseDown = (item, event) => {
      const idx = itemsRef.value.findIndex(i => i._key === item._key)
      const nouEstat = !isSelected(item)
      if (event.shiftKey && lastIndex.value !== null) {
        const [des, fins] = [lastIndex.value, idx].sort((a, b) => a - b)
        for (let i = des; i <= fins; i++) {
          setSelected(itemsRef.value[i], true)
        }
      } else {
        setSelected(item, nouEstat)
        dragValue.value = nouEstat
      }
      lastIndex.value = idx
      dragging.value = true
    }

    const onMouseEnter = (item) => {
      if (dragging.value) setSelected(item, dragValue.value)
    }

    const stopDragging = () => { dragging.value = false }

    onMounted(() => window.addEventListener('mouseup', stopDragging))
    onUnmounted(() => window.removeEventListener('mouseup', stopDragging))

    // "Selecciona/desselecciona tot" opera sobre itemsRef (passa-hi la llista
    // FILTRADA perquè només afecti el que es veu en aquell moment).
    const allSelected = computed(() => itemsRef.value.length > 0 && itemsRef.value.every(isSelected))
    const toggleAll = (value) => {
      if (value) {
        const nous = itemsRef.value.filter(i => !isSelected(i))
        selectedRef.value = [...selectedRef.value, ...nous]
      } else {
        const keys = new Set(itemsRef.value.map(i => i._key))
        selectedRef.value = selectedRef.value.filter(s => !keys.has(s._key))
      }
    }

    return { isSelected, onMouseDown, onMouseEnter, allSelected, toggleAll }
  }

  const mostrarDialegImport = ref(false)

  const carregantPropostes = ref(false)

  const propostes = ref([])

  const propostesSeleccionades = ref([])

  const important = ref(false)

  const sobreescriuImportacio = ref(false)

  const filtreNivellImport = ref([])

  const filtreAssignaturaImport = ref([])

  const filtreEstatImport = ref('')

  const nivellsImport = computed(() => [...new Set(propostes.value.map(p => p.nivell))].sort())

  const assignaturesImport = computed(() => [...new Set(propostes.value.map(p => p.assignatura))].sort())

  const propostesFiltrades = computed(() => propostes.value.filter(p =>
    (filtreNivellImport.value.length === 0 || filtreNivellImport.value.includes(p.nivell)) &&
    (filtreAssignaturaImport.value.length === 0 || filtreAssignaturaImport.value.includes(p.assignatura)) &&
    (!filtreEstatImport.value ||
      (filtreEstatImport.value === 'nova' && !p.ja_existeix) ||
      (filtreEstatImport.value === 'existent' && p.ja_existeix))
  ))

  const dragSelectAssignacions = useDragSelect(propostesFiltrades, propostesSeleccionades)

  const obrirImportacio = async () => {
    mostrarDialegImport.value = true
    carregantPropostes.value = true
    propostes.value = []
    propostesSeleccionades.value = []
    filtreNivellImport.value = []
    filtreAssignaturaImport.value = []
    filtreEstatImport.value = ''
    try {
      const data = await apiExamens.previsualitzaImportacio()
      propostes.value = (data.propostes || []).map((p, idx) => ({ ...p, _key: idx }))
      // Pre-selecciona només les que encara no existeixen i que no s'havien
      // descartat expressament en una importació anterior
      propostesSeleccionades.value = propostes.value.filter(p => !p.ja_existeix && !p.descartada)
    } catch (error) {
      console.error('Error generant propostes d\'importació:', error)
      avisaError(error, () => toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.import.errorPreview'), life: 3000 }))
      mostrarDialegImport.value = false
    } finally {
      carregantPropostes.value = false
    }
  }

  const mostrarResumPrevi = ref(false)

  const resumPrevi = ref(null)

  const resumPreviSobreescriu = ref(false)

  const calculantResumPrevi = ref(false)

  const mostrarResumFinal = ref(false)

  const resumFinal = ref(null)

  const origenResumPrevi = ref('xml')

  const fitxerCsvPendent = ref(null)

  const overwriteCsvPendent = ref(false)

  const netejaProposta = ({ _key, ja_existeix, descartada, ...rest }) => rest

  const previsualitzarImportacio = async () => {
    if (propostesSeleccionades.value.length === 0) return
    calculantResumPrevi.value = true
    try {
      const data = await apiExamens.simulaImportacio({
        propostes: propostesSeleccionades.value.map(netejaProposta),
        overwrite: sobreescriuImportacio.value
      })
      origenResumPrevi.value = 'xml'
      resumPreviSobreescriu.value = sobreescriuImportacio.value
      resumPrevi.value = data
      mostrarResumPrevi.value = true
    } catch (error) {
      console.error('Error calculant el resum previ:', error)
      avisaError(error, () => toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.import.errorPreview'), life: 3000 }))
    } finally {
      calculantResumPrevi.value = false
    }
  }

  const previsualitzarImportacioCsv = async (fitxer, overwrite) => {
    const formData = new FormData()
    formData.append('file', fitxer)
    formData.append('overwrite', overwrite)
    try {
      const data = await apiExamens.simulaImportacioCsv(formData)
      origenResumPrevi.value = 'csv'
      resumPreviSobreescriu.value = overwrite
      fitxerCsvPendent.value = fitxer
      overwriteCsvPendent.value = overwrite
      resumPrevi.value = data
      mostrarResumPrevi.value = true
    } catch (error) {
      console.error('Error calculant el resum previ del CSV:', error)
      const detail = error.response?.data?.detail || t('examConfig.import.errorPreview')
      avisaError(error, () => toast.add({ severity: 'error', summary: t('common.error'), detail, life: 4000 }))
    }
  }

  const confirmarImportacioDefinitiva = async () => {
    important.value = true
    try {
      let data
      if (origenResumPrevi.value === 'csv') {
        const formData = new FormData()
        formData.append('file', fitxerCsvPendent.value)
        formData.append('overwrite', overwriteCsvPendent.value)
        data = await apiExamens.importaCsv(formData)
        fitxerCsvPendent.value = null
      } else {
        const seleccionadesKeys = new Set(propostesSeleccionades.value.map(p => p._key))
        const descartades = propostes.value
          .filter(p => !seleccionadesKeys.has(p._key) && !p.ja_existeix)
          .map(({ assignatura, grup, titular }) => ({ assignatura, grup, titular }))

        data = await apiExamens.importa({
          propostes: propostesSeleccionades.value.map(netejaProposta),
          descartades,
          overwrite: sobreescriuImportacio.value
        })
        mostrarDialegImport.value = false
        sobreescriuImportacio.value = false
      }

      mostrarResumPrevi.value = false
      resumFinal.value = data
      mostrarResumFinal.value = true
      await carregarAssignacions()
    } catch (error) {
      console.error('Error important:', error)
      const detail = error.response?.data?.detail || t('examConfig.import.errorApply')
      avisaError(error, () => toast.add({ severity: 'error', summary: t('common.error'), detail, life: 4000 }))
    } finally {
      important.value = false
    }
  }

  const inputCsvRef = ref(null)

  const exportarAssignacionsCsv = () => {
    window.open(ruta('api/config/exportar-assignacions-csv'), '_blank')
  }

  const triarFitxerCsv = () => {
    inputCsvRef.value?.click()
  }

  const onFitxerCsvSeleccionat = (event) => {
    const fitxer = event.target.files?.[0]
    event.target.value = ''
    if (!fitxer) return

    confirm.require({
      message: t('examConfig.import.overwriteConfirmCsv', { filename: fitxer.name }),
      header: t('examConfig.import.importCsv'),
      icon: 'pi pi-question-circle',
      acceptLabel: t('examConfig.import.overwrite'),
      rejectLabel: t('examConfig.import.merge'),
      accept: () => previsualitzarImportacioCsv(fitxer, true),
      reject: () => previsualitzarImportacioCsv(fitxer, false)
    })
  }

  return { mostrarDialegImport, carregantPropostes, propostes, propostesSeleccionades, important, sobreescriuImportacio, filtreNivellImport, filtreAssignaturaImport, filtreEstatImport, nivellsImport, assignaturesImport, propostesFiltrades, dragSelectAssignacions, obrirImportacio, mostrarResumPrevi, resumPrevi, resumPreviSobreescriu, calculantResumPrevi, mostrarResumFinal, resumFinal, previsualitzarImportacio, confirmarImportacioDefinitiva, inputCsvRef, exportarAssignacionsCsv, triarFitxerCsv, onFitxerCsvSeleccionat }
}
