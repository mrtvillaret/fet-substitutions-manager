import { avisaError, detallDError } from '../errorsApi.js'
import { ref, computed, watch, onMounted } from 'vue'
import * as apiPlanificador from '../api/planificador'
import { debounce } from 'lodash-es'
import { localizeBackendDayName } from '../views/scheduler/textUtils'

export function useHorariEditable(dependents) {
  const { props, emit, t, toast } = dependents

  // slotKey pot ser "Dimarts_8h" o "2025-01-07_8h" — l'hora és sempre l'últim segment
  const parseSlotKey = (slotKey) => {
    const idx = slotKey.lastIndexOf('_')
    return [slotKey.slice(0, idx), slotKey.slice(idx + 1)]
  }

  const horariLocal = ref(null)
  const horariOriginal = ref(null)
  const costTotal = ref(0)
  const costBreakdown = ref({})
  const costBreakdownDetails = ref({})
  const costsPerSlot = ref({})
  const isValid = ref(true)
  const carregant = ref(false)
  const itemsAparcats = ref([])
  const grupsAparcats = ref([])
  // Pins derivats de la prop pinnedNoms (= restriccions dia/hora de la BD)
  const fixatsCount = computed(() => props.pinnedNoms.size)

  const toggleFixarItem = async ({ item, slotKey }) => {
    const [key, hora] = parseSlotKey(slotKey)
    const diaNomPin = key  // ja és data ISO o nom de dia
    // Recollir tots els noms de l'agrupació (mateix item_id al slot)
    const slotItems = getItemsSlot(key, hora)
    const agrupacioItems = slotItems.filter(i => i.item_id === item.item_id)
    const noms = agrupacioItems.map(i => i.nom).filter(Boolean)
    if (!noms.length) return

    const isPinned = noms.some(n => props.pinnedNoms.has(n))

    try {
      let payload
      if (isPinned) {
        payload = { pins: [], unpins: noms }
      } else {
        payload = { pins: noms.map(n => ({ nom: n, dia: diaNomPin, hora })), unpins: [] }
      }
      await apiPlanificador.pins(payload)
      emit('pin-changed')
    } catch (err) {
      console.error('Error fixant/desfixant sessió:', err)
      avisaError(err, () => toast.add({
        severity: 'error',
        summary: t('scheduler.editable.toasts.recalcErrorTitle'),
        detail: detallDError(err) || err.message,
        life: 3000
      }))
    }
  }

  const fixarTot = async () => {
    if (!horariLocal.value?.dies) return
    const pins = []
    const seen = new Set()
    for (const dia of horariLocal.value.dies) {
      for (const slot of dia.sessions || []) {
        for (const sessio of slot.sessions_simultanees || []) {
          if (sessio.nom && !seen.has(sessio.nom)) {
            seen.add(sessio.nom)
            pins.push({ nom: sessio.nom, dia: dia.data || dia.dia, hora: slot.hora })
          }
        }
      }
    }
    if (!pins.length) return
    try {
      await apiPlanificador.pins({ pins, unpins: [] })

      emit('pin-changed')
    } catch (err) {
      console.error('Error fixant tot:', err)
    }
  }

  const desfixarTot = async () => {
    const unpins = Array.from(props.pinnedNoms)
    if (!unpins.length) return
    try {
      await apiPlanificador.pins({ pins: [], unpins })
      emit('pin-changed')
    } catch (err) {
      console.error('Error desfixant tot:', err)
    }
  }

  const nivellColors = {
    '1-ESO': '#22c55e',
    '2-ESO': '#3b82f6',
    '3-ESO': '#f59e0b',
    '4-ESO': '#ef4444',
    '1-BATX': '#8b5cf6',
    '2-BATX': '#ec4899',
    'CFGM': '#14b8a6',
    'CFGS': '#06b6d4'
  }

  const getNivellColor = (curs) => {
    return nivellColors[curs] || '#94a3b8'
  }
  const dayLabel = (key) => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(key)) {
      const date = new Date(key + 'T12:00:00')
      const weekday = date.getDay()
      const nomDia = ['Diumenge', 'Dilluns', 'Dimarts', 'Dimecres', 'Dijous', 'Divendres', 'Dissabte'][weekday]
      const label = localizeBackendDayName(nomDia, t)
      const dd = String(date.getDate()).padStart(2, '0')
      const mm = String(date.getMonth() + 1).padStart(2, '0')
      return `${label} ${dd}/${mm}`
    }
    return localizeBackendDayName(key, t)
  }

  const findDiaObj = (key) => horariLocal.value?.dies?.find(d => (d.data || d.dia) === key)

  const normalizeGroupLabel = (label) => {
    if (!label) return label
    return label.replace(/\s*\(\s*\d+\s*assig.*\)\s*$/i, '').trim()
  }

  const dies = computed(() => {
    if (!horariLocal.value?.dies) return []
    return horariLocal.value.dies.map(d => d.data || d.dia)
  })

  const hores = computed(() => {
    if (!horariLocal.value?.dies) return []
    const horaSet = new Set()
    for (const dia of horariLocal.value.dies) {
      for (const slot of dia.sessions || []) {
        if (slot.hora) horaSet.add(slot.hora)
      }
    }
    return Array.from(horaSet).sort()
  })

  const haCanvis = computed(() => {
    // Hi ha canvis si l'horari és diferent O si hi ha items/grups aparcats
    return JSON.stringify(horariLocal.value) !== JSON.stringify(horariOriginal.value) ||
           itemsAparcats.value.length > 0 ||
           grupsAparcats.value.length > 0
  })

  const costBreakdownFiltered = computed(() => {
    const filtered = {}
    for (const [k, v] of Object.entries(costBreakdown.value || {})) {
      if (v && !k.includes('unitari')) {
        filtered[k] = v
      }
    }
    return filtered
  })

  const formatBreakdownKey = (key) => {
    const map = {
      substitucio: t('scheduler.editable.breakdown.substitucions'),
      abans_jornada: t('scheduler.editable.breakdown.abans_jornada'),
      despres_jornada: t('scheduler.editable.breakdown.despres_jornada'),
      no_treballa_dia: t('scheduler.editable.breakdown.no_treballa_dia'),
      limit_dies_professor: t('scheduler.editable.breakdown.limit_dies_professor'),
    }
    return map[key] || key
  }

  const formatBreakdownDetails = (key) => {
    const details = costBreakdownDetails.value?.[key]
    if (!details || !details.length) return ''
    return details.join(', ')
  }

  const formatBreakdownSuffix = (key) => {
    const details = costBreakdownDetails.value?.[key]
    if (!details || !details.length) return ''
    if (details.length <= 2) return details.join(', ')
    return t('scheduler.editable.breakdown.profCount', { count: details.length })
  }

  const transformarHorariAItems = (horari) => {
    if (!horari?.dies) return

    for (const dia of horari.dies) {
      for (const slot of dia.sessions || []) {
        // Cada sessió és un ítem individual, però mantenim la info d'agrupació
        const items = []
        let counter = 0

        for (const sessio of slot.sessions_simultanees || []) {
          counter++
          const baseUid = sessio._uid || `${sessio.item_id || sessio.id || sessio.nom}_${sessio.curs}_${counter}`
          items.push({
            ...sessio,
            // ID únic per cada sessió individual (per drag-drop)
            _uid: baseUid,
            // Mantenim l'item_id original per identificar l'agrupació
            item_id: sessio.item_id || sessio.id || `${sessio.nom}_${sessio.curs}`,
            item_label: sessio.item_label || sessio.nom
          })
        }

        slot._items = items
      }
    }
  }

  const getItemsSlot = (key, hora) => {
    if (!horariLocal.value?.dies) return []
    const diaObj = findDiaObj(key)
    if (!diaObj) return []
    const slot = diaObj.sessions?.find(s => s.hora === hora)
    if (!slot) return []
    return slot._items || slot.sessions_simultanees || []
  }

  const getCostSlot = (dia, hora) => {
    const key = `${dia}_${hora}`
    return costsPerSlot.value[key] || null
  }

  const removeItemFromSlots = (item, exceptSlotKey = null) => {
    if (!horariLocal.value?.dies) return

    for (const d of horariLocal.value.dies) {
      for (const s of d.sessions || []) {
        const slotKey = `${d.data || d.dia}_${s.hora}`
        if (exceptSlotKey && slotKey === exceptSlotKey) continue

        const idx = (s._items || []).findIndex(i => i._uid === item._uid)
        if (idx !== -1) {
          s._items.splice(idx, 1)
          s.sessions_simultanees = s._items.map(item => ({
            ...item,
            item_id: item.item_id,
            item_label: item.item_label || item.nom
          }))
        }
      }
    }
  }

  const upsertItemAparcat = (item) => {
    if (!itemsAparcats.value.some(i => i._uid === item._uid)) {
      itemsAparcats.value.push(item)
    }
  }

  const upsertGrupAparcat = (grup) => {
    const idx = grupsAparcats.value.findIndex(g => g.id === grup.id)
    if (idx === -1) {
      grupsAparcats.value.push(grup)
      return
    }

    const existing = grupsAparcats.value[idx]
    const existingUids = new Set(existing.items.map(i => i._uid))
    for (const item of grup.items) {
      if (!existingUids.has(item._uid)) {
        existing.items.push(item)
      }
    }
  }

  const aparcarItemIdDelSlot = (slot, itemId) => {
    if (!itemId) return
    slot._items = slot._items || []

    const itemsGrup = slot._items.filter(i => i.item_id === itemId)
    if (!itemsGrup.length) return

    slot._items = slot._items.filter(i => i.item_id !== itemId)

    if (itemsGrup.length > 1) {
      upsertGrupAparcat({
        id: itemId,
        label: normalizeGroupLabel(itemsGrup[0].item_label || itemsGrup[0].nom),
        items: itemsGrup
      })
    } else {
      upsertItemAparcat(itemsGrup[0])
    }
  }

  const onItemsChanged = async (event) => {
    if (event.type === 'added') {
      const [key, hora] = parseSlotKey(event.slotKey)
      const diaObj = findDiaObj(key)
      if (!diaObj) return

      // Primer, eliminar l'ítem de qualsevol altre slot on estigui
      removeItemFromSlots(event.item, event.slotKey)
      // També treure de itemsAparcats si hi era
      const aparcatIdx = itemsAparcats.value.findIndex(i => i._uid === event.item._uid)
      if (aparcatIdx !== -1) {
        itemsAparcats.value.splice(aparcatIdx, 1)
      }

      let slot = diaObj.sessions?.find(s => s.hora === hora)
      if (!slot) {
        slot = { hora, sessions_simultanees: [], _items: [] }
        diaObj.sessions = diaObj.sessions || []
        diaObj.sessions.push(slot)
        diaObj.sessions.sort((a, b) => a.hora.localeCompare(b.hora))
      }

      slot._items = slot._items || []

      const alreadyInSlot = slot._items.some(i => i._uid === event.item._uid)
      if (!alreadyInSlot) {
        const nivellItem = event.item.curs
        if (nivellItem) {
          const conflictius = slot._items.filter(i =>
            i.curs === nivellItem && i.item_id !== event.item.item_id
          )
          const conflicteIds = Array.from(new Set(conflictius.map(i => i.item_id)))
          for (const itemId of conflicteIds) {
            aparcarItemIdDelSlot(slot, itemId)
          }
        }

        slot._items.push(event.item)
      }

      // Reconstruir sessions_simultanees directament dels _items
      slot.sessions_simultanees = slot._items.map(item => ({
        ...item,
        item_id: item.item_id,
        item_label: item.item_label || item.nom
      }))
    }

    // Ignorem 'removed' - la lògica d'eliminar es fa quan rebem 'added' d'un altre slot

    recalcularCostDebounced()
  }

  const recalcularCost = async () => {
    carregant.value = true
    try {
      const horariPerEnviar = JSON.parse(JSON.stringify(horariLocal.value))
      for (const dia of horariPerEnviar.dies || []) {
        for (const slot of dia.sessions || []) {
          if (slot._items && slot._items.length) {
            slot.sessions_simultanees = slot._items.map(item => ({
              ...item,
              item_id: item.item_id,
              item_label: item.item_label || item.nom
            }))
          }
          delete slot._items
        }
      }

      const { data } = await apiPlanificador.recalculaCost({
        horari: horariPerEnviar,
        data_referencia: props.dataReferencia,
        selected_dates: props.selectedDates
      })

      costTotal.value = data.cost_total
      costBreakdown.value = data.cost_breakdown || {}
      costBreakdownDetails.value = data.cost_breakdown_details || {}
      isValid.value = data.valid

      const slotsMap = {}
      for (const slotInfo of data.slots || []) {
        slotsMap[slotInfo.slot_key] = slotInfo
      }
      costsPerSlot.value = slotsMap

      if (horariLocal.value) {
        horariLocal.value.metadata = horariLocal.value.metadata || {}
        horariLocal.value.metadata.cost_total = data.cost_total
        horariLocal.value.metadata.logs = data.logs || []
        horariLocal.value.metadata.total_substitucions = data.stats?.total_substitucions || 0
        horariLocal.value.metadata.professors_abans = data.stats?.professors_abans || 0
        horariLocal.value.metadata.professors_despres = data.stats?.professors_despres || 0
        horariLocal.value.metadata.professors_no_treballa = data.stats?.professors_no_treballa || 0
      }

      emit('cost-changed', {
        cost: data.cost_total,
        valid: data.valid,
        logs: data.logs || [],
        stats: data.stats || {}
      })
    } catch (error) {
      console.error('Error recalculant cost:', error)
      avisaError(error, () => toast.add({
        severity: 'error',
        summary: t('scheduler.editable.toasts.recalcErrorTitle'),
        detail: t('scheduler.editable.toasts.recalcErrorDetail'),
        life: 3000
      }))
    } finally {
      carregant.value = false
    }
  }

  const recalcularCostDebounced = debounce(recalcularCost, 300)

  const onStagingChange = (evt) => {
    // Quan s'afegeix a staging, no cal recalcular (ja no està a l'horari)
    // Quan es treu de staging, es gestiona via onItemsChanged del slot destí
    if (evt.added) {
      removeItemFromSlots(evt.added.element)
    }
    if (evt.added || evt.removed) {
      recalcularCostDebounced()
    }
  }

  const onStagingGrupsChange = (evt) => {
    // Quan una agrupació s'afegeix o es treu del staging
    if (evt.added || evt.removed) {
      recalcularCostDebounced()
    }
  }

  const onMoveGrup = (event) => {
    // Gestiona quan una agrupació sencera es mou entre slots
    const { type, slotKey, grup } = event

    if (type === 'added') {
      // Actualitzar el slot destí
      const [key, hora] = parseSlotKey(slotKey)
      const diaObj = findDiaObj(key)
      if (diaObj) {
        let slot = diaObj.sessions?.find(s => s.hora === hora)
        if (!slot) {
          slot = { hora, sessions_simultanees: [], _items: [] }
          diaObj.sessions = diaObj.sessions || []
          diaObj.sessions.push(slot)
          diaObj.sessions.sort((a, b) => a.hora.localeCompare(b.hora))
        }

        slot._items = slot._items || []
        const incomingItems = grup.items || []
        const incomingUids = new Set(incomingItems.map(i => i._uid))
        const hasNew = incomingItems.some(item => !slot._items.some(i => i._uid === item._uid))

        if (hasNew) {
          const conflicteIds = new Set()
          for (const item of incomingItems) {
            const nivellItem = item.curs
            if (!nivellItem) continue

            for (const existing of slot._items) {
              if (incomingUids.has(existing._uid)) continue
              if (existing.curs === nivellItem && existing.item_id !== item.item_id) {
                conflicteIds.add(existing.item_id)
              }
            }
          }

          for (const itemId of conflicteIds) {
            aparcarItemIdDelSlot(slot, itemId)
          }

          for (const item of incomingItems) {
            const exists = slot._items.find(i => i._uid === item._uid)
            if (!exists) {
              slot._items.push(item)
            }
          }
        }

        slot.sessions_simultanees = slot._items.map(item => ({
          ...item,
          item_id: item.item_id,
          item_label: item.item_label || item.nom
        }))
      }
    }

    if (type === 'removed') {
      // Actualitzar el slot origen
      const [key, hora] = parseSlotKey(slotKey)
      const diaObj = findDiaObj(key)
      if (diaObj) {
        const slot = diaObj.sessions?.find(s => s.hora === hora)
        if (slot) {
          const itemUids = new Set(grup.items.map(i => i._uid))
          slot._items = (slot._items || []).filter(i => !itemUids.has(i._uid))
          slot.sessions_simultanees = slot._items.map(item => ({
            ...item,
            item_id: item.item_id,
            item_label: item.item_label || item.nom
          }))
        }
      }
    }

    recalcularCostDebounced()
  }

  const desferCanvis = () => {
    horariLocal.value = JSON.parse(JSON.stringify(horariOriginal.value))
    transformarHorariAItems(horariLocal.value)
    itemsAparcats.value = []  // Buidar zona d'aparcar items
    grupsAparcats.value = []  // Buidar zona d'aparcar grups
    recalcularCost()
  }

  const aplicarCanvis = () => {
    if (!isValid.value) {
      toast.add({
        severity: 'warn',
        summary: t('scheduler.editable.toasts.pendingConflictsTitle'),
        detail: t('scheduler.editable.toasts.pendingConflictsDetail'),
        life: 3000
      })
      return
    }

    const horariPerEmetre = JSON.parse(JSON.stringify(horariLocal.value))
    for (const dia of horariPerEmetre.dies || []) {
      for (const slot of dia.sessions || []) {
        delete slot._items
      }
    }

    horariPerEmetre.metadata = horariPerEmetre.metadata || {}
    horariPerEmetre.metadata.editat_manualment = true
    horariPerEmetre.metadata.cost_total = costTotal.value

    horariOriginal.value = JSON.parse(JSON.stringify(horariLocal.value))

    emit('actualitzat', horariPerEmetre)
    toast.add({
      severity: 'success',
      summary: t('scheduler.editable.toasts.changesAppliedTitle'),
      detail: t('scheduler.editable.toasts.changesAppliedDetail', { cost: costTotal.value }),
      life: 2000
    })
  }

  onMounted(() => {
    horariLocal.value = JSON.parse(JSON.stringify(props.horariInicial))
    horariOriginal.value = JSON.parse(JSON.stringify(props.horariInicial))
    transformarHorariAItems(horariLocal.value)

    if (props.horariInicial?.metadata?.cost_total) {
      costTotal.value = props.horariInicial.metadata.cost_total
    }

    recalcularCost()
  })

  watch(() => props.horariInicial, (newVal) => {
    if (newVal && !haCanvis.value) {
      horariLocal.value = JSON.parse(JSON.stringify(newVal))
      horariOriginal.value = JSON.parse(JSON.stringify(newVal))
      transformarHorariAItems(horariLocal.value)
      recalcularCost()
    }
  }, { deep: true })

  return {
    parseSlotKey,
    horariLocal,
    horariOriginal,
    costTotal,
    costBreakdown,
    costBreakdownDetails,
    costsPerSlot,
    isValid,
    carregant,
    itemsAparcats,
    grupsAparcats,
    fixatsCount,
    toggleFixarItem,
    fixarTot,
    desfixarTot,
    nivellColors,
    getNivellColor,
    dayLabel,
    findDiaObj,
    normalizeGroupLabel,
    dies,
    hores,
    haCanvis,
    costBreakdownFiltered,
    formatBreakdownKey,
    formatBreakdownDetails,
    formatBreakdownSuffix,
    transformarHorariAItems,
    getItemsSlot,
    getCostSlot,
    removeItemFromSlots,
    upsertItemAparcat,
    upsertGrupAparcat,
    aparcarItemIdDelSlot,
    onItemsChanged,
    recalcularCost,
    recalcularCostDebounced,
    onStagingChange,
    onStagingGrupsChange,
    onMoveGrup,
    desferCanvis,
    aplicarCanvis,
  }
}
