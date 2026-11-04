<template>
    <!-- Esborrar un nivell o un grup que fan servir assignacions -->
    <Dialog
      :visible="!!esborrantAmbAssignacions"
      @update:visible="(v) => { if (!v) esborrantAmbAssignacions = null }"
      :header="esborrantAmbAssignacions ? $t(ELIMINAR[esborrantAmbAssignacions.tipus].capcalera) : ''"
      :modal="true"
      :style="{ width: '460px' }"
      :breakpoints="{ '520px': '94vw' }"
    >
      <div v-if="esborrantAmbAssignacions" class="esborrar-assignacions">
        <p>{{ $t(ELIMINAR[esborrantAmbAssignacions.tipus].confirma, { code: esborrantAmbAssignacions.codi }) }}</p>
        <p class="esborrar-assignacions__pregunta">
          {{ $t(ELIMINAR[esborrantAmbAssignacions.tipus].pregunta, { count: esborrantAmbAssignacions.quantes }, esborrantAmbAssignacions.quantes) }}
        </p>
      </div>
      <template #footer>
        <div v-if="esborrantAmbAssignacions" class="esborrar-assignacions__botons">
          <Button :label="$t('common.cancel')" class="p-button-text" @click="esborrantAmbAssignacions = null" />
          <Button
            :label="$t('examConfig.deleteAssignments.keep', { count: esborrantAmbAssignacions.quantes }, esborrantAmbAssignacions.quantes)"
            class="p-button-secondary"
            @click="esborra(esborrantAmbAssignacions.tipus, esborrantAmbAssignacions.codi, false)"
          />
          <Button
            :label="$t('examConfig.deleteAssignments.deleteToo', { count: esborrantAmbAssignacions.quantes }, esborrantAmbAssignacions.quantes)"
            class="p-button-danger"
            @click="esborra(esborrantAmbAssignacions.tipus, esborrantAmbAssignacions.codi, true)"
          />
        </div>
      </template>
    </Dialog>

    <!-- Diàleg reanomenar item -->
    <Dialog
      v-model:visible="mostrarDialogRenomItem"
      :header="$t('common.edit')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-1'">{{ $t('common.new') }}</label>
          <InputText :id="prefixEtiquetes + '-camp-1'"
            v-model="renomValor"
            @keyup.enter="reanomenarItem"
            autofocus
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogRenomItem = false" class="p-button-text" />
        <Button
          :label="$t('common.save')"
          @click="reanomenarItem"
          class="p-button-success"
          :disabled="!renomValor || renomValor === itemEditant"
        />
      </template>
    </Dialog>

</template>

<script setup>
import { useId } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'

const prefixEtiquetes = useId()

const esborrantAmbAssignacions = defineModel('esborrantAmbAssignacions', { required: true })
const mostrarDialogRenomItem = defineModel('mostrarDialogRenomItem', { required: true })
const renomValor = defineModel('renomValor', { required: true })
defineProps({
  ELIMINAR: Object,
  itemEditant: String,
  esborra: Function,
  reanomenarItem: Function,
})
</script>

<style scoped src="./configuracioExamens.css"></style>
