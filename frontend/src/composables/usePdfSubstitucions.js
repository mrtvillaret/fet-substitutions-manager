import { ref, computed } from 'vue'
import * as apiPdf from '../api/pdf.js'
import * as apiSubstitucions from '../api/substitucions.js'
import { jaAvisat } from '../errorsApi.js'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../pdfOpcions.js'

// Flux del PDF de substitucions; la data i l'ordre continuen sent els de la vista.
export function usePdfSubstitucions({ dataISO, ordreFiles, horesDisponibles, collator, toast, t, mostrarAvisos, carregarSubstitucions }) {
  // PDF export
  const mostrarDialogPDF = ref(false)
  const mostrarDialogValidacions = ref(false)
  const confirmacioImportants = ref(false)

  const generantPDF = ref(false)
  const reassignantProblematics = ref(false)
  const reassignChanges = ref([])
  const validacions = ref({
    conflicts: [],
    warnings: [],
    total: 0,
    has_critical: false
  })

  const warningsFiltrats = computed(() => {
    const warnings = validacions.value.warnings || []
    return warnings.filter((warning) => {
      const text = (warning || '').trim().toLowerCase()
      if (!text.startsWith('⚠️')) return true
      return !(text.includes('prioritat') || text.includes('prioridad') || text.includes('priority'))
    })
  })

  const totalIssuesFiltrats = computed(() => {
    const conflicts = validacions.value.conflicts || []
    return conflicts.length + warningsFiltrats.value.length
  })
  // Mida de la lletra de la taula del dia (routes/pdf.py, MIDES_LLETRA)
  const pdfConfig = ref({
    includeSubstitutions: true,
    includeVigilancies: true,
    showComments: true,
    showHours: false,
    showConflicts: true,
    compress: false,
    blankRows: false,
    format: 'hores',
    midaLletra: midaPerDefecte('hores')
  })

  // PDF Functions
  const aplicarPreferenciesPdf = (prefs) => {
    aplicaPreferencies(pdfConfig, prefs, ['includeSubstitutions', 'includeVigilancies', 'showComments', 'showHours', 'showConflicts', 'compress', 'blankRows', 'format', 'midaLletra'])
  }

  const carregarPreferenciesPdf = async () => {
    try {
      const response = await apiPdf.preferencies({ _silent: true })
      aplicarPreferenciesPdf(response.data?.substitucions)
    } catch (error) {
      console.error('Error carregant preferències PDF:', error)
    }
  }

  const desarPreferenciesPdf = async () => {
    try {
      await apiPdf.desaPreferencies({
        substitucions: {
          includeSubstitutions: pdfConfig.value.includeSubstitutions,
          includeVigilancies: pdfConfig.value.includeVigilancies,
          showComments: pdfConfig.value.showComments,
          showHours: pdfConfig.value.showHours,
          showConflicts: pdfConfig.value.showConflicts,
          compress: pdfConfig.value.compress,
          blankRows: pdfConfig.value.blankRows,
          format: pdfConfig.value.format,
          midaLletra: pdfConfig.value.midaLletra
        }
      }, { _silent: true })
    } catch (error) {
      console.error('Error desant preferències PDF:', error)
    }
  }

  const mostrarDialegPDF = async () => {
    confirmacioImportants.value = false
    await carregarPreferenciesPdf()
    mostrarDialogPDF.value = true
  }


  const generarPDFComplet = async () => {
    confirmacioImportants.value = false
    // Validar que almenys un tipus de contingut està seleccionat
    if (!pdfConfig.value.includeSubstitutions && !pdfConfig.value.includeVigilancies) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('substitutions.dialogs.pdf.selectAtLeastOneShort'),
        life: 3000
      })
      return
    }

    generantPDF.value = true
    try {
      reassignChanges.value = []
      // 1. Primer validar abans de generar PDF
      const validacioResponse = await apiPdf.validacions(dataISO.value)
      confirmacioImportants.value = false
      validacions.value = validacioResponse.data

      // 2. Mostrar diàleg de validacions si hi ha problemes
      if (validacions.value.total > 0) {
        // Tancar diàleg de configuració i mostrar diàleg de validacions
        mostrarDialogPDF.value = false
        mostrarDialogValidacions.value = true
        generantPDF.value = false
        return
      }

      // 3. Si no hi ha problemes, continuar directament
      await generarPDFAmbOpcions()

    } catch (error) {
      console.error('Error validant PDF:', error)
      // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
      if (!jaAvisat(error)) {
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('substitutions.errors.validatePdf'),
          life: 3000
        })
      }
      generantPDF.value = false
    }
  }

  const generarPDFAmbOpcions = async () => {
    generantPDF.value = true
    try {
      // Generar PDF
      const params = new URLSearchParams({
        ...parametresComuns(pdfConfig.value),
        include_substitutions: pdfConfig.value.includeSubstitutions,
        include_vigilancies: pdfConfig.value.includeVigilancies,
        show_conflicts: pdfConfig.value.showConflicts,
        blank_rows: pdfConfig.value.blankRows,
        ordre: ordreFiles.value // el mateix ordre que la pantalla
      })

      const url = `/api/pdf/complete/${dataISO.value}?${params.toString()}`

      // Download PDF
      const response = await apiPdf.descarrega(url, {
        responseType: 'blob'
      })

      // Create download link
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `complet_${dataISO.value}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)

      toast.add({
        severity: 'success',
        summary: t('substitutions.messages.pdfGeneratedTitle'),
        detail: t('substitutions.messages.pdfGeneratedDetail', { date: dataISO.value }),
        life: 3000
      })

      await desarPreferenciesPdf()

      // Tancar tots els diàlegs
      mostrarDialogPDF.value = false
      mostrarDialogValidacions.value = false
    } catch (error) {
      console.error('Error generant PDF:', error)
      // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
      if (!jaAvisat(error)) {
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('substitutions.errors.generatePdf'),
          life: 3000
        })
      }
    } finally {
      generantPDF.value = false
    }
  }

  const continuarPDF = async () => {
    if (validacions.value.conflicts?.length && !confirmacioImportants.value) return
    await generarPDFAmbOpcions()
  }

  const cancelarPDF = () => {
    confirmacioImportants.value = false
    mostrarDialogValidacions.value = false
    mostrarDialogPDF.value = true
    generantPDF.value = false
  }

  const reassignarProblematics = async () => {
    confirmacioImportants.value = false
    reassignantProblematics.value = true
    try {
      const canvis = []
      if (pdfConfig.value.includeSubstitutions) {
        const respostaSubs = await apiSubstitucions.reassignaProblematiques(dataISO.value)
        mostrarAvisos(respostaSubs?.avisos)
        if (Array.isArray(respostaSubs?.changes)) {
          respostaSubs.changes.forEach(change => {
            const meta = [change.professor_absent, change.assignatura, change.grup]
              .filter(Boolean)
              .join(' · ')
            canvis.push({
              hora: change.hora || '',
              label: `SUB ${change.hora} ${meta}: ${change.abans || '—'} → ${change.despres || '—'}`
            })
          })
        }
        if (respostaSubs?.cleared !== undefined) {
          toast.add({
            severity: 'success',
            summary: t('substitutions.messages.reassignSubstitutionsTitle'),
            detail: t('substitutions.messages.reassignSubstitutionsDetail', { count: respostaSubs.cleared }, respostaSubs.cleared),
            life: 6000
          })
        }
        await carregarSubstitucions()
      }

      if (canvis.length > 0) {
        const validacioResponse = await apiPdf.validacions(dataISO.value)
        confirmacioImportants.value = false
        validacions.value = validacioResponse.data
        reassignChanges.value = ordenarCanvisPerHora(canvis).map((item) => item.label)
        mostrarDialogPDF.value = false
        mostrarDialogValidacions.value = true
        return
      }

      const validacioResponse = await apiPdf.validacions(dataISO.value)
      confirmacioImportants.value = false
      validacions.value = validacioResponse.data

      if (validacions.value.total === 0) {
        await generarPDFAmbOpcions()
        return
      }

      toast.add({
        severity: 'info',
        summary: t('substitutions.messages.reassignDoneTitle'),
        detail: t('substitutions.messages.reassignDoneDetail'),
        life: 3500
      })
    } catch (error) {
      console.error('Error reassignant problemàtics:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('substitutions.errors.reassignProblematics'),
        life: 3000
      })
    } finally {
      reassignantProblematics.value = false
    }
  }

  const ordenarCanvisPerHora = (canvis) => {
    const ordreHores = horesDisponibles.value || []
    const horaIndex = (hora) => {
      const idx = ordreHores.indexOf(hora)
      return idx === -1 ? 999 : idx
    }

    return [...canvis].sort((a, b) => {
      const diff = horaIndex(a.hora) - horaIndex(b.hora)
      if (diff !== 0) return diff
      return collator.value.compare(a.label || '', b.label || '')
    })
  }


  return { confirmacioImportants, mostrarDialogPDF, mostrarDialogValidacions, generantPDF, reassignantProblematics, reassignChanges, validacions, warningsFiltrats, totalIssuesFiltrats, pdfConfig, mostrarDialegPDF, carregarPreferenciesPdf, generarPDFComplet, continuarPDF, cancelarPDF, reassignarProblematics }
}
