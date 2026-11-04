import { watch } from 'vue'
import * as apiVigilancies from '../api/vigilancies.js'
import { llistaSimple as llistaSubstitucions } from '../api/substitucions.js'

// Cap dada ni error d'una petició antiga no pot substituir el dia actual.
export function useCarregaVigilancies({ dataISO, loading, error, vigilancies, seleccionades, substitucionsCount, carregarDisponiblesPerLlista, publicaConfig, oblidaAjudes, t }) {
  let versio = 0
  watch(dataISO, () => { versio++ }, { flush: 'sync' })

  const carregarSubstitucionsCount = async () => {
    const data = dataISO.value, id = versio
    try {
      const files = await llistaSubstitucions(data)
      if (id === versio && data === dataISO.value) substitucionsCount.value = files.length
    } catch (err) {
      if (id !== versio || data !== dataISO.value) return
      console.error('Error carregant substitucions:', err)
      substitucionsCount.value = 0
    }
  }

  const carregarVigilancies = async () => {
    const id = ++versio, data = dataISO.value
    const vigent = () => id === versio && data === dataISO.value
    loading.value = true
    error.value = null
    seleccionades.value = []
    oblidaAjudes()
    try {
      const [config, files, substitucions] = await Promise.all([
        apiVigilancies.configuracio({ params: { data } }),
        apiVigilancies.llista(data),
        llistaSubstitucions(data)
      ])
      if (!vigent()) return
      await carregarDisponiblesPerLlista(files, { substitueix: true, data, vigent, alhora: () => {
        publicaConfig(config)
        vigilancies.value = files
        substitucionsCount.value = substitucions.length
      } })
    } catch (err) {
      if (!vigent()) return
      console.error('Error carregant vigilàncies:', err)
      error.value = t('vigilancies.errors.load')
      vigilancies.value = []
      substitucionsCount.value = 0
    } finally {
      if (vigent()) loading.value = false
    }
  }
  return { carregarVigilancies, carregarSubstitucionsCount }
}
