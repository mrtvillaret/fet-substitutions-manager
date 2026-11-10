<template>
    <!-- Diàleg d'importació des de l'XML -->
    <Dialog
      v-model:visible="mostrarDialegImport"
      :header="$t('examConfig.import.title')"
      :modal="true"
      :style="{ width: '950px', maxHeight: '85vh' }"
    >
      <div v-if="carregantPropostes" class="loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
        <p>{{ $t('examConfig.import.loading') }}</p>
      </div>

      <div v-else>
        <Message severity="info" :closable="false">
          {{ $t('examConfig.import.helpText') }}
        </Message>

        <div class="filtres-import">
          <MultiSelect :aria-label="$t('examConfig.assignments.filterLevel')"
            v-model="filtreNivellImport"
            :options="nivellsImport"
            :placeholder="$t('examConfig.assignments.filterLevel')"
            :selectedItemsLabel="$t('examConfig.import.levelsSelected', { count: filtreNivellImport.length }, filtreNivellImport.length)"
            :maxSelectedLabels="2"
            display="chip"
            class="filtre-dropdown"
          />
          <MultiSelect :filterInputProps="{ 'aria-label': $t('common.filterOptions') }" :aria-label="$t('examConfig.assignments.filterSubject')"
            v-model="filtreAssignaturaImport"
            :options="assignaturesImport"
            :placeholder="$t('examConfig.assignments.filterSubject')"
            :selectedItemsLabel="$t('examConfig.import.subjectsSelected', { count: filtreAssignaturaImport.length }, filtreAssignaturaImport.length)"
            :maxSelectedLabels="2"
            display="chip"
            :filter="true"
            class="filtre-dropdown"
          />
          <Dropdown :aria-label="$t('examConfig.import.status')"
            v-model="filtreEstatImport"
            :options="[
              { value: '', label: $t('common.all') },
              { value: 'nova', label: $t('examConfig.import.newProposal') },
              { value: 'existent', label: $t('examConfig.import.alreadyExists') }
            ]"
            optionLabel="label" optionValue="value"
            :placeholder="$t('examConfig.import.status')"
            class="filtre-dropdown"
          />
        </div>

        <Tag severity="info" :value="$t('examConfig.import.selectedCount', {
          selected: propostesSeleccionades.length, total: propostes.length }, propostesSeleccionades.length)" style="margin: 8px 0; display: inline-block;" />
        <Tag v-if="propostesFiltrades.length !== propostes.length" severity="secondary"
          :value="$t('examConfig.import.filteredCount', { count: propostesFiltrades.length })" style="margin: 8px 0 8px 6px; display: inline-block;" />

        <DataTable
          :value="propostesFiltrades"
          dataKey="_key"
          :paginator="true"
          :rows="15"
          :rowsPerPageOptions="[15, 30, 50, 100]"
          stripedRows
          showGridlines
          responsiveLayout="scroll"
          class="assignacions-table p-datatable-sm"
        >
          <Column style="width: 3rem">
            <template #header>
              <Checkbox
                :aria-label="$t('vigilancies.table.selectAll')" :modelValue="dragSelectAssignacions.allSelected.value"
                @update:modelValue="dragSelectAssignacions.toggleAll"
                binary
              />
            </template>
            <template #body="slotProps">
              <Checkbox
                :aria-label="`${slotProps.data.assignatura} · ${slotProps.data.grup}`" :modelValue="dragSelectAssignacions.isSelected(slotProps.data)"
                binary
                @mousedown.prevent="dragSelectAssignacions.onMouseDown(slotProps.data, $event)"
                @mouseenter="dragSelectAssignacions.onMouseEnter(slotProps.data)"
              />
            </template>
          </Column>
          <Column field="nivell" :header="$t('examConfig.tabs.levels')" sortable style="min-width: 100px" />
          <Column field="assignatura" :header="$t('common.subject')" sortable style="min-width: 180px">
            <template #editor="{ data, field }">
              <InputText :aria-label="field === 'titular' ? $t('examConfig.assignments.selectTeacher') : $t('examConfig.assignments.selectRoom')" v-model="data[field]" class="w-full p-inputtext-sm" />
            </template>
          </Column>
          <Column field="grup" :header="$t('common.group')" sortable style="min-width: 120px">
            <template #editor="{ data, field }">
              <InputText :aria-label="field === 'titular' ? $t('examConfig.assignments.selectTeacher') : $t('examConfig.assignments.selectRoom')" v-model="data[field]" class="w-full p-inputtext-sm" />
            </template>
          </Column>
          <Column field="titular" :header="$t('examConfig.assignments.owner')" sortable style="min-width: 150px" />
          <Column field="aula" :header="$t('common.room')" sortable style="min-width: 120px" />
          <Column field="ja_existeix" :header="$t('examConfig.import.status')" style="min-width: 110px">
            <template #body="slotProps">
              <Tag v-if="slotProps.data.ja_existeix" severity="secondary" :value="$t('examConfig.import.alreadyExists')" />
              <Tag v-else-if="slotProps.data.descartada" severity="warning" :value="$t('examConfig.import.previouslyDismissed')" />
              <Tag v-else severity="success" :value="$t('examConfig.import.newProposal')" />
            </template>
          </Column>
        </DataTable>
      </div>

      <template #footer>
        <div class="import-footer">
          <div class="overwrite-check">
            <Checkbox v-model="sobreescriuImportacio" inputId="overwrite-xml" binary />
            <label for="overwrite-xml">{{ $t('examConfig.import.overwrite') }}</label>
          </div>
          <div>
            <Button :label="$t('common.cancel')" @click="mostrarDialegImport = false" class="p-button-text" />
            <Button
              :label="$t('examConfig.import.confirmButton', { count: propostesSeleccionades.length }, propostesSeleccionades.length)"
              icon="pi pi-check"
              @click="previsualitzarImportacio"
              class="p-button-success"
              :loading="calculantResumPrevi"
              :disabled="propostesSeleccionades.length === 0"
            />
          </div>
        </div>
      </template>
    </Dialog>

    <!-- Diàleg de resum PREVI (abans d'escriure res): cal confirmar o cancel·lar -->
    <Dialog
      v-model:visible="mostrarResumPrevi"
      :header="$t('examConfig.import.previewTitle')"
      :modal="true"
      :closable="false"
      :style="{ width: '600px', maxHeight: '85vh' }"
    >
      <div v-if="resumPrevi" class="resum-import">
        <Message severity="info" :closable="false">
          {{ $t('examConfig.import.previewHelp') }}
        </Message>

        <Message v-if="resumPreviSobreescriu" severity="warn" :closable="false">
          <div class="resum-avis-sobreescriu">
            <span>{{ $t('examConfig.import.overwriteBackupWarning') }}</span>
            <Button
              :label="$t('examConfig.import.downloadBackup')"
              icon="pi pi-download"
              size="small"
              class="p-button-outlined p-button-sm"
              @click="exportarAssignacionsCsv"
            />
          </div>
        </Message>

        <template v-for="secio in [
          { key: 'nivells_creats', label: $t('examConfig.tabs.levels') },
          { key: 'grups_creats', label: $t('common.group') },
          { key: 'assignatures_creades', label: $t('common.subject') },
          { key: 'aules_creades', label: $t('examConfig.tabs.rooms') },
          { key: 'assignacions_creades', label: $t('examConfig.tabs.assignments') },
        ]" :key="secio.key">
          <div v-if="resumPrevi[secio.key] && resumPrevi[secio.key].length" class="resum-seccio">
            <h4>{{ secio.label }} ({{ resumPrevi[secio.key].length }})</h4>
            <ul>
              <li v-for="(item, i) in resumPrevi[secio.key]" :key="i">{{ item }}</li>
            </ul>
          </div>
        </template>

        <p v-if="resumPrevi.ja_existien">
          {{ $t('examConfig.import.alreadyExistedCount', { count: resumPrevi.ja_existien }, resumPrevi.ja_existien) }}
        </p>

        <Message
          v-if="resumPrevi.avisos && resumPrevi.avisos.length"
          severity="warn"
          :closable="false"
          class="resum-avisos"
        >
          <ul>
            <li v-for="(avis, i) in resumPrevi.avisos" :key="i">{{ avis }}</li>
          </ul>
        </Message>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarResumPrevi = false" class="p-button-text" />
        <Button
          :label="$t('examConfig.import.confirmImport')"
          icon="pi pi-check"
          @click="confirmarImportacioDefinitiva"
          class="p-button-success"
          :loading="important"
        />
      </template>
    </Dialog>

    <!-- Diàleg de resum FINAL (breu, després d'importar de veritat) -->
    <Dialog
      v-model:visible="mostrarResumFinal"
      :header="$t('examConfig.import.summaryTitle')"
      :modal="true"
      :closable="false"
      :style="{ width: '500px' }"
    >
      <div v-if="resumFinal">
        <p>{{ $t('examConfig.import.doneBrief', {
          nivells: resumFinal.nivells_creats.length,
          grups: resumFinal.grups_creats.length,
          assignatures: resumFinal.assignatures_creades.length,
          aules: resumFinal.aules_creades.length,
          assignacions: resumFinal.assignacions_creades.length,
        }) }}</p>
        <p v-if="resumFinal.ja_existien">
          {{ $t('examConfig.import.alreadyExistedCount', { count: resumFinal.ja_existien }, resumFinal.ja_existien) }}
        </p>
        <Message
          v-if="resumFinal.avisos && resumFinal.avisos.length"
          severity="warn"
          :closable="false"
          class="resum-avisos"
        >
          <ul>
            <li v-for="(avis, i) in resumFinal.avisos" :key="i">{{ avis }}</li>
          </ul>
        </Message>
      </div>

      <template #footer>
        <Button
          :label="$t('common.close')"
          icon="pi pi-times"
          @click="mostrarResumFinal = false"
          class="p-button-success"
        />
      </template>
    </Dialog>

</template>

<script setup>
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Message from 'primevue/message'
import MultiSelect from 'primevue/multiselect'
import Dropdown from 'primevue/dropdown'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'

const mostrarDialegImport = defineModel('mostrarDialegImport', { required: true })
const filtreNivellImport = defineModel('filtreNivellImport', { required: true })
const filtreAssignaturaImport = defineModel('filtreAssignaturaImport', { required: true })
const filtreEstatImport = defineModel('filtreEstatImport', { required: true })
const sobreescriuImportacio = defineModel('sobreescriuImportacio', { required: true })
const mostrarResumPrevi = defineModel('mostrarResumPrevi', { required: true })
const mostrarResumFinal = defineModel('mostrarResumFinal', { required: true })
defineProps({
  carregantPropostes: Boolean,
  nivellsImport: Array,
  assignaturesImport: Array,
  propostesSeleccionades: Array,
  propostes: Array,
  propostesFiltrades: Array,
  dragSelectAssignacions: Object,
  previsualitzarImportacio: Function,
  calculantResumPrevi: Boolean,
  resumPrevi: Object,
  resumPreviSobreescriu: Boolean,
  exportarAssignacionsCsv: Function,
  confirmarImportacioDefinitiva: Function,
  important: Boolean,
  resumFinal: Object,
})
</script>

<style scoped src="./configuracioExamens.css"></style>
