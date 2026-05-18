<template>
  <div class="horari-editable">
    <div class="horari-toolbar">
      <div class="horari-stats">
        <span class="stat-label">{{ t('scheduler.editable.totalCost') }}:</span>
        <span class="stat-value" :class="{ 'cost-alt': costTotal > 5000, 'cost-ok': costTotal <= 2000 }">
          {{ costTotal }}
        </span>
        <span v-if="!isValid" class="stat-warning">
          {{ t('scheduler.editable.levelConflictsDetected') }}
        </span>
      </div>
      <div class="horari-actions">
        <Button
          @click="fixarTot"
          :label="t('scheduler.editable.pinAll')"
          icon="pi pi-lock"
          severity="secondary"
          size="small"
          outlined
        />
        <Button
          @click="desfixarTot"
          :label="t('scheduler.editable.unpinAll')"
          icon="pi pi-lock-open"
          severity="secondary"
          size="small"
          outlined
          :disabled="fixatsCount === 0"
        />
        <span v-if="fixatsCount > 0" class="pin-badge">
          {{ t('scheduler.editable.pinCount', { count: fixatsCount }) }}
        </span>
        <Button
          v-if="haCanvis"
          @click="desferCanvis"
          :label="t('scheduler.editable.actions.undo')"
          icon="pi pi-undo"
          severity="secondary"
          size="small"
        />
        <Button
          v-if="haCanvis"
          @click="aplicarCanvis"
          :label="t('scheduler.editable.actions.apply')"
          icon="pi pi-check"
          severity="success"
          size="small"
          :disabled="!isValid"
        />
        <ProgressSpinner v-if="carregant" style="width: 24px; height: 24px" strokeWidth="4" />
      </div>
    </div>

    <!-- ZONA D'APARCAR (staging) - Items individuals -->
    <div class="staging-area">
      <div class="staging-header">
        <span class="staging-title">{{ t('scheduler.editable.staging.itemsTitle') }}</span>
        <span class="staging-hint">{{ t('scheduler.editable.staging.itemsHint') }}</span>
      </div>
      <draggable
        :list="itemsAparcats"
        group="scheduler-items"
        item-key="_uid"
        :animation="200"
        class="staging-dropzone"
        ghost-class="item-ghost"
        @change="onStagingChange"
      >
        <template #item="{ element }">
          <div class="item-card staged" :style="{ borderLeftColor: getNivellColor(element.curs) }">
            <div class="item-nom">{{ element.nom || element.nom_base }}</div>
            <div v-if="element.item_label && element.item_label !== element.nom" class="item-agrupacio">
              {{ element.item_label }}
            </div>
          </div>
        </template>
      </draggable>
      <div v-if="!itemsAparcats.length" class="staging-empty-items">
        {{ t('scheduler.editable.staging.itemsEmpty') }}
      </div>
    </div>

    <!-- ZONA D'APARCAR (staging) - Agrupacions senceres -->
    <div class="staging-area staging-grups">
      <div class="staging-header">
        <span class="staging-title">{{ t('scheduler.editable.staging.groupsTitle') }}</span>
        <span class="staging-hint">{{ t('scheduler.editable.staging.groupsHint') }}</span>
      </div>
      <draggable
        :list="grupsAparcats"
        group="scheduler-grups"
        item-key="id"
        :animation="200"
        class="staging-dropzone staging-grups-dropzone"
        ghost-class="grup-ghost"
        @change="onStagingGrupsChange"
      >
        <template #item="{ element: grup }">
          <div class="agrupacio-box staged">
            <div class="agrupacio-header agrupacio-drag-handle">
              <span class="agrupacio-nom">{{ grup.label }}</span>
              <span class="agrupacio-count">{{ grup.items.length }}</span>
              <span class="agrupacio-drag-hint">⋮⋮</span>
            </div>
            <div class="agrupacio-items-preview">
              <span v-for="item in grup.items.slice(0, 3)" :key="item._uid" class="item-mini">
                {{ item.nom }}
              </span>
              <span v-if="grup.items.length > 3" class="item-mini-more">
                +{{ t('scheduler.editable.staging.moreItems', { count: grup.items.length - 3 }) }}
              </span>
            </div>
          </div>
        </template>
      </draggable>
      <div v-if="!grupsAparcats.length" class="staging-empty-grups">
        {{ t('scheduler.editable.staging.groupsEmpty') }}
      </div>
    </div>

    <div class="horari-grid-wrapper">
      <table class="horari-grid">
        <thead>
          <tr>
            <th class="hora-header">{{ t('scheduler.editable.table.hour') }}</th>
            <th v-for="dia in dies" :key="dia" class="dia-header">{{ dayLabel(dia) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="hora in hores" :key="hora">
            <td class="hora-label">{{ hora }}</td>
            <td v-for="dia in dies" :key="`${dia}_${hora}`" class="slot-cell">
              <SlotDropZone
                :slot-key="`${dia}_${hora}`"
                :items="getItemsSlot(dia, hora)"
                :cost-info="getCostSlot(dia, hora)"
                :logs="horariLocal?.metadata?.logs || []"
                :fixed-item-ids="pinnedNoms"
                @items-changed="onItemsChanged"
                @move-grup="onMoveGrup"
                @toggle-pin="toggleFixarItem"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="costBreakdown && Object.keys(costBreakdown).length" class="cost-breakdown">
      <span class="breakdown-title">{{ t('scheduler.editable.breakdown.title') }}:</span>
      <span v-for="(val, key) in costBreakdownFiltered" :key="key" class="breakdown-item" :title="formatBreakdownDetails(key)">
        {{ formatBreakdownKey(key) }}: {{ val }}<span v-if="formatBreakdownSuffix(key)"> ({{ formatBreakdownSuffix(key) }})</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import SlotDropZone from './SlotDropZone.vue'
import draggable from 'vuedraggable'
import axios from 'axios'
import { debounce } from 'lodash-es'
import { localizeBackendDayName } from '../views/scheduler/textUtils'

// slotKey pot ser "Dimarts_8h" o "2025-01-07_8h" — l'hora és sempre l'últim segment
const parseSlotKey = (slotKey) => {
  const idx = slotKey.lastIndexOf('_')
  return [slotKey.slice(0, idx), slotKey.slice(idx + 1)]
}

const props = defineProps({
  horariInicial: { type: Object, required: true },
  dataReferencia: { type: String, default: null },
  selectedDates: { type: Array, default: () => [] },
  pinnedNoms: { type: Set, default: () => new Set() }
})

const emit = defineEmits(['actualitzat', 'cost-changed', 'pin-changed'])
const toast = useToast()
const { t } = useI18n()

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
const isItemFixat = (item) => props.pinnedNoms.has(item.nom)
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
    await axios.post('/api/scheduler/restriccions/pin', payload)
    emit('pin-changed')
  } catch (err) {
    console.error('Error fixant/desfixant sessió:', err)
    toast.add({
      severity: 'error',
      summary: t('scheduler.editable.toasts.recalcErrorTitle'),
      detail: err.response?.data?.detail || err.message,
      life: 3000
    })
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
    await axios.post('/api/scheduler/restriccions/pin', { pins, unpins: [] })

    emit('pin-changed')
  } catch (err) {
    console.error('Error fixant tot:', err)
  }
}

