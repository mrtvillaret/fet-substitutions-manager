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
          {{ t('scheduler.editable.pinCount', { count: fixatsCount }, fixatsCount) }}
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
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import SlotDropZone from './SlotDropZone.vue'
import draggable from 'vuedraggable'
import { useHorariEditable } from '../composables/useHorariEditable'

const props = defineProps({
  horariInicial: { type: Object, required: true },
  dataReferencia: { type: String, default: null },
  selectedDates: { type: Array, default: () => [] },
  pinnedNoms: { type: Set, default: () => new Set() }
})

const emit = defineEmits(['actualitzat', 'cost-changed', 'pin-changed'])
const toast = useToast()
const { t } = useI18n()

const {
  horariLocal,
  costTotal,
  costBreakdown,
  isValid,
  carregant,
  itemsAparcats,
  grupsAparcats,
  fixatsCount,
  toggleFixarItem,
  fixarTot,
  desfixarTot,
  getNivellColor,
  dayLabel,
  dies,
  hores,
  haCanvis,
  costBreakdownFiltered,
  formatBreakdownKey,
  formatBreakdownDetails,
  formatBreakdownSuffix,
  getItemsSlot,
  getCostSlot,
  onItemsChanged,
  onStagingChange,
  onStagingGrupsChange,
  onMoveGrup,
  desferCanvis,
  aplicarCanvis,
} = useHorariEditable({ props, emit, t, toast })
</script>

<style scoped src="./horariEditable.css"></style>
