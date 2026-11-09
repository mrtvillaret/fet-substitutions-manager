import { avisaError } from '../errorsApi.js'
import { ref, computed, watch } from 'vue'
import * as apiExamens from '../api/configuracioExamens.js'

// Extret de la vista: es preserven estat, efectes i ordre de les operacions.
export function useAssignacionsExamens({ assignacions, aules, toast, t, confirmaEsborrar }) {
  const assignacionsFiltrades = ref([])

  const allLabel = computed(() => t('common.all'))

  const filtreNivellAssignacions = ref(allLabel.value)

  const filtreAssignaturaAssignacions = ref(allLabel.value)

  const filtreAulaAssignacions = ref(allLabel.value)

  const aulesDelFiltre = computed(() =>
    [...new Set([...aules.value, ...assignacions.value.map(a => a.aula)].filter(Boolean))].sort((a, b) => a.localeCompare(b))
  )

  const assignaturesUniques = ref([])

  const nextTempId = ref(-1)

  watch(allLabel, (newVal, oldVal) => {
    if (filtreNivellAssignacions.value === oldVal) {
      filtreNivellAssignacions.value = newVal
    }
    if (filtreAssignaturaAssignacions.value === oldVal) {
      filtreAssignaturaAssignacions.value = newVal
    }
    if (filtreAulaAssignacions.value === oldVal) {
      filtreAulaAssignacions.value = newVal
    }
  })

  const assignacionsObsoletes = ref([])

  const carregarAssignacionsObsoletes = async () => {
    try {
      const response = await apiExamens.assignacionsObsoletes()
      assignacionsObsoletes.value = response.assignacions || []
    } catch {
      assignacionsObsoletes.value = []
    }
  }

  const treureAssignacionsObsoletes = () => {
    confirmaEsborrar({
      message: t('examConfig.assignments.obsolete.confirm', { count: assignacionsObsoletes.value.length }, assignacionsObsoletes.value.length),
      header: t('common.confirmDelete'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        try {
          const ids = assignacionsObsoletes.value.map(a => a.id)
          const data = await apiExamens.esborraAssignacions({ ids })
          toast.add({ severity: 'success', summary: t('examConfig.assignments.obsolete.removed', { count: data.eliminades }, data.eliminades), life: 3000 })
          await carregarAssignacions()
        } catch (errorCapturat) {
          avisaError(errorCapturat, () => toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.errors.deleteAssignment'), life: 3000 }))
        }
      }
    })
  }

  const carregarAssignacions = async () => {
    carregarAssignacionsObsoletes()
    try {
      const response = await apiExamens.assignacions()
      assignacions.value = response.assignacions

      // Extreure assignatures úniques
      const assignaturesSet = new Set(assignacions.value.map(a => a.assignatura))
      assignaturesUniques.value = Array.from(assignaturesSet).sort()

      filtrarAssignacions()
    } catch (error) {
      console.error('Error carregant assignacions:', error)
      assignacions.value = []
    }
  }

  const filtrarAssignacions = () => {
    let filtrades = [...assignacions.value]

    // Filtrar per nivell (hem de buscar quins grups pertanyen al nivell)
    if (filtreNivellAssignacions.value && filtreNivellAssignacions.value !== allLabel.value) {
      filtrades = filtrades.filter(a => {
        // Comprovar si el grup comença amb el nivell
        return a.grup.startsWith(filtreNivellAssignacions.value)
      })
    }

    // Filtrar per assignatura
    if (filtreAssignaturaAssignacions.value && filtreAssignaturaAssignacions.value !== allLabel.value) {
      filtrades = filtrades.filter(a => a.assignatura === filtreAssignaturaAssignacions.value)
    }

    // Filtrar per aula
    if (filtreAulaAssignacions.value && filtreAulaAssignacions.value !== allLabel.value) {
      filtrades = filtrades.filter(a => a.aula === filtreAulaAssignacions.value)
    }

    assignacionsFiltrades.value = filtrades
  }

  const afegirFilaAssignacio = () => {
    // Afegir fila temporal amb id negatiu
    const novaFila = {
      id: nextTempId.value--,
      assignatura: '',
      grup: '',
      titular: '',
      aula: '',
      _isNew: true
    }
    assignacions.value.unshift(novaFila)
    filtrarAssignacions()
  }

  const onCellEditComplete = async (event) => {
    const { data, newValue, field } = event

    // Actualitzar valor
    data[field] = newValue

    // Si és una fila nova i té assignatura + grup, crear-la
    if (data._isNew && data.assignatura && data.grup) {
      try {
        const response = await apiExamens.creaAssignacio({
          assignatura: data.assignatura,
          grup: data.grup,
          titular: data.titular || '',
          aula: data.aula || ''
        })

        // Substituir id temporal per id real
        data.id = response.id
        delete data._isNew

        toast.add({
          severity: 'success',
          summary: t('common.created'),
          detail: t('examConfig.assignments.created'),
          life: 2000
        })

        // NO recarreguem - ja tenim les dades actualitzades localment
        filtrarAssignacions()
      } catch (error) {
        console.error('Error creant assignació:', error)
        avisaError(error, () => toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('examConfig.errors.createAssignment'),
          life: 3000
        }))
      }
    }
    // Si és una fila existent, actualitzar-la
    else if (!data._isNew && data.id > 0) {
      try {
        await apiExamens.editaAssignacio(data.id, {
          titular: data.titular || '',
          aula: data.aula || ''
        })

        toast.add({
          severity: 'success',
          summary: t('common.updated'),
          detail: t('examConfig.assignments.updated'),
          life: 1500
        })
      } catch (error) {
        console.error('Error actualitzant assignació:', error)
        avisaError(error, () => toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: t('examConfig.errors.updateAssignment'),
          life: 3000
        }))
      }
    }
  }

  const eliminarAssignacio = async (id) => {
    // Si és una fila nova local (id negatiu), eliminar directament sense API
    if (id < 0) {
      assignacions.value = assignacions.value.filter(a => a.id !== id)
      filtrarAssignacions()
      return
    }

    confirmaEsborrar({
      message: t('examConfig.assignments.deleteConfirmMessage'),
      header: t('common.confirmDelete'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        try {
          await apiExamens.esborraAssignacio(id)

          toast.add({
            severity: 'success',
            summary: t('common.deleted'),
            detail: t('examConfig.assignments.deleted'),
            life: 2000
          })

          await carregarAssignacions()
        } catch (error) {
          console.error('Error eliminant assignació:', error)
          avisaError(error, () => toast.add({
            severity: 'error',
            summary: t('common.error'),
            detail: t('examConfig.errors.deleteAssignment'),
            life: 3000
          }))
        }
      }
    })
  }

  const eliminarAssignacionsFiltrades = () => {
    if (assignacionsFiltrades.value.length === 0) return

    confirmaEsborrar({
      message: t('examConfig.assignments.deleteFilteredConfirmMessage', { count: assignacionsFiltrades.value.length }, assignacionsFiltrades.value.length),
      header: t('common.confirmDelete'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        try {
          const ids = assignacionsFiltrades.value.filter(a => a.id > 0).map(a => a.id)
          await apiExamens.esborraAssignacions({ ids })
          toast.add({ severity: 'success', summary: t('common.deleted'), detail: t('examConfig.assignments.deleted'), life: 2000 })
          await carregarAssignacions()
        } catch (error) {
          console.error('Error eliminant assignacions:', error)
          avisaError(error, () => toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.errors.deleteAssignment'), life: 3000 }))
        }
      }
    })
  }

  const eliminarTotesAssignacions = () => {
    if (assignacions.value.length === 0) return

    confirmaEsborrar({
      message: t('examConfig.assignments.deleteAllConfirmMessage', { count: assignacions.value.length }, assignacions.value.length),
      header: t('common.confirmDelete'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        try {
          await apiExamens.esborraAssignacions({ tot: true })
          toast.add({ severity: 'success', summary: t('common.deleted'), detail: t('examConfig.assignments.deleted'), life: 2000 })
          await carregarAssignacions()
        } catch (error) {
          console.error('Error eliminant totes les assignacions:', error)
          avisaError(error, () => toast.add({ severity: 'error', summary: t('common.error'), detail: t('examConfig.errors.deleteAssignment'), life: 3000 }))
        }
      }
    })
  }

  return { assignacionsFiltrades, allLabel, filtreNivellAssignacions, filtreAssignaturaAssignacions, filtreAulaAssignacions, aulesDelFiltre, assignaturesUniques, assignacionsObsoletes, treureAssignacionsObsoletes, carregarAssignacions, filtrarAssignacions, afegirFilaAssignacio, onCellEditComplete, eliminarAssignacio, eliminarAssignacionsFiltrades, eliminarTotesAssignacions, assignacions }
}
