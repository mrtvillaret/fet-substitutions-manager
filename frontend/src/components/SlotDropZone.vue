<template>
  <div
    class="slot-dropzone"
    :class="{
      'slot-error': costInfo?.conflicte_nivell,
      'slot-warning': !costInfo?.conflicte_nivell && costInfo?.cost > 500,
      'slot-ok': !costInfo?.conflicte_nivell && costInfo?.cost <= 500,
      'slot-dragover': isDragOver
    }"
    @dragover.prevent="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div class="slot-header">
      <span class="slot-cost" :class="{ 'cost-high': costInfo?.cost > 500 }">
        {{ costInfo?.cost || 0 }}
      </span>
      <span v-if="costInfo?.conflicte_nivell" class="slot-conflict-badge">!</span>
    </div>

    <!-- Missatge de rebuig -->
    <div v-if="rejectMessage" class="reject-message">
      {{ rejectMessage }}
    </div>

    <!-- Draggable principal per agrupacions -->
    <draggable
      :list="itemsAgrupats"
      group="scheduler-grups"
      item-key="id"
      :animation="200"
      ghost-class="grup-ghost"
      class="slot-grups-container"
      handle=".agrupacio-drag-handle"
      :clone="cloneGrup"
      @change="onChangeAgrupacions"
    >
      <template #item="{ element: grup }">
        <div class="agrupacio-box" :class="{ 'agrupacio-single': grup.items.length === 1 }">
          <div v-if="grup.items.length > 1" class="agrupacio-header agrupacio-drag-handle">
            <span class="agrupacio-nom">{{ grup.label }}</span>
            <span class="agrupacio-count">{{ grup.items.length }}</span>
            <span class="agrupacio-drag-hint" :title="t('scheduler.editable.staging.dragWholeGroup')">⋮⋮</span>
          </div>
          <draggable
            :list="grup.items"
            group="scheduler-items"
            item-key="_uid"
            :animation="200"
            ghost-class="item-ghost"
            drag-class="item-drag"
            class="agrupacio-items"
            :move="validarMoviment"
            @change="(evt) => onChangeGrup(evt, grup.id)"
          >
            <template #item="{ element }">
              <div
                class="item-card"
                :class="{ 'item-error': element._conflicte, 'item-pinned': isItemFixat(element) }"
                :style="{ borderLeftColor: getNivellColor(element.curs) }"
              >
                <div class="item-nom">
                  <span class="item-title">{{ element.nom || element.nom_base }}</span>
                  <span
                    v-if="getItemWarningIcons(element).length"
                    class="item-warnings-inline"
                    v-tooltip.top="{ value: getItemWarningsHtml(element), escape: false }"
                  >
                    <span v-for="(icon, idx) in getItemWarningIcons(element)" :key="idx">{{ icon }}</span>
                  </span>
                  <span
                    class="item-pin-icon"
                    :class="{ 'pinned': isItemFixat(element) }"
                    :title="isItemFixat(element) ? t('scheduler.editable.unpin') : t('scheduler.editable.pin')"
                    @click.stop="emit('toggle-pin', { item: element, slotKey: props.slotKey })"
                  >{{ isItemFixat(element) ? '📌' : '📍' }}</span>
                </div>
              </div>
            </template>
          </draggable>
        </div>
      </template>
    </draggable>

    <!-- Zona de recepció per ítems individuals (sempre visible) -->
    <draggable
      :list="itemsSolts"
      group="scheduler-items"
      item-key="_uid"
      :animation="200"
      ghost-class="item-ghost"
      drag-class="item-drag"
      class="slot-items-receiver"
      :class="{ 'slot-items-receiver-empty': !localItems.length }"
      :move="validarMoviment"
      @change="onChangeItemsSolts"
    >
      <template #item="{ element }">
        <div
          class="item-card"
          :class="{ 'item-error': element._conflicte, 'item-pinned': isItemFixat(element) }"
          :style="{ borderLeftColor: getNivellColor(element.curs) }"
        >
          <div class="item-nom">
            <span class="item-title">{{ element.nom || element.nom_base }}</span>
            <span
              v-if="getItemWarningIcons(element).length"
              class="item-warnings-inline"
              v-tooltip.top="{ value: getItemWarningsHtml(element), escape: false }"
            >
              <span v-for="(icon, idx) in getItemWarningIcons(element)" :key="idx">{{ icon }}</span>
            </span>
            <span
              class="item-pin-icon"
              :class="{ 'pinned': isItemFixat(element) }"
              :title="isItemFixat(element) ? t('scheduler.editable.unpin') : t('scheduler.editable.pin')"
              @click.stop="emit('toggle-pin', { item: element, slotKey: props.slotKey })"
            >{{ isItemFixat(element) ? '📌' : '📍' }}</span>
          </div>
        </div>
      </template>
    </draggable>

    <div v-if="!localItems.length && !itemsSolts.length" class="slot-empty">
      {{ t('scheduler.editable.table.dragHere') }}
    </div>

    <!-- Avisos per item (icona + tooltip) -->
  </div>
