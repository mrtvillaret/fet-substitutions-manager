<template>
    <!-- Diàleg validacions PDF -->
    <Dialog
      v-model:visible="mostrarDialogValidacionsVig"
      :header="validacionsVig.has_critical ? $t('substitutions.dialogs.pdfValidation.criticalTitle') : $t('substitutions.dialogs.pdfValidation.warningTitle')"
      :modal="true"
      :style="{ width: '600px', maxHeight: '80vh' }"
    >
      <div class="validacions-content">
        <p style="font-weight: 600; margin-bottom: 1rem;">{{ $t('substitutions.dialogs.pdfValidation.detectedIssues') }}</p>

        <div v-if="conflictesVigFiltrats.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #d32f2f; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.critical') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(conflict, idx) in conflictesVigFiltrats.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">{{ conflict }}</li>
          </ul>
        </div>

        <div v-if="warningsVigFiltrats.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #f57c00; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.warnings') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(warning, idx) in warningsVigFiltrats.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">{{ warning }}</li>
          </ul>
        </div>

        <Message severity="warn" style="margin-top: 1rem;">
          {{ $t('substitutions.dialogs.pdfValidation.continueQuestion') }}
        </Message>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          icon="pi pi-times"
          @click="cancelarPDFVig"
          class="p-button-text"
        />
        <Button
          :label="$t('common.continue')"
          icon="pi pi-check"
          @click="continuarPDFVig"
          :loading="generantPDF"
          :class="validacionsVig.has_critical ? 'p-button-danger' : 'p-button-warning'"
        />
      </template>
    </Dialog>

    <!-- Diàleg Exportar PDF -->
    <Dialog
      v-model:visible="mostrarDialogPDF"
      :header="$t('vigilancies.dialogs.pdfTitle')"
      :modal="true"
      :style="{ width: '500px', maxWidth: 'calc(100vw - 2rem)' }"
      :closable="true"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-1'">{{ $t('vigilancies.dialogs.levelsLabel') }}</label>
          <MultiSelect :aria-label="$t('vigilancies.dialogs.levelsLabel')" :inputId="prefixEtiquetes + '-camp-1'"
            v-model="pdfConfig.nivells"
            :options="opcionsNivellsPdfDia"
            optionLabel="etiqueta"
            optionValue="valor"
            :placeholder="$t('vigilancies.dialogs.levelsPlaceholder')"
            display="chip"
            :showToggleAll="true"
            style="width: 100%;"
          />
          <small style="color: #6b7280;">{{ $t('vigilancies.dialogs.levelsHint') }}</small>
        </div>

        <PdfOpcionsComunes
          v-model:config="pdfConfig"
          prefix="vig"
          :opcions-propies="[{ clau: 'includeSubstitucions', etiqueta: 'vigilancies.dialogs.includeSubstitucions' }]"
        />
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogPDF = false" class="p-button-text" />
        <Button
          :label="$t('vigilancies.dialogs.generatePdf')"
          icon="pi pi-file-pdf"
          @click="generarPDF"
          class="p-button-success"
          :disabled="opcionsNivellsPdfDia.length > 0 && !pdfConfig.nivells?.length"
          :loading="generantPDF"
        />
      </template>
    </Dialog>

    <!-- Diàleg PDF Interval -->
    <Dialog
      v-model:visible="mostrarDialogInterval"
      :header="$t('vigilancies.dialogs.intervalTitle')"
      :modal="true"
      :style="{ width: '550px', maxWidth: 'calc(100vw - 2rem)' }"
      :closable="true"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-2'">{{ $t('vigilancies.dialogs.startDateLabel') }}</label>
          <Calendar :inputId="prefixEtiquetes + '-camp-2'"
            v-model="intervalConfig.dataInici"
            dateFormat="yy-mm-dd"
            :placeholder="$t('vigilancies.dialogs.startDate')"
            :showIcon="true"
          />
        </div>

        <div class="field">
          <label :for="prefixEtiquetes + '-camp-3'">{{ $t('vigilancies.dialogs.endDateLabel') }}</label>
          <Calendar :inputId="prefixEtiquetes + '-camp-3'"
            v-model="intervalConfig.dataFinal"
            dateFormat="yy-mm-dd"
            :placeholder="$t('vigilancies.dialogs.endDate')"
            :showIcon="true"
          />
        </div>

        <div class="field">
          <label :for="prefixEtiquetes + '-camp-4'">{{ $t('vigilancies.dialogs.levelsLabel') }}</label>
          <MultiSelect :aria-label="$t('vigilancies.dialogs.levelsLabel')" :inputId="prefixEtiquetes + '-camp-4'"
            v-model="intervalConfig.nivells"
            :options="opcionsNivellsPdfInterval"
            optionLabel="etiqueta"
            optionValue="valor"
            :placeholder="$t('vigilancies.dialogs.levelsPlaceholder')"
            display="chip"
            :showToggleAll="true"
            style="width: 100%;"
          />
        </div>

        <PdfOpcionsComunes
          v-model:config="intervalConfig"
          prefix="interval"
          amb-dia-per-pagina
          :opcions-propies="[
            { clau: 'includeWeekends', etiqueta: 'vigilancies.dialogs.includeWeekends' },
            { clau: 'includeEmptyDays', etiqueta: 'vigilancies.dialogs.includeEmpty' },
            { clau: 'includeSubstitucions', etiqueta: 'vigilancies.dialogs.includeSubstitucions' }
          ]"
        />
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogInterval = false" class="p-button-text" />
        <Button
          :label="$t('vigilancies.dialogs.generatePdf')"
          icon="pi pi-file-pdf"
          @click="generarPDFInterval"
          class="p-button-success"
          :disabled="!intervalConfig.dataInici || !intervalConfig.dataFinal || (opcionsNivellsPdfInterval.length > 0 && !intervalConfig.nivells?.length)"
          :loading="generantPDFInterval"
        />
      </template>
    </Dialog>

