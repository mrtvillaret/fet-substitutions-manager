<template>

          <div class="tab-content-table">
            <div class="filtres-assignacions">
              <div class="filtre-group">
                <label>{{ $t('examConfig.affinities.title') }}</label>
                <small >{{ $t('examConfig.affinities.subtitle') }}</small>
              </div>
              <div class="toolbar-right">
                <Button
                  :label="$t('common.add')"
                  icon="pi pi-plus"
                  @click="afegirFilaAfinitat"
                  size="small"
                  class="p-button-success"
                />
                <Button
                  :label="$t('common.save')"
                  icon="pi pi-save"
                  @click="desarAfinitats"
                  size="small"
                  class="p-button-primary"
                />
              </div>
            </div>

            <Message severity="info" :closable="false">
              {{ $t('examConfig.affinities.flowInfo') }}
            </Message>

            <DataTable
              :value="afinitats"
              stripedRows
              showGridlines
              responsiveLayout="scroll"
              class="assignacions-table p-datatable-sm"
            >
              <Column field="base" :header="$t('examConfig.affinities.base')" style="min-width: 180px">
                <template #body="{ data }">
                  <InputText :aria-label="$t('examConfig.affinities.base')" v-model="data.base" class="w-full p-inputtext-sm" />
                </template>
              </Column>
              <Column field="ordreText" :header="$t('examConfig.affinities.order')" style="min-width: 420px">
                <template #body="{ data }">
                  <InputText :aria-label="$t('examConfig.affinities.order')" v-model="data.ordreText" class="w-full p-inputtext-sm" :placeholder="$t('examConfig.affinities.orderPlaceholder')" />
                </template>
              </Column>
              <Column :header="$t('common.actions')" style="width: 90px" :frozen="true" alignFrozen="right">
                <template #body="{ index }">
                  <Button
                    icon="pi pi-trash"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    @click="eliminarFilaAfinitat(index)"
                    v-tooltip.top="$t('common.delete')"
                  />
                </template>
              </Column>
            </DataTable>
          </div>
</template>

<script setup>
import Button from 'primevue/button'
import Message from 'primevue/message'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'

const afinitats = defineModel('afinitats', { required: true })
defineProps({
  afegirFilaAfinitat: Function,
  eliminarFilaAfinitat: Function,
  desarAfinitats: Function,
})
</script>

<style scoped src="./configuracioExamens.css"></style>
