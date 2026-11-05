<template>
    <!-- Diàleg personalitzat per mostrar validacions PDF -->
    <Dialog
      v-model:visible="mostrarDialogValidacions"
      :header="validacions.has_critical ? $t('substitutions.dialogs.pdfValidation.criticalTitle') : $t('substitutions.dialogs.pdfValidation.warningTitle')"
      :modal="true"
      :style="{ width: '600px', maxWidth: 'calc(100vw - 2rem)', maxHeight: '80vh' }"
    >
      <div class="validacions-content">
        <p style="font-weight: 600; margin-bottom: 1rem;">{{ $t('substitutions.dialogs.pdfValidation.detectedIssues') }}</p>

        <div v-if="validacions.conflicts && validacions.conflicts.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #d32f2f; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.critical') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(conflict, idx) in validacions.conflicts.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">
              {{ conflict }}
            </li>
          </ul>
          <p v-if="validacions.conflicts.length > 10" style="margin-top: 0.5rem; font-style: italic; color: #666;">
            {{ $t('common.moreItems', { count: validacions.conflicts.length - 10 }) }}
          </p>
        </div>

        <div v-if="warningsFiltrats.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #f57c00; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.warnings') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(warning, idx) in warningsFiltrats.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">
              {{ warning }}
            </li>
          </ul>
          <p v-if="warningsFiltrats.length > 10" style="margin-top: 0.5rem; font-style: italic; color: #666;">
            {{ $t('common.moreItems', { count: warningsFiltrats.length - 10 }) }}
          </p>
        </div>

        <div v-if="reassignChanges.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #2c3e50; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.appliedChanges') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(change, idx) in reassignChanges.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">
              {{ change }}
            </li>
          </ul>
          <p v-if="reassignChanges.length > 10" style="margin-top: 0.5rem; font-style: italic; color: #666;">
            {{ $t('common.moreItems', { count: reassignChanges.length - 10 }) }}
          </p>
        </div>

        <p style="font-weight: 600; margin-top: 1rem;">
          {{ $t('substitutions.dialogs.pdfValidation.totalIssues', { count: totalIssuesFiltrats }, totalIssuesFiltrats) }}
        </p>

        <InformatiusPdf :missatges="informatiusFiltrats" />

        <div v-if="validacions.conflicts?.length > 0" class="confirmacio-importants">
          <Checkbox v-model="confirmacioImportants" :binary="true" :inputId="prefixEtiquetes + '-confirma-importants'" />
          <label :for="prefixEtiquetes + '-confirma-importants'">{{ $t('substitutions.dialogs.pdfValidation.confirmImportant') }}</label>
        </div>

        <Message severity="warn" style="margin-top: 1rem;">
          {{ $t('substitutions.dialogs.pdfValidation.continueQuestion') }}
        </Message>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          icon="pi pi-times"
          @click="emit('cancelarPDF')"
          class="p-button-text"
        />
        <Button
          :label="$t('substitutions.dialogs.pdfValidation.reassign')"
          icon="pi pi-refresh"
          @click="emit('reassignarProblematics')"
          :loading="reassignantProblematics"
          class="p-button-secondary"
        />
        <Button
          :label="$t('common.continue')"
          :disabled="(validacions.conflicts?.length > 0) && !confirmacioImportants"
          icon="pi pi-check"
          @click="emit('continuarPDF')"
          :loading="generantPDF"
          :class="validacions.has_critical ? 'p-button-danger' : 'p-button-warning'"
        />
      </template>
    </Dialog>

    <!-- Diàleg per exportar PDF -->
    <Dialog
      v-model:visible="mostrarDialogPDF"
      :header="$t('substitutions.dialogs.pdf.title')"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
<PdfOpcionsComunes
          v-model:config="pdfConfig"
          prefix="subs"
          amb-conflictes
          titol-contingut="substitutions.dialogs.pdf.includeContent"
          :contingut="[
            { clau: 'includeSubstitutions', etiqueta: 'substitutions.dialogs.pdf.substitutions' },
            { clau: 'includeVigilancies', etiqueta: 'substitutions.dialogs.pdf.vigilancies' }
          ]"
          :opcions-propies="[{
            clau: 'blankRows',
            etiqueta: 'substitutions.dialogs.pdf.blankRows',
            ajuda: 'substitutions.dialogs.pdf.blankRowsHint',
            amagada: !pdfConfig.includeSubstitutions
          }]"
        />

        <Message v-if="!pdfConfig.includeSubstitutions && !pdfConfig.includeVigilancies" severity="warn">
          {{ $t('substitutions.dialogs.pdf.selectAtLeastOne') }}
        </Message>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          icon="pi pi-times"
          @click="mostrarDialogPDF = false"
          class="p-button-text"
        />
        <Button
          :label="$t('substitutions.dialogs.pdf.generate')"
          icon="pi pi-file-pdf"
          @click="emit('generarPDFComplet')"
          :loading="generantPDF"
          :disabled="!pdfConfig.includeSubstitutions && !pdfConfig.includeVigilancies"
          class="p-button-success"
        />
      </template>
    </Dialog>
</template>

<script setup>
import InformatiusPdf from '../InformatiusPdf.vue'
import { useId } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import PdfOpcionsComunes from '../PdfOpcionsComunes.vue'

const prefixEtiquetes = useId()

const mostrarDialogValidacions = defineModel('mostrarDialogValidacions', { required: true })
const mostrarDialogPDF = defineModel('mostrarDialogPDF', { required: true })
const confirmacioImportants = defineModel('confirmacioImportants', { required: true })
const pdfConfig = defineModel('pdfConfig', { required: true })
defineProps({
  validacions: { type: Object, required: true },
  warningsFiltrats: { type: Array, required: true },
  informatiusFiltrats: { type: Array, required: true },
  totalIssuesFiltrats: { type: Number, required: true },
  reassignChanges: { type: Array, required: true },
  reassignantProblematics: { type: Boolean, required: true },
  generantPDF: { type: Boolean, required: true }
})
const emit = defineEmits(['cancelarPDF', 'reassignarProblematics', 'continuarPDF', 'generarPDFComplet'])
</script>

<style scoped>
.confirmacio-importants { display: flex; align-items: center; gap: 0.75rem; }
</style>