const desfixarTot = async () => {
  const unpins = Array.from(props.pinnedNoms)
  if (!unpins.length) return
  try {
    await axios.post('/api/scheduler/restriccions/pin', { pins: [], unpins })
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

const validarMovimentLocal = (item, slotDesti) => {
  const [diaDesti, horaDesti] = parseSlotKey(slotDesti)
  const itemsAlSlot = getItemsSlot(diaDesti, horaDesti)

  const nivellItem = item.curs
  const nivellsExistents = itemsAlSlot
    .filter(i => i.item_id !== item.item_id)
    .map(i => i.curs)

  if (nivellsExistents.includes(nivellItem)) {
    toast.add({
      severity: 'error',
      summary: t('scheduler.editable.toasts.levelConflictTitle'),
      detail: t('scheduler.editable.toasts.levelConflictDetail', { level: nivellItem }),
      life: 3000
    })
    return false
  }
  return true
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

    const { data } = await axios.post('/api/scheduler/recalcular-cost', {
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
    toast.add({
      severity: 'error',
      summary: t('scheduler.editable.toasts.recalcErrorTitle'),
      detail: t('scheduler.editable.toasts.recalcErrorDetail'),
      life: 3000
    })
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

</script>

<style scoped>
.horari-editable {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.horari-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.horari-stats {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-label {
  font-size: 0.9rem;
  color: #64748b;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: bold;
  color: #1e293b;
  padding: 4px 12px;
  border-radius: 6px;
  background: #f1f5f9;
}

.stat-value.cost-alt {
  background: #fef3c7;
  color: #92400e;
}

.stat-value.cost-ok {
  background: #dcfce7;
  color: #166534;
}

.stat-warning {
  font-size: 0.8rem;
  color: #ef4444;
  background: #fef2f2;
  padding: 4px 8px;
  border-radius: 4px;
}

.horari-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.pin-badge {
  font-size: 0.75rem;
  color: #92400e;
  background: #fef3c7;
  padding: 4px 8px;
  border-radius: 12px;
  font-weight: 600;
}

.horari-grid-wrapper {
  overflow-x: auto;
}

.horari-grid {
  width: 100%;
  border-collapse: separate;
  border-spacing: 4px;
}

.horari-grid th {
  padding: 8px 12px;
  text-align: center;
  font-weight: 600;
  color: #475569;
  background: #f8fafc;
  border-radius: 6px;
}

.hora-header {
  width: 80px;
}

.dia-header {
  min-width: 140px;
}

.hora-label {
  padding: 8px;
  font-weight: 600;
  color: #64748b;
  background: #f8fafc;
  border-radius: 6px;
  text-align: center;
  vertical-align: top;
}

.slot-cell {
  vertical-align: top;
  padding: 2px;
}

.cost-breakdown {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.8rem;
}

.breakdown-title {
  color: #64748b;
  font-weight: 500;
}

.breakdown-item {
  color: #475569;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}

/* Staging area */
.staging-area {
  margin-bottom: 16px;
  padding: 12px;
  background: #fefce8;
  border: 2px dashed #facc15;
  border-radius: 8px;
}

.staging-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.staging-title {
  font-weight: 600;
  color: #854d0e;
  font-size: 0.9rem;
}

.staging-hint {
  font-size: 0.75rem;
  color: #a16207;
}

.staging-dropzone {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 40px;
}

.staging-empty {
  color: #ca8a04;
  font-style: italic;
  font-size: 0.8rem;
  padding: 8px;
  text-align: center;
}

.item-card.staged {
  background: white;
  border: 1px solid #fde047;
  border-left-width: 3px;
  border-radius: 6px;
  padding: 6px 10px;
  cursor: grab;
  transition: transform 0.15s, box-shadow 0.15s;
  min-width: 120px;
}

.item-card.staged:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.item-card .item-nom {
  font-size: 0.8rem;
  font-weight: 600;
  color: #1e293b;
}

.item-card .item-info {
  display: flex;
  gap: 6px;
  margin-top: 2px;
}

.item-card .item-curs {
  font-size: 0.65rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 3px;
}

.item-card .item-examens {
  font-size: 0.65rem;
  color: #94a3b8;
}

.item-card .item-agrupacio {
  font-size: 0.6rem;
  color: #6366f1;
  background: #eef2ff;
  padding: 1px 4px;
  border-radius: 3px;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-ghost {
  opacity: 0.4;
}

.grup-ghost {
  opacity: 0.5;
  background: #e0e7ff;
  border: 2px dashed #6366f1;
}

/* Staging per grups */
.staging-grups {
  background: #f0f9ff;
  border-color: #38bdf8;
}

.staging-grups-dropzone {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 60px;
}

.staging-empty-items,
.staging-empty-grups {
  color: #94a3b8;
  font-style: italic;
  font-size: 0.8rem;
  padding: 8px;
  text-align: center;
}

.agrupacio-box.staged {
  background: white;
  border: 1px solid #93c5fd;
  border-radius: 6px;
  padding: 8px;
  min-width: 150px;
}

.agrupacio-box .agrupacio-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: #eef2ff;
  border-radius: 4px;
  margin-bottom: 6px;
}

.agrupacio-box .agrupacio-nom {
  font-size: 0.75rem;
  font-weight: 600;
  color: #4f46e5;
  flex: 1;
}

.agrupacio-box .agrupacio-count {
  font-size: 0.65rem;
  background: #4f46e5;
  color: white;
  padding: 1px 5px;
  border-radius: 10px;
}

.agrupacio-box .agrupacio-drag-hint {
  font-size: 0.8rem;
  color: #a5b4fc;
}

.agrupacio-drag-handle {
  cursor: grab;
}

.agrupacio-drag-handle:active {
  cursor: grabbing;
}

.agrupacio-items-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.item-mini {
  font-size: 0.65rem;
  background: #f1f5f9;
  color: #475569;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-mini-more {
  font-size: 0.6rem;
  color: #94a3b8;
  font-style: italic;
}
</style>
