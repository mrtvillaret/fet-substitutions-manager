<template>

          <div class="tab-content">
            <div class="toolbar">
              <div class="toolbar-left">
                <Tag severity="info" :value="$t('examConfig.levels.count', { count: nivells.length }, nivells.length)" />
              </div>
              <div class="toolbar-right">
                <Button
                  :label="$t('common.add')"
                  icon="pi pi-plus"
                  @click="mostrarDialogAfegirNivell = true"
                  size="small"
                  class="p-button-success"
                />
              </div>
            </div>

            <div class="items-list">
              <div
                v-for="(nivell, idx) in nivells"
                :key="idx"
                class="item-card"
              >
                <span class="item-name">{{ nivell }}</span>
                <!-- Un nivell no s'edita: el codi és la clau del planificador -->
                <div class="item-actions">
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarNivell(nivell)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="nivells.length === 0" class="empty-message">
                {{ $t('examConfig.levels.empty') }}
              </div>
            </div>
            <p class="info-text">
              <i class="pi pi-info-circle"></i>
              {{ $t('examConfig.levels.hint') }}
            </p>
          </div>

    <!-- Diàleg afegir nivell -->
    <Dialog
      v-model:visible="mostrarDialogAfegirNivell"
      :header="$t('examConfig.levels.addTitle')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-1'">{{ $t('examConfig.levels.codeLabel') }}</label>
          <InputText :id="prefixEtiquetes + '-camp-1'"
            v-model="nouNivell"
            :placeholder="$t('examConfig.levels.codePlaceholder')"
            @keyup.enter="afegirNivell"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogAfegirNivell = false" class="p-button-text" />
        <Button
          :label="$t('common.add')"
          @click="afegirNivell"
          class="p-button-success"
          :disabled="!nouNivell"
        />
      </template>
    </Dialog>

</template>

<script setup>
import { useId } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'

const prefixEtiquetes = useId()

const mostrarDialogAfegirNivell = defineModel('mostrarDialogAfegirNivell', { required: true })
const nouNivell = defineModel('nouNivell', { required: true })
defineProps({
  nivells: Array,
  afegirNivell: Function,
  eliminarNivell: Function,
})
</script>

<style scoped src="./configuracioExamens.css"></style>
