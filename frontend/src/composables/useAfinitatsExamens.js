import { avisaError, detallDError } from '../errorsApi.js'
import { ref } from 'vue'
import * as apiExamens from '../api/configuracioExamens.js'

// Extret de la vista: es preserven estat, efectes i ordre de les operacions.
export function useAfinitatsExamens({ toast, t }) {
  const afinitats = ref([])

  const carregarAfinitats = async () => {
    try {
      const response = await apiExamens.afinitats()
      const rows = Array.isArray(response?.afinitats) ? response.afinitats : []
      afinitats.value = rows.map((row) => ({
        base: row.base || '',
        ordreText: Array.isArray(row.ordre) ? row.ordre.join(',') : ''
      }))
    } catch (error) {
      console.error('Error carregant afinitats:', error)
      afinitats.value = []
    }
  }

  const afegirFilaAfinitat = () => {
    afinitats.value.push({ base: '', ordreText: '' })
  }

  const eliminarFilaAfinitat = (index) => {
    afinitats.value.splice(index, 1)
  }

  const desarAfinitats = async () => {
    const payload = afinitats.value
      .map((row) => ({
        base: (row.base || '').trim(),
        ordre: (row.ordreText || '')
          .split(',')
          .map((x) => x.trim())
          .filter(Boolean)
      }))
      .filter((row) => row.base)

    try {
      const response = await apiExamens.desaAfinitats({ afinitats: payload })
      const saved = Array.isArray(response?.afinitats) ? response.afinitats : payload
      afinitats.value = saved.map((row) => ({
        base: row.base || '',
        ordreText: Array.isArray(row.ordre) ? row.ordre.join(',') : ''
      }))

      toast.add({
        severity: 'success',
        summary: t('common.saved'),
        detail: t('examConfig.affinities.saved'),
        life: 2000
      })
    } catch (error) {
      console.error('Error desant afinitats:', error)
      avisaError(error, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: detallDError(error) || t('examConfig.errors.saveAffinities'),
        life: 3000
      }))
    }
  }

  return { afinitats, carregarAfinitats, afegirFilaAfinitat, eliminarFilaAfinitat, desarAfinitats }
}
