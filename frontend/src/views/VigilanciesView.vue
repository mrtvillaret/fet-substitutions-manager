<template>
  <div class="vigilancies-view">
    <div class="view-header">
      <h2>{{ $t('vigilancies.title') }}</h2>
      <div class="subtitle-row">
        <p class="subtitle">{{ dataFormatada }}</p>
        <div class="day-stats">
          <Badge :value="vigilanciesFiltrades.length" severity="success" class="day-badge" />
          <span class="day-stat-label">{{ $t('substitutions.stats.vigilanciesLabel') }}</span>
          <a class="day-stat-link" @click="anarASubstitucions">
            <Badge :value="substitucionsCount" severity="info" class="day-badge" />
            <span class="day-stat-label">{{ $t('substitutions.stats.substitutionsLabel') }}</span>
          </a>
        </div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="main-actions">
        <Button
          :label="$t('vigilancies.actions.new')"
          icon="pi pi-plus"
          @click="afegirNovaVigilancia"
          class="p-button-primary"
          v-tooltip.bottom="$t('vigilancies.actions.newHint')"
        />
        <Button
          :label="$t('vigilancies.actions.assignOwners')"
          icon="pi pi-user-plus"
          @click="assignarTitulars"
          class="p-button-info"
          :loading="assignantTitulars"
          v-tooltip.bottom="$t('vigilancies.actions.assignOwnersHint')"
        />
        <Button
          :label="$t('vigilancies.actions.assignPending')"
          icon="pi pi-check-circle"
          @click="assignarPendents"
          class="p-button-warning"
          :loading="assignantPendents"
          v-tooltip.bottom="$t('vigilancies.actions.assignPendingHint')"
        />
        <Button
          v-if="seleccionades.length > 0"
          :label="$t('vigilancies.actions.deleteSelected', { count: seleccionades.length })"
          icon="pi pi-trash"
          @click="confirmarEliminarSeleccionades"
          class="p-button-danger"
          v-tooltip.bottom="$t('vigilancies.actions.deleteSelectedHint')"
        />
        <Button
          :label="$t('vigilancies.actions.clear')"
          icon="pi pi-trash"
          @click="confirmarNetejar"
          class="p-button-danger"
          outlined
          v-tooltip.bottom="$t('vigilancies.actions.clearHint')"
        />
        <Button
          :label="$t('vigilancies.actions.sort')"
          icon="pi pi-sort-amount-down"
          @click="ordenarPerHora"
          class="p-button-secondary"
          outlined
          :loading="ordenant"
          v-tooltip.bottom="$t('vigilancies.actions.sortHint')"
        />
      </div>

      <div class="toolbar-row">
        <div class="export-actions">
          <Button
            :label="$t('vigilancies.actions.exportPdf')"
            icon="pi pi-file-pdf"
            @click="mostrarDialegPDF"
            class="p-button-success"
            outlined
            v-tooltip.bottom="$t('vigilancies.actions.exportPdfHint')"
          />
          <Button
            :label="$t('vigilancies.actions.exportInterval')"
            icon="pi pi-calendar"
            @click="mostrarDialegInterval"
            class="p-button-help"
            outlined
            v-tooltip.bottom="$t('vigilancies.actions.exportIntervalHint')"
          />
        </div>

        <!-- Filtres -->
        <div class="filters">
          <Dropdown
            v-model="filtreLevell"
            :options="[allLabel, ...nivells]"
            :placeholder="$t('vigilancies.filters.level')"
            class="p-inputtext-sm"
            style="width: 180px;"
          />
          <Dropdown
            v-model="filtreHora"
            :options="[allLabel, ...hores]"
            :placeholder="$t('vigilancies.filters.hour')"
            class="p-inputtext-sm"
            style="width: 150px;"
          />
          <Dropdown
            v-model="filtreEstat"
            :options="statusOptions"
            :placeholder="$t('vigilancies.filters.status')"
            class="p-inputtext-sm"
            style="width: 150px;"
          />
        </div>
      </div>

      <div class="stats" v-if="vigilanciesFiltrades.length > 0">
        <div class="stat-card">
          <span class="stat-value">{{ vigilanciesFiltrades.length }}</span>
          <span class="stat-label">{{ $t('common.total') }}</span>
        </div>
        <div class="stat-card assignades">
          <span class="stat-value">{{ vigilanciesAssignades }}</span>
          <span class="stat-label">{{ $t('vigilancies.stats.assigned') }}</span>
        </div>
        <div class="stat-card pendents">
          <span class="stat-value">{{ vigilanciesPendents }}</span>
          <span class="stat-label">{{ $t('vigilancies.stats.pending') }}</span>
        </div>
      </div>
    </div>

    <!-- Carregant -->
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('vigilancies.loading') }}</p>
    </div>

    <div v-else-if="error" class="error-message">
      <Message severity="error" :closable="false">{{ error }}</Message>
    </div>

    <!-- Taula de vigilàncies -->
    <div v-else class="table-wrapper">
      <DataTable
        :value="vigilanciesFiltrades"
        :loading="loading"
        stripedRows
        :paginator="true"
        :rows="25"
        :rowsPerPageOptions="[10, 20, 25, 50, 100]"
        responsiveLayout="scroll"
        class="vigilancies-table"
        :rowClass="getRowClass"
        :scrollable="true"
        :autoLayout="false"
        selectionMode="multiple"
        v-model:selection="seleccionades"
        dataKey="id"
      >
        <Column selectionMode="multiple" style="width: 2.5rem; min-width: 2.5rem; max-width: 2.5rem;" />

        <template #empty>
          <div class="empty-state">
            <i class="pi pi-inbox" style="font-size: 3rem; color: #ccc;"></i>
            <p>{{ $t('vigilancies.empty.title') }}</p>
            <small>{{ $t('vigilancies.empty.hint') }}</small>
          </div>
        </template>

        <Column field="hora" :header="$t('common.hour')" :sortable="true" style="width: 75px;">
          <template #body="slotProps">
            <Dropdown
              v-model="slotProps.data.hora"
              :options="hores"
              @change="actualitzarVigilancia(slotProps.data)"
              class="hora-dropdown"
            >
              <template #value="slotPropsValue">
                <Tag
                  :value="slotPropsValue.value || $t('common.hour')"
                  :style="{
                    backgroundColor: 'var(--primary-color)',
                    color: 'white',
                    fontSize: '0.95rem',
                    fontWeight: '600',
                    padding: '0.4rem 0.8rem',
                    width: '100%',
                    textAlign: 'center'
                  }"
                />
              </template>
            </Dropdown>
          </template>
        </Column>

        <Column field="nivell" :header="$t('vigilancies.columns.level')" :sortable="true" style="width: 100px;">
          <template #body="slotProps">
            <Dropdown
              v-model="slotProps.data.nivell"
              :options="[$t('vigilancies.placeholders.level'), ...nivells]"
              @change="actualitzarVigilancia(slotProps.data)"
              :placeholder="$t('vigilancies.placeholders.level')"
              class="p-inputtext-sm w-full"
            />
          </template>
        </Column>

        <Column field="tipus" :header="$t('vigilancies.columns.type')" :sortable="true" style="width: 120px;">
          <template #body="slotProps">
            <Dropdown
              :modelValue="slotProps.data.tipus || $t('vigilancies.placeholders.type')"
              @update:modelValue="slotProps.data.tipus = $event; actualitzarVigilancia(slotProps.data)"
              :options="getTipusOptions(slotProps.data.nivell, true)"
              class="p-inputtext-sm w-full"
              :placeholder="$t('vigilancies.placeholders.type')"
            />
          </template>
        </Column>

        <Column field="grups" :header="$t('common.group')" :sortable="true" style="width: 80px;">
          <template #body="slotProps">
            <div class="cell-wrapper-relative">
              <Dropdown
                :modelValue="slotProps.data.grups || $t('vigilancies.placeholders.groups')"
                @update:modelValue="slotProps.data.grups = $event; actualitzarVigilancia(slotProps.data)"
                :options="[$t('vigilancies.placeholders.groups'), ...getGrupsPerNivell(slotProps.data.nivell)]"
                class="p-inputtext-sm w-full"
                :placeholder="$t('vigilancies.placeholders.groups')"
              />
              <!-- Botons hover (estil Colab) - Centrats a la fila (columna central) -->
              <div class="row-hover-actions">
                <Button
                  icon="pi pi-plus"
                  :label="$t('common.add')"
                  class="p-button-secondary p-button-sm action-btn subtle-action"
                  @click.stop="afegirVigilanciaDesprés(slotProps.data)"
                  v-tooltip.top="$t('vigilancies.actions.addRow')"
                />
                <Button
                  icon="pi pi-trash"
                  :label="$t('common.delete')"
                  class="p-button-secondary p-button-sm action-btn subtle-action"
                  @click.stop="confirmarEliminar(slotProps.data)"
                  v-tooltip.top="$t('common.delete')"
                />
              </div>
            </div>
          </template>
        </Column>

        <Column field="aula" :header="$t('common.room')" :sortable="true" style="width: 100px;">
          <template #body="slotProps">
            <Dropdown
              :modelValue="slotProps.data.aula || $t('vigilancies.placeholders.room')"
              @update:modelValue="slotProps.data.aula = $event; actualitzarVigilancia(slotProps.data)"
              :options="[$t('vigilancies.placeholders.room'), ...aules]"
              :placeholder="$t('vigilancies.placeholders.room')"
              class="p-inputtext-sm w-full"
            />
          </template>
        </Column>

        <Column field="vigilant" :header="$t('vigilancies.columns.supervisor')" style="width: 200px;">
          <template #body="slotProps">
            <Dropdown
              v-model="slotProps.data.vigilant"
              :options="getDisponiblesPerHora(slotProps.data.hora, slotProps.data.tipus, slotProps.data.grups, slotProps.data.aula)"
              optionLabel="label"
              optionValue="value"
              @change="actualitzarVigilancia(slotProps.data)"
              :placeholder="$t('vigilancies.placeholders.supervisor')"
              filter
              class="p-inputtext-sm w-full"
            >
              <template #value="slotPropsValue">
                <span v-if="slotPropsValue.value">
                  {{ getVigilantLabel(slotProps.data.hora, slotPropsValue.value, slotProps.data.tipus, slotProps.data.grups, slotProps.data.aula) }}
                </span>
                <span v-else class="text-gray-400">{{ $t('vigilancies.placeholders.supervisor') }}</span>
              </template>
              <template #option="optionProps">
                <div
                  class="professor-option"
                  :style="{
                    backgroundColor: optionProps.option.color,
                    padding: '0.5rem',
                    borderRadius: '4px',
                    fontWeight: optionProps.option.ja_assignat ? 'normal' : '500',
                    opacity: optionProps.option.ja_assignat ? 0.7 : 1
                  }"
                >
                  {{ optionProps.option.label }}
                </div>
              </template>
            </Dropdown>
          </template>
        </Column>

        <Column field="comentaris" :header="$t('common.comments')" style="min-width: 200px;">
          <template #body="slotProps">
            <InputText
              v-model="slotProps.data.comentaris"
              @change="actualitzarVigilancia(slotProps.data)"
              class="p-inputtext-sm w-full"
              :placeholder="$t('common.commentsPlaceholder')"
            />
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Diàleg per afegir nova vigilància -->
    <Dialog
      v-model:visible="mostrarDialogNova"
      :header="$t('vigilancies.dialogs.newTitle')"
      :modal="true"
      :style="{ width: '500px' }"
      :closable="true"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('vigilancies.dialogs.hourLabel') }}</label>
          <Dropdown
            v-model="novaVigilancia.hora"
            :options="hores"
            :placeholder="$t('vigilancies.placeholders.hour')"
          />
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.levelLabel') }}</label>
          <Dropdown
            v-model="novaVigilancia.nivell"
            :options="nivells"
            :placeholder="$t('vigilancies.placeholders.level')"
          />
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.typeLabel') }}</label>
          <Dropdown
            v-model="novaVigilancia.tipus"
            :options="getTipusOptions(novaVigilancia.nivell, true)"
            :placeholder="$t('vigilancies.placeholders.type')"
            :editable="true"
          />
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.groupsLabel') }}</label>
          <Dropdown
            v-model="novaVigilancia.grups"
            :options="getGrupsPerNivell(novaVigilancia.nivell)"
            :placeholder="$t('vigilancies.placeholders.groupsSelect')"
            :editable="true"
            :showClear="true"
          />
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.roomLabel') }}</label>
          <Dropdown
            v-model="novaVigilancia.aula"
            :options="aules"
            :placeholder="$t('vigilancies.placeholders.roomSelect')"
            :editable="true"
          />
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.supervisorLabel') }}</label>
          <Dropdown
            v-model="novaVigilancia.vigilant"
            :options="getDisponiblesPerHora(novaVigilancia.hora)"
            optionLabel="label"
            optionValue="value"
            @show="novaVigilancia.hora && carregarDisponibles(novaVigilancia.hora)"
            :placeholder="$t('vigilancies.placeholders.supervisorSelect')"
            filter
            :disabled="!novaVigilancia.hora"
          >
            <template #option="optionProps">
              <div
                class="professor-option"
                :style="{
                  backgroundColor: optionProps.option.color,
                  padding: '0.5rem',
                  borderRadius: '4px',
                  fontWeight: optionProps.option.ja_assignat ? 'normal' : '500',
                  opacity: optionProps.option.ja_assignat ? 0.7 : 1
                }"
              >
                {{ optionProps.option.label }}
              </div>
            </template>
          </Dropdown>
          <small v-if="!novaVigilancia.hora" style="color: #6b7280;">
            {{ $t('vigilancies.dialogs.selectHourFirst') }}
          </small>
        </div>

        <div class="field">
          <label>{{ $t('common.comments') }}</label>
          <InputText
            v-model="novaVigilancia.comentaris"
            :placeholder="$t('vigilancies.placeholders.notes')"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogNova = false" class="p-button-text" />
          <Button
          :label="$t('common.create')"
          @click="crearVigilancia"
          class="p-button-success"
          :disabled="!novaVigilancia.hora"
        />
      </template>
    </Dialog>

    <!-- Diàleg validacions PDF -->
    <Dialog
      v-model:visible="mostrarDialogValidacionsVig"
      :header="validacionsVig.has_critical ? $t('substitutions.dialogs.pdfValidation.criticalTitle') : $t('substitutions.dialogs.pdfValidation.warningTitle')"
      :modal="true"
      :style="{ width: '600px', maxHeight: '80vh' }"
    >
      <div class="validacions-content">
        <p style="font-weight: 600; margin-bottom: 1rem;">{{ $t('substitutions.dialogs.pdfValidation.detectedIssues') }}</p>

        <div v-if="conflictesVigFiltrats.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #d32f2f; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.critical') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(conflict, idx) in conflictesVigFiltrats.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">{{ conflict }}</li>
          </ul>
        </div>

        <div v-if="warningsVigFiltrats.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #f57c00; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.warnings') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(warning, idx) in warningsVigFiltrats.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">{{ warning }}</li>
          </ul>
        </div>

        <Message severity="warn" style="margin-top: 1rem;">
          {{ $t('substitutions.dialogs.pdfValidation.continueQuestion') }}
        </Message>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          icon="pi pi-times"
          @click="cancelarPDFVig"
          class="p-button-text"
        />
        <Button
          :label="$t('common.continue')"
          icon="pi pi-check"
          @click="continuarPDFVig"
          :loading="generantPDF"
          :class="validacionsVig.has_critical ? 'p-button-danger' : 'p-button-warning'"
        />
      </template>
    </Dialog>

    <!-- Diàleg Exportar PDF -->
    <Dialog
      v-model:visible="mostrarDialogPDF"
      :header="$t('vigilancies.dialogs.pdfTitle')"
      :modal="true"
      :style="{ width: '500px' }"
      :closable="true"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('vigilancies.dialogs.levelsLabel') }}</label>
          <MultiSelect
            v-model="pdfConfig.nivells"
            :options="nivells"
            :placeholder="$t('vigilancies.dialogs.levelsPlaceholder')"
            display="chip"
            :showToggleAll="true"
          />
          <small style="color: #6b7280;">{{ $t('vigilancies.dialogs.levelsHint') }}</small>
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.options') }}</label>
          <div class="flex flex-column gap-2">
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.showComments" inputId="showComments" :binary="true" />
              <label for="showComments" class="ml-2">{{ $t('vigilancies.dialogs.showComments') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.showHours" inputId="showHours" :binary="true" />
              <label for="showHours" class="ml-2">{{ $t('vigilancies.dialogs.showHours') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.compress" inputId="compress" :binary="true" />
              <label for="compress" class="ml-2">{{ $t('vigilancies.dialogs.compress') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.includeSubstitucions" inputId="includeSubstitucions" :binary="true" />
              <label for="includeSubstitucions" class="ml-2">{{ $t('vigilancies.dialogs.includeSubstitucions') }}</label>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogPDF = false" class="p-button-text" />
        <Button
          :label="$t('vigilancies.dialogs.generatePdf')"
          icon="pi pi-file-pdf"
          @click="generarPDF"
          class="p-button-success"
          :disabled="!pdfConfig.nivells || pdfConfig.nivells.length === 0"
          :loading="generantPDF"
        />
      </template>
    </Dialog>

    <!-- Diàleg PDF Interval -->
    <Dialog
      v-model:visible="mostrarDialogInterval"
      :header="$t('vigilancies.dialogs.intervalTitle')"
      :modal="true"
      :style="{ width: '550px' }"
      :closable="true"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('vigilancies.dialogs.startDateLabel') }}</label>
          <Calendar
            v-model="intervalConfig.dataInici"
            dateFormat="yy-mm-dd"
            :placeholder="$t('vigilancies.dialogs.startDate')"
            :showIcon="true"
          />
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.endDateLabel') }}</label>
          <Calendar
            v-model="intervalConfig.dataFinal"
            dateFormat="yy-mm-dd"
            :placeholder="$t('vigilancies.dialogs.endDate')"
            :showIcon="true"
          />
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.levelsLabel') }}</label>
          <MultiSelect
            v-model="intervalConfig.nivells"
            :options="nivells"
            :placeholder="$t('vigilancies.dialogs.levelsPlaceholder')"
            display="chip"
            :showToggleAll="true"
          />
        </div>

        <div class="field">
          <label>{{ $t('vigilancies.dialogs.options') }}</label>
          <div class="flex flex-column gap-2">
            <div class="flex align-items-center">
              <Checkbox v-model="intervalConfig.includeWeekends" inputId="includeWeekends" :binary="true" />
              <label for="includeWeekends" class="ml-2">{{ $t('vigilancies.dialogs.includeWeekends') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="intervalConfig.includeEmptyDays" inputId="includeEmptyDays" :binary="true" />
              <label for="includeEmptyDays" class="ml-2">{{ $t('vigilancies.dialogs.includeEmpty') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="intervalConfig.showComments" inputId="intervalShowComments" :binary="true" />
              <label for="intervalShowComments" class="ml-2">{{ $t('vigilancies.dialogs.showComments') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="intervalConfig.showHours" inputId="intervalShowHours" :binary="true" />
              <label for="intervalShowHours" class="ml-2">{{ $t('vigilancies.dialogs.showHoursShort') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="intervalConfig.compress" inputId="intervalCompress" :binary="true" />
              <label for="intervalCompress" class="ml-2">{{ $t('vigilancies.dialogs.compress') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="intervalConfig.includeSubstitucions" inputId="includeSubstitucions" :binary="true" />
              <label for="includeSubstitucions" class="ml-2">{{ $t('vigilancies.dialogs.includeSubstitucions') }}</label>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" @click="mostrarDialogInterval = false" class="p-button-text" />
        <Button
          :label="$t('vigilancies.dialogs.generatePdf')"
          icon="pi pi-file-pdf"
          @click="generarPDFInterval"
          class="p-button-success"
          :disabled="!intervalConfig.dataInici || !intervalConfig.dataFinal || !intervalConfig.nivells || intervalConfig.nivells.length === 0"
          :loading="generantPDFInterval"
        />
      </template>
    </Dialog>

    <!-- Diàleg de confirmació -->
    <ConfirmDialog></ConfirmDialog>
    <ConflicteDialog
      v-model:visible="mostrarDialogConflicte"
      :title="$t('common.conflict.title')"
      :message="$t('common.conflict.message')"
      :reload-label="$t('common.conflict.reload')"
      :overwrite-label="$t('common.conflict.overwrite')"
      @reload="gestionarConflicte"
      @overwrite="executarOverwrite"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import MultiSelect from 'primevue/multiselect'
import Calendar from 'primevue/calendar'
import Checkbox from 'primevue/checkbox'
import Badge from 'primevue/badge'
import ConflicteDialog from '../components/ConflicteDialog.vue'

const emit = defineEmits(['anar-substitucions'])
const toast = useToast()
const confirm = useConfirm()
const { t, locale } = useI18n()

// Props
const props = defineProps({
  dataGlobal: {
    type: Date,
    required: true
  }
})

// State
const vigilancies = ref([])
const seleccionades = ref([])
const substitucionsCount = ref(0)
const loading = ref(false)
const error = ref(null)
const mostrarDialogNova = ref(false)
const assignantTitulars = ref(false)
const assignantPendents = ref(false)
const ordenant = ref(false)
const mostrarDialogConflicte = ref(false)
const conflicteOverwrite = ref(null)

// State PDF
const mostrarDialogPDF = ref(false)
const mostrarDialogInterval = ref(false)
const generantPDF = ref(false)
const generantPDFInterval = ref(false)
const mostrarDialogValidacionsVig = ref(false)
const validacionsVig = ref({ conflicts: [], warnings: [], total: 0, has_critical: false })

const esAvisVigilancia = (text) => {
  const t = (text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  return t.includes('vigilant') || t.includes('aula') || t.includes('vigilanci')
}
const conflictesVigFiltrats = computed(() =>
  (validacionsVig.value.conflicts || []).filter(esAvisVigilancia)
)
const warningsVigFiltrats = computed(() =>
  (validacionsVig.value.warnings || []).filter(esAvisVigilancia)
)
const totalVigFiltrats = computed(() =>
  conflictesVigFiltrats.value.length + warningsVigFiltrats.value.length
)

const pdfConfig = ref({
  nivells: [],
  showComments: true,
  showHours: false,
  compress: false,
  includeSubstitucions: false
})

const intervalConfig = ref({
  dataInici: null,
  dataFinal: null,
  nivells: [],
  includeWeekends: false,
  includeEmptyDays: false,
  showComments: true,
  showHours: false,
  compress: false,
  includeSubstitucions: false
})

// Configuració
const professors = ref([])
const hores = ref([])
const nivells = ref([])
const aules = ref([])
const grupsPerNivell = ref({})
const tipusExamens = ref([])
const tipusPerNivell = ref({})
const disponiblesPerHora = ref({}) // Cache de professors disponibles per hora
const DISPONIBLES_BATCH_SIZE = 8

// Filtres
const allLabel = computed(() => t('common.all'))
const statusAssignedLabel = computed(() => t('vigilancies.stats.assigned'))
const statusPendingLabel = computed(() => t('vigilancies.stats.pending'))
const statusOptions = computed(() => [
  allLabel.value,
  statusAssignedLabel.value,
  statusPendingLabel.value
])

const filtreLevell = ref(allLabel.value)
const filtreHora = ref(allLabel.value)
const filtreEstat = ref(allLabel.value)

watch(allLabel, (newVal, oldVal) => {
  if (filtreLevell.value === oldVal) {
    filtreLevell.value = newVal
  }
  if (filtreHora.value === oldVal) {
    filtreHora.value = newVal
  }
  if (filtreEstat.value === oldVal) {
    filtreEstat.value = newVal
  }
})

// Nova vigilància
const novaVigilancia = ref({
  hora: '',
  nivell: null,
  tipus: null,
  grups: '',
  aula: '',
  vigilant: '',
  comentaris: ''
})

// Computed
const dataISO = computed(() => {
  const year = props.dataGlobal.getFullYear()
  const month = String(props.dataGlobal.getMonth() + 1).padStart(2, '0')
  const day = String(props.dataGlobal.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
})

const dataFormatada = computed(() => {
  return props.dataGlobal.toLocaleDateString(locale.value || 'ca-ES', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
})

const collator = computed(() => new Intl.Collator(locale.value || 'ca', { sensitivity: 'base' }))

const vigilanciesAssignades = computed(() =>
  vigilanciesFiltrades.value.filter(v => v.vigilant && v.vigilant.trim()).length
)

const vigilanciesPendents = computed(() =>
  vigilanciesFiltrades.value.filter(v => !v.vigilant || !v.vigilant.trim()).length
)

const vigilanciesFiltrades = computed(() => {
  let result = [...vigilancies.value]

  // Filtrar per nivell
  if (filtreLevell.value && filtreLevell.value !== allLabel.value) {
    result = result.filter(v => v.nivell === filtreLevell.value)
  }

  // Filtrar per hora
  if (filtreHora.value && filtreHora.value !== allLabel.value) {
    result = result.filter(v => v.hora === filtreHora.value)
  }

  // Filtrar per estat
  if (filtreEstat.value === statusAssignedLabel.value) {
    result = result.filter(v => v.vigilant && v.vigilant.trim())
  } else if (filtreEstat.value === statusPendingLabel.value) {
    result = result.filter(v => !v.vigilant || !v.vigilant.trim())
  }

  const horesIndex = new Map(hores.value.map((hora, idx) => [hora, idx]))
  result.sort((a, b) => {
    const idxA = horesIndex.has(a.hora) ? horesIndex.get(a.hora) : Number.POSITIVE_INFINITY
    const idxB = horesIndex.has(b.hora) ? horesIndex.get(b.hora) : Number.POSITIVE_INFINITY
    if (idxA !== idxB) return idxA - idxB
    const nivellA = a.nivell || ''
    const nivellB = b.nivell || ''
    return nivellA.localeCompare(nivellB)
  })

  return result
})

// Mètodes
const getGrupsPerNivell = (nivell) => {
  if (!nivell || !grupsPerNivell.value[nivell]) {
    return []
  }
  return grupsPerNivell.value[nivell]
}

const getTipusOptions = (nivell, includePlaceholder) => {
  if (!nivell || nivell.startsWith('--') || nivell === t('vigilancies.placeholders.level')) {
    return includePlaceholder ? [t('vigilancies.placeholders.type')] : []
  }
  const base = tipusPerNivell.value[nivell]
  const tipusBase = base && base.length > 0 ? base : tipusExamens.value
  const tipusAmbVigilancia = tipusBase.includes('VIGILÀNCIA')
    ? tipusBase
    : ['VIGILÀNCIA', ...tipusBase]
  const normalitzats = tipusAmbVigilancia.filter(Boolean)
  return includePlaceholder ? [t('vigilancies.placeholders.type'), ...normalitzats] : normalitzats
}

const normalitzarDisponiblesParam = (value) => {
  if (value === null || value === undefined) return null
  const normalized = String(value).trim()
  return normalized || null
}

const getDisponiblesCacheKey = (hora, tipus = null, grups = null, aula = null) => {
  const horaNorm = String(hora || '').trim()
  const tipusNorm = normalitzarDisponiblesParam(tipus)
  if (!tipusNorm) {
    return horaNorm
  }
  const grupsNorm = normalitzarDisponiblesParam(grups) || ''
  const aulaNorm = normalitzarDisponiblesParam(aula) || ''
  return `${horaNorm}|${tipusNorm}|${grupsNorm}|${aulaNorm}`
}

const carregarDisponibles = async (hora, force = false, tipus = null, grups = null, aula = null) => {
  const horaNorm = String(hora || '').trim()
  if (!horaNorm) return []

  const tipusNorm = normalitzarDisponiblesParam(tipus)
  const grupsNorm = normalitzarDisponiblesParam(grups)
  const aulaNorm = normalitzarDisponiblesParam(aula)
  const cacheKey = getDisponiblesCacheKey(horaNorm, tipusNorm, grupsNorm, aulaNorm)

  // Si ja tenim les dades en cache i no es força, retornar-les
  if (!force && disponiblesPerHora.value[cacheKey]) {
    return disponiblesPerHora.value[cacheKey]
  }

  try {
    // Construir URL amb paràmetres opcionals per detectar titulars
    let url = `/api/vigilancies/${dataISO.value}/${horaNorm}/disponibles`
    const params = new URLSearchParams()
    if (tipusNorm) params.append('tipus', tipusNorm)
    if (grupsNorm) params.append('grups', grupsNorm)
    if (aulaNorm) params.append('aula', aulaNorm)

    if (params.toString()) {
      url += '?' + params.toString()
    }

    const response = await axios.get(url)
    disponiblesPerHora.value[cacheKey] = response.data

    // També guardar a la cache general per hora (sense tipus) per compatibilitat
    if (!disponiblesPerHora.value[horaNorm]) {
      disponiblesPerHora.value[horaNorm] = response.data
    }

    return response.data
  } catch (err) {
    console.error(`Error carregant disponibles per hora ${horaNorm}:`, err)
    // Fallback: retornar professors sense format
    return professors.value.map(p => ({
      value: p,
      label: p,
      emoji: '',
      estat: '',
      info: '',
      ordre_tipus: 999,
      color: '#FFFFFF',
      ja_assignat: false
    }))
  }
}

const carregarDisponiblesPerLlista = async (llistaVigilancies = []) => {
  if (!llistaVigilancies.length) return

  const queriesMap = new Map()
  const addQuery = (hora, tipus = null, grups = null, aula = null) => {
    const horaNorm = String(hora || '').trim()
    if (!horaNorm) return
    const tipusNorm = normalitzarDisponiblesParam(tipus)
    const grupsNorm = normalitzarDisponiblesParam(grups)
    const aulaNorm = normalitzarDisponiblesParam(aula)
    const key = getDisponiblesCacheKey(horaNorm, tipusNorm, grupsNorm, aulaNorm)
    if (!queriesMap.has(key)) {
      queriesMap.set(key, {
        hora: horaNorm,
        tipus: tipusNorm,
        grups: grupsNorm,
        aula: aulaNorm
      })
    }
  }

  for (const vigilancia of llistaVigilancies) {
    addQuery(vigilancia.hora, vigilancia.tipus, vigilancia.grups, vigilancia.aula)
  }

  const horesUniques = new Set(llistaVigilancies.map(v => v.hora))
  for (const hora of horesUniques) {
    addQuery(hora)
  }

  const queries = Array.from(queriesMap.values())
  if (!queries.length) return

  try {
    const response = await axios.post(`/api/vigilancies/${dataISO.value}/disponibles-batch`, {
      queries
    })
    const results = response.data?.results || {}
    const novaCache = { ...disponiblesPerHora.value }

    for (const [key, value] of Object.entries(results)) {
      const disponibles = Array.isArray(value) ? value : []
      novaCache[key] = disponibles
      const horaKey = key.includes('|') ? key.split('|')[0] : key
      if (!novaCache[horaKey]) {
        novaCache[horaKey] = disponibles
      }
    }
    disponiblesPerHora.value = novaCache
  } catch (err) {
    console.error('Error en batch de disponibles, fallback a crides individuals:', err)
    const tasques = queries.map((query) => () =>
      carregarDisponibles(query.hora, false, query.tipus, query.grups, query.aula)
    )
    for (let i = 0; i < tasques.length; i += DISPONIBLES_BATCH_SIZE) {
      const lot = tasques.slice(i, i + DISPONIBLES_BATCH_SIZE)
      await Promise.all(lot.map((tasca) => tasca()))
    }
  }
}

const refrescarDisponiblesHora = async (hora) => {
  const novaCache = { ...disponiblesPerHora.value }
  for (const clau of Object.keys(novaCache)) {
    if (clau === hora || clau.startsWith(`${hora}|`)) {
      delete novaCache[clau]
    }
  }
  disponiblesPerHora.value = novaCache

  const vigilanciesHora = vigilancies.value.filter(v => v.hora === hora)
  if (!vigilanciesHora.length) return
  await carregarDisponiblesPerLlista(vigilanciesHora)
}

const getDisponiblesPerHora = (hora, tipus = null, grups = null, aula = null) => {
  // Retornar disponibles amb tipus, grups i aula per detectar titulars
  const horaNorm = String(hora || '').trim()
  const cacheKey = getDisponiblesCacheKey(horaNorm, tipus, grups, aula)

  // Buscar primer amb la clau específica (amb titular), sinó la genèrica
  const disponibles = disponiblesPerHora.value[cacheKey] || disponiblesPerHora.value[horaNorm] || []

  const ordenats = [...disponibles].sort((a, b) => {
    const ordreA = Number.isFinite(Number(a.ordre_tipus)) ? Number(a.ordre_tipus) : 999
    const ordreB = Number.isFinite(Number(b.ordre_tipus)) ? Number(b.ordre_tipus) : 999
    if (ordreA !== ordreB) {
      return ordreA - ordreB
    }
    const catA = Number.isFinite(Number(a.categoria)) ? Number(a.categoria) : 999
    const catB = Number.isFinite(Number(b.categoria)) ? Number(b.categoria) : 999
    if (catA !== catB) {
      return catA - catB
    }
    return collator.value.compare(a.value || a.label || '', b.value || b.label || '')
  })

  // AFEGIR opció buida al principi (estil Softcatalà: "Seleccioneu")
  return [
    {
      value: '',
      label: t('vigilancies.placeholders.supervisorSelect'),
      emoji: '',
      estat: '',
      info: '',
      ordre_tipus: -1,
      color: '#F3F4F6',
      ja_assignat: false
    },
    ...ordenats
  ]
}

const getVigilantLabel = (hora, vigilantValue, tipus = null, grups = null, aula = null) => {
  // Troba el label del vigilant dins de les opcions disponibles (amb titular si és el cas)
  const horaNorm = String(hora || '').trim()
  const cacheKey = getDisponiblesCacheKey(horaNorm, tipus, grups, aula)
  const disponibles = disponiblesPerHora.value[cacheKey] || disponiblesPerHora.value[horaNorm] || []
  const vigilant = disponibles.find(d => d.value === vigilantValue)
  return vigilant ? vigilant.label : vigilantValue
}

const carregarConfig = async () => {
  try {
    const response = await axios.get('/api/vigilancies/config')
    const llista = response.data.professors || []
    professors.value = [...llista].sort((a, b) => collator.value.compare(a, b))
    hores.value = response.data.hores
    nivells.value = response.data.nivells
    aules.value = response.data.aules
    grupsPerNivell.value = response.data.grups_per_nivell
    tipusExamens.value = response.data.tipus_examens
    tipusPerNivell.value = response.data.tipus_per_nivell || {}
  } catch (err) {
    console.error('Error carregant configuració:', err)
  }
}

const carregarVigilancies = async () => {
  loading.value = true
  error.value = null

  // Netejar cache de disponibles (per recalcular amb les noves assignacions)
  disponiblesPerHora.value = {}
  seleccionades.value = []

  try {
    const response = await axios.get(`/api/vigilancies/${dataISO.value}`)
    vigilancies.value = response.data

    // Precarregar disponibles deduplicant claus i en paral·lel limitat
    await carregarDisponiblesPerLlista(vigilancies.value)
  } catch (err) {
    console.error('Error carregant vigilàncies:', err)
    error.value = t('vigilancies.errors.load')
    vigilancies.value = []
  } finally {
    loading.value = false
  }
  await carregarSubstitucionsCount()
}

const carregarSubstitucionsCount = async () => {
  try {
    const response = await axios.get(`/api/substitucions/${dataISO.value}`)
    substitucionsCount.value = Array.isArray(response.data) ? response.data.length : 0
  } catch (err) {
    console.error('Error carregant substitucions:', err)
    substitucionsCount.value = 0
  }
}

const anarASubstitucions = () => {
  emit('anar-substitucions')
}

const obrirDialogConflicte = (overwriteAction) => {
  conflicteOverwrite.value = overwriteAction
  mostrarDialogConflicte.value = true
}

const gestionarConflicte = async () => {
  await carregarVigilancies()
}

const executarOverwrite = async () => {
  if (conflicteOverwrite.value) {
    await conflicteOverwrite.value()
  }
}

const actualitzarVigilancia = async (vigilancia) => {
  const esPlaceholder = (value, fallback) =>
    !value || value.startsWith('--') || value === fallback

  const tipusNormalitzat = esPlaceholder(vigilancia.tipus, t('vigilancies.placeholders.type')) ? '' : vigilancia.tipus
  const grupsNormalitzat = esPlaceholder(vigilancia.grups, t('vigilancies.placeholders.groups')) ? '' : vigilancia.grups
  const aulaNormalitzada = esPlaceholder(vigilancia.aula, t('vigilancies.placeholders.room')) ? '' : vigilancia.aula
  const nivellNormalitzat = esPlaceholder(vigilancia.nivell, t('vigilancies.placeholders.level')) ? '' : vigilancia.nivell

  try {
    const response = await axios.put(`/api/vigilancies/${dataISO.value}/${vigilancia.id}`, {
      hora: vigilancia.hora,
      tipus: tipusNormalitzat,
      grups: grupsNormalitzat,
      aula: aulaNormalitzada,
      vigilant: vigilancia.vigilant,
      comentaris: vigilancia.comentaris,
      nivell: nivellNormalitzat,
      updated_at: vigilancia.updated_at
    })

    if (response.data?.updated_at) {
      vigilancia.updated_at = response.data.updated_at
    }

    // Recarregar disponibles de l'hora afectada per mantenir consistència de candidats
    await refrescarDisponiblesHora(vigilancia.hora)

    // Actualitzar recompte de substitucions (assignar vigilant amb classe en genera)
    await carregarSubstitucionsCount()

    toast.add({
      severity: 'success',
      summary: t('common.updated'),
      detail: t('vigilancies.messages.updated'),
      life: 2000
    })
  } catch (err) {
    console.error('Error actualitzant vigilància:', err)
    if (err.response?.status === 409 && err.response?.data?.detail?.current_data) {
      const currentData = err.response.data.detail.current_data
      obrirDialogConflicte(async () => {
        await axios.put(`/api/vigilancies/${dataISO.value}/${vigilancia.id}`, {
          hora: vigilancia.hora,
          tipus: tipusNormalitzat,
          grups: grupsNormalitzat,
          aula: aulaNormalitzada,
          vigilant: vigilancia.vigilant,
          comentaris: vigilancia.comentaris,
          nivell: nivellNormalitzat,
          updated_at: currentData.updated_at,
          force: true
        })
        await carregarVigilancies()
      })
      return
    }
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('vigilancies.errors.update'),
      life: 3000
    })
    // Recarregar per restaurar estat original
    await carregarVigilancies()
  }
}

const obrirDialogNova = () => {
  novaVigilancia.value = {
    hora: '',
    nivell: null,
    tipus: null,
    grups: '',
    aula: '',
    vigilant: '',
    comentaris: ''
  }
  mostrarDialogNova.value = true
}

const crearVigilancia = async () => {
  try {
    const esPlaceholder = (value, fallback) =>
      !value || value.startsWith('--') || value === fallback

    const payload = {
      ...novaVigilancia.value,
      nivell: esPlaceholder(novaVigilancia.value.nivell, t('vigilancies.placeholders.level')) ? '' : (novaVigilancia.value.nivell || ''),
      tipus: esPlaceholder(novaVigilancia.value.tipus, t('vigilancies.placeholders.type')) ? '' : (novaVigilancia.value.tipus || '')
    }
    await axios.post(`/api/vigilancies/${dataISO.value}`, payload)

    toast.add({
      severity: 'success',
      summary: t('common.created'),
      detail: t('vigilancies.messages.created'),
      life: 3000
    })

    mostrarDialogNova.value = false
    await carregarVigilancies()
  } catch (err) {
    console.error('Error creant vigilància:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('vigilancies.errors.create'),
      life: 3000
    })
  }
}

const confirmarEliminar = (vigilancia) => {
  confirm.require({
    message: t('vigilancies.confirm.deleteMessage', { hour: vigilancia.hora }),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      await eliminarVigilancia(vigilancia)
    }
  })
}

const confirmarEliminarSeleccionades = () => {
  const count = seleccionades.value.length
  confirm.require({
    message: t('vigilancies.confirm.deleteSelectedMessage', { count }),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('vigilancies.actions.deleteSelected', { count }),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      const llistaAEliminar = [...seleccionades.value]
      seleccionades.value = []
      let errors = 0
      await Promise.all(llistaAEliminar.map(async (vig) => {
        try {
          const params = vig.updated_at ? `?updated_at=${encodeURIComponent(vig.updated_at)}` : ''
          await axios.delete(`/api/vigilancies/${dataISO.value}/${vig.id}${params}`)
        } catch {
          errors++
        }
      }))
      await carregarVigilancies()
      if (errors === 0) {
        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('vigilancies.messages.deletedSelected', { count: llistaAEliminar.length }),
          life: 3000
        })
      } else {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('vigilancies.messages.deletedSelectedPartial', { ok: llistaAEliminar.length - errors, errors }),
          life: 5000
        })
      }
    }
  })
}

const eliminarVigilancia = async (vigilancia) => {
  try {
    const params = vigilancia.updated_at ? `?updated_at=${encodeURIComponent(vigilancia.updated_at)}` : ''
    await axios.delete(`/api/vigilancies/${dataISO.value}/${vigilancia.id}${params}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('vigilancies.messages.deleted'),
      life: 3000
    })

    await carregarVigilancies()
  } catch (err) {
    console.error('Error eliminant vigilància:', err)
    if (err.response?.status === 409 && err.response?.data?.detail?.current_data) {
      const currentData = err.response.data.detail.current_data
      obrirDialogConflicte(async () => {
        const params = currentData.updated_at ? `?updated_at=${encodeURIComponent(currentData.updated_at)}&force=true` : '?force=true'
        await axios.delete(`/api/vigilancies/${dataISO.value}/${vigilancia.id}${params}`)
        await carregarVigilancies()
      })
      return
    }
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('vigilancies.errors.delete'),
      life: 3000
    })
  }
}

const getRowClass = (data) => {
  // Afegir classe per separar hores
  const index = vigilanciesFiltrades.value.indexOf(data)
  if (index === 0) return 'primera-hora'

  const horaAnterior = vigilanciesFiltrades.value[index - 1]?.hora
  const horaActual = data.hora

  return horaAnterior !== horaActual ? 'hora-separador' : ''
}

const afegirNovaVigilancia = async () => {
  // Afegeix una vigilància buida (des del botó toolbar)
  try {
    const esPlaceholder = (value, fallback) =>
      !value || value.startsWith('--') || value === fallback

    // Si hi ha vigilàncies, agafar valors de la darrera; si no, valors per defecte
    let darreraVigilancia = null
    if (vigilanciesFiltrades.value.length > 0) {
      darreraVigilancia = vigilanciesFiltrades.value[vigilanciesFiltrades.value.length - 1]
    }

    const novaVig = {
      hora: darreraVigilancia?.hora || (hores.value.length > 0 ? hores.value[0] : '08:00'),
      nivell: darreraVigilancia?.nivell || null,
      tipus: darreraVigilancia?.tipus || '',
      grups: '',
      aula: '',
      vigilant: '',
      comentaris: ''
    }
    const payload = {
      ...novaVig,
      nivell: esPlaceholder(novaVig.nivell, t('vigilancies.placeholders.level')) ? '' : (novaVig.nivell || ''),
      tipus: esPlaceholder(novaVig.tipus, t('vigilancies.placeholders.type')) ? '' : (novaVig.tipus || '')
    }

    await axios.post(`/api/vigilancies/${dataISO.value}`, payload)

    toast.add({
      severity: 'success',
      summary: t('common.created'),
      detail: t('vigilancies.messages.added'),
      life: 2000
    })

    await carregarVigilancies()
  } catch (err) {
    console.error('Error creant vigilància:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('vigilancies.errors.create'),
      life: 3000
    })
  }
}

const afegirVigilanciaDesprés = async (vigilancia) => {
  // Crear nova vigilància amb els mateixos valors que l'actual
  try {
    const esPlaceholder = (value, fallback) =>
      !value || value.startsWith('--') || value === fallback

    const novaVig = {
      hora: vigilancia.hora,
      nivell: vigilancia.nivell || null,
      tipus: vigilancia.tipus || '',
      grups: vigilancia.grups,
      aula: vigilancia.aula,
      vigilant: '',
      comentaris: ''
    }
    const payload = {
      ...novaVig,
      nivell: esPlaceholder(novaVig.nivell, t('vigilancies.placeholders.level')) ? '' : (novaVig.nivell || ''),
      tipus: esPlaceholder(novaVig.tipus, t('vigilancies.placeholders.type')) ? '' : (novaVig.tipus || '')
    }

    await axios.post(`/api/vigilancies/${dataISO.value}`, payload)

    toast.add({
      severity: 'success',
      summary: t('common.created'),
      detail: t('vigilancies.messages.added'),
      life: 2000
    })

    await carregarVigilancies()
  } catch (err) {
    console.error('Error creant vigilància:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('vigilancies.errors.create'),
      life: 3000
    })
  }
}

// Mètodes d'assignació automàtica

const assignarTitulars = async () => {
  assignantTitulars.value = true

  try {
    const response = await axios.post(`/api/vigilancies/${dataISO.value}/assign/titulars`)

    toast.add({
      severity: 'success',
      summary: t('vigilancies.messages.assignOwnersTitle'),
      detail: response.data.message,
      life: 5000
    })

    // Recarregar vigilàncies
    await carregarVigilancies()
  } catch (err) {
    console.error('Error assignant titulars:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: err.response?.data?.detail || t('vigilancies.errors.assignOwners'),
      life: 5000
    })
  } finally {
    assignantTitulars.value = false
  }
}

const assignarPendents = async () => {
  // FASE 1: Assignar només alliberats
  assignantPendents.value = true

  try {
    const response1 = await axios.post(`/api/vigilancies/${dataISO.value}/assign/pendents?disponibles=false`)

    await carregarVigilancies()

    const assignats = response1.data.assigned_count
    const pendents = response1.data.remaining_count

    // Si s'han assignat alliberats, mostrar missatge
    if (assignats > 0) {
      toast.add({
        severity: 'success',
        summary: t('vigilancies.messages.assignedFreeTitle'),
        detail: t('vigilancies.messages.assignedFreeDetail', { count: assignats }),
        life: 4000
      })
    }

    // Si encara queden pendents, preguntar si vol disponibles
    if (pendents > 0) {
      assignantPendents.value = false

      confirm.require({
        message: t('vigilancies.confirm.assignAvailableMessage', { assigned: assignats, pending: pendents }),
        header: t('vigilancies.confirm.assignAvailableTitle'),
        icon: 'pi pi-question-circle',
        acceptLabel: t('vigilancies.confirm.assignAvailableAccept', { count: pendents }),
        rejectLabel: t('vigilancies.confirm.assignAvailableReject'),
        accept: async () => {
          // FASE 2: Assignar disponibles
          assignantPendents.value = true
          try {
            const response2 = await axios.post(`/api/vigilancies/${dataISO.value}/assign/pendents?disponibles=true`)

            await carregarVigilancies()

            toast.add({
              severity: 'success',
              summary: t('vigilancies.messages.availableAssignedTitle'),
              detail: response2.data.message,
              life: 5000
            })
          } catch (err) {
            console.error('Error assignant disponibles:', err)
            toast.add({
              severity: 'error',
              summary: t('common.error'),
              detail: err.response?.data?.detail || t('vigilancies.errors.assignAvailable'),
              life: 5000
            })
          } finally {
            assignantPendents.value = false
          }
        }
      })
    } else {
      // No queden pendents
      toast.add({
        severity: 'info',
        summary: t('vigilancies.messages.allAssignedTitle'),
        detail: t('vigilancies.messages.allAssignedDetail'),
        life: 3000
      })
      assignantPendents.value = false
    }

  } catch (err) {
    console.error('Error assignant alliberats:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: err.response?.data?.detail || t('vigilancies.errors.assignFree'),
      life: 5000
    })
    assignantPendents.value = false
  }
}

const confirmarNetejar = () => {
  confirm.require({
    message: t('vigilancies.confirm.clearMessage'),
    header: t('vigilancies.confirm.clearTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('vigilancies.confirm.clearAccept'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        const response = await axios.post(`/api/vigilancies/${dataISO.value}/clear`)

        toast.add({
          severity: 'success',
          summary: t('vigilancies.messages.clearedTitle'),
          detail: response.data.message,
          life: 3000
        })

        await carregarVigilancies()
      } catch (err) {
        console.error('Error netejant assignacions:', err)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: t('vigilancies.errors.clear'),
          life: 3000
        })
      }
    }
  })
}

const ordenarPerHora = async () => {
  ordenant.value = true

  try {
    const response = await axios.post(`/api/vigilancies/${dataISO.value}/sort`)

    toast.add({
      severity: 'success',
      summary: t('vigilancies.messages.sortedTitle'),
      detail: response.data.message,
      life: 3000
    })

    await carregarVigilancies()
  } catch (err) {
    console.error('Error ordenant vigilàncies:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('vigilancies.errors.sort'),
      life: 3000
    })
  } finally {
    ordenant.value = false
  }
}

// Funcions PDF
const aplicarPreferenciesPdf = (prefs, target, keys) => {
  if (!prefs) return
  keys.forEach((key) => {
    if (prefs[key] !== undefined) {
      target.value[key] = prefs[key]
    }
  })
}

const carregarPreferenciesPdf = async () => {
  try {
    const response = await axios.get('/api/settings/pdf-preferences')
    aplicarPreferenciesPdf(
      response.data?.vigilancies,
      pdfConfig,
      ['showComments', 'showHours', 'compress', 'includeSubstitucions']
    )
    aplicarPreferenciesPdf(
      response.data?.vigilancies_interval,
      intervalConfig,
      ['includeWeekends', 'includeEmptyDays', 'showComments', 'showHours', 'compress', 'includeSubstitucions']
    )
  } catch (error) {
    console.error('Error carregant preferències PDF:', error)
  }
}

const desarPreferenciesPdf = async (tipus) => {
  try {
    if (tipus === 'vigilancies') {
      await axios.put('/api/settings/pdf-preferences', {
        vigilancies: {
          showComments: pdfConfig.value.showComments,
          showHours: pdfConfig.value.showHours,
          compress: pdfConfig.value.compress,
          includeSubstitucions: pdfConfig.value.includeSubstitucions
        }
      })
      return
    }
    if (tipus === 'interval') {
      await axios.put('/api/settings/pdf-preferences', {
        vigilancies_interval: {
          includeWeekends: intervalConfig.value.includeWeekends,
          includeEmptyDays: intervalConfig.value.includeEmptyDays,
          showComments: intervalConfig.value.showComments,
          showHours: intervalConfig.value.showHours,
          compress: intervalConfig.value.compress,
          includeSubstitucions: intervalConfig.value.includeSubstitucions
        }
      })
    }
  } catch (error) {
    console.error('Error desant preferències PDF:', error)
  }
}

const mostrarDialegPDF = async () => {
  // Pre-seleccionar tots els nivells disponibles
  pdfConfig.value.nivells = [...nivells.value]
  await carregarPreferenciesPdf()
  mostrarDialogPDF.value = true
}

const mostrarDialegInterval = async () => {
  // Pre-seleccionar tots els nivells i dates predeterminades
  intervalConfig.value.nivells = [...nivells.value]
  intervalConfig.value.dataInici = props.dataGlobal
  intervalConfig.value.dataFinal = props.dataGlobal
  await carregarPreferenciesPdf()
  mostrarDialogInterval.value = true
}

const generarPDF = async () => {
  generantPDF.value = true
  try {
    const validacioResponse = await axios.get(`/api/pdf/${dataISO.value}/validacions`)
    validacionsVig.value = validacioResponse.data

    if (totalVigFiltrats.value > 0) {
      mostrarDialogPDF.value = false
      mostrarDialogValidacionsVig.value = true
      generantPDF.value = false
      return
    }

    await _baixarPDFVigilancies()
  } catch (err) {
    console.error('Error validant PDF:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: err.response?.data?.detail || t('vigilancies.errors.generatePdf'),
      life: 5000
    })
    generantPDF.value = false
  }
}

const continuarPDFVig = async () => {
  await _baixarPDFVigilancies()
  mostrarDialogValidacionsVig.value = false
}

const cancelarPDFVig = () => {
  mostrarDialogValidacionsVig.value = false
  mostrarDialogPDF.value = true
  generantPDF.value = false
}

const _baixarPDFVigilancies = async () => {
  generantPDF.value = true
  try {
    const nivellsParam = pdfConfig.value.nivells.join(',')
    const params = new URLSearchParams({
      nivells: nivellsParam,
      show_comments: pdfConfig.value.showComments,
      show_hours: pdfConfig.value.showHours,
      compress: pdfConfig.value.compress,
      include_substitucions: pdfConfig.value.includeSubstitucions
    })

    const url = `/api/pdf/vigilancies/${dataISO.value}?${params.toString()}`
    const response = await axios.get(url, { responseType: 'blob' })

    const blob = new Blob([response.data], { type: 'application/pdf' })
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `vigilancies_${dataISO.value}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)

    toast.add({
      severity: 'success',
      summary: t('vigilancies.messages.pdfGeneratedTitle'),
      detail: t('vigilancies.messages.pdfGeneratedDetail'),
      life: 3000
    })

    await desarPreferenciesPdf('vigilancies')
    mostrarDialogPDF.value = false
  } catch (err) {
    console.error('Error generant PDF:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: err.response?.data?.detail || t('vigilancies.errors.generatePdf'),
      life: 5000
    })
  } finally {
    generantPDF.value = false
  }
}

const generarPDFInterval = async () => {
  // Validar dates abans de començar
  if (!intervalConfig.value.dataInici || !intervalConfig.value.dataFinal) {
    toast.add({
      severity: 'warn',
      summary: t('vigilancies.errors.datesRequiredTitle'),
      detail: t('vigilancies.errors.datesRequired'),
      life: 3000
    })
    return
  }

  if (!intervalConfig.value.nivells || intervalConfig.value.nivells.length === 0) {
    toast.add({
      severity: 'warn',
      summary: t('vigilancies.errors.levelsRequiredTitle'),
      detail: t('vigilancies.errors.levelsRequired'),
      life: 3000
    })
    return
  }

  generantPDFInterval.value = true

  try {
    // Convertir dates a format YYYY-MM-DD
    const formatDate = (date) => {
      if (!date) return null
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    const dataInici = formatDate(intervalConfig.value.dataInici)
    const dataFinal = formatDate(intervalConfig.value.dataFinal)

    if (!dataInici || !dataFinal) {
      toast.add({
        severity: 'error',
        summary: t('vigilancies.errors.dateFormatTitle'),
        detail: t('vigilancies.errors.dateFormat'),
        life: 3000
      })
      return
    }
    const nivellsParam = intervalConfig.value.nivells.join(',')

    // Construir URL amb paràmetres
    const params = new URLSearchParams({
      data_inici: dataInici,
      data_final: dataFinal,
      nivells: nivellsParam,
      include_weekends: intervalConfig.value.includeWeekends,
      include_empty_days: intervalConfig.value.includeEmptyDays,
      show_comments: intervalConfig.value.showComments,
      show_hours: intervalConfig.value.showHours,
      compress: intervalConfig.value.compress,
      include_substitucions: intervalConfig.value.includeSubstitucions
    })

    const url = `/api/pdf/vigilancies/interval?${params.toString()}`

    // Descarregar PDF
    const response = await axios.get(url, {
      responseType: 'blob'
    })

    // Crear link temporal per descarregar
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `vigilancies_interval_${dataInici}_a_${dataFinal}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)

    toast.add({
      severity: 'success',
      summary: t('vigilancies.messages.pdfIntervalTitle'),
      detail: t('vigilancies.messages.pdfIntervalDetail'),
      life: 3000
    })

    await desarPreferenciesPdf('interval')

    mostrarDialogInterval.value = false
  } catch (err) {
    console.error('Error generant PDF interval:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: err.response?.data?.detail || t('vigilancies.errors.generatePdfInterval'),
      life: 5000
    })
  } finally {
    generantPDFInterval.value = false
  }
}

// Watch per canvis de data
watch(() => props.dataGlobal, async () => {
  await carregarVigilancies()
})

// Lifecycle
onMounted(async () => {
  await carregarConfig()
  await carregarVigilancies()
})
</script>

<style scoped>
.vigilancies-view {
  width: 100%;
}

.view-header {
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
}

.view-header h2 {
  font-size: 2rem;
  color: #1f2937;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: #6b7280;
  font-size: 0.95rem;
  margin-bottom: 0;
  line-height: 1.2;
}

.subtitle-row {
  display: flex;
  align-items: baseline;
  gap: 1rem;
  flex-wrap: wrap;
}

.day-stats {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: #6b7280;
  line-height: 1;
}

.day-badge {
  font-size: 0.8rem;
}

.day-stat-label {
  margin-right: 0.4rem;
  text-transform: lowercase;
}

.day-stat-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  color: #4b5563;
  text-decoration: none;
}

.day-stat-link:hover {
  color: #2563eb;
}

/* Toolbar */
.toolbar {
  background: white;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  display: flex;
  flex-wrap: wrap; /* Allow main groups to wrap */
  gap: 1rem;
  align-items: center; /* Align items vertically in the middle */
  justify-content: space-between;
}

.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex: 1 1 100%;
}

.export-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.main-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.filters {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  flex-grow: 1; /* Allow filters to take available space */
  justify-content: flex-end; /* Align filters to the right if space allows */
}

/* Stat Cards */
.stats {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 1rem; /* Add some space above stats when wrapped */
  width: 100%; /* Take full width when wrapped */
  justify-content: center; /* Center stats when they wrap */
}

.stat-card {
  background: var(--background-light);
  color: var(--text-color-primary);
  padding: 0.65rem 1.15rem; /* More generous padding */
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border: 1px solid var(--border-color);
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.stat-card.assignades {
  background: #d4edda;
  border-color: #c3e6cb;
  color: #155724;
}

.stat-card.pendents {
  background: #fff3cd;
  border-color: #ffeaa7;
  color: #856404;
}

.stat-label {
  font-size: 0.85rem; /* Slightly larger */
  font-weight: 500;
  opacity: 0.9;
}

.stat-value {
  font-size: 1.35rem; /* Slightly larger */
  font-weight: 700;
}

/* Loading i Error */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  text-align: center;
  gap: 1rem;
  color: var(--primary-color);
}

.error-message {
  margin: 2rem 0;
}


.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: #6b7280;
}

.empty-state i {
  margin-bottom: 1rem;
}

.empty-state p {
  font-size: 1.1rem;
  margin-bottom: 0.5rem;
}

/* Taula */
.vigilancies-table {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  overflow: hidden;
}

/* Forçar table-layout fixed per evitar recàlcul d'amplades */
:deep(.vigilancies-table .p-datatable-table) {
  table-layout: fixed !important;
  width: 100% !important;
  border-collapse: collapse !important;
}

:deep(.vigilancies-table .p-datatable-wrapper) {
  padding-bottom: 2.2rem;
}

/* Mida fixa per tots els dropdowns i inputs */
:deep(.p-inputtext-sm),
:deep(.p-dropdown),
:deep(.p-inputtext) {
  height: 2.2rem !important;
  min-height: 2.2rem !important;
  max-height: 2.2rem !important;
  font-size: 0.9rem !important;
}

:deep(.p-dropdown .p-dropdown-label) {
  padding: 0.4rem 0.5rem !important;
  line-height: 1.4rem;
  font-size: 0.9rem !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}

/* Truncar text en inputs */
:deep(.p-inputtext) {
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}

:deep(.p-dropdown .p-dropdown-trigger) {
  width: 1.5rem !important;
  min-width: 1.5rem !important;
}

@media (max-width: 768px) {
  .view-header h2 {
    font-size: 1.6rem;
  }

  .toolbar {
    padding: 0.75rem;
    gap: 0.75rem;
  }

  .main-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .main-actions :deep(.p-button) {
    flex: 1 1 160px;
    justify-content: center;
  }

  .filters {
    width: 100%;
    justify-content: flex-start;
  }

  .stats {
    margin-top: 0.5rem;
    gap: 0.5rem;
  }

  .stat-card {
    flex: 1 1 140px;
  }

  :deep(.p-datatable-wrapper) {
    padding-bottom: 1.5rem;
  }

  :deep(.p-datatable .p-datatable-thead > tr > th),
  :deep(.p-datatable .p-datatable-tbody > tr > td) {
    padding: 0.65rem 0.5rem;
  }
}

@media (max-width: 520px) {
  .main-actions :deep(.p-button) {
    flex: 1 1 100%;
  }

  .filters :deep(.p-dropdown) {
    width: 100% !important;
  }

  .stat-card {
    flex: 1 1 100%;
  }
}

/* Botó clear (X) més petit i compacte - ocult per defecte, visible en hover */
:deep(.p-dropdown .p-dropdown-clear-icon) {
  width: 0.9rem !important;
  height: 0.9rem !important;
  font-size: 0.65rem !important;
  opacity: 0.4;
  transition: opacity 0.2s;
}

:deep(.p-dropdown:hover .p-dropdown-clear-icon) {
  opacity: 1;
}

:deep(.p-inputtext .p-inputtext-clear-icon) {
  width: 0.9rem !important;
  height: 0.9rem !important;
  font-size: 0.65rem !important;
  opacity: 0.4;
  transition: opacity 0.2s;
}

:deep(.p-inputtext:hover .p-inputtext-clear-icon) {
  opacity: 1;
}

:deep(.p-inputtext) {
  padding: 0.4rem 0.6rem !important;
}

/* Centrar contingut verticalment i evitar overflow (EXCEPTE per row actions) */
:deep(.vigilancies-table .p-datatable-tbody > tr > td) {
  vertical-align: middle;
  padding: 0.4rem 0.5rem;
  overflow: visible !important; /* Canviat a visible per permetre botons fora */
  position: static;
}

:deep(.vigilancies-table .p-datatable-tbody > tr) {
  position: relative;
}

:deep(.vigilancies-table .p-datatable-thead > tr > th) {
  overflow: hidden !important;
  padding: 0.35rem 0.5rem !important;
}

/* Forçar amplades de columnes */
/* Checkbox selecció - 2.5rem */
:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(1)),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(1)) {
  width: 2.5rem !important;
  min-width: 2.5rem !important;
  max-width: 2.5rem !important;
  padding: 0.35rem 0.3rem !important;
  text-align: center !important;
}

:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(1)) {
  display: table-cell !important;
  justify-content: center !important;
}

:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(1) .p-checkbox) {
  display: block !important;
  margin: 0 auto !important;
}

/* Hora - 75px */
:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(2)),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(2)) {
  width: 75px !important;
  min-width: 75px !important;
  max-width: 75px !important;
  padding: 0.35rem 0.3rem !important;
}

/* Tag blau d'hora que ocupi tot l'ample */
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(2) .p-dropdown) {
  width: 100% !important;
}

:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(2) .p-dropdown .p-dropdown-label) {
  padding: 0 !important;
  margin: 0 !important;
}

:deep(.hora-dropdown.p-dropdown) {
  height: auto !important;
  min-height: 0 !important;
  max-height: none !important;
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
  width: 100% !important;
}

:deep(.hora-dropdown .p-dropdown-label) {
  display: flex !important;
  align-items: center !important;
  padding: 0 !important;
}

:deep(.hora-dropdown .p-dropdown-trigger) {
  background: transparent !important;
  border: none !important;
  width: 1.5rem !important;
  min-width: 1.5rem !important;
  padding: 0 !important;
  margin-left: 0 !important;
}

:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(2) .p-tag) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0 !important;
  width: 100% !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}

/* Nivell - 90px */
:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(3)),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(3)) {
  width: 90px !important;
  min-width: 90px !important;
  max-width: 90px !important;
}

:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(3) .p-dropdown) {
  width: 100% !important;
}

:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(4) .p-dropdown) {
  width: 100% !important;
}

:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(5) .p-dropdown),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(6) .p-dropdown),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(7) .p-dropdown) {
  width: 100% !important;
}

:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(8) .p-inputtext) {
  width: 100% !important;
}

/* Tipus - 110px */
:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(4)),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(4)) {
  width: 110px !important;
  min-width: 110px !important;
  max-width: 110px !important;
}

/* Grups - 90px */
:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(5)),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(5)) {
  width: 90px !important;
  min-width: 90px !important;
  max-width: 90px !important;
}

/* Aula - 90px */
:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(6)),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(6)) {
  width: 90px !important;
  min-width: 90px !important;
  max-width: 90px !important;
}

/* Vigilant - 240px */
:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(7)),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(7)) {
  width: 240px !important;
  min-width: 240px !important;
  max-width: 240px !important;
}

/* Comentaris - 240px */
:deep(.vigilancies-table .p-datatable-thead > tr > th:nth-child(8)),
:deep(.vigilancies-table .p-datatable-tbody > tr > td:nth-child(8)) {
  width: 240px !important;
  min-width: 240px !important;
  max-width: 240px !important;
}

/* Separadors d'hora */
:deep(.hora-separador) {
  border-top: 2px solid #e5e7eb !important;
}

:deep(.primera-hora) {
  /* Sense border a la primera fila */
}

/* Diàleg */
.field {
  margin-bottom: 1rem;
}

.field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}

/* Professor option amb colors */
.professor-option {
  cursor: pointer;
  transition: all 0.2s ease;
  border-left: 3px solid rgba(0, 0, 0, 0.1);
}

.professor-option:hover {
  filter: brightness(0.95);
}

/* Cell wrapper relative per posicionament */
.cell-wrapper-relative {
  position: static;
  width: 100%;
}

/* Row hover actions - apareixen a baix de la fila, centrats i discrets */
.row-hover-actions {
  position: absolute !important;
  bottom: -1.1rem !important; /* A sota de la fila (una mica més amunt) */
  left: 50% !important;
  transform: translateX(-50%) !important;
  display: flex !important;
  gap: 0.4rem !important;
  opacity: 0 !important;
  pointer-events: none !important;
  transition: opacity 0.2s ease !important;
  z-index: 100 !important;
  background: white !important;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
  padding: 0.2rem !important;
  border-radius: 20px !important;
  border: 1px solid #e5e7eb !important;
}

.row-hover-actions .action-btn {
  width: auto !important;
  height: 1.25rem !important;
  padding: 0 0.5rem !important;
  min-width: 0 !important;
  border-radius: 6px !important;
  font-size: 0.7rem !important;
}

.row-hover-actions .subtle-action {
  background: #f8fafc !important;
  border: 1px solid #e5e7eb !important;
  color: #6b7280 !important;
  box-shadow: none !important;
}

.row-hover-actions .subtle-action:hover {
  background: #eef2f7 !important;
  border-color: #d1d5db !important;
}

.row-hover-actions .action-btn .p-button-icon {
  font-size: 0.5rem !important;
  opacity: 0.55;
  margin-right: 0.25rem;
}

/* Mostrar botons quan passa el ratolí per la fila */
:deep(tr:hover .row-hover-actions) {
  opacity: 0.6 !important;
  pointer-events: auto !important;
}

/* Responsive */
@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .stats {
    justify-content: center;
  }
}
</style>
