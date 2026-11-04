import { ref } from 'vue'
import * as apiExamens from '../api/configuracioExamens.js'
import * as apiPlanificador from '../api/planificador.js'
import { professors as carregaProfessorsHorari } from '../api/horari.js'

// Extret de la vista: es preserven estat, efectes i ordre de les operacions.
export function useCatalegsExamens({ toast, t, confirmaEsborrar, assignacions, carregarAssignacions, filtrarAssignacions }) {
  const nivells = ref([])

  const xmlMissingNotified = ref(false)

  const itemEditant = ref(null)

  const mostrarDialogRenomItem = ref(false)

  const renomTipus = ref('')

  const renomValor = ref('')

  const mostrarDialogAfegirNivell = ref(false)

  const nouNivell = ref('')

  const nivellSeleccionat = ref(null)

  const assignatures = ref([])

  const mostrarDialogAfegirAssignatura = ref(false)

  const novaAssignatura = ref('')

  const nivellSeleccionatGrups = ref(null)

  const grups = ref([])

  const mostrarDialogAfegirGrup = ref(false)

  const nouGrup = ref('')

  const aules = ref([])

  const mostrarDialogAfegirAula = ref(false)

  const novaAula = ref('')

  const totesAssignatures = ref([])

  const totsGrups = ref([])

  const professors = ref([])

  const carregarNivells = async () => {
    try {
      const response = await apiExamens.nivells()
      nivells.value = response.nivells
    } catch (error) {
      console.error('Error carregant nivells:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('examConfig.errors.loadLevels'),
        life: 3000
      })
    }
  }

  const carregarAssignatures = async () => {
    if (!nivellSeleccionat.value) return

    try {
      const response = await apiExamens.assignatures(nivellSeleccionat.value)
      assignatures.value = response.assignatures
    } catch (error) {
      console.error('Error carregant assignatures:', error)
      assignatures.value = []
    }
  }

  const afegirNivell = async () => {
    if (!nouNivell.value) return

    try {
      await apiExamens.creaNivell({
        codi: nouNivell.value.trim().toUpperCase(),
        nom: nouNivell.value.trim().toUpperCase()
      })

      toast.add({
        severity: 'success',
        summary: t('common.added'),
        detail: t('examConfig.levels.added'),
        life: 2000
      })

      nouNivell.value = ''
      mostrarDialogAfegirNivell.value = false
      await carregarNivells()
    } catch (error) {
      console.error('Error afegint nivell:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('examConfig.errors.addLevel'),
        life: 3000
      })
    }
  }

  const ELIMINAR = {
    nivell: {
      url: (codi) => `/api/config/nivells/${encodeURIComponent(codi)}`,
      capcalera: 'common.confirmation',
      confirma: 'examConfig.levels.deleteConfirmMessage',
      pregunta: 'examConfig.levels.usedByAssignments',
      esborrat: 'examConfig.levels.deleted',
      error: 'examConfig.errors.deleteLevel',
      recarrega: () => carregarNivells()
    },
    grup: {
      url: (codi) => `/api/config/grups/${encodeURIComponent(codi)}`,
      capcalera: 'common.confirmDelete',
      confirma: 'examConfig.groups.deleteConfirmMessage',
      pregunta: 'examConfig.groups.usedByAssignments',
      esborrat: 'examConfig.groups.deleted',
      error: 'examConfig.errors.deleteGroup',
      recarrega: () => carregarGrups()
    }
  }

  const esborrantAmbAssignacions = ref(null)

  const eliminarAmbAssignacions = async (tipus, codi) => {
    const e = ELIMINAR[tipus]
    let quantes = 0
    try {
      quantes = (await apiExamens.comptaAssignacions(e.url(codi))).assignacions
    } catch (error) {
      toast.add({ severity: 'error', summary: t('common.error'), detail: error.response?.data?.detail || t(e.error), life: 3000 })
      return
    }
    if (quantes) {
      esborrantAmbAssignacions.value = { tipus, codi, quantes }
      return
    }
    confirmaEsborrar({
      message: t(e.confirma, { code: codi }),
      header: t(e.capcalera),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: () => esborra(tipus, codi, false)
    })
  }

  const esborra = async (tipus, codi, ambAssignacions) => {
    const e = ELIMINAR[tipus]
    esborrantAmbAssignacions.value = null
    try {
      const data = await apiExamens.esborraElement(e.url(codi), ambAssignacions)
      toast.add({ severity: 'success', summary: t('common.deleted'), detail: t(e.esborrat), life: 2000 })
      if (data.assignacions_esborrades) await carregarAssignacions()
      else avisaAssignacionsQueHoFanServir(data.assignacions)
      await e.recarrega()
    } catch (error) {
      console.error(`Error eliminant ${tipus}:`, error)
      toast.add({ severity: 'error', summary: t('common.error'), detail: error.response?.data?.detail || t(e.error), life: 3000 })
    }
  }

  const avisaAssignacionsQueHoFanServir = (quantes) => {
    if (!quantes) return
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('examConfig.stillUsedByAssignments', { count: quantes }, quantes),
      life: 6000
    })
  }

  const eliminarNivell = (codi) => eliminarAmbAssignacions('nivell', codi)

  const afegirAssignatura = async () => {
    if (!novaAssignatura.value || !nivellSeleccionat.value) return

    try {
      await apiExamens.creaAssignatura(nivellSeleccionat.value, {
        nom: novaAssignatura.value.trim().toUpperCase()
      })

      toast.add({
        severity: 'success',
        summary: t('common.added'),
        detail: t('examConfig.subjects.added'),
        life: 2000
      })

      novaAssignatura.value = ''
      mostrarDialogAfegirAssignatura.value = false
      await carregarAssignatures()
    } catch (error) {
      console.error('Error afegint assignatura:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('examConfig.errors.addSubject'),
        life: 3000
      })
    }
  }

  const eliminarAssignatura = async (nom) => {
    confirmaEsborrar({
      message: t('examConfig.subjects.deleteConfirmMessage', { name: nom }),
      header: t('common.confirmDelete'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        try {
          await apiExamens.esborraAssignatura(nivellSeleccionat.value, nom)

          toast.add({
            severity: 'success',
            summary: t('common.deleted'),
            detail: t('examConfig.subjects.deleted'),
            life: 2000
          })

          await carregarAssignatures()
        } catch (error) {
          console.error('Error eliminant assignatura:', error)
          toast.add({
            severity: 'error',
            summary: t('common.error'),
            detail: t('examConfig.errors.deleteSubject'),
            life: 3000
          })
        }
      }
    })
  }

  const carregarGrups = async () => {
    if (!nivellSeleccionatGrups.value) return

    try {
      const response = await apiExamens.grups(nivellSeleccionatGrups.value)
      grups.value = response.grups
    } catch (error) {
      console.error('Error carregant grups:', error)
      grups.value = []
    }
  }

  const afegirGrup = async () => {
    if (!nouGrup.value || !nivellSeleccionatGrups.value) return

    try {
      await apiExamens.creaGrup(nivellSeleccionatGrups.value, {
        codi: nouGrup.value.trim()
      })

      toast.add({
        severity: 'success',
        summary: t('common.added'),
        detail: t('examConfig.groups.added'),
        life: 2000
      })

      nouGrup.value = ''
      mostrarDialogAfegirGrup.value = false
      await carregarGrups()
    } catch (error) {
      console.error('Error afegint grup:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('examConfig.errors.addGroup'),
        life: 3000
      })
    }
  }

  const eliminarGrup = (codi) => eliminarAmbAssignacions('grup', codi)

  const carregarAules = async () => {
    try {
      const response = await apiExamens.aules()
      aules.value = response.aules
    } catch (error) {
      console.error('Error carregant aules:', error)
      aules.value = []
    }
  }

  const afegirAula = async () => {
    if (!novaAula.value) return

    try {
      await apiExamens.creaAula({
        codi: novaAula.value.trim()
      })

      toast.add({
        severity: 'success',
        summary: t('common.added'),
        detail: t('examConfig.rooms.added'),
        life: 2000
      })

      novaAula.value = ''
      mostrarDialogAfegirAula.value = false
      await carregarAules()
    } catch (error) {
      console.error('Error afegint aula:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('examConfig.errors.addRoom'),
        life: 3000
      })
    }
  }

  const eliminarAula = async (codi) => {
    confirmaEsborrar({
      message: t('examConfig.rooms.deleteConfirmMessage', { code: codi }),
      header: t('common.confirmDelete'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        try {
          const data = await apiExamens.esborraAula(codi)

          toast.add({
            severity: 'success',
            summary: t('common.deleted'),
            detail: t('examConfig.rooms.deleted'),
            life: 2000
          })

          avisaAssignacionsQueHoFanServir(data.assignacions)
          await carregarAules()
        } catch (error) {
          console.error('Error eliminant aula:', error)
          toast.add({
            severity: 'error',
            summary: t('common.error'),
            detail: t('examConfig.errors.deleteRoom'),
            life: 3000
          })
        }
      }
    })
  }

  const carregarTotesAssignatures = async () => {
    // Carregar totes les assignatures de tots els nivells
    const assignaturesSet = new Set()
    for (const nivell of nivells.value) {
      try {
        const response = await apiExamens.assignatures(nivell)
        response.assignatures.forEach(a => assignaturesSet.add(a))
      } catch (error) {
        console.error(`Error carregant assignatures de ${nivell}:`, error)
      }
    }
    totesAssignatures.value = Array.from(assignaturesSet).sort()
  }

  const carregarTotsGrups = async () => {
    // Carregar tots els grups de tots els nivells
    const grupsSet = new Set()
    for (const nivell of nivells.value) {
      try {
        const response = await apiExamens.grups(nivell)
        response.grups.forEach(g => grupsSet.add(g))
      } catch (error) {
        console.error(`Error carregant grups de ${nivell}:`, error)
      }
    }
    totsGrups.value = Array.from(grupsSet).sort()
  }

  const horariPlanificacio = ref(null)

  const carregarProfessors = async () => {
    try {
      const { data: horari } = await apiPlanificador.horari()
      horariPlanificacio.value = horari
      const resposta = await carregaProfessorsHorari({ params: { data: horari.data_referencia } })
      if (resposta?.xml_missing && !xmlMissingNotified.value) {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('common.xmlMissing'),
          life: 4000
        })
        xmlMissingNotified.value = true
      }
      professors.value = resposta.professors
    } catch (error) {
      console.error('Error carregant professors:', error)
      professors.value = []
    }
  }

  const prepararRenomAssignatura = (nom) => {
    itemEditant.value = nom
    renomValor.value = nom
    renomTipus.value = 'assignatura'
    mostrarDialogRenomItem.value = true
  }

  const prepararRenomGrup = (codi) => {
    itemEditant.value = codi
    renomValor.value = codi
    renomTipus.value = 'grup'
    mostrarDialogRenomItem.value = true
  }

  const prepararRenomAula = (codi) => {
    itemEditant.value = codi
    renomValor.value = codi
    renomTipus.value = 'aula'
    mostrarDialogRenomItem.value = true
  }

  const reanomenarItem = async () => {
    const antic = itemEditant.value
    const nou = renomValor.value.trim()

    if (!nou || antic === nou) {
      mostrarDialogRenomItem.value = false
      return
    }

    try {
      let url = ''
      let payload = {}

      if (renomTipus.value === 'assignatura') {
        url = `/api/config/assignatures/${nivellSeleccionat.value}/${encodeURIComponent(antic)}`
        payload = { nou_nom: nou }
      } else if (renomTipus.value === 'grup') {
        url = `/api/config/grups/${encodeURIComponent(antic)}`
        payload = { nou_nom: nou }
      } else if (renomTipus.value === 'aula') {
        url = `/api/config/aules/${encodeURIComponent(antic)}`
        payload = { nou_nom: nou }
      }

      await apiExamens.editaElement(url, payload)

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('common.updated'),
        life: 2000
      })

      // Propagació local a Assignacions per evitar recàrrega lenta
      assignacions.value.forEach(a => {
        if (renomTipus.value === 'assignatura' && a.assignatura === antic) {
          a.assignatura = nou
        } else if (renomTipus.value === 'grup' && a.grup === antic) {
          a.grup = nou
        } else if (renomTipus.value === 'aula' && a.aula === antic) {
          a.aula = nou
        }
      })

      // Recarregar la llista específica
      if (renomTipus.value === 'assignatura') await carregarAssignatures()
      else if (renomTipus.value === 'grup') await carregarGrups()
      else if (renomTipus.value === 'aula') await carregarAules()

      // Recarregar també les llistes auxiliars dels dropdowns
      await carregarTotesAssignatures()
      await carregarTotsGrups()
      
      // Recarregar assignacions per actualitzar els filtres (assignaturesUniques)
      await carregarAssignacions()

      filtrarAssignacions()
      mostrarDialogRenomItem.value = false
    } catch (error) {
      console.error('Error reanomenant:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('common.error'),
        life: 3000
      })
    }
  }

  return { nivells, itemEditant, mostrarDialogRenomItem, renomValor, mostrarDialogAfegirNivell, nouNivell, nivellSeleccionat, assignatures, mostrarDialogAfegirAssignatura, novaAssignatura, nivellSeleccionatGrups, grups, mostrarDialogAfegirGrup, nouGrup, aules, mostrarDialogAfegirAula, novaAula, totesAssignatures, totsGrups, professors, carregarNivells, carregarAssignatures, afegirNivell, ELIMINAR, esborrantAmbAssignacions, esborra, eliminarNivell, afegirAssignatura, eliminarAssignatura, carregarGrups, afegirGrup, eliminarGrup, carregarAules, afegirAula, eliminarAula, carregarTotesAssignatures, carregarTotsGrups, horariPlanificacio, carregarProfessors, prepararRenomAssignatura, prepararRenomGrup, prepararRenomAula, reanomenarItem }
}
