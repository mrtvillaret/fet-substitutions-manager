<template>
    <RevisioPdfDialog
      v-model:visible="mostrarDialogValidacions"
      v-model:confirmacioImportants="confirmacioImportants"
      :validacions="validacions"
      :generant="generantPDF"
      :maxim="10"
      amb-total
      @cancela="emit('cancelarPDF')"
      @continua="emit('continuarPDF')"
    >
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
      <template #accions>
        <Button
          :label="$t('substitutions.dialogs.pdfValidation.reassign')"
          icon="pi pi-refresh"
          @click="emit('reassignarProblematics')"
          :loading="reassignantProblematics"
          class="p-button-secondary"
        />
      </template>
    </RevisioPdfDialog>

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
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import PdfOpcionsComunes from '../PdfOpcionsComunes.vue'
import RevisioPdfDialog from '../RevisioPdfDialog.vue'

const mostrarDialogValidacions = defineModel('mostrarDialogValidacions', { required: true })
const mostrarDialogPDF = defineModel('mostrarDialogPDF', { required: true })
const confirmacioImportants = defineModel('confirmacioImportants', { required: true })
const pdfConfig = defineModel('pdfConfig', { required: true })
defineProps({
  validacions: { type: Object, required: true },
  reassignChanges: { type: Array, required: true },
  reassignantProblematics: { type: Boolean, required: true },
  generantPDF: { type: Boolean, required: true }
})
const emit = defineEmits(['cancelarPDF', 'reassignarProblematics', 'continuarPDF', 'generarPDFComplet'])
</script>

