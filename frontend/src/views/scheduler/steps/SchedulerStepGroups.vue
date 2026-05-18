<template>
  <div class="step-panel animate-fade-in">
    <div class="card shadow-sm">
      <div class="flex flex-column gap-2 mb-3 agrupacions-head">
        <div>
          <h3>🔗 {{ t('scheduler.steps.groups.title') }}</h3>
          <p class="text-sm text-color-secondary m-0">{{ t('scheduler.steps.groups.subtitle') }}</p>
        </div>
        <div class="toolbar agrupacions-toolbar">
          <div class="actions">
            <Dropdown
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
      <p class="text-xs text-color-secondary mt-0 mb-3 agrupacions-desc">{{ t('scheduler.steps.groups.description') }}</p>

      <div class="mb-3 agrupacions-soltes-section">
        <div class="text-xs text-color-secondary mb-2">{{ t('scheduler.steps.groups.ungroupedTitle') }}</div>
        <div class="flex flex-wrap gap-2">
          <Tag v-for="a in sessionsSoltes" :key="a" :value="a" severity="info" class="text-xs scheduler-tag" />
          <span v-if="!sessionsSoltes.length" class="text-color-secondary text-xs">{{ t('common.none') }}</span>
        </div>
      </div>

      <DataTable :value="agrupacionsFiltrades" class="p-datatable-sm" stripedRows :emptyMessage="t('scheduler.steps.groups.emptyMessage')">
        <Column field="nom" :header="t('scheduler.steps.groups.columns.name')" style="width: 160px"></Column>
        <Column field="assignatures" :header="t('scheduler.steps.groups.columns.subjects')">
          <template #body="s">
            <div class="flex flex-wrap gap-2">
              <Tag v-for="a in s.data.assignatures" :key="a" :value="a" severity="warning" class="text-xs scheduler-tag" />
            </div>
          </template>
        </Column>
        <Column style="width: 120px">
          <template #body="s">
            <div class="flex gap-2 align-items-center justify-content-end">
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
</script>
