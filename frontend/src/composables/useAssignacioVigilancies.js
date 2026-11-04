import { ref, computed } from 'vue'
import * as apiVigilancies from '../api/vigilancies.js'

// Extret de la vista: es preserven estat, efectes i ordre de les operacions.
export function useAssignacioVigilancies({ dataISO, vigilancies, toast, t, confirm, confirmaEsborrar, carregarVigilancies }) {
  const titularsHoraLliure = ref([])

  const vigilanciesSenseTitular = ref([])

  const posantTitular = ref(null)

  const assignantTitulars = ref(false)

  const assignantPendents = ref(false)

  const ordenant = ref(false)

  const idsTitularsHoraLliure = computed(() => new Set(titularsHoraLliure.value.map(item => String(item.vigilancia_id))))

  const posaTitularHoraLliure = async (item) => {
    const vigilancia = vigilancies.value.find(v => String(v.id) === String(item.vigilancia_id))
    posantTitular.value = item.vigilancia_id
    try {
      await apiVigilancies.edita(dataISO.value, item.vigilancia_id, {
        vigilant: item.titular,
        updated_at: vigilancia?.updated_at
      })
      titularsHoraLliure.value = titularsHoraLliure.value.filter(x => x.vigilancia_id !== item.vigilancia_id)
      toast.add({ severity: 'success', summary: t('vigilancies.freeHourOwners.assigned'), detail: `${item.titular} · ${item.hora} · ${item.grups}`, life: 3000 })
      await carregarVigilancies()
    } catch (err) {
      console.error('Error posant el titular:', err)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: err.response?.status === 409 ? t('vigilancies.freeHourOwners.conflict') : (err.response?.data?.detail || t('vigilancies.errors.assignOwners')),
        life: 5000
      })
      await carregarVigilancies()
    } finally {
      posantTitular.value = null
    }
  }

  const assignarTitulars = async () => {
    assignantTitulars.value = true

    try {
      const resposta = await apiVigilancies.assignaTitulars(dataISO.value)
      titularsHoraLliure.value = resposta.titulars_hora_lliure || []
      vigilanciesSenseTitular.value = resposta.vigilancies_sense_titular || []

      toast.add({
        severity: 'success',
        summary: t('vigilancies.messages.assignOwnersTitle'),
        detail: resposta.message,
        life: 5000
      })

      // Recarregar vigilàncies
      await carregarVigilancies()
    } catch (err) {
      console.error('Error assignant titulars:', err)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: err.response?.data?.detail || t('vigilancies.errors.assignOwners'),
        life: 5000
      })
    } finally {
      assignantTitulars.value = false
    }
  }

  const assignarPendents = async () => {
    // FASE 1: Assignar només alliberats
    assignantPendents.value = true

    try {
      const resposta1 = await apiVigilancies.assignaPendents(dataISO.value, false)

      await carregarVigilancies()

      const assignats = resposta1.assigned_count
      const pendents = resposta1.remaining_count

      // Si s'han assignat alliberats, mostrar missatge
      if (assignats > 0) {
        toast.add({
          severity: 'success',
          summary: t('vigilancies.messages.assignedFreeTitle'),
          detail: t('vigilancies.messages.assignedFreeDetail', { count: assignats }, assignats),
          life: 4000
        })
      }

      // Si encara queden pendents, preguntar si vol disponibles
      if (pendents > 0) {
        assignantPendents.value = false

        confirm.require({
          message: t('vigilancies.confirm.assignAvailableMessage', { assigned: assignats, pending: pendents }),
          header: t('vigilancies.confirm.assignAvailableTitle'),
          icon: 'pi pi-question-circle',
          acceptLabel: t('vigilancies.confirm.assignAvailableAccept', { count: pendents }, pendents),
          rejectLabel: t('vigilancies.confirm.assignAvailableReject'),
          accept: async () => {
            // FASE 2: Assignar disponibles
            assignantPendents.value = true
            try {
              const resposta2 = await apiVigilancies.assignaPendents(dataISO.value, true)

              await carregarVigilancies()

              toast.add({
                severity: 'success',
                summary: t('vigilancies.messages.availableAssignedTitle'),
                detail: resposta2.message,
                life: 5000
              })
            } catch (err) {
              console.error('Error assignant disponibles:', err)
              toast.add({
                severity: 'error',
                summary: t('common.error'),
                detail: err.response?.data?.detail || t('vigilancies.errors.assignAvailable'),
                life: 5000
              })
            } finally {
              assignantPendents.value = false
            }
          }
        })
      } else {
        // No queden pendents
        toast.add({
          severity: 'info',
          summary: t('vigilancies.messages.allAssignedTitle'),
          detail: t('vigilancies.messages.allAssignedDetail'),
          life: 3000
        })
        assignantPendents.value = false
      }

    } catch (err) {
      console.error('Error assignant alliberats:', err)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: err.response?.data?.detail || t('vigilancies.errors.assignFree'),
        life: 5000
      })
      assignantPendents.value = false
    }
  }

  const confirmarNetejar = () => {
    confirmaEsborrar({
      message: t('vigilancies.confirm.clearMessage'),
      header: t('vigilancies.confirm.clearTitle'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('vigilancies.confirm.clearAccept'),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        try {
          const resposta = await apiVigilancies.neteja(dataISO.value)

          toast.add({
            severity: 'success',
            summary: t('vigilancies.messages.clearedTitle'),
            detail: resposta.message,
            life: 3000
          })

          await carregarVigilancies()
        } catch (err) {
          console.error('Error netejant assignacions:', err)
          toast.add({
            severity: 'error',
            summary: t('common.error'),
            detail: t('vigilancies.errors.clear'),
            life: 3000
          })
        }
      }
    })
  }

  const ordenarPerHora = async () => {
    let manual = false
    try {
      manual = await apiVigilancies.teOrdreManual(dataISO.value)
    } catch (err) {
      console.error('Error consultant l\'ordre:', err)
    }
    if (!manual) return ordena()
    confirm.require({
      header: t('vigilancies.confirm.sortManualTitle'),
      message: t('vigilancies.confirm.sortManualMessage'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('vigilancies.actions.sort'),
      rejectLabel: t('common.cancel'),
      accept: ordena
    })
  }

  const ordena = async () => {
    ordenant.value = true

    try {
      const resposta = await apiVigilancies.ordena(dataISO.value)

      toast.add({
        severity: 'success',
        summary: t('vigilancies.messages.sortedTitle'),
        detail: resposta.message,
        life: 3000
      })

      // Ordenar no canvia qui està disponible ni les substitucions: només cal
      // el llistat (amb l'ordre i els updated_at nous)
      vigilancies.value = await apiVigilancies.llista(dataISO.value)
    } catch (err) {
      console.error('Error ordenant vigilàncies:', err)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('vigilancies.errors.sort'),
        life: 3000
      })
    } finally {
      ordenant.value = false
    }
  }

  return { titularsHoraLliure, vigilanciesSenseTitular, posantTitular, assignantTitulars, assignantPendents, ordenant, posaTitularHoraLliure, assignarTitulars, assignarPendents, confirmarNetejar, ordenarPerHora, idsTitularsHoraLliure }
}
