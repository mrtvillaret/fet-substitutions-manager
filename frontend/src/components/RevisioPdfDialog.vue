<template>
  <!-- La revisió d'abans d'un PDF: els avisos que imprimirà (pdf/validacions.py);
       amb importants, cal confirmar-los per continuar -->
  <Dialog
    v-model:visible="visible"
    :header="validacions.has_critical ? $t('substitutions.dialogs.pdfValidation.criticalTitle') : $t('substitutions.dialogs.pdfValidation.warningTitle')"
    :modal="true"
    :style="{ width: '600px', maxWidth: 'calc(100vw - 2rem)', maxHeight: '80vh' }"
  >
    <div class="validacions-content">
      <p style="font-weight: 600; margin-bottom: 1rem;">{{ $t('substitutions.dialogs.pdfValidation.detectedIssues') }}</p>

      <div
        v-for="seccio in seccions"
        :key="seccio.titol"
        style="margin-bottom: 1.5rem;"
      >
        <p :style="{ fontWeight: 600, color: seccio.color, marginBottom: '0.5rem' }">{{ $t(seccio.titol) }}</p>
        <ul style="margin: 0; padding-left: 1.5rem;">
          <li v-for="(missatge, idx) in seccio.missatges.slice(0, maxim)" :key="idx" style="margin-bottom: 0.25rem;">{{ missatge }}</li>
        </ul>
        <p v-if="seccio.missatges.length > maxim" style="margin-top: 0.5rem; font-style: italic; color: #666;">
          {{ $t('common.moreItems', { count: seccio.missatges.length - maxim }) }}
        </p>
      </div>

      <slot />

      <p v-if="ambTotal" style="font-weight: 600; margin-top: 1rem;">
        {{ $t('substitutions.dialogs.pdfValidation.totalIssues', { count: validacions.total }, validacions.total) }}
      </p>

      <InformatiusPdf :missatges="validacions.informatius" />

      <div v-if="validacions.conflicts.length > 0" class="confirmacio-importants">
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
        @click="emit('cancela')"
        class="p-button-text"
      />
      <slot name="accions" />
      <Button
        :label="$t('common.continue')"
        :disabled="(validacions.conflicts.length > 0) && !confirmacioImportants"
        icon="pi pi-check"
        @click="emit('continua')"
        :loading="generant"
        :class="validacions.has_critical ? 'p-button-danger' : 'p-button-warning'"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, useId } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import InformatiusPdf from './InformatiusPdf.vue'

const prefixEtiquetes = useId()

const visible = defineModel('visible', { required: true })
const confirmacioImportants = defineModel('confirmacioImportants', { required: true })
const props = defineProps({
  validacions: { type: Object, required: true }, // { conflicts, warnings, informatius, total, has_critical }
  generant: { type: Boolean, required: true },
  maxim: { type: Number, default: Infinity }, // missatges de cada llista que es mostren
  ambTotal: { type: Boolean, default: false } // la línia amb el total d'avisos
})
const emit = defineEmits(['cancela', 'continua'])

const seccions = computed(() => [
  { titol: 'substitutions.dialogs.pdfValidation.critical', color: '#d32f2f', missatges: props.validacions.conflicts },
  { titol: 'substitutions.dialogs.pdfValidation.warnings', color: '#f57c00', missatges: props.validacions.warnings }
].filter(seccio => seccio.missatges.length > 0))
</script>

<style scoped>
.confirmacio-importants { display: flex; align-items: center; gap: 0.75rem; }
.confirmacio-importants label { margin: 0; }
</style>
