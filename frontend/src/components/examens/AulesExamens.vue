<template>

          <div class="tab-content">
            <div class="toolbar">
              <div class="toolbar-left">
                <Tag severity="info" :value="$t('examConfig.rooms.count', { count: aules.length }, aules.length)" />
              </div>
              <Button
                :label="$t('common.add')"
                icon="pi pi-plus"
                @click="mostrarDialogAfegirAula = true"
                size="small"
                class="p-button-success"
              />
            </div>

            <div class="items-list">
              <div
                v-for="(aula, idx) in aules"
                :key="idx"
                class="item-card"
              >
                <span class="item-name">{{ aula }}</span>
                <div class="item-actions">
                  <Button
                    icon="pi pi-pencil"
                    @click="prepararRenomAula(aula)"
                    class="p-button-rounded p-button-text p-button-warning p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarAula(aula)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="aules.length === 0" class="empty-message">
                {{ $t('examConfig.rooms.empty') }}
              </div>
            </div>
          </div>

    <!-- Diàleg afegir aula -->
    <Dialog
      v-model:visible="mostrarDialogAfegirAula"
      :header="$t('examConfig.rooms.addTitle')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-1'">{{ $t('examConfig.rooms.codeLabel') }}</label>
          <InputText :id="prefixEtiquetes + '-camp-1'"
            v-model="novaAula"
            :placeholder="$t('examConfig.rooms.codePlaceholder')"
            @keyup.enter="afegirAula"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogAfegirAula = false" class="p-button-text" />
        <Button
          :label="$t('common.add')"
          @click="afegirAula"
          class="p-button-success"
          :disabled="!novaAula"
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

const mostrarDialogAfegirAula = defineModel('mostrarDialogAfegirAula', { required: true })
const novaAula = defineModel('novaAula', { required: true })
defineProps({
  aules: Array,
  afegirAula: Function,
  prepararRenomAula: Function,
  eliminarAula: Function,
})
</script>

<style scoped src="./configuracioExamens.css"></style>
