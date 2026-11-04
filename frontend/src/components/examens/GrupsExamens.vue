<template>

          <div class="tab-content">
            <div class="toolbar">
              <Dropdown :aria-label="$t('examConfig.groups.selectLevel')"
                v-model="nivellSeleccionatGrups"
                :options="nivells"
                :placeholder="$t('examConfig.groups.selectLevel')"
                @change="carregarGrups"
                class="nivell-selector"
              />
              <Button
                :label="$t('common.add')"
                icon="pi pi-plus"
                @click="mostrarDialogAfegirGrup = true"
                size="small"
                class="p-button-success"
              />
            </div>

            <div v-if="nivellSeleccionatGrups" class="items-list">
              <div
                v-for="(grup, idx) in grups"
                :key="idx"
                class="item-card"
              >
                <span class="item-name">{{ grup }}</span>
                <div class="item-actions">
                  <Button
                    icon="pi pi-pencil"
                    @click="prepararRenomGrup(grup)"
                    class="p-button-rounded p-button-text p-button-warning p-button-sm"
                    v-tooltip.top="$t('common.edit')"
                  />
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarGrup(grup)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </div>
              </div>
              <div v-if="grups.length === 0" class="empty-message">
                {{ $t('examConfig.groups.empty') }}
              </div>
            </div>
            <div v-else class="select-nivell-message">
              {{ $t('examConfig.groups.selectLevelHint') }}
            </div>
          </div>

    <!-- Diàleg afegir grup -->
    <Dialog
      v-model:visible="mostrarDialogAfegirGrup"
      :header="$t('examConfig.groups.addTitle')"
      :modal="true"
      :style="{ width: '400px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-1'">{{ $t('examConfig.groups.codeLabel') }}</label>
          <InputText :id="prefixEtiquetes + '-camp-1'"
            v-model="nouGrup"
            :placeholder="$t('examConfig.groups.codePlaceholder')"
            @keyup.enter="afegirGrup"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogAfegirGrup = false" class="p-button-text" />
        <Button
          :label="$t('common.add')"
          @click="afegirGrup"
          class="p-button-success"
          :disabled="!nouGrup"
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

const nivellSeleccionatGrups = defineModel('nivellSeleccionatGrups', { required: true })
const mostrarDialogAfegirGrup = defineModel('mostrarDialogAfegirGrup', { required: true })
const nouGrup = defineModel('nouGrup', { required: true })
defineProps({
  nivells: Array,
  grups: Array,
  carregarGrups: Function,
  afegirGrup: Function,
  prepararRenomGrup: Function,
  eliminarGrup: Function,
})
</script>

<style scoped src="./configuracioExamens.css"></style>
