<template>

          <div class="tab-content-table">
            <!-- Assignacions amb grups o titulars que ja no són a l'horari (curs anterior) -->
            <Message v-if="assignacionsObsoletes.length" severity="warn" :closable="false">
              <div>{{ $t('examConfig.assignments.obsolete.text', { count: assignacionsObsoletes.length }, assignacionsObsoletes.length) }}</div>
              <ul >
                <li v-for="a in assignacionsObsoletes.slice(0, 10)" :key="a.id">
                  {{ a.assignatura }} – {{ a.grup }}<span v-if="a.titular"> ({{ a.titular }})</span>:
                  {{ a.motius.map(m => $t(`examConfig.assignments.obsolete.reason.${m}`)).join(', ') }}
                </li>
                <li v-if="assignacionsObsoletes.length > 10">…</li>
              </ul>
              <Button :label="$t('examConfig.assignments.obsolete.remove')" icon="pi pi-trash" size="small" severity="danger" @click="treureAssignacionsObsoletes" />
            </Message>
            <!-- Filtres -->
            <div class="filtres-assignacions">
              <div class="filtre-group">
                <label :for="prefixEtiquetes + '-camp-1'">{{ $t('examConfig.assignments.filterLevel') }}</label>
                <Dropdown :aria-label="$t('examConfig.assignments.filterLevel')" :inputId="prefixEtiquetes + '-camp-1'"
                  v-model="filtreNivellAssignacions"
                  :options="[$t('common.all'), ...nivells]"
                  :placeholder="$t('common.all')"
                  @change="filtrarAssignacions"
                  class="filtre-dropdown"
                />
              </div>
              <div class="filtre-group">
                <label :for="prefixEtiquetes + '-camp-2'">{{ $t('examConfig.assignments.filterSubject') }}</label>
                <Dropdown :aria-label="$t('examConfig.assignments.filterSubject')" :inputId="prefixEtiquetes + '-camp-2'"
                  v-model="filtreAssignaturaAssignacions"
                  :options="[$t('common.all'), ...assignaturesUniques]"
                  :placeholder="$t('common.all')"
                  @change="filtrarAssignacions"
                  class="filtre-dropdown"
                />
              </div>
              <!-- Per aula: amb «ENLLAÇ» es veu de seguida qui fa d'enllaç -->
              <div class="filtre-group">
                <label>{{ $t('examConfig.assignments.filterRoom') }}</label>
                <FiltreAula
                  v-model="filtreAulaAssignacions"
                  :aules="aulesDelFiltre"
                  :etiqueta-totes="$t('common.all')"
                  class="filtre-dropdown"
                  @change="filtrarAssignacions"
                />
              </div>
              <div class="toolbar-right">
                <Tag severity="info" :value="$t('examConfig.assignments.count', { shown: assignacionsFiltrades.length, total: assignacions.length })" />
                <Button
                  :label="$t('examConfig.assignments.newRow')"
                  icon="pi pi-plus"
                  @click="afegirFilaAssignacio"
                  size="small"
                  class="p-button-success"
                />
                <Button
                  :label="$t('examConfig.assignments.deleteFiltered')"
                  icon="pi pi-trash"
                  @click="eliminarAssignacionsFiltrades"
                  size="small"
                  class="p-button-danger p-button-outlined"
                  :disabled="assignacionsFiltrades.length === 0"
                />
                <Button
                  :label="$t('examConfig.assignments.deleteAll')"
                  icon="pi pi-trash"
                  @click="eliminarTotesAssignacions"
                  size="small"
                  class="p-button-danger"
                  :disabled="assignacions.length === 0"
                />
              </div>
            </div>

            <!-- Taula inline editable -->
            <DataTable
              :value="assignacionsFiltrades"
              :paginator="true"
              :rows="15"
              :rowsPerPageOptions="[15, 30, 50, 100]"
              editMode="cell"
              @cell-edit-complete="onCellEditComplete"
              stripedRows
              showGridlines
              responsiveLayout="scroll"
              class="assignacions-table p-datatable-sm"
            >
              <Column field="assignatura" :header="$t('common.subject')" sortable style="min-width: 200px">
                <template #editor="{ data, field }">
                  <Dropdown :filterInputProps="{ 'aria-label': $t('common.filterOptions') }" :aria-label="$t('examConfig.assignments.selectSubject')"
                    v-model="data[field]"
                    :options="['', ...totesAssignatures]"
                    :placeholder="$t('examConfig.assignments.selectSubject')"
                    class="w-full p-inputtext-sm"
                    :filter="true"
                  />
                </template>
              </Column>
              <Column field="grup" :header="$t('common.group')" sortable style="min-width: 130px">
                <template #editor="{ data, field }">
                  <Dropdown :aria-label="$t('examConfig.assignments.selectGroup')"
                    v-model="data[field]"
                    :options="['', ...totsGrups]"
                    :placeholder="$t('examConfig.assignments.selectGroup')"
                    class="w-full p-inputtext-sm"
                  />
                </template>
              </Column>
              <Column field="titular" :header="$t('examConfig.assignments.owner')" sortable style="min-width: 150px">
                <template #body="slotProps">
                  <span>{{ slotProps.data.titular || $t('common.noneDash') }}</span>
                </template>
                <template #editor="{ data, field }">
                  <Dropdown :filterInputProps="{ 'aria-label': $t('common.filterOptions') }" :aria-label="$t('examConfig.assignments.selectTeacher')"
                    v-model="data[field]"
                    :options="['', ...professors]"
                    :placeholder="$t('examConfig.assignments.selectTeacher')"
                    class="w-full p-inputtext-sm"
                    :filter="true"
                  />
                </template>
              </Column>
              <Column field="aula" :header="$t('common.room')" sortable style="min-width: 150px">
                <template #body="slotProps">
                  <span>{{ slotProps.data.aula || $t('common.noneDash') }}</span>
                </template>
                <template #editor="{ data, field }">
                  <Dropdown :aria-label="$t('examConfig.assignments.selectRoom')"
                    v-model="data[field]"
                    :options="['', ...aules]"
                    :placeholder="$t('examConfig.assignments.selectRoom')"
                    class="w-full p-inputtext-sm"
                  />
                </template>
              </Column>
              <Column :header="$t('common.actions')" style="width: 100px" :frozen="true" alignFrozen="right">
                <template #body="slotProps">
                  <Button
                    icon="pi pi-trash"
                    @click="eliminarAssignacio(slotProps.data.id)"
                    class="p-button-rounded p-button-text p-button-danger p-button-sm"
                    v-tooltip.top="$t('common.delete')"
                  />
                </template>
              </Column>
            </DataTable>
          </div>
</template>

<script setup>
import { useId } from 'vue'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import FiltreAula from '../vigilancies/FiltreAula.vue'

const prefixEtiquetes = useId()

const filtreNivellAssignacions = defineModel('filtreNivellAssignacions', { required: true })
const filtreAssignaturaAssignacions = defineModel('filtreAssignaturaAssignacions', { required: true })
const filtreAulaAssignacions = defineModel('filtreAulaAssignacions', { required: true })
defineProps({
  assignacionsObsoletes: Array,
  assignacions: Array,
  assignacionsFiltrades: Array,
  nivells: Array,
  assignaturesUniques: Array,
  aulesDelFiltre: Array,
  totesAssignatures: Array,
  totsGrups: Array,
  professors: Array,
  aules: Array,
  filtrarAssignacions: Function,
  treureAssignacionsObsoletes: Function,
  afegirFilaAssignacio: Function,
  eliminarAssignacionsFiltrades: Function,
  eliminarTotesAssignacions: Function,
  eliminarAssignacio: Function,
  onCellEditComplete: Function,
})
</script>

<style scoped src="./configuracioExamens.css"></style>
