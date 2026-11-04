<template>
  <div class="step-panel animate-fade-in">
    <div class="card">
      <div class="agrupacions-head">
        <div>
          <h3>🔗 {{ t('scheduler.steps.groups.title') }}</h3>
          <p >{{ t('scheduler.steps.groups.subtitle') }}</p>
        </div>
        <div class="toolbar agrupacions-toolbar">
          <div class="actions">
            <Dropdown :aria-label="t('scheduler.steps.groups.filterPlaceholder')"
              :modelValue="filtreNivellAgrupacio"
              @update:modelValue="emit('update:filtreNivellAgrupacio', $event)"
              :options="nivellsFiltreOptions"
              optionLabel="label"
              optionValue="value"
              :placeholder="t('scheduler.steps.groups.filterPlaceholder')"
              class="scheduler-dropdown scheduler-dropdown-sm"
            />
          </div>
          <div class="actions">
            <Button :label="t('common.add')" icon="pi pi-plus" outlined @click="obrirDialogAgrupacio" />
          </div>
        </div>
      </div>
      <p class="agrupacions-desc">{{ t('scheduler.steps.groups.description') }}</p>
      <p class="agrupacions-avis">
        <i class="pi pi-info-circle"></i>{{ t('scheduler.steps.groups.levelsHint', { cami: camiMateixMoment }) }}
      </p>

      <div class="agrupacions-soltes-section">
        <div >{{ t('scheduler.steps.groups.ungroupedTitle') }}</div>
        <div >
          <Tag v-for="a in sessionsSoltes" :key="a" :value="a" severity="info" class="scheduler-tag" />
          <span v-if="!sessionsSoltes.length">{{ t('common.none') }}</span>
        </div>
      </div>

      <DataTable :value="agrupacionsFiltrades" class="p-datatable-sm" stripedRows :emptyMessage="t('scheduler.steps.groups.emptyMessage')">
        <Column field="nom" :header="t('scheduler.steps.groups.columns.name')" style="width: 160px"></Column>
        <Column field="assignatures" :header="t('scheduler.steps.groups.columns.subjects')">
          <template #body="s">
            <div >
              <Tag v-for="a in s.data.assignatures" :key="a" :value="a" severity="warning" class="scheduler-tag" />
            </div>
          </template>
        </Column>
        <Column style="width: 120px">
          <template #body="s">
            <div >
              <Button icon="pi pi-pencil" text severity="secondary" size="small" @click="obrirDialogAgrupacio(s.data)" />
              <Button icon="pi pi-trash" text severity="danger" size="small" @click="eliminarAgrupacio(s.data.id)" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'

defineProps({
  filtreNivellAgrupacio: { type: String, default: '__all__' },
  nivellsFiltreOptions: { type: Array, default: () => [] },
  sessionsSoltes: { type: Array, default: () => [] },
  agrupacionsFiltrades: { type: Array, default: () => [] },
  obrirDialogAgrupacio: { type: Function, required: true },
  eliminarAgrupacio: { type: Function, required: true }
})

const emit = defineEmits(['update:filtreNivellAgrupacio'])
const { t } = useI18n()

// On es configura "mateix moment" per a exàmens de nivells diferents
const camiMateixMoment = computed(() => [
  t('scheduler.view.steps.restrictions'),
  t('scheduler.steps.restrictions.tabs.dayPreferences'),
  `«${t('scheduler.steps.restrictions.dayPreferences.type.sameSlot')}»`
].join(' → '))
</script>
