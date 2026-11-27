import { avisaError, detallDError } from '../api/errors.js'
import { ref, computed, watch } from 'vue'
import * as apiPdf from '../api/pdf.js'
import { dataIso } from '../dates.js'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../pdfOpcions.js'
import { desaPdf } from '../desaPdf.js'
import { SENSE_NIVELL, opcionsNivellsPdf, parametresNivellsPdf, seleccioInicialNivellsPdf } from '../vigilanciesPdf.js'

// Els PDF de Vigilàncies: el del dia (amb la revisió dels nivells triats) i el d'un interval.
export function usePdfVigilancies({ dataISO, dataTreball, nivells, toast, t }) {
  const mostrarDialogPDF = ref(false)

  const mostrarDialogInterval = ref(false)

  const confirmacioImportants = ref(false)

  const generantPDF = ref(false)

  const generantPDFInterval = ref(false)

  const mostrarDialogValidacionsVig = ref(false)

  // La revisió del PDF dels nivells triats: el backend hi posa els problemes de les
  // vigilàncies que imprimirà (com el PDF), separats per gravetat.
  const validacionsVig = ref({ conflicts: [], warnings: [], informatius: [], total: 0, has_critical: false })

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
      const validacioResponse = await apiPdf.validacions(dataISO.value, {
        params: parametresNivellsPdf(pdfConfig.value.nivells)
      })
      confirmacioImportants.value = false
      validacionsVig.value = validacioResponse.data

      if (validacionsVig.value.total > 0) {
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
    if (validacionsVig.value.has_critical && !confirmacioImportants.value) return
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
      const response = await apiPdf.vigilanciesDelDia(dataISO.value, {
        ...parametresComuns(pdfConfig.value),
        ...parametresNivellsPdf(pdfConfig.value.nivells),
        include_substitucions: pdfConfig.value.includeSubstitucions
      })
      desaPdf(response.data, `vigilancies_${dataISO.value}.pdf`)

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
      const dataInici = dataIso(intervalConfig.value.dataInici)
      const dataFinal = dataIso(intervalConfig.value.dataFinal)

      if (!dataInici || !dataFinal) {
        toast.add({
          severity: 'error',
          summary: t('vigilancies.errors.dateFormatTitle'),
          detail: t('vigilancies.errors.dateFormat'),
          life: 3000
        })
        return
      }
      const response = await apiPdf.vigilanciesInterval({
        data_inici: dataInici,
        data_final: dataFinal,
        ...parametresNivellsPdf(intervalConfig.value.nivells),
        ...parametresComuns(intervalConfig.value),
        include_weekends: intervalConfig.value.includeWeekends,
        include_empty_days: intervalConfig.value.includeEmptyDays,
        dia_per_pagina: intervalConfig.value.diaPerPagina,
        include_substitucions: intervalConfig.value.includeSubstitucions
      })
      desaPdf(response.data, `vigilancies_interval_${dataInici}_a_${dataFinal}.pdf`)

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

  return { confirmacioImportants, mostrarDialogPDF, mostrarDialogInterval, generantPDF, generantPDFInterval, mostrarDialogValidacionsVig, validacionsVig, pdfConfig, intervalConfig, opcionsNivellsPdfDia, opcionsNivellsPdfInterval, mostrarDialegPDF, mostrarDialegInterval, generarPDF, continuarPDFVig, cancelarPDFVig, generarPDFInterval }
}