</template>

<script setup>
import { useId } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import MultiSelect from 'primevue/multiselect'
import Calendar from 'primevue/calendar'
import Message from 'primevue/message'
import PdfOpcionsComunes from '../PdfOpcionsComunes.vue'

const prefixEtiquetes = useId()

const mostrarDialogValidacionsVig = defineModel('mostrarDialogValidacionsVig', { required: true })
const mostrarDialogPDF = defineModel('mostrarDialogPDF', { required: true })
const mostrarDialogInterval = defineModel('mostrarDialogInterval', { required: true })
const pdfConfig = defineModel('pdfConfig', { required: true })
const intervalConfig = defineModel('intervalConfig', { required: true })
defineProps({
  validacionsVig: Object,
  conflictesVigFiltrats: Array,
  warningsVigFiltrats: Array,
  generantPDF: Boolean,
  opcionsNivellsPdfDia: Array,
  opcionsNivellsPdfInterval: Array,
  generantPDFInterval: Boolean,
  cancelarPDFVig: Function,
  continuarPDFVig: Function,
  generarPDF: Function,
  generarPDFInterval: Function,
})
</script>

<style scoped>
/* Mida fixa per tots els dropdowns i inputs */
:deep(.p-inputtext-sm),
:deep(.p-dropdown),
:deep(.p-inputtext) {
  height: 2.2rem !important;
  min-height: 2.2rem !important;
  max-height: 2.2rem !important;
  font-size: 0.9rem !important;
}
:deep(.p-dropdown .p-dropdown-label) {
  padding: 0.4rem 0.5rem !important;
  line-height: 1.4rem;
  font-size: 0.9rem !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}
/* Truncar text en inputs */
:deep(.p-inputtext) {
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}
:deep(.p-dropdown .p-dropdown-trigger) {
  width: 1.5rem !important;
  min-width: 1.5rem !important;
}
.main-actions :deep(.p-button) {
    flex: 1 1 160px;
    justify-content: center;
  }
.main-actions :deep(.p-button) {
    flex: 1 1 100%;
  }
.filters :deep(.p-dropdown) {
    width: 100% !important;
  }
/* Botó clear (X) més petit i compacte - ocult per defecte, visible en hover */
:deep(.p-dropdown .p-dropdown-clear-icon) {
  width: 0.9rem !important;
  height: 0.9rem !important;
  font-size: 0.65rem !important;
  opacity: 0.4;
  transition: opacity 0.2s;
}
:deep(.p-dropdown:hover .p-dropdown-clear-icon) {
  opacity: 1;
}
:deep(.p-inputtext .p-inputtext-clear-icon) {
  width: 0.9rem !important;
  height: 0.9rem !important;
  font-size: 0.65rem !important;
  opacity: 0.4;
  transition: opacity 0.2s;
}
:deep(.p-inputtext:hover .p-inputtext-clear-icon) {
  opacity: 1;
}
:deep(.p-inputtext) {
  padding: 0.4rem 0.6rem !important;
}
.field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}
</style>
