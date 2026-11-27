import { ref, watch } from 'vue'
import * as apiVigilancies from '../api/vigilancies.js'

// Els disponibles de cada hora i fila de vigilància (memòria per consulta) i les opcions del desplegable.
export function useDisponiblesVigilancies({ dataISO, vigilancies, locale, t }) {
  const disponiblesPerHora = ref({})

  let versioDia = 0
  watch(dataISO, () => { versioDia++; disponiblesPerHora.value = {} }, { flush: 'sync' })

  const normalitzarDisponiblesParam = (value) => {
    if (value === null || value === undefined) return null
    const normalized = String(value).trim()
    return normalized || null
  }

  const getDisponiblesCacheKey = (hora, tipus = null, grups = null, aula = null, vigilanciaId = null) => {
    const horaNorm = String(hora || '').trim()
    const tipusNorm = normalitzarDisponiblesParam(tipus)
    const grupsNorm = normalitzarDisponiblesParam(grups) || ''
    const aulaNorm = normalitzarDisponiblesParam(aula) || ''
    const clau = tipusNorm ? `${horaNorm}|${tipusNorm}|${grupsNorm}|${aulaNorm}` : horaNorm
    return vigilanciaId ? `${clau}|fila:${vigilanciaId}` : clau
  }

  // Els disponibles d'una sola consulta (el formulari d'una vigilància nova), a la memòria
  const carregarDisponibles = async (hora, tipus = null, grups = null, aula = null) => {
    const horaNorm = String(hora || '').trim()
    if (!horaNorm) return

    const tipusNorm = normalitzarDisponiblesParam(tipus)
    const grupsNorm = normalitzarDisponiblesParam(grups)
    const aulaNorm = normalitzarDisponiblesParam(aula)
    const cacheKey = getDisponiblesCacheKey(horaNorm, tipusNorm, grupsNorm, aulaNorm)
    if (disponiblesPerHora.value[cacheKey]) return

    const data = dataISO.value, id = versioDia
    try {
      const disponibles = await apiVigilancies.disponibles(data, horaNorm, { tipus: tipusNorm, grups: grupsNorm, aula: aulaNorm })
      if (id !== versioDia || data !== dataISO.value) return
      disponiblesPerHora.value[cacheKey] = disponibles
    } catch (err) {
      if (id !== versioDia || data !== dataISO.value) return
      console.error(`Error carregant disponibles per hora ${horaNorm}:`, err)
    }
  }

  const carregarDisponiblesPerLlista = async (llistaVigilancies = [], { substitueix = false, alhora = null, silent = false, data = dataISO.value, vigent = () => true } = {}) => {
    const id = versioDia
    const actual = () => id === versioDia && data === dataISO.value && vigent()
    if (!actual()) return
    if (!llistaVigilancies.length) {
      alhora?.()
      if (substitueix) disponiblesPerHora.value = {}
      return
    }

    const queriesMap = new Map()
    const addQuery = (hora, tipus = null, grups = null, aula = null, vigilanciaId = null) => {
      const horaNorm = String(hora || '').trim()
      if (!horaNorm) return
      const tipusNorm = normalitzarDisponiblesParam(tipus)
      const grupsNorm = normalitzarDisponiblesParam(grups)
      const aulaNorm = normalitzarDisponiblesParam(aula)
      const key = getDisponiblesCacheKey(horaNorm, tipusNorm, grupsNorm, aulaNorm, vigilanciaId)
      if (!queriesMap.has(key)) {
        queriesMap.set(key, {
          hora: horaNorm,
          tipus: tipusNorm,
          grups: grupsNorm,
          aula: aulaNorm,
          ...(vigilanciaId ? { vigilancia_id: String(vigilanciaId) } : {})
        })
      }
    }

    for (const vigilancia of llistaVigilancies) {
      addQuery(vigilancia.hora, vigilancia.tipus, vigilancia.grups, vigilancia.aula, vigilancia.id)
    }

    const horesUniques = new Set(llistaVigilancies.map(v => v.hora))
    for (const hora of horesUniques) {
      addQuery(hora)
    }

    const queries = Array.from(queriesMap.values())
    if (!queries.length) {
      alhora?.()
      return
    }

    const results = await apiVigilancies.disponiblesEnBloc(data, queries, ...(silent ? [{ _silent: true }] : []))
    if (!actual()) return
    const novaCache = substitueix ? {} : { ...disponiblesPerHora.value }
    for (const [key, value] of Object.entries(results)) {
      novaCache[key] = Array.isArray(value) ? value : []
    }
    alhora?.()
    disponiblesPerHora.value = novaCache
  }

  const refrescarDisponiblesHora = async (hora) => {
    const novaCache = { ...disponiblesPerHora.value }
    for (const clau of Object.keys(novaCache)) {
      if (clau === hora || clau.startsWith(`${hora}|`)) {
        delete novaCache[clau]
      }
    }
    disponiblesPerHora.value = novaCache

    const vigilanciesHora = vigilancies.value.filter(v => v.hora === hora)
    if (!vigilanciesHora.length) return
    await carregarDisponiblesPerLlista(vigilanciesHora)
  }

  const opcionsDesades = new WeakMap()

  const SENSE_DISPONIBLES = []

  const getDisponiblesPerHora = (hora, tipus = null, grups = null, aula = null, vigilanciaId = null) => {
    // Retornar disponibles amb tipus, grups i aula per detectar titulars
    const horaNorm = String(hora || '').trim()
    const cacheKey = getDisponiblesCacheKey(horaNorm, tipus, grups, aula, vigilanciaId)

    // Primer la clau de la fila (amb titulars); si no hi és, la genèrica de l'hora,
    // que només s'omple amb la consulta genèrica (mai amb les dades d'una fila)
    const disponibles = disponiblesPerHora.value[cacheKey] || disponiblesPerHora.value[horaNorm] || SENSE_DISPONIBLES
    const desades = opcionsDesades.get(disponibles)
    if (desades && desades.idioma === locale.value) return desades.opcions

    // AFEGIR opció buida al principi (estil Softcatalà: "Seleccioneu")
    const opcions = [
      {
        value: '',
        label: t('vigilancies.placeholders.supervisorSelect'),
        emoji: '',
        estat: '',
        info: '',
        ordre_tipus: -1,
        color: '#F3F4F6',
        ja_assignat: false
      },
      ...disponibles // en l'ordre del backend (vigilancies/services.py)
    ]
    opcionsDesades.set(disponibles, { idioma: locale.value, opcions })
    return opcions
  }

  const getVigilantLabel = (hora, vigilantValue, tipus = null, grups = null, aula = null, vigilanciaId = null) => {
    // Troba el label del vigilant dins de les opcions disponibles (amb titular si és el cas)
    const horaNorm = String(hora || '').trim()
    const cacheKey = getDisponiblesCacheKey(horaNorm, tipus, grups, aula, vigilanciaId)
    const disponibles = disponiblesPerHora.value[cacheKey] || disponiblesPerHora.value[horaNorm] || []
    const vigilant = disponibles.find(d => d.value === vigilantValue)
    return vigilant ? vigilant.label : vigilantValue
  }

  return { disponiblesPerHora, carregarDisponibles, carregarDisponiblesPerLlista, refrescarDisponiblesHora, getDisponiblesPerHora, getVigilantLabel }
}
