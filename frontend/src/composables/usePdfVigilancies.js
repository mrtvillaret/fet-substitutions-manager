import { avisaError, detallDError } from '../errorsApi.js'
import { ref, computed, watch } from 'vue'
import * as apiPdf from '../api/pdf.js'
import { dataIso } from '../dates.js'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../pdfOpcions.js'
import { SENSE_NIVELL, opcionsNivellsPdf, parametresNivellsPdf, seleccioInicialNivellsPdf } from '../vigilanciesPdf.js'

// Extret de la vista: es preserven estat, efectes i ordre de les operacions.
export function usePdfVigilancies({ dataISO, dataTreball, nivells, vigilancies, toast, t }) {
  const mostrarDialogPDF = ref(false)

  const mostrarDialogInterval = ref(false)

  const confirmacioImportants = ref(false)

  const generantPDF = ref(false)

  const generantPDFInterval = ref(false)

  const mostrarDialogValidacionsVig = ref(false)

  const validacionsVig = ref({ conflicts: [], warnings: [], total: 0, has_critical: false })

  const problemesVigFiltrats = computed(() => {
    const seleccio = parametresNivellsPdf(pdfConfig.value.nivells)
    const nivellsTriats = new Set(pdfConfig.value.nivells.filter(n => n !== SENSE_NIVELL))
    const ids = new Set(vigilancies.value.filter(v => v.nivell
      ? (!nivellsTriats.size || nivellsTriats.has(v.nivell))
      : seleccio.inclou_sense_nivell).map(v => String(v.id)))
    // L'API separa els problemes tipats de vigilàncies; mai no mirem el text traduït.
    return (validacionsVig.value.problemes_vigilancies || []).filter(p =>
      p.tipus && (!p.files.length || p.files.some(id => ids.has(String(id))))
    )
  })

  const conflictesVigFiltrats = computed(() =>
    problemesVigFiltrats.value.filter(p => p.gravetat === 'important').map(p => p.missatge)
  )

  const warningsVigFiltrats = computed(() =>
    problemesVigFiltrats.value.filter(p => p.gravetat === 'avis').map(p => p.missatge)
  )

  const informatiusVigFiltrats = computed(() =>
    problemesVigFiltrats.value.filter(p => p.gravetat === 'informacio').map(p => p.missatge)
  )

  const totalVigFiltrats = computed(() =>
    conflictesVigFiltrats.value.length + warningsVigFiltrats.value.length + informatiusVigFiltrats.value.length
  )

  const pdfConfig = ref({
    nivells: [],
    format: 'hores',
    midaLletra: midaPerDefecte('hores'),
    showComments: true,
    showHours: false,
    compress: false,
    includeSubstitucions: false
  })

  const intervalConfig = ref({
    dataInici: null,
    dataFinal: null,
    nivells: [],
    includeWeekends: false,
    includeEmptyDays: false,
    format: 'hores',
    midaLletra: midaPerDefecte('hores'),
    diaPerPagina: false,
    showComments: true,
    showHours: false,
    compress: false,
    includeSubstitucions: false
  })

  const senseNivellDia = ref(0)

  const senseNivellInterval = ref(0)

  const opcionsNivellsPdfDia = computed(() =>
    opcionsNivellsPdf(nivells.value, senseNivellDia.value, (count) =>
      t('vigilancies.dialogs.withoutLevel', { count })
    )
  )

  const opcionsNivellsPdfInterval = computed(() =>
    opcionsNivellsPdf(nivells.value, senseNivellInterval.value, (count) =>
      t('vigilancies.dialogs.withoutLevel', { count })
    )
  )

  const carregarPreferenciesPdf = async () => {
    try {
      const response = await apiPdf.preferencies()
      aplicaPreferencies(
        pdfConfig,
        response.data?.vigilancies,
        ['format', 'midaLletra', 'showComments', 'showHours', 'compress', 'includeSubstitucions']
      )
      aplicaPreferencies(
        intervalConfig,
        response.data?.vigilancies_interval,
        ['format', 'midaLletra', 'diaPerPagina', 'includeWeekends', 'includeEmptyDays', 'showComments', 'showHours', 'compress', 'includeSubstitucions']
      )
    } catch (error) {
      console.error('Error carregant preferències PDF:', error)
    }
  }

  const desarPreferenciesPdf = async (tipus) => {
    try {
      if (tipus === 'vigilancies') {
        await apiPdf.desaPreferencies({
          vigilancies: {
            format: pdfConfig.value.format,
            midaLletra: pdfConfig.value.midaLletra,
            showComments: pdfConfig.value.showComments,
            showHours: pdfConfig.value.showHours,
            compress: pdfConfig.value.compress,
            includeSubstitucions: pdfConfig.value.includeSubstitucions
          }
        })
        return
      }
      if (tipus === 'interval') {
        await apiPdf.desaPreferencies({
          vigilancies_interval: {
            format: intervalConfig.value.format,
            midaLletra: intervalConfig.value.midaLletra,
            diaPerPagina: intervalConfig.value.diaPerPagina,
            includeWeekends: intervalConfig.value.includeWeekends,
            includeEmptyDays: intervalConfig.value.includeEmptyDays,
            showComments: intervalConfig.value.showComments,
            showHours: intervalConfig.value.showHours,
            compress: intervalConfig.value.compress,
            includeSubstitucions: intervalConfig.value.includeSubstitucions
          }
        })
      }
    } catch (error) {
      console.error('Error desant preferències PDF:', error)
    }
  }

  const recompteSenseNivell = async (dataInici, dataFinal) => {
    const response = await apiPdf.comptesSenseNivell({
      params: { data_inici: dataInici, data_final: dataFinal }
    })
    return response.data.sense_nivell || 0
  }

  const mostrarDialegPDF = async () => {
    confirmacioImportants.value = false
    senseNivellDia.value = await recompteSenseNivell(dataISO.value, dataISO.value)
    pdfConfig.value.nivells = seleccioInicialNivellsPdf(opcionsNivellsPdfDia.value)
    await carregarPreferenciesPdf()
    mostrarDialogPDF.value = true
  }

  const mostrarDialegInterval = async () => {
    intervalConfig.value.dataInici = dataTreball.value
    intervalConfig.value.dataFinal = dataTreball.value
    senseNivellInterval.value = await recompteSenseNivell(dataISO.value, dataISO.value)
    intervalConfig.value.nivells = seleccioInicialNivellsPdf(opcionsNivellsPdfInterval.value)
    await carregarPreferenciesPdf()
    mostrarDialogInterval.value = true
  }

  watch(
    () => [intervalConfig.value.dataInici, intervalConfig.value.dataFinal],
    async ([inici, final]) => {
      if (!mostrarDialogInterval.value || !inici || !final) return
      const dataInici = dataIso(inici)
      const dataFinal = dataIso(final)
      if (!dataInici || !dataFinal) return
      const teniaOpcioSenseNivell = senseNivellInterval.value > 0
      senseNivellInterval.value = await recompteSenseNivell(dataInici, dataFinal)
      const valorsValids = new Set(opcionsNivellsPdfInterval.value.map((opcio) => opcio.valor))
      intervalConfig.value.nivells = intervalConfig.value.nivells.filter((valor) => valorsValids.has(valor))
      if (!teniaOpcioSenseNivell && senseNivellInterval.value > 0) {
        intervalConfig.value.nivells.push(SENSE_NIVELL)
      }
    }
  )

  const generarPDF = async () => {
    confirmacioImportants.value = false
    generantPDF.value = true
    try {
      const validacioResponse = await apiPdf.validacions(dataISO.value)
      confirmacioImportants.value = false
      validacionsVig.value = validacioResponse.data
      validacionsVig.value.has_critical = conflictesVigFiltrats.value.length > 0

      if (totalVigFiltrats.value > 0) {
        mostrarDialogPDF.value = false
        mostrarDialogValidacionsVig.value = true
        generantPDF.value = false
        return
      }

      await _baixarPDFVigilancies()
    } catch (err) {
      console.error('Error validant PDF:', err)
      // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
      avisaError(err, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: detallDError(err) || t('vigilancies.errors.generatePdf'),
        life: 5000
      }))
      generantPDF.value = false
    }
  }

  const continuarPDFVig = async () => {
    if (conflictesVigFiltrats.value.length && !confirmacioImportants.value) return
    await _baixarPDFVigilancies()
    mostrarDialogValidacionsVig.value = false
  }

  const cancelarPDFVig = () => {
    confirmacioImportants.value = false
    mostrarDialogValidacionsVig.value = false
    mostrarDialogPDF.value = true
    generantPDF.value = false
  }

  const _baixarPDFVigilancies = async () => {
    generantPDF.value = true
    try {
      const seleccioNivells = parametresNivellsPdf(pdfConfig.value.nivells)
      const params = new URLSearchParams({
        ...parametresComuns(pdfConfig.value),
        ...seleccioNivells,
        include_substitucions: pdfConfig.value.includeSubstitucions
      })

      const url = `/api/pdf/vigilancies/${dataISO.value}?${params.toString()}`
      const response = await apiPdf.descarrega(url, { responseType: 'blob' })

      const blob = new Blob([response.data], { type: 'application/pdf' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `vigilancies_${dataISO.value}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)

      toast.add({
        severity: 'success',
        summary: t('vigilancies.messages.pdfGeneratedTitle'),
        detail: t('vigilancies.messages.pdfGeneratedDetail'),
        life: 3000
      })

      await desarPreferenciesPdf('vigilancies')
      mostrarDialogPDF.value = false
    } catch (err) {
      console.error('Error generant PDF:', err)
      // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
      avisaError(err, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: detallDError(err) || t('vigilancies.errors.generatePdf'),
        life: 5000
      }))
    } finally {
      generantPDF.value = false
    }
  }

  const generarPDFInterval = async () => {
    // Validar dates abans de començar
    if (!intervalConfig.value.dataInici || !intervalConfig.value.dataFinal) {
      toast.add({
        severity: 'warn',
        summary: t('vigilancies.errors.datesRequiredTitle'),
        detail: t('vigilancies.errors.datesRequired'),
        life: 3000
      })
      return
    }

    if (opcionsNivellsPdfInterval.value.length > 0 && !intervalConfig.value.nivells?.length) {
      toast.add({
        severity: 'warn',
        summary: t('vigilancies.errors.levelsRequiredTitle'),
        detail: t('vigilancies.errors.levelsRequired'),
        life: 3000
      })
      return
    }

    generantPDFInterval.value = true

    try {
      // Convertir dates a format YYYY-MM-DD
          const formatDate = dataIso

      const dataInici = formatDate(intervalConfig.value.dataInici)
      const dataFinal = formatDate(intervalConfig.value.dataFinal)

      if (!dataInici || !dataFinal) {
        toast.add({
          severity: 'error',
          summary: t('vigilancies.errors.dateFormatTitle'),
          detail: t('vigilancies.errors.dateFormat'),
          life: 3000
        })
        return
      }
      const seleccioNivells = parametresNivellsPdf(intervalConfig.value.nivells)

      // Construir URL amb paràmetres
      const params = new URLSearchParams({
        data_inici: dataInici,
        data_final: dataFinal,
        ...seleccioNivells,
        ...parametresComuns(intervalConfig.value),
        include_weekends: intervalConfig.value.includeWeekends,
        include_empty_days: intervalConfig.value.includeEmptyDays,
        dia_per_pagina: intervalConfig.value.diaPerPagina,
        include_substitucions: intervalConfig.value.includeSubstitucions
      })

      const url = `/api/pdf/vigilancies/interval?${params.toString()}`

      // Descarregar PDF
      const response = await apiPdf.descarrega(url, {
        responseType: 'blob'
      })

      // Crear link temporal per descarregar
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `vigilancies_interval_${dataInici}_a_${dataFinal}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)

      toast.add({
        severity: 'success',
        summary: t('vigilancies.messages.pdfIntervalTitle'),
        detail: t('vigilancies.messages.pdfIntervalDetail'),
        life: 3000
      })

      await desarPreferenciesPdf('interval')

      mostrarDialogInterval.value = false
    } catch (err) {
      console.error('Error generant PDF interval:', err)
      // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
      avisaError(err, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: detallDError(err) || t('vigilancies.errors.generatePdfInterval'),
        life: 5000
      }))
    } finally {
      generantPDFInterval.value = false
    }
  }

  return { informatiusVigFiltrats, confirmacioImportants, mostrarDialogPDF, mostrarDialogInterval, generantPDF, generantPDFInterval, mostrarDialogValidacionsVig, validacionsVig, conflictesVigFiltrats, warningsVigFiltrats, pdfConfig, intervalConfig, opcionsNivellsPdfDia, opcionsNivellsPdfInterval, mostrarDialegPDF, mostrarDialegInterval, generarPDF, continuarPDFVig, cancelarPDFVig, generarPDFInterval }
}
