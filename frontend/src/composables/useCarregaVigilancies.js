import { avisaError } from '../errorsApi.js'
import { watch } from 'vue'
import * as apiVigilancies from '../api/vigilancies.js'
import { llistaSimple as llistaSubstitucions } from '../api/substitucions.js'

// Cap dada ni error d'una petició antiga no pot substituir el dia actual.
export function useCarregaVigilancies({ dataISO, loading, error, vigilancies, seleccionades, substitucionsCount, problemes, carregarDisponiblesPerLlista, publicaConfig, oblidaAjudes, t }) {
  let versio = 0
  watch(dataISO, () => { versio++ }, { flush: 'sync' })

  const carregarSubstitucionsCount = async () => {
    const data = dataISO.value, id = versio
    try {
      const [files, analisi] = await Promise.all([llistaSubstitucions(data), apiVigilancies.analisi(data)])
      if (id === versio && data === dataISO.value) {
        substitucionsCount.value = files.length
        problemes.value = analisi
      }
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
      const [config, files, substitucions, analisi] = await Promise.all([
        apiVigilancies.configuracio({ params: { data }, _silent: true }),
        apiVigilancies.llista(data, { _silent: true }),
        llistaSubstitucions(data, { _silent: true }),
        apiVigilancies.analisi(data, { _silent: true })
      ])
      if (!vigent()) return
      await carregarDisponiblesPerLlista(files, { substitueix: true, data, vigent, silent: true, alhora: () => {
        publicaConfig(config)
        problemes.value = analisi
        vigilancies.value = files
        substitucionsCount.value = substitucions.length
      } })
    } catch (err) {
      if (!vigent()) return
      console.error('Error carregant vigilàncies:', err)
      avisaError(err, () => { error.value = t('vigilancies.errors.load') })
      problemes.value = []
      vigilancies.value = []
      substitucionsCount.value = 0
    } finally {
      if (vigent()) loading.value = false
    }
  }
  return { carregarVigilancies, carregarSubstitucionsCount }
}