</template>

<script setup>
import { ref, watch, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import draggable from 'vuedraggable'
import { localizeIncidentText } from '../views/scheduler/textUtils'

const props = defineProps({
  slotKey: { type: String, required: true },
  items: { type: Array, default: () => [] },
  costInfo: { type: Object, default: null },
  logs: { type: Array, default: () => [] },
  fixedItemIds: { type: Set, default: () => new Set() }
})

const emit = defineEmits(['move-item', 'items-changed', 'move-grup', 'move-rejected', 'toggle-pin'])
const { t } = useI18n()

// Missatge de rebuig temporal
const rejectMessage = ref(null)

const localItems = ref([...props.items])
const isDragOver = ref(false)
const itemsSolts = ref([])  // Zona de recepció per ítems individuals
const pendingRemove = ref(null)  // Ítem pendent de confirmar eliminació

watch(() => props.items, (newItems) => {
  localItems.value = [...newItems]
  recalcularAgrupacions()
}, { deep: true })

// Agrupar items pel seu item_id
const itemsAgrupats = ref([])

const normalizeGroupLabel = (label) => {
  if (!label) return label
  return label.replace(/\s*\(\s*\d+\s*assig.*\)\s*$/i, '').trim()
}

const recalcularAgrupacions = () => {
  const grupsMap = new Map()

  for (const item of localItems.value) {
    const grupId = item.item_id || item._uid

    if (!grupsMap.has(grupId)) {
      grupsMap.set(grupId, {
        id: grupId,
        label: normalizeGroupLabel(item.item_label || item.nom),
        items: []
      })
    }
    grupsMap.get(grupId).items.push(item)
  }

  itemsAgrupats.value = Array.from(grupsMap.values())
}

// Inicialitzar
recalcularAgrupacions()

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

// Helper per normalitzar text (treure accents, minúscules)
const normalizeText = (t) => (t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')

// Helper per extreure hora d'un log (busca patró "a les HH:MM")
const extractHour = (text) => {
  const m = (text || '').match(/a(?: les)? (\d{1,2}:\d{2})/)
  return m ? m[1] : null
}

// Extreure dia i hora del slotKey (format: "Dimarts_09:00")
const getSlotDiaHora = () => {
  const parts = props.slotKey?.split('_') || []
  return { dia: parts[0] || '', hora: parts[1] || '' }
}

const getItemWarnings = (item) => {
  if (!item) return []

  // Primer intentem amb item_avisos (clau directa)
  const map = props.costInfo?.item_avisos || {}
  let directWarnings = item._uid ? (map[item._uid] || []) : []
  if (!directWarnings.length && item.item_id) {
    const sameIdCount = localItems.value.filter(i => i.item_id === item.item_id).length
    if (sameIdCount <= 1) {
      directWarnings = map[item.item_id] || []
    }
  }

  // Buscar als logs globals de l'horari (com fa SchedulerView)
  const logs = props.logs || []
  if (!logs.length) return directWarnings

  const professors = (item.examens || []).map(ex => ex?.titular).filter(Boolean)
  if (!professors.length) return directWarnings

  const { dia, hora } = getSlotDiaHora()
  const diaNorm = normalizeText(dia)
  const horaNorm = hora

  // Filtrar logs que:
  // 1. Mencionen algun professor de l'ítem
  // 2. Coincideixen amb el dia i hora del slot
  const profsNorm = professors.map(normalizeText)

  const logWarnings = logs.filter(log => {
    const logNorm = normalizeText(log)
    const logHour = extractHour(log)

    // Ha de mencionar el professor
    const matchesProf = profsNorm.some(prof => logNorm.includes(prof))
    if (!matchesProf) return false

    // Ha de coincidir amb el dia
    if (!logNorm.includes(diaNorm)) return false

    // Ha de coincidir amb l'hora (si es pot extreure)
    if (logHour && logHour !== horaNorm) return false

    // Només permetre avisos globals (enllaç, avisos, límit dies)
    if (!(logNorm.includes('enllac') || logNorm.includes('avis') || logNorm.includes('limit dies'))) {
      return false
    }

    return true
  })

  if (!logWarnings.length) return directWarnings
  if (!directWarnings.length) return logWarnings
  return Array.from(new Set([...directWarnings, ...logWarnings]))
}

const getAvisEmoji = (text) => {
  const norm = normalizeText(text)
  if (norm.includes('limit dies')) return '⚠️'
  if (norm.includes('enllac')) return '🔗'
  if (norm.includes('avis')) return '⚠️'
  if (norm.includes('substitu') || norm.includes('conflicte')) return '🚨'
  if (norm.includes('arriba abans') || norm.includes('queda mes estona')) return '🕐'
  if (norm.includes('no treballa')) return '🚫'
  const m = (text || '').trim().match(/^(🚨|🕐|⚠️|⚠|📋|🔗|🚫|❌|ℹ️)/u)
  if (m) return m[0] === '⚠' ? '⚠️' : m[0]
  return '⚠️'
}

const getAvisType = (text) => {
  const norm = normalizeText(text)
  if (norm.includes('substitu') || norm.includes('conflicte')) return 'sub'
  if (norm.includes('arriba abans') || norm.includes('queda mes estona')) return 'time'
  if (norm.includes('no treballa')) return 'no'
  if (norm.includes('enllac')) return 'link'
  if (norm.includes('limit dies') || norm.includes('avis')) return 'warn'
  return 'warn'
}

const formatWarningText = (text) => {
  return localizeIncidentText(text, t)
}

const escapeHtml = (text) => {
  return (text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const getItemWarningsHtml = (item) => {
  const warnings = getItemWarnings(item)
  if (!warnings.length) return ''
  const rows = warnings.map((warn) => {
    const emoji = getAvisEmoji(warn)
    const type = getAvisType(warn)
    const text = escapeHtml(formatWarningText(warn))
    return `<div class="warn-row"><span class="warn-emoji warn-emoji--${type}">${emoji}</span><span class="warn-text">${text}</span></div>`
  })
  return `<div class="warn-tooltip">${rows.join('')}</div>`
}

const getItemWarningIcons = (item) => {
  const warnings = getItemWarnings(item)
  if (!warnings.length) return []
  const order = ['🚨', '🕐', '🚫', '🔗', '⚠️']
  const set = new Set(warnings.map(getAvisEmoji))
  return order.filter(e => set.has(e))
}

const isItemFixat = (item) => {
  return props.fixedItemIds.has(item.nom)
}

// Permetre moviment excepte per items fixats
const validarMoviment = (evt) => {
  const item = evt.draggedContext?.element
  if (item && isItemFixat(item)) {
    return false
  }
  return true
}

// Clonar grup amb els seus items per evitar problemes amb nested draggables
const cloneGrup = (original) => {
  return {
    ...original,
    items: original.items.map(item => ({ ...item }))
  }
}

const onDragOver = (e) => {
  isDragOver.value = true
}

const onDragLeave = () => {
  isDragOver.value = false
}

const onDrop = (e) => {
  isDragOver.value = false
}

const onChangeGrup = (evt, grupId) => {
  if (evt.added) {
    const item = evt.added.element
    // Cancel·lar pending si és moviment intern
    if (pendingRemove.value?._uid === item._uid) {
      pendingRemove.value = null
    }
    // Afegir si ve de fora
    if (!localItems.value.some(i => i._uid === item._uid)) {
      localItems.value.push(item)
      emit('items-changed', { type: 'added', slotKey: props.slotKey, item })
      recalcularAgrupacions()
    }
  }
  if (evt.removed) {
    const item = evt.removed.element
    pendingRemove.value = item
    // Esperar per veure si arriba a algun lloc
    setTimeout(() => {
      if (pendingRemove.value?._uid === item._uid) {
        pendingRemove.value = null
        // L'ítem no ha anat enlloc dins d'aquest slot, recalcular per restaurar-lo
        recalcularAgrupacions()
      }
    }, 50)
  }
}

const onChangeAgrupacions = (evt) => {
  if (evt.added) {
    // Una agrupació sencera ha arribat a aquest slot
    const grup = evt.added.element
    // Afegir tots els ítems del grup a localItems
    for (const item of grup.items) {
      const exists = localItems.value.find(i => i._uid === item._uid)
      if (!exists) {
        localItems.value.push(item)
      }
    }
    recalcularAgrupacions()

    // Emetre event per cada ítem afegit
    emit('move-grup', {
      type: 'added',
      slotKey: props.slotKey,
      grup: grup
    })
  }
  if (evt.removed) {
    // Una agrupació sencera ha sortit d'aquest slot
    const grup = evt.removed.element
    // Treure tots els ítems del grup de localItems
    const itemUids = new Set(grup.items.map(i => i._uid))
    localItems.value = localItems.value.filter(i => !itemUids.has(i._uid))
    recalcularAgrupacions()

    emit('move-grup', {
      type: 'removed',
      slotKey: props.slotKey,
      grup: grup
    })
  }
}

const onChange = (evt) => {
  onChangeGrup(evt, null)
}

// Gestiona ítems que arriben directament al slot (no dins d'una agrupació)
const onChangeItemsSolts = (evt) => {
  if (evt.added) {
    const item = evt.added.element
    // Cancel·lar pending si és moviment intern
    if (pendingRemove.value?._uid === item._uid) {
      pendingRemove.value = null
    }
    // Afegir si ve de fora
    if (!localItems.value.some(i => i._uid === item._uid)) {
      localItems.value.push(item)
      emit('items-changed', { type: 'added', slotKey: props.slotKey, item })
    }
    // Recalcular i buidar itemsSolts
    nextTick(() => {
      recalcularAgrupacions()
      itemsSolts.value = []
    })
  }
  if (evt.removed) {
    const item = evt.removed.element
    pendingRemove.value = item
    setTimeout(() => {
      if (pendingRemove.value?._uid === item._uid) {
        pendingRemove.value = null
        recalcularAgrupacions()
      }
    }, 50)
  }
}

</script>

<style scoped>
.slot-dropzone {
  min-height: 60px;
  border: 2px dashed #e2e8f0;
  border-radius: 8px;
  padding: 6px;
  transition: all 0.2s;
  position: relative;
  background: #f8fafc;
}

.slot-dropzone.slot-error {
  border-color: #ef4444;
  background: #fef2f2;
}

.slot-dropzone.slot-warning {
  border-color: #f59e0b;
  background: #fffbeb;
}

.slot-dropzone.slot-ok {
  border-color: #10b981;
  background: #ecfdf5;
}

.slot-dropzone.slot-dragover {
  border-style: solid;
  background: #e0f2fe;
  transform: scale(1.02);
}

.slot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.slot-cost {
  font-size: 0.7rem;
  font-weight: bold;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
  color: #475569;
}

.slot-cost.cost-high {
  background: #fef3c7;
  color: #92400e;
}

.slot-conflict-badge {
  background: #ef4444;
  color: white;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: bold;
}

.item-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #94a3b8;
  border-radius: 6px;
  padding: 6px 8px;
  margin-bottom: 4px;
  cursor: grab;
  transition: transform 0.15s, box-shadow 0.15s;
}

.item-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.item-card:active {
  cursor: grabbing;
}

.item-card.item-error {
  border-color: #ef4444;
  background: #fef2f2;
}

.item-card.item-pinned {
  background: #fffbeb;
  border-color: #f59e0b;
  cursor: default;
}

.item-pin-icon {
  font-size: 0.75rem;
  cursor: pointer;
  opacity: 0.4;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.item-pin-icon:hover {
  opacity: 1;
}

.item-pin-icon.pinned {
  opacity: 1;
}

/* Caixa d'agrupació */
.agrupacio-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 4px;
  margin-bottom: 4px;
}

.agrupacio-box.agrupacio-single {
  background: transparent;
  border: none;
  padding: 0;
}

.agrupacio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 4px;
  margin-bottom: 4px;
  background: #eef2ff;
  border-radius: 4px;
  cursor: grab;
  transition: background 0.15s;
}

.agrupacio-header:hover {
  background: #e0e7ff;
}

.agrupacio-header:active {
  cursor: grabbing;
}

.agrupacio-drag-hint {
  font-size: 0.8rem;
  color: #a5b4fc;
  margin-left: 4px;
}

.agrupacio-nom {
  font-size: 0.65rem;
  font-weight: 600;
  color: #4f46e5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agrupacio-count {
  font-size: 0.6rem;
  background: #4f46e5;
  color: white;
  padding: 1px 5px;
  border-radius: 10px;
  font-weight: 600;
}

.agrupacio-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 20px;
}

.item-ghost {
  opacity: 0.4;
  background: #f1f5f9;
}

.item-drag {
  opacity: 0.9;
  transform: rotate(2deg);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
}

/* Ghost i estils per arrossegar agrupacions */
.grup-ghost {
  opacity: 0.5;
  background: #e0e7ff;
  border: 2px dashed #6366f1;
}

.agrupacio-drag-handle {
  cursor: grab;
}

.agrupacio-drag-handle:active {
  cursor: grabbing;
}

.slot-grups-container {
  min-height: 20px;
}

/* Zona de recepció per ítems individuals */
.slot-items-receiver {
  min-height: 32px;
  border: 2px dashed transparent;
  border-radius: 6px;
  padding: 4px;
  margin-top: 4px;
  transition: all 0.2s;
}

.slot-items-receiver:empty {
  border-color: #cbd5e1;
  background: rgba(148, 163, 184, 0.1);
}

.slot-items-receiver-empty {
  min-height: 40px;
  border-color: #94a3b8;
  background: rgba(148, 163, 184, 0.08);
}

.slot-items-receiver:hover {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}

.item-nom {
  display: flex;
  align-items: center;
  gap: 6px;
}

.item-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.slot-empty {
  color: #94a3b8;
  font-style: italic;
  text-align: center;
  padding: 12px 4px;
  font-size: 0.75rem;
}

.item-warnings-inline {
  margin-left: auto;
  font-size: 0.8rem;
  line-height: 1;
  cursor: help;
  display: inline-flex;
  gap: 4px;
}

:deep(.warn-tooltip) {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 320px;
}

:deep(.warn-row) {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

:deep(.warn-emoji) {
  font-size: 0.85rem;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 4px;
  background: #e2e8f0;
  color: #0f172a;
  flex: 0 0 auto;
}

:deep(.warn-emoji--sub) {
  background: #fee2e2;
  color: #b91c1c;
}

:deep(.warn-emoji--time) {
  background: #ffedd5;
  color: #c2410c;
}

:deep(.warn-emoji--link) {
  background: #dbeafe;
  color: #1d4ed8;
}

:deep(.warn-emoji--warn) {
  background: #fef3c7;
  color: #92400e;
}

:deep(.warn-emoji--no) {
  background: #e5e7eb;
  color: #374151;
}

:deep(.warn-text) {
  font-size: 0.75rem;
  color: #0f172a;
  line-height: 1.2;
  white-space: normal;
}

/* Missatge de rebuig */
.reject-message {
  background: #fef2f2;
  border: 1px solid #ef4444;
  color: #dc2626;
  font-size: 0.7rem;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 6px;
  text-align: center;
  animation: shake 0.3s ease-in-out;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}
</style>
