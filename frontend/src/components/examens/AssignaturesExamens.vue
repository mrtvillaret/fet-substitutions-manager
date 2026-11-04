<template>

          <div class="tab-content">
            <div class="toolbar">
              <Dropdown :aria-label="$t('examConfig.subjects.selectLevel')"
                v-model="nivellSeleccionat"
                :options="nivells"
                :placeholder="$t('examConfig.subjects.selectLevel')"
                @change="carregarAssignatures"
                class="nivell-selector"
              />
              <Button
                :label="$t('common.add')"
                icon="pi pi-plus"
                @click="mostrarDialogAfegirAssignatura = true"
                size="small"
                class="p-button-success"
              />
            </div>

            <div v-if="nivellSeleccionat" class="items-list">
              <div
                v-for="(assignatura, idx) in assignatures"
                :key="idx"
                class="item-card"
              >
                <span class="item-name">{{ assignatura }}</span>
                <div class="item-actions">
                  <Button
                    icon="pi pi-pencil"
                    @click="prepararRenomAssignatura(assignatura)"
                    class="p-button-rounded p-button-text p-button-warning p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarAssignatura(assignatura)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="assignatures.length === 0" class="empty-message">
                {{ $t('examConfig.subjects.empty') }}
              </div>
            </div>
            <div v-else class="select-nivell-message">
              {{ $t('examConfig.subjects.selectLevelHint') }}
            </div>
          </div>

    <!-- Diàleg afegir assignatura -->
    <Dialog
      v-model:visible="mostrarDialogAfegirAssignatura"
      :header="$t('examConfig.subjects.addTitle')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-1'">{{ $t('examConfig.subjects.nameLabel') }}</label>
          <InputText :id="prefixEtiquetes + '-camp-1'"
            v-model="novaAssignatura"
            :placeholder="$t('examConfig.subjects.namePlaceholder')"
            @keyup.enter="afegirAssignatura"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogAfegirAssignatura = false" class="p-button-text" />
        <Button
          :label="$t('common.add')"
          @click="afegirAssignatura"
          class="p-button-success"
          :disabled="!novaAssignatura"
        />
      </template>
    </Dialog>

</template>

<script setup>
import { useId } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'

const prefixEtiquetes = useId()

const nivellSeleccionat = defineModel('nivellSeleccionat', { required: true })
const mostrarDialogAfegirAssignatura = defineModel('mostrarDialogAfegirAssignatura', { required: true })
const novaAssignatura = defineModel('novaAssignatura', { required: true })
defineProps({
  nivells: Array,
  assignatures: Array,
  carregarAssignatures: Function,
  afegirAssignatura: Function,
  prepararRenomAssignatura: Function,
  eliminarAssignatura: Function,
})
</script>

<style scoped src="./configuracioExamens.css"></style>
