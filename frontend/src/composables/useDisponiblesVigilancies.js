import { ref, watch } from 'vue'
import * as apiVigilancies from '../api/vigilancies.js'

// Extret de la vista: es preserven estat, efectes i ordre de les operacions.
export function useDisponiblesVigilancies({ dataISO, professors, vigilancies, locale, collator, t }) {
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

  const carregarDisponibles = async (hora, force = false, tipus = null, grups = null, aula = null, vigilanciaId = null) => {
    const horaNorm = String(hora || '').trim()
    if (!horaNorm) return []

    const tipusNorm = normalitzarDisponiblesParam(tipus)
    const grupsNorm = normalitzarDisponiblesParam(grups)
    const aulaNorm = normalitzarDisponiblesParam(aula)
    const cacheKey = getDisponiblesCacheKey(horaNorm, tipusNorm, grupsNorm, aulaNorm, vigilanciaId)

    // Si ja tenim les dades en cache i no es força, retornar-les
    if (!force && disponiblesPerHora.value[cacheKey]) {
      return disponiblesPerHora.value[cacheKey]
    }

    const data = dataISO.value, id = versioDia
    try {
      const disponibles = await apiVigilancies.disponibles(data, horaNorm, {
        tipus: tipusNorm,
        grups: grupsNorm,
        aula: aulaNorm,
        ...(vigilanciaId ? { vigilancia_id: String(vigilanciaId) } : {})
      })
      if (id !== versioDia || data !== dataISO.value) return []
      disponiblesPerHora.value[cacheKey] = disponibles

      // També guardar a la cache general per hora (sense tipus) per compatibilitat
      if (!disponiblesPerHora.value[horaNorm]) {
        disponiblesPerHora.value[horaNorm] = disponibles
      }

      return disponibles
    } catch (err) {
      if (id !== versioDia || data !== dataISO.value) return []
      console.error(`Error carregant disponibles per hora ${horaNorm}:`, err)
      // Fallback: retornar professors sense format
      return professors.value.map(p => ({
        value: p,
        label: p,
        emoji: '',
        estat: '',
        info: '',
        ordre_tipus: 999,
        color: '#FFFFFF',
        ja_assignat: false
      }))
    }
  }

  const carregarDisponiblesPerLlista = async (llistaVigilancies = [], { substitueix = false, alhora = null, data = dataISO.value, vigent = () => true } = {}) => {
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

    const results = await apiVigilancies.disponiblesEnBloc(data, queries)
    if (!actual()) return
    const novaCache = substitueix ? {} : { ...disponiblesPerHora.value }
    for (const [key, value] of Object.entries(results)) {
      const disponibles = Array.isArray(value) ? value : []
      novaCache[key] = disponibles
      const horaKey = key.includes('|') ? key.split('|')[0] : key
      if (!novaCache[horaKey]) novaCache[horaKey] = disponibles
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

  const opcionsOrdenades = new WeakMap()

  const SENSE_DISPONIBLES = []

  const getDisponiblesPerHora = (hora, tipus = null, grups = null, aula = null, vigilanciaId = null) => {
    // Retornar disponibles amb tipus, grups i aula per detectar titulars
    const horaNorm = String(hora || '').trim()
    const cacheKey = getDisponiblesCacheKey(horaNorm, tipus, grups, aula, vigilanciaId)

    // Buscar primer amb la clau específica (amb titular), sinó la genèrica
    const disponibles = disponiblesPerHora.value[cacheKey] || disponiblesPerHora.value[horaNorm] || SENSE_DISPONIBLES
    const desades = opcionsOrdenades.get(disponibles)
    if (desades && desades.idioma === locale.value) return desades.opcions

    const ordenats = [...disponibles].sort((a, b) => {
      const ordreA = Number.isFinite(Number(a.ordre_tipus)) ? Number(a.ordre_tipus) : 999
      const ordreB = Number.isFinite(Number(b.ordre_tipus)) ? Number(b.ordre_tipus) : 999
      if (ordreA !== ordreB) {
        return ordreA - ordreB
      }
      const catA = Number.isFinite(Number(a.categoria)) ? Number(a.categoria) : 999
      const catB = Number.isFinite(Number(b.categoria)) ? Number(b.categoria) : 999
      if (catA !== catB) {
        return catA - catB
      }
      return collator.value.compare(a.value || a.label || '', b.value || b.label || '')
    })

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
      ...ordenats
    ]
    opcionsOrdenades.set(disponibles, { idioma: locale.value, opcions })
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
