<template>
  <div class="substitucions-view">
    <div class="view-header">
      <h2>{{ $t('substitutions.title') }}</h2>
      <div class="subtitle-row">
        <p class="subtitle">{{ dataFormatada }}</p>
        <div class="day-stats">
          <Badge :value="substitucionsFiltrades.length" severity="info" class="day-badge" />
          <span class="day-stat-label">{{ $t('substitutions.stats.substitutionsLabel') }}</span>
          <a class="day-stat-link" @click="anarAVigilancies">
            <Badge :value="vigilanciesCount" severity="success" class="day-badge" />
            <span class="day-stat-label">{{ $t('substitutions.stats.vigilanciesLabel') }}</span>
          </a>
        </div>
      </div>
    </div>

    <div class="toolbar">
      <div class="actions">
        <Button
          :label="$t('substitutions.actions.generatePending')"
          icon="pi pi-bolt"
          @click="generarPendents"
          :loading="loading"
          class="p-button-success"
          v-tooltip.bottom="$t('substitutions.actions.generatePendingHint')"
        />
        <Button
          :label="$t('substitutions.actions.regenerateAll')"
          icon="pi pi-refresh"
          @click="regenerarTot"
          :loading="loading"
          class="p-button-warning"
          v-tooltip.bottom="$t('substitutions.actions.regenerateAllHint')"
        />
        <Button
          :label="$t('common.new')"
          icon="pi pi-plus"
          @click="obrirDialogNou"
          class="p-button-primary"
        />
        <Button
          :label="$t('substitutions.actions.savePdf')"
          icon="pi pi-file-pdf"
          @click="mostrarDialegPDF"
          class="p-button-success"
          outlined
          v-tooltip.bottom="$t('substitutions.actions.savePdfHint')"
        />
      </div>

      <div class="stats" v-if="substitucionsFiltrades.length > 0">
        <div class="stat-card">
          <span class="stat-value">{{ substitucionsFiltrades.length }}</span>
          <span class="stat-label">{{ $t('common.total') }}</span>
        </div>
        <div class="stat-card assignades">
          <span class="stat-value">{{ substitucionsAssignades }}</span>
          <span class="stat-label">{{ $t('substitutions.stats.assigned') }}</span>
        </div>
        <div class="stat-card pendents">
          <span class="stat-value">{{ substitucionsPendents }}</span>
          <span class="stat-label">{{ $t('substitutions.stats.pending') }}</span>
        </div>
      </div>
    </div>

    <div class="content-card">
      <DataTable
        :value="substitucionsFiltrades"
        :loading="loading"
        stripedRows
        :paginator="true"
        :rows="20"
        :rowsPerPageOptions="[10, 20, 50]"
        responsiveLayout="scroll"
        :rowClass="getRowClass"
        class="substitucions-table"
      >
        <template #empty>
          <div class="empty-state">
            <i class="pi pi-inbox" style="font-size: 3rem; color: #ccc;"></i>
            <p>{{ $t('substitutions.empty.title') }}</p>
            <small>{{ $t('substitutions.empty.hint') }}</small>
          </div>
        </template>

        <Column field="hora" :header="$t('common.hour')" style="width: 110px;">
          <template #body="slotProps">
            <Tag
              :value="slotProps.data.hora"
              :style="{
                backgroundColor: 'var(--primary-color)',
                color: 'white',
                fontSize: '0.95rem',
                fontWeight: '600',
                padding: '0.4rem 0.8rem'
              }"
            />
          </template>
        </Column>

        <Column field="professor_absent" :header="$t('substitutions.columns.absentTeacher')" :sortable="true" style="width: 220px;">
          <template #body="slotProps">
            <span style="font-weight: 500; color: #2c3e50;">{{ slotProps.data.professor_absent }}</span>
          </template>
        </Column>

        <Column field="assignatura" :header="$t('common.subject')" :sortable="true" style="width: 200px;">
          <template #body="slotProps">
            <span style="color: #495057;">{{ slotProps.data.assignatura }}</span>
          </template>
        </Column>

        <Column field="grup" :header="$t('common.group')" :sortable="true" style="width: 140px;">
          <template #body="slotProps">
            <div class="cell-wrapper-relative">
              <span style="font-weight: 500; color: #6c757d;">{{ slotProps.data.grup }}</span>
              <div class="row-hover-actions">
                <Button
                  icon="pi pi-pencil"
                  :label="$t('common.edit')"
                  class="p-button-secondary p-button-sm action-btn subtle-action"
                  @click.stop="editarAbsenciesProfessor(slotProps.data)"
                  v-tooltip.top="$t('substitutions.actions.manageAbsences')"
                />
                <Button
                  icon="pi pi-trash"
                  :label="$t('common.delete')"
                  class="p-button-secondary p-button-sm action-btn subtle-action"
                  @click.stop="confirmarEliminarAbsenciesProf(slotProps.data.professor_absent)"
                  v-tooltip.top="$t('substitutions.actions.deleteRow')"
                />
              </div>
            </div>
          </template>
        </Column>

        <Column field="substitut" :header="$t('substitutions.columns.substitute')" style="min-width: 250px;">
          <template #body="rowProps">
            <Dropdown
              v-model="rowProps.data.substitut"
              :options="formatDisponibles(rowProps.data.disponibles, rowProps.data.substitut)"
              optionLabel="label"
              optionValue="value"
              :placeholder="$t('substitutions.columns.pickSubstitute')"
              :filter="true"
              @change="actualitzarSubstitut(rowProps.data, $event)"
              class="w-full"
            >
              <template #value="slotProps">
                <span
                  v-if="slotProps.value"
                  :style="esSubstitutAbsentAquestHora(rowProps.data.hora, slotProps.value)
                    ? { backgroundColor: '#fff3cd', padding: '2px 6px', borderRadius: '4px', fontWeight: '600' }
                    : {}"
                >{{ slotProps.value }}</span>
                <span v-else class="p-placeholder">{{ $t('substitutions.columns.pickSubstitute') }}</span>
              </template>
              <template #option="slotProps">
                <div
                  class="disponible-option"
                  :style="{ backgroundColor: slotProps.option.color }"
                >
                  {{ slotProps.option.label }}
                </div>
              </template>
            </Dropdown>
          </template>
        </Column>

        <Column field="comentaris" :header="$t('common.comments')" style="min-width: 200px;">
          <template #body="slotProps">
            <InputText
              :id="'comentaris-' + slotProps.data.id"
              v-model="slotProps.data.comentaris"
              @change="actualitzarComentari(slotProps.data)"
              class="p-inputtext-sm"
              style="width: 100%;"
              :placeholder="$t('common.commentsPlaceholder')"
              autocomplete="new-password"
              autocapitalize="off"
              spellcheck="false"
              data-lpignore="true"
              data-form-type="other"
              readonly
              @focus="$event.target.removeAttribute('readonly')"
            />
          </template>
        </Column>

        <Column field="estat" :header="$t('common.status')" style="width: 180px;">
          <template #body="slotProps">
            <Tag
              :value="slotProps.data.estat === 'assignada' ? $t('substitutions.status.assigned') : $t('substitutions.status.pending')"
              :style="{
                backgroundColor: slotProps.data.estat === 'assignada' ? '#d4edda' : '#fff3cd',
                color: slotProps.data.estat === 'assignada' ? '#155724' : '#856404',
                border: slotProps.data.estat === 'assignada' ? '1px solid #c3e6cb' : '1px solid #ffeaa7',
                fontSize: '0.875rem',
                fontWeight: '500',
                padding: '0.35rem 0.7rem'
              }"
            />
          </template>
        </Column>

      </DataTable>
    </div>

    <!-- Bottom Sheet per gestionar absències -->
    <Teleport to="body">
      <Transition name="bs-overlay">
        <div v-if="mostrarDialogGestio" class="bs-overlay" @click="tancarDialogGestio"></div>
      </Transition>
      <div class="bs-sheet" :class="{ 'bs-sheet--visible': mostrarDialogGestio }" role="dialog" aria-modal="true">
        <div class="bs-drag-handle"></div>
        <div class="bs-header">
          <span class="p-dialog-title">{{ $t('substitutions.dialogs.absences.title') }}</span>
          <button ref="closeBtnRef" class="bs-close-btn" @click="tancarDialogGestio" :aria-label="$t('common.close')">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="bs-content">
          <!-- Professor selector -->
          <div class="bs-field">
            <label class="bs-label">{{ $t('substitutions.dialogs.absences.absentTeacherLabel') }}</label>
            <Dropdown
              v-model="dropdownProfValue"
              :options="professorsAmbInfo"
              optionLabel="nom"
              :filter="true"
              :placeholder="$t('substitutions.dialogs.absences.selectTeacher')"
              @change="seleccionarProfessorDropdown"
              class="w-full"
            >
              <template #value="{ value, placeholder }">
                {{ value ? value.nom : placeholder }}
              </template>
              <template #option="{ option }">
                <div class="bs-prof-option" :class="{ 'bs-prof-option--absencies': option.teAbsencies }">
                  <span>{{ option.nom }}</span>
                  <span v-if="option.teAbsencies" class="bs-badge-hores">{{ option.numHores }}h</span>
                </div>
              </template>
            </Dropdown>
          </div>

          <!-- Rang de dates -->
          <div class="bs-field bs-field--rang" v-if="gestioAbsencies.professor">
            <div class="bs-rang-toggle">
              <button type="button"
                :class="['bs-rang-opt', !modeRang && 'bs-rang-opt--active']"
                @click="modeRang = false; dataFinalRang = ''">
                {{ $t('substitutions.range.onlyToday') }}
              </button>
              <button type="button"
                :class="['bs-rang-opt', modeRang && 'bs-rang-opt--active']"
                @click="modeRang = true">
                {{ $t('substitutions.range.until') }}
              </button>
            </div>
            <div v-if="modeRang" class="bs-rang-dates">
              <span class="bs-rang-inici">{{ dataISOCurta }}</span>
              <span class="bs-rang-arrow">→</span>
              <input type="date" class="bs-input bs-rang-fi"
                v-model="dataFinalRang" :min="dataISO" />
            </div>
            <div v-if="modeRang && datesDelRang.length > 1" class="bs-rang-resum">
              {{ $t('substitutions.range.summary', { count: datesDelRang.length }) }}
            </div>
          </div>

          <!-- Hores d'absència Normal -->
          <div class="bs-field">
            <div class="bs-label-row">
              <label class="bs-label">{{ $t('substitutions.dialogs.absences.normalHoursLabel') }} <span class="bs-type-badge bs-type-badge--normal">{{ $t('substitutions.dialogs.absences.normalBadge') }}</span></label>
              <button type="button" class="bs-sel-all-btn" @click="toggleTotesAbsencia">{{ totesTrnadesAbsencia ? $t('substitutions.dialogs.absences.selectNone') : $t('substitutions.dialogs.absences.selectAll') }}</button>
            </div>
            <div class="bs-hours-grid">
              <button
                v-for="hora in horesDisponibles"
                :key="`abs-${hora}`"
                type="button"
                class="bs-hour-btn"
                :class="{
                  'bs-hour-btn--selected': gestioAbsencies.horesAbsencia.includes(hora),
                  'bs-hour-btn--al-centre': horesCarregades && !horesAmbClasse.includes(hora) && horesAlCentre.includes(hora),
                  'bs-hour-btn--fora': horesCarregades && !horesAmbClasse.includes(hora) && !horesAlCentre.includes(hora)
                }"
                :disabled="gestioAbsencies.horesServei.includes(hora)"
                @click="toggleHoraAbsencia(hora)"
              >{{ hora }}</button>
            </div>
          </div>

          <!-- Hores de Servei -->
          <div class="bs-field">
            <div class="bs-label-row">
              <label class="bs-label">{{ $t('substitutions.dialogs.absences.serviceHoursLabel') }} <span class="bs-type-badge bs-type-badge--servei">{{ $t('substitutions.dialogs.absences.serviceBadge') }}</span></label>
              <button type="button" class="bs-sel-all-btn bs-sel-all-btn--servei" @click="toggleTotesServei">{{ totesTrnadesServei ? $t('substitutions.dialogs.absences.selectNone') : $t('substitutions.dialogs.absences.selectAll') }}</button>
            </div>
            <div class="bs-hours-grid">
              <button
                v-for="hora in horesDisponibles"
                :key="`serv-${hora}`"
                type="button"
                class="bs-hour-btn bs-hour-btn--servei-base"
                :class="{
                  'bs-hour-btn--servei-selected': gestioAbsencies.horesServei.includes(hora),
                  'bs-hour-btn--al-centre': horesCarregades && !horesAmbClasse.includes(hora) && horesAlCentre.includes(hora),
                  'bs-hour-btn--fora': horesCarregades && !horesAmbClasse.includes(hora) && !horesAlCentre.includes(hora)
                }"
                :disabled="gestioAbsencies.horesAbsencia.includes(hora)"
                @click="toggleHoraServei(hora)"
              >{{ hora }}</button>
            </div>
          </div>

          <!-- Llista absències del dia -->
          <div v-if="absenciesDelDiaAgrupades.length > 0" class="bs-absencies-section">
            <p class="bs-section-title">{{ $t('substitutions.dialogs.absences.todayAbsences') }}</p>
            <div
              v-for="grup in absenciesDelDiaAgrupades"
              :key="grup.professor"
              class="bs-card bs-card--clickable"
              @click="editarAbsenciesProfessor({ professor_absent: grup.professor })"
            >
              <span class="bs-card-prof">{{ grup.professor }}</span>
              <button class="bs-card-del" @click.stop="confirmarEliminarAbsenciesProf(grup.professor)"
                :disabled="loading" :aria-label="$t('common.delete')">🗑</button>
            </div>
          </div>
        </div>

        <div class="bs-footer">
          <button
            type="button"
            class="bs-btn-primary"
            :disabled="!gestioAbsencies.professor || (gestioAbsencies.horesAbsencia.length === 0 && gestioAbsencies.horesServei.length === 0) || loading"
            @click="afegirAbsenciaImmediata"
          >
            <span v-if="loading" class="bs-spinner"></span>
            <span v-else>{{ $t('substitutions.dialogs.absences.addAbsence') }}</span>
          </button>
        </div>
      </div>
    </Teleport>

    <!-- Diàleg de confirmació per eliminar -->
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

    <!-- Diàleg personalitzat per mostrar validacions PDF -->
    <Dialog
      v-model:visible="mostrarDialogValidacions"
      :header="validacions.has_critical ? $t('substitutions.dialogs.pdfValidation.criticalTitle') : $t('substitutions.dialogs.pdfValidation.warningTitle')"
      :modal="true"
      :style="{ width: '600px', maxHeight: '80vh' }"
    >
      <div class="validacions-content">
        <p style="font-weight: 600; margin-bottom: 1rem;">{{ $t('substitutions.dialogs.pdfValidation.detectedIssues') }}</p>

        <div v-if="validacions.conflicts && validacions.conflicts.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #d32f2f; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.critical') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(conflict, idx) in validacions.conflicts.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">
              {{ conflict }}
            </li>
          </ul>
          <p v-if="validacions.conflicts.length > 10" style="margin-top: 0.5rem; font-style: italic; color: #666;">
            {{ $t('common.moreItems', { count: validacions.conflicts.length - 10 }) }}
          </p>
        </div>

        <div v-if="warningsFiltrats.length > 0" style="margin-bottom: 1.5rem;">
          <p style="font-weight: 600; color: #f57c00; margin-bottom: 0.5rem;">{{ $t('substitutions.dialogs.pdfValidation.warnings') }}</p>
          <ul style="margin: 0; padding-left: 1.5rem;">
            <li v-for="(warning, idx) in warningsFiltrats.slice(0, 10)" :key="idx" style="margin-bottom: 0.25rem;">
              {{ warning }}
            </li>
          </ul>
          <p v-if="warningsFiltrats.length > 10" style="margin-top: 0.5rem; font-style: italic; color: #666;">
            {{ $t('common.moreItems', { count: warningsFiltrats.length - 10 }) }}
          </p>
        </div>

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

        <p style="font-weight: 600; margin-top: 1rem;">
          {{ $t('substitutions.dialogs.pdfValidation.totalIssues', { count: totalIssuesFiltrats }) }}
        </p>

        <Message severity="warn" style="margin-top: 1rem;">
          {{ $t('substitutions.dialogs.pdfValidation.continueQuestion') }}
        </Message>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          icon="pi pi-times"
          @click="cancelarPDF"
          class="p-button-text"
        />
        <Button
          :label="$t('substitutions.dialogs.pdfValidation.reassign')"
          icon="pi pi-refresh"
          @click="reassignarProblematics"
          :loading="reassignantProblematics"
          class="p-button-secondary"
        />
        <Button
          :label="$t('common.continue')"
          icon="pi pi-check"
          @click="continuarPDF"
          :loading="generantPDF"
          :class="validacions.has_critical ? 'p-button-danger' : 'p-button-warning'"
        />
      </template>
    </Dialog>

    <!-- Diàleg per exportar PDF -->
    <Dialog
      v-model:visible="mostrarDialogPDF"
      :header="$t('substitutions.dialogs.pdf.title')"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('substitutions.dialogs.pdf.includeContent') }}</label>
          <div class="flex flex-column gap-3">
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.includeSubstitutions" inputId="includeSubstitutions" :binary="true" />
              <label for="includeSubstitutions" class="ml-2">{{ $t('substitutions.dialogs.pdf.substitutions') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.includeVigilancies" inputId="includeVigilancies" :binary="true" />
              <label for="includeVigilancies" class="ml-2">{{ $t('substitutions.dialogs.pdf.vigilancies') }}</label>
            </div>
          </div>
        </div>

        <div class="field mt-3">
          <label>{{ $t('substitutions.dialogs.pdf.options') }}</label>
          <div class="flex flex-column gap-3">
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.showComments" inputId="showCommentsSubs" :binary="true" />
              <label for="showCommentsSubs" class="ml-2">{{ $t('substitutions.dialogs.pdf.showComments') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.showHours" inputId="showHoursSubs" :binary="true" />
              <label for="showHoursSubs" class="ml-2">{{ $t('substitutions.dialogs.pdf.showHours') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.showConflicts" inputId="showConflictsSubs" :binary="true" />
              <label for="showConflictsSubs" class="ml-2">{{ $t('substitutions.dialogs.pdf.showConflicts') }}</label>
            </div>
            <div class="flex align-items-center">
              <Checkbox v-model="pdfConfig.compress" inputId="compressSubs" :binary="true" />
              <label for="compressSubs" class="ml-2">{{ $t('substitutions.dialogs.pdf.compress') }}</label>
            </div>
          </div>
        </div>

        <Message v-if="!pdfConfig.includeSubstitutions && !pdfConfig.includeVigilancies" severity="warn" class="mt-3">
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
          @click="generarPDFComplet"
          :loading="generantPDF"
          :disabled="!pdfConfig.includeSubstitutions && !pdfConfig.includeVigilancies"
          class="p-button-success"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

// Components PrimeVue
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Calendar from 'primevue/calendar'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import InputText from 'primevue/inputtext'
import Checkbox from 'primevue/checkbox'
import Tag from 'primevue/tag'
import Badge from 'primevue/badge'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import ConflicteDialog from '../components/ConflicteDialog.vue'

const toast = useToast()
const confirm = useConfirm()
const { t, locale } = useI18n()
const emit = defineEmits(['anar-vigilancies'])

// Props
const props = defineProps({
  dataGlobal: {
    type: Date,
    required: true
  }
})

// State
const substitucions = ref([])
const substitucionsFiltrades = ref([])
const totesAbsencies = ref([]) // TOTES les absències (amb i sense grup) per detectar professors absents
const vigilanciesCount = ref(0)
const professors = ref([])
const horesDisponibles = ref([])
const noSubstituir = ref([])
const xmlMissingNotified = ref(false)
const loading = ref(false)
const mostrarDialogGestio = ref(false)
const closeBtnRef = ref(null)
watch(mostrarDialogGestio, (val) => {
  if (val) nextTick(() => closeBtnRef.value?.focus())
})
const dropdownProfValue = ref(null)
const gestioAbsencies = ref({
  professor: null,
  professorSearch: '',
  horesAbsencia: [],
  horesServei: []
})
const horesAmbClasse = ref([])
const horesAlCentre = ref([])
const horesCarregades = ref(false)
const modeRang = ref(false)
const dataFinalRang = ref('')
const mostrarDialogConflicte = ref(false)
const conflicteOverwrite = ref(null)

// PDF export
const mostrarDialogPDF = ref(false)
const mostrarDialogValidacions = ref(false)
const generantPDF = ref(false)
const reassignantProblematics = ref(false)
const reassignChanges = ref([])
const validacions = ref({
  conflicts: [],
  warnings: [],
  total: 0,
  has_critical: false
})

const warningsFiltrats = computed(() => {
  const warnings = validacions.value.warnings || []
  return warnings.filter((warning) => {
    const text = (warning || '').trim().toLowerCase()
    if (!text.startsWith('⚠️')) return true
    return !(text.includes('prioritat') || text.includes('prioridad') || text.includes('priority'))
  })
})

const totalIssuesFiltrats = computed(() => {
  const conflicts = validacions.value.conflicts || []
  return conflicts.length + warningsFiltrats.value.length
})
const pdfConfig = ref({
  includeSubstitutions: true,
  includeVigilancies: true,
  showComments: true,
  showHours: false,
  showConflicts: true,
  compress: false
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

const dataISOCurta = computed(() =>
  props.dataGlobal.toLocaleDateString(locale.value || 'ca-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric'
  })
)

const collator = computed(() => new Intl.Collator(locale.value || 'ca', { sensitivity: 'base' }))

const substitucionsAssignades = computed(() =>
  substitucionsFiltrades.value.filter(s => s.substitut).length
)

const substitucionsPendents = computed(() =>
  substitucionsFiltrades.value.filter(s => !s.substitut).length
)

const professorsAmbInfo = computed(() => {
  // Detectar quins professors tenen absències REALS (excloent vigilàncies tècniques i forats)
  const absenciesReals = totesAbsencies.value.filter(sub => {
    const tipus = (sub.tipus_absencia || "").toUpperCase();
    return !["VIGILANCIA", "VIGILÀNCIA", "ENCADENADA"].includes(tipus);
  });

  const professorsAmbAbsencies = new Set(
    absenciesReals.map(sub => sub.professor_absent)
  );

  return professors.value.map(prof => ({
    nom: prof,
    teAbsencies: professorsAmbAbsencies.has(prof),
    numHores: absenciesReals.filter(sub => sub.professor_absent === prof).length
  }))
})

const professorsAbsentsAvui = computed(() =>
  new Set(totesAbsencies.value.map(s => s.professor_absent).filter(Boolean))
)

const esSubstitutAbsentAquestHora = (hora, nomSubstitut) => {
  if (!nomSubstitut) return false
  return totesAbsencies.value.some(a => a.hora === hora && a.professor_absent === nomSubstitut)
}

// Detecta si una sub és Tipus A VIGILANCIA_ABSENT (vigilant absent → slot descobert)
const esVigilanciaAbsent = (sub) => (sub.tipus_absencia || '').toUpperCase() === 'VIGILANCIA_ABSENT'

const absenciesDelDia = computed(() => {
  return totesAbsencies.value
    .filter(a => {
      const tipus = (a.tipus_absencia || '').toUpperCase()
      if (tipus === 'ENCADENADA') return false
      if (tipus === 'VIGILANCIA') return esVigilanciaAbsent(a) // Inclou Tipus A, exclou Tipus B
      return true
    })
    .sort((a, b) => {
      const ia = horesDisponibles.value.indexOf(a.hora)
      const ib = horesDisponibles.value.indexOf(b.hora)
      if (ia !== ib) return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
      return (a.professor_absent || '').localeCompare(b.professor_absent || '')
    })
})

const absenciesDelDiaAgrupades = computed(() => {
  const grups = {}
  for (const abs of absenciesDelDia.value) {
    const prof = abs.professor_absent
    if (!grups[prof]) grups[prof] = { professor: prof, horesAbsencia: [], horesServei: [] }
    const tipus = (abs.tipus_absencia || '').toUpperCase()
    if (tipus === 'SERVEI') grups[prof].horesServei.push(abs.hora)
    else grups[prof].horesAbsencia.push(abs.hora)
  }
  return Object.values(grups).sort((a, b) => a.professor.localeCompare(b.professor))
})

const seleccionarProfessorDropdown = (event) => {
  if (event.value) {
    seleccionarProfessor(event.value)
  }
}

const datesDelRang = computed(() => {
  if (!modeRang.value || !dataFinalRang.value) return [dataISO.value]
  const isoLocal = (d) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }
  const dates = []
  const fi = new Date(dataFinalRang.value + 'T00:00:00')
  let actual = new Date(dataISO.value + 'T00:00:00')
  while (actual <= fi) {
    const dow = actual.getDay()
    if (dow !== 0 && dow !== 6) dates.push(isoLocal(actual))
    actual.setDate(actual.getDate() + 1)
  }
  return dates.length > 0 ? dates : [dataISO.value]
})

// Mètodes
const carregarSubstitucions = async () => {
  loading.value = true
  try {
    // Carregar en paral·lel: substitucions (filtrades) i totes les absències
    const [responseFiltrades, responseTotes] = await Promise.all([
      axios.get(`/api/substitucions/${dataISO.value}`),
      axios.get(`/api/substitucions/${dataISO.value}?include_all=true`)
    ])

    substitucions.value = responseFiltrades.data
    totesAbsencies.value = responseTotes.data
    await carregarVigilanciesCount()

    // Filtrar activitats que no necessiten substitució
    substitucionsFiltrades.value = substitucions.value.filter(sub => {
      // Si assignatura és buida o és al llistat de no_substituir, no mostrar
      const assignatura = sub.assignatura || ''
      return !noSubstituir.value.includes(assignatura)
    })

    // Carregar disponibles per cada hora
    await carregarDisponiblesPerHores()
  } catch (error) {
    console.error('Error carregant substitucions:', error)
    if (error.response?.data?.xml_missing && !xmlMissingNotified.value) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('common.xmlMissing'),
        life: 4000
      })
      xmlMissingNotified.value = true
    }
    substitucions.value = []
    substitucionsFiltrades.value = []
    totesAbsencies.value = []
    vigilanciesCount.value = 0
  } finally {
    loading.value = false
  }
}

// Nova funció per carregar TOTES les absències (incloses les sense grup: VP, Guàrdia, etc.)
// Útil per editar absències i veure totes les hores marcades
const carregarTotesAbsencies = async () => {
  // Si ja estan carregades (de carregarSubstitucions), retornar-les
  if (totesAbsencies.value.length > 0) {
    return totesAbsencies.value
  }

  // Sinó, carregar-les
  try {
    const response = await axios.get(`/api/substitucions/${dataISO.value}?include_all=true`)
    totesAbsencies.value = response.data
    return response.data
  } catch (error) {
    console.error('Error carregant totes les absències:', error)
    return []
  }
}

const carregarDisponiblesPerHores = async () => {
  const data = dataISO.value

  // Obtenir hores úniques
  const horesUniques = [...new Set(substitucionsFiltrades.value.map(s => s.hora))]

  // Carregar disponibles per cada hora
  for (const hora of horesUniques) {
    try {
      const response = await axios.get(`/api/substitucions/${data}/${hora}/disponibles`)
      const disponibles = response.data.disponibles || []

      // Afegir disponibles a cada substitució d'aquesta hora
      substitucionsFiltrades.value.forEach(sub => {
        if (sub.hora === hora) {
          sub.disponibles = disponibles
        }
      })
    } catch (error) {
      console.error(`Error carregant disponibles per hora ${hora}:`, error)
    }
  }
}

const carregarVigilanciesCount = async () => {
  try {
    const response = await axios.get(`/api/vigilancies/${dataISO.value}`)
    vigilanciesCount.value = Array.isArray(response.data) ? response.data.length : 0
  } catch (error) {
    console.error('Error carregant vigilàncies:', error)
    vigilanciesCount.value = 0
  }
}

const anarAVigilancies = () => {
  emit('anar-vigilancies')
}

const carregarProfessors = async () => {
  try {
    const response = await axios.get('/api/professors')
    if (response.data?.xml_missing && !xmlMissingNotified.value) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('common.xmlMissing'),
        life: 4000
      })
      xmlMissingNotified.value = true
    }
    const llista = response.data.professors || []
    professors.value = [...llista].sort((a, b) => collator.value.compare(a, b))
  } catch (error) {
    console.error('Error carregant professors:', error)
  }
}

const carregarNoSubstituir = async () => {
  try {
    const response = await axios.get('/api/config/no-substituir')
    noSubstituir.value = response.data.no_substituir
    console.log('📋 Activitats que no necessiten substitució:', noSubstituir.value)
  } catch (error) {
    console.error('Error carregant no_substituir:', error)
  }
}

const obrirDialogConflicte = (overwriteAction) => {
  conflicteOverwrite.value = overwriteAction
  mostrarDialogConflicte.value = true
}

const gestionarConflicte = async () => {
  await carregarSubstitucions()
}

const executarOverwrite = async () => {
  if (conflicteOverwrite.value) {
    await conflicteOverwrite.value()
  }
}

const carregarHores = async () => {
  try {
    const response = await axios.get('/api/hores')
    if (response.data?.xml_missing && !xmlMissingNotified.value) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('common.xmlMissing'),
        life: 4000
      })
      xmlMissingNotified.value = true
    }
    horesDisponibles.value = response.data.hores
  } catch (error) {
    console.error('Error carregant hores:', error)
  }
}

const mostrarResultatGeneracio = (data, summary = null) => {
  const { message, pendents, pendents_detall } = data
  const summaryText = summary ?? t('common.generated')
  toast.add({
    severity: pendents > 0 ? 'warn' : 'success',
    summary: summaryText,
    detail: message,
    life: pendents > 0 ? 8000 : 3000
  })
  if (pendents > 0 && pendents_detall?.length) {
    const lines = pendents_detall.map(p => `${p.hora} — ${p.professor} (${p.assignatura}${p.grup ? ' ' + p.grup : ''})`).join('\n')
    toast.add({
      severity: 'warn',
      summary: t('substitutions.senseCobertura'),
      detail: lines,
      life: 12000
    })
  }
}

const generarPendents = async () => {
  loading.value = true
  try {
    const data = dataISO.value
    const response = await axios.post(`/api/substitucions/${data}/generar?regenerar_tot=false`)
    await carregarSubstitucions()
    mostrarResultatGeneracio(response.data)
  } catch (error) {
    console.error('Error generant substitucions:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('substitutions.errors.generatePending'),
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const regenerarTot = async () => {
  // Confirmació abans de regenerar tot
  confirm.require({
    message: t('substitutions.confirm.regenerateAllMessage'),
    header: t('substitutions.confirm.regenerateAllTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('substitutions.confirm.regenerateAllAccept'),
    rejectLabel: t('common.cancel'),
    accept: async () => {
      loading.value = true
      try {
        const data = dataISO.value
        const response = await axios.post(`/api/substitucions/${data}/generar?regenerar_tot=true`)

        await carregarSubstitucions()
        mostrarResultatGeneracio(response.data, t('common.regenerated'))
      } catch (error) {
        console.error('Error regenerant substitucions:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: t('substitutions.errors.regenerateAll'),
          life: 3000
        })
      } finally {
        loading.value = false
      }
    }
  })
}

const actualitzarSubstitut = async (substitucio, event) => {
  try {
    const data = dataISO.value
    const response = await axios.put(
      `/api/substitucions/${data}/${substitucio.hora}/${substitucio.professor_absent}`,
      { substitut: substitucio.substitut, updated_at: substitucio.updated_at },
      { _silent: true }
    )

    if (response.data?.updated_at) {
      substitucio.updated_at = response.data.updated_at
    }

    // Actualitzar estat
    substitucio.estat = substitucio.substitut ? 'assignada' : 'pendent'

    // Recarregar disponibles per actualitzar colors (alguns professors poden passar de disponible a "JA ASSIGNAT")
    await carregarDisponiblesPerHores()

    toast.add({
      severity: 'success',
      summary: t('common.updated'),
      detail: t('substitutions.messages.substituteAssigned', { name: substitucio.substitut || t('common.none') }),
      life: 2000
    })
  } catch (error) {
    console.error('Error actualitzant substitut:', error)
    if (error.response?.status === 409 && error.response?.data?.detail?.current_data) {
      const currentData = error.response.data.detail.current_data
      obrirDialogConflicte(async () => {
        const data = dataISO.value
        await axios.put(
          `/api/substitucions/${data}/${substitucio.hora}/${substitucio.professor_absent}`,
          {
            substitut: substitucio.substitut,
            updated_at: currentData.updated_at,
            force: true
          }
        )
        await carregarSubstitucions()
      })
      return
    }

    // Mostrar missatge d'error de l'API (si està disponible)
    const errorDetail = error.response?.data?.detail || t('substitutions.errors.updateSubstitute')

    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: errorDetail,
      life: 4000
    })

    // Recarregar substitucions per restaurar els valors correctes de la BD
    await carregarSubstitucions()
  }
}

const actualitzarComentari = async (substitucio) => {
  try {
    const data = dataISO.value
    const response = await axios.put(
      `/api/substitucions/${data}/${substitucio.hora}/${substitucio.professor_absent}`,
      {
        substitut: substitucio.substitut,
        comentaris: substitucio.comentaris,
        updated_at: substitucio.updated_at
      },
      { _silent: true }
    )

    if (response.data?.updated_at) {
      substitucio.updated_at = response.data.updated_at
    }

    toast.add({
      severity: 'success',
      summary: t('common.updated'),
      detail: t('substitutions.messages.commentSaved'),
      life: 2000
    })
  } catch (error) {
    console.error('Error actualitzant comentari:', error)
    if (error.response?.status === 409 && error.response?.data?.detail?.current_data) {
      const currentData = error.response.data.detail.current_data
      obrirDialogConflicte(async () => {
        const data = dataISO.value
        await axios.put(
          `/api/substitucions/${data}/${substitucio.hora}/${substitucio.professor_absent}`,
          {
            substitut: substitucio.substitut,
            comentaris: substitucio.comentaris,
            updated_at: currentData.updated_at,
            force: true
          }
        )
        await carregarSubstitucions()
      })
      return
    }
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('substitutions.errors.saveComment'),
      life: 3000
    })
  }
}

const formatDisponibles = (disponibles, substitutActual = '') => {
  // Sempre afegir una opció neutra al principi (valor buit per esborrar substitut)
  const opcioNeutra = { label: t('common.selectOption'), value: '', color: '#F3F4F6' };

  const llistaDisponibles = Array.isArray(disponibles) ? disponibles : []
  const ordenats = [...llistaDisponibles].sort((a, b) => {
    const baixaA = a.de_baixa ? 1 : 0
    const baixaB = b.de_baixa ? 1 : 0
    if (baixaA !== baixaB) {
      return baixaA - baixaB
    }
    const ocupatA = a.ocupat ? 1 : 0
    const ocupatB = b.ocupat ? 1 : 0
    if (ocupatA !== ocupatB) {
      return ocupatA - ocupatB
    }
    const catA = Number.isFinite(Number(a.categoria)) ? Number(a.categoria) : 999
    const catB = Number.isFinite(Number(b.categoria)) ? Number(b.categoria) : 999
    if (catA !== catB) {
      return catA - catB
    }
    return collator.value.compare(a.professor || '', b.professor || '')
  })
  const opcionsDisponibles = ordenats.map(disp => {
    // Usar text_display del backend si existeix, sinó crear-lo manualment
    let label = disp.text_display || disp.professor

    // Fallback si no hi ha text_display (compatibilitat)
    if (!disp.text_display && disp.tipus && disp.detall) {
      label = `${disp.professor} (${disp.tipus} - ${disp.detall})`
    }

    return {
      label: label,
      value: disp.professor,
      color: disp.color || 'transparent'
    }
  });

  const valors = new Set(opcionsDisponibles.map(op => op.value))
  const opcions = [opcioNeutra, ...opcionsDisponibles]

  if (substitutActual && !valors.has(substitutActual)) {
    opcions.push({
      label: `${substitutActual} (${t('common.inactive')})`,
      value: substitutActual,
      color: '#F3F4F6'
    })
  }

  if (llistaDisponibles.length === 0) {
    return opcions
  }

  return opcions;
}

const obrirDialogNou = () => {
  gestioAbsencies.value = {
    professor: null,
    professorSearch: '',
    horesAbsencia: [],
    horesServei: []
  }
  mostrarDialogGestio.value = true
  document.body.style.overflow = 'hidden'
}

const confirmarEliminarAbsenciesProf = (professorNom) => {
  confirm.require({
    message: t('substitutions.confirm.deleteAllAbsencesMessage', { teacher: professorNom }),
    header: t('substitutions.confirm.deleteAbsenceTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: () => eliminarTotesAbsenciesProf(professorNom)
  })
}

const eliminarTotesAbsenciesProf = async (professorNom) => {
  loading.value = true
  try {
    const data = dataISO.value
    const professorEncoded = encodeURIComponent(professorNom)
    const updatedAtMap = {}
    absenciesDelDia.value
      .filter(a => a.professor_absent === professorNom && !esVigilanciaAbsent(a))
      .forEach(a => { if (a.updated_at) updatedAtMap[a.hora] = a.updated_at })

    await axios.put(`/api/substitucions/${data}/absencies/${professorEncoded}`, {
      hores_absencia: [],
      hores_servei: [],
      updated_at_map: updatedAtMap
    }, { _silent: true })

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('substitutions.messages.allAbsencesDeleted', { teacher: professorNom }),
      life: 3000
    })

    await carregarSubstitucions()
  } catch (error) {
    console.error('Error eliminant absències:', error)
    if (error.response?.status === 409) {
      obrirDialogConflicte(async () => {
        await axios.put(`/api/substitucions/${dataISO.value}/absencies/${encodeURIComponent(professorNom)}`, {
          hores_absencia: [],
          hores_servei: [],
          force: true
        })
        await carregarSubstitucions()
      })
      return
    }
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('substitutions.errors.deleteAbsence'),
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const editarAbsenciesProfessor = async (substitucio) => {
  const professorNom = substitucio.professor_absent
  await carregarTotesAbsencies()

  const absProf = totesAbsencies.value.filter(a => {
    const tipus = (a.tipus_absencia || '').toUpperCase()
    if (a.professor_absent !== professorNom) return false
    if (tipus === 'ENCADENADA') return false
    if (tipus === 'VIGILANCIA') return esVigilanciaAbsent(a) // Inclou Tipus A, exclou Tipus B
    return true
  })
  const tipusAbsencia = absProf[0]?.tipus_absencia || 'ABSENCIA'

  // Hores ABSENCIA + hores on el vigilant és absent (Tipus A VIGILANCIA)
  const horesAbsencia = absProf
    .filter(a => a.tipus_absencia === 'ABSENCIA' || esVigilanciaAbsent(a))
    .map(a => a.hora)
  gestioAbsencies.value = {
    professor: professorNom,
    professorSearch: '',
    horesAbsencia,
    horesServei: absProf.filter(a => a.tipus_absencia === 'SERVEI').map(a => a.hora)
  }
  dropdownProfValue.value = professorsAmbInfo.value.find(p => p.nom === professorNom) || null

  carregarHoresAmbClasse(professorNom)
  mostrarDialogGestio.value = true
  document.body.style.overflow = 'hidden'
}

const tancarDialogGestio = () => {
  mostrarDialogGestio.value = false
  gestioAbsencies.value = {
    professor: null,
    professorSearch: '',
    horesAbsencia: [],
    horesServei: []
  }
  dropdownProfValue.value = null
  horesAmbClasse.value = []
  horesAlCentre.value = []
  horesCarregades.value = false
  modeRang.value = false
  dataFinalRang.value = ''
  document.body.style.overflow = ''
}

// Funcions del bottom sheet
const carregarHoresAmbClasse = async (professorNom) => {
  horesCarregades.value = false
  try {
    const res = await axios.get(`/api/substitucions/${dataISO.value}/hores-professor/${encodeURIComponent(professorNom)}`)
    horesAmbClasse.value = res.data.hores_amb_classe
    horesAlCentre.value = res.data.hores_al_centre || []
  } catch {
    horesAmbClasse.value = []
    horesAlCentre.value = []
  } finally {
    horesCarregades.value = true
  }
}

const seleccionarProfessor = (prof) => {
  const absProf = absenciesDelDia.value.filter(a => a.professor_absent === prof.nom)
  gestioAbsencies.value.professor = prof.nom
  gestioAbsencies.value.professorSearch = ''
  gestioAbsencies.value.horesAbsencia = absProf.filter(a => a.tipus_absencia === 'ABSENCIA' || esVigilanciaAbsent(a)).map(a => a.hora)
  gestioAbsencies.value.horesServei = absProf.filter(a => a.tipus_absencia === 'SERVEI').map(a => a.hora)
  carregarHoresAmbClasse(prof.nom)
}


const toggleHoraAbsencia = (hora) => {
  const idx = gestioAbsencies.value.horesAbsencia.indexOf(hora)
  if (idx === -1) gestioAbsencies.value.horesAbsencia.push(hora)
  else gestioAbsencies.value.horesAbsencia.splice(idx, 1)
}

const toggleHoraServei = (hora) => {
  const idx = gestioAbsencies.value.horesServei.indexOf(hora)
  if (idx === -1) gestioAbsencies.value.horesServei.push(hora)
  else gestioAbsencies.value.horesServei.splice(idx, 1)
}

const disponiblesPerAbsencia = computed(() =>
  horesDisponibles.value.filter(h => !gestioAbsencies.value.horesServei.includes(h))
)
const disponiblesPerServei = computed(() =>
  horesDisponibles.value.filter(h => !gestioAbsencies.value.horesAbsencia.includes(h))
)
const totesTrnadesAbsencia = computed(() =>
  disponiblesPerAbsencia.value.length > 0 &&
  disponiblesPerAbsencia.value.every(h => gestioAbsencies.value.horesAbsencia.includes(h))
)
const totesTrnadesServei = computed(() =>
  disponiblesPerServei.value.length > 0 &&
  disponiblesPerServei.value.every(h => gestioAbsencies.value.horesServei.includes(h))
)

const toggleTotesAbsencia = () => {
  if (totesTrnadesAbsencia.value) {
    gestioAbsencies.value.horesAbsencia = []
  } else {
    gestioAbsencies.value.horesAbsencia = [...disponiblesPerAbsencia.value]
  }
}
const toggleTotesServei = () => {
  if (totesTrnadesServei.value) {
    gestioAbsencies.value.horesServei = []
  } else {
    gestioAbsencies.value.horesServei = [...disponiblesPerServei.value]
  }
}

const afegirAbsenciaImmediata = async () => {
  if (!gestioAbsencies.value.professor) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('substitutions.errors.selectTeacher'), life: 3000 })
    return
  }
  if (gestioAbsencies.value.horesAbsencia.length === 0 && gestioAbsencies.value.horesServei.length === 0) {
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('substitutions.dialogs.absences.hoursHint'), life: 3000 })
    return
  }

  const profNom = gestioAbsencies.value.professor
  const horesAbsencia = [...gestioAbsencies.value.horesAbsencia]
  const horesServei = [...gestioAbsencies.value.horesServei]

  loading.value = true
  try {
    const professorEncoded = encodeURIComponent(profNom)
    const dates = datesDelRang.value

    if (dates.length === 1) {
      const data = dates[0]
      const updatedAtMap = {}
      absenciesDelDia.value
        .filter(a => a.professor_absent === profNom && !esVigilanciaAbsent(a))
        .forEach(a => { if (a.updated_at) updatedAtMap[a.hora] = a.updated_at })

      // Únic PUT multi-tipus: el backend processa ABSENCIA i SERVEI de forma independent
      const resposta = await axios.put(`/api/substitucions/${data}/absencies/${professorEncoded}`, {
        hores_absencia: horesAbsencia,
        hores_servei: horesServei,
        updated_at_map: updatedAtMap
      }, { _silent: true })

      toast.add({
        severity: 'success',
        summary: t('common.saved'),
        detail: t('substitutions.messages.absencesSaved', { teacher: profNom }),
        life: 2500
      })
      if (resposta.data?.vigilancies_desassignades > 0) {
        toast.add({
          severity: 'info',
          summary: t('substitutions.messages.vigilanciesUnassignedTitle'),
          detail: t('substitutions.messages.vigilanciesUnassignedDetail', { count: resposta.data.vigilancies_desassignades }),
          life: 6000
        })
      }
      await carregarSubstitucions()
    } else {
      await Promise.all(dates.map(d =>
        axios.put(`/api/substitucions/${d}/absencies/${professorEncoded}`, {
          hores_absencia: horesAbsencia,
          hores_servei: horesServei,
          updated_at_map: {}
        })
      ))
      toast.add({
        severity: 'success',
        summary: t('common.saved'),
        detail: `${dates.length} ${t('substitutions.range.daysRegistered', { teacher: profNom })}`,
        life: 4000
      })
      modeRang.value = false
      dataFinalRang.value = ''
      await carregarSubstitucions()
    }
  } catch (error) {
    console.error('Error afegint absència:', error)
    if (error.response?.status === 409) {
      obrirDialogConflicte(async () => {
        const d = dataISO.value
        const profEncoded = encodeURIComponent(profNom)
        await axios.put(`/api/substitucions/${d}/absencies/${profEncoded}`, {
          hores_absencia: horesAbsencia,
          hores_servei: horesServei,
          force: true
        })
        await carregarSubstitucions()
      })
      return
    }
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('substitutions.errors.saveAbsences'), life: 3000 })
  } finally {
    loading.value = false
  }
}

const getRowClass = (data) => {
  // Afegir classe 'hora-separador' a la primera fila de cada hora
  const index = substitucionsFiltrades.value.indexOf(data)
  if (index === 0) return 'primera-hora'

  const horaAnterior = substitucionsFiltrades.value[index - 1]?.hora
  const horaActual = data.hora

  return horaAnterior !== horaActual ? 'hora-separador' : ''
}

// PDF Functions
const aplicarPreferenciesPdf = (prefs) => {
  if (!prefs) return
  const keys = ['includeSubstitutions', 'includeVigilancies', 'showComments', 'showHours', 'showConflicts', 'compress']
  keys.forEach((key) => {
    if (prefs[key] !== undefined) {
      pdfConfig.value[key] = prefs[key]
    }
  })
}

const carregarPreferenciesPdf = async () => {
  try {
    const response = await axios.get('/api/settings/pdf-preferences')
    aplicarPreferenciesPdf(response.data?.substitucions)
  } catch (error) {
    console.error('Error carregant preferències PDF:', error)
  }
}

const desarPreferenciesPdf = async () => {
  try {
    await axios.put('/api/settings/pdf-preferences', {
      substitucions: {
        includeSubstitutions: pdfConfig.value.includeSubstitutions,
        includeVigilancies: pdfConfig.value.includeVigilancies,
        showComments: pdfConfig.value.showComments,
        showHours: pdfConfig.value.showHours,
        showConflicts: pdfConfig.value.showConflicts,
        compress: pdfConfig.value.compress
      }
    })
  } catch (error) {
    console.error('Error desant preferències PDF:', error)
  }
}

const mostrarDialegPDF = async () => {
  await carregarPreferenciesPdf()
  mostrarDialogPDF.value = true
}

defineExpose({
  mostrarDialegPDF
})

const generarPDFComplet = async () => {
  // Validar que almenys un tipus de contingut està seleccionat
  if (!pdfConfig.value.includeSubstitutions && !pdfConfig.value.includeVigilancies) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('substitutions.dialogs.pdf.selectAtLeastOneShort'),
      life: 3000
    })
    return
  }

  generantPDF.value = true
  try {
    reassignChanges.value = []
    // 1. Primer validar abans de generar PDF
    const validacioResponse = await axios.get(`/api/pdf/${dataISO.value}/validacions`)
    validacions.value = validacioResponse.data

    // 2. Mostrar diàleg de validacions si hi ha problemes
    if (validacions.value.total > 0) {
      // Tancar diàleg de configuració i mostrar diàleg de validacions
      mostrarDialogPDF.value = false
      mostrarDialogValidacions.value = true
      generantPDF.value = false
      return
    }

    // 3. Si no hi ha problemes, continuar directament
    await generarPDFAmbOpcions()

  } catch (error) {
    console.error('Error validant PDF:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('substitutions.errors.validatePdf'),
      life: 3000
    })
    generantPDF.value = false
  }
}

const generarPDFAmbOpcions = async () => {
  generantPDF.value = true
  try {
    // Generar PDF
    const params = new URLSearchParams({
      include_substitutions: pdfConfig.value.includeSubstitutions,
      include_vigilancies: pdfConfig.value.includeVigilancies,
      show_comments: pdfConfig.value.showComments,
      show_hours: pdfConfig.value.showHours,
      show_conflicts: pdfConfig.value.showConflicts,
      compress: pdfConfig.value.compress
    })

    const url = `/api/pdf/complete/${dataISO.value}?${params.toString()}`

    // Download PDF
    const response = await axios.get(url, {
      responseType: 'blob'
    })

    // Create download link
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `complet_${dataISO.value}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)

    toast.add({
      severity: 'success',
      summary: t('substitutions.messages.pdfGeneratedTitle'),
      detail: t('substitutions.messages.pdfGeneratedDetail', { date: dataISO.value }),
      life: 3000
    })

    await desarPreferenciesPdf()

    // Tancar tots els diàlegs
    mostrarDialogPDF.value = false
    mostrarDialogValidacions.value = false
  } catch (error) {
    console.error('Error generant PDF:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('substitutions.errors.generatePdf'),
      life: 3000
    })
  } finally {
    generantPDF.value = false
  }
}

const continuarPDF = async () => {
  await generarPDFAmbOpcions()
}

const cancelarPDF = () => {
  mostrarDialogValidacions.value = false
  mostrarDialogPDF.value = true
  generantPDF.value = false
}

const reassignarProblematics = async () => {
  reassignantProblematics.value = true
  try {
    const canvis = []
    if (pdfConfig.value.includeSubstitutions) {
      const respSubs = await axios.post(`/api/substitucions/${dataISO.value}/reassign-problematics`)
      if (Array.isArray(respSubs?.data?.changes)) {
        respSubs.data.changes.forEach(change => {
          const meta = [change.professor_absent, change.assignatura, change.grup]
            .filter(Boolean)
            .join(' · ')
          canvis.push({
            hora: change.hora || '',
            label: `SUB ${change.hora} ${meta}: ${change.abans || '—'} → ${change.despres || '—'}`
          })
        })
      }
      if (respSubs?.data?.cleared !== undefined) {
        toast.add({
          severity: 'success',
          summary: t('substitutions.messages.reassignSubstitutionsTitle'),
          detail: t('substitutions.messages.reassignSubstitutionsDetail', { count: respSubs.data.cleared }),
          life: 6000
        })
      }
      await carregarSubstitucions()
    }

    if (canvis.length > 0) {
      const validacioResponse = await axios.get(`/api/pdf/${dataISO.value}/validacions`)
      validacions.value = validacioResponse.data
      reassignChanges.value = ordenarCanvisPerHora(canvis).map((item) => item.label)
      mostrarDialogPDF.value = false
      mostrarDialogValidacions.value = true
      return
    }

    const validacioResponse = await axios.get(`/api/pdf/${dataISO.value}/validacions`)
    validacions.value = validacioResponse.data

    if (validacions.value.total === 0) {
      await generarPDFAmbOpcions()
      return
    }

    toast.add({
      severity: 'info',
      summary: t('substitutions.messages.reassignDoneTitle'),
      detail: t('substitutions.messages.reassignDoneDetail'),
      life: 3500
    })
  } catch (error) {
    console.error('Error reassignant problemàtics:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('substitutions.errors.reassignProblematics'),
      life: 3000
    })
  } finally {
    reassignantProblematics.value = false
  }
}

const ordenarCanvisPerHora = (canvis) => {
  const ordreHores = horesDisponibles.value || []
  const horaIndex = (hora) => {
    const idx = ordreHores.indexOf(hora)
    return idx === -1 ? 999 : idx
  }

  return [...canvis].sort((a, b) => {
    const diff = horaIndex(a.hora) - horaIndex(b.hora)
    if (diff !== 0) return diff
    return collator.value.compare(a.label || '', b.label || '')
  })
}

// Watch per canvis de data
watch(() => props.dataGlobal, async () => {
  await carregarSubstitucions()
})

// Quan les dades canvien (desa/elimina), sincronitzar els dos grids si hi ha professor seleccionat
watch(absenciesDelDia, () => {
  if (!mostrarDialogGestio.value || !gestioAbsencies.value.professor) return
  const prof = gestioAbsencies.value.professor
  const absProf = absenciesDelDia.value.filter(a => a.professor_absent === prof)
  gestioAbsencies.value.horesAbsencia = absProf.filter(a => a.tipus_absencia === 'ABSENCIA' || esVigilanciaAbsent(a)).map(a => a.hora)
  gestioAbsencies.value.horesServei = absProf.filter(a => a.tipus_absencia === 'SERVEI').map(a => a.hora)
})

// Lifecycle
onBeforeUnmount(() => {
  document.body.style.overflow = ''
})

onMounted(async () => {
  await carregarNoSubstituir()
  await carregarHores()
  await carregarProfessors()
  await carregarSubstitucions()
})
</script>

<style scoped>
.substitucions-view {
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
  color: inherit;
  text-decoration: none;
}

.day-stat-link:hover {
  color: var(--primary-color-dark);
}

.toolbar {
  background: white;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.content-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.date-selector {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.date-selector label {
  font-weight: 600;
  color: #2c3e50;
}

.actions {
  display: flex;
  gap: 0.75rem;
}

.stats {
  display: flex;
  gap: 1rem;
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

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: #666;
}

.empty-state p {
  margin: 1rem 0 0.5rem;
  font-size: 1.1rem;
}

.empty-state small {
  color: #999;
}

/* Millores generals de la taula */
:deep(.p-datatable) {
  font-size: 0.95rem;
}

:deep(.p-datatable .p-datatable-thead > tr > th) {
  background: #f8f9fa;
  color: #2c3e50;
  font-weight: 600;
  font-size: 0.9rem;
  padding: 1rem 0.75rem;
  border-bottom: 2px solid #dee2e6;
}

:deep(.p-datatable .p-datatable-tbody > tr > td) {
  padding: 1rem 0.75rem;
  vertical-align: middle;
}

:deep(.p-dropdown) {
  width: 100%;
  font-size: 0.925rem;
}

:deep(.p-dropdown .p-dropdown-label) {
  padding: 0.65rem 0.75rem;
  font-weight: 500;
}

:deep(.p-dropdown-panel .p-dropdown-items .p-dropdown-item) {
  padding: 0.65rem 1rem;
  font-size: 0.925rem;
}


/* Accions flotants a la fila (estil vigilàncies) */
.cell-wrapper-relative {
  position: static;
  width: 100%;
}

.row-hover-actions {
  position: absolute !important;
  bottom: -1.1rem !important;
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

.row-hover-actions .action-btn .p-button-icon {
  font-size: 0.5rem !important;
  opacity: 0.55;
  margin-right: 0.25rem;
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

:deep(tr:hover .row-hover-actions) {
  opacity: 0.6 !important;
  pointer-events: auto !important;
}




/* Separadors entre hores */
:deep(.hora-separador td) {
  border-top: 3px solid #667eea !important;
  padding-top: 1rem !important;
}

:deep(.primera-hora td) {
  border-top: none !important;
}

/* Millora visual de files */
:deep(.p-datatable .p-datatable-tbody > tr) {
  transition: all 0.2s;
}

:deep(.p-datatable .p-datatable-tbody > tr:hover) {
  background: #f0f4ff !important;
  transform: scale(1.01);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15);
}

:deep(.substitucions-table .p-inputtext) {
  height: 2.2rem !important;
  min-height: 2.2rem !important;
  max-height: 2.2rem !important;
  padding: 0.4rem 0.6rem !important;
  font-size: 0.9rem !important;
}

:deep(.substitucions-table .p-datatable-wrapper) {
  padding-bottom: 2.2rem;
}

/* Formulari Nova Substitució */
.nova-substitucio-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1rem 0;
}

:deep(.substitucions-view .p-dialog-content) {
  padding: 1rem 1.25rem;
}

:deep(.substitucions-view .p-dialog-footer) {
  padding: 0.75rem 1.25rem 1rem;
}

.nova-substitucio-form .field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.nova-substitucio-form .field label {
  font-weight: 600;
  color: #2c3e50;
  font-size: 0.95rem;
}

.nova-substitucio-form .field-hint {
  color: #6c757d;
  font-size: 0.85rem;
  font-style: italic;
  margin-top: 0.25rem;
}

.nova-substitucio-form .field-checkbox {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.nova-substitucio-form .field-checkbox label {
  font-weight: 500;
  color: #495057;
  margin-bottom: 0;
  cursor: pointer;
}

.nova-substitucio-form :deep(.p-dropdown),
.nova-substitucio-form :deep(.p-multiselect),
.nova-substitucio-form :deep(.p-inputtext) {
  width: 100%;
}

.nova-substitucio-form .field-hours :deep(.p-multiselect.hours-select) {
  width: min(360px, 100%);
}

.nova-substitucio-form :deep(.p-multiselect .p-multiselect-label) {
  padding: 0.65rem 0.75rem;
}

/* Professors amb absències al dropdown */
.professor-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.professor-option.amb-absencies {
  background-color: #fff3cd;
  border-left: 3px solid #ff9800;
  padding-left: 0.5rem;
  margin-left: -0.5rem;
}

.absencies-badge {
  font-size: 0.85rem;
  color: #856404;
  font-weight: 600;
  margin-left: 0.5rem;
}

/* Estils per disponibles amb colors */
.disponible-option {
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.disponible-option:hover {
  filter: brightness(0.95);
}

@media (max-width: 768px) {
  .view-header h2 {
    font-size: 1.6rem;
  }

  .toolbar {
    padding: 0.75rem;
  }

  .actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .actions :deep(.p-button) {
    flex: 1 1 160px;
    justify-content: center;
  }

  .stats {
    width: 100%;
    flex-wrap: wrap;
    justify-content: space-between;
  }

  .stat-card {
    flex: 1 1 140px;
  }

  .content-card {
    padding: 0.9rem;
  }

  :deep(.p-datatable .p-datatable-thead > tr > th) {
    padding: 0.65rem 0.5rem;
  }

  :deep(.p-datatable .p-datatable-tbody > tr > td) {
    padding: 0.65rem 0.5rem;
  }
}

@media (max-width: 520px) {
  .actions :deep(.p-button) {
    flex: 1 1 100%;
  }

  .stat-card {
    flex: 1 1 100%;
  }
}

/* ================================================================
   BOTTOM SHEET — Gestionar absències
   Mobile: slide up from bottom. Desktop: centered modal.
   ================================================================ */

.bs-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.48);
  z-index: 1050;
}

.bs-overlay-enter-active,
.bs-overlay-leave-active {
  transition: opacity 0.25s ease;
}
.bs-overlay-enter-from,
.bs-overlay-leave-to {
  opacity: 0;
}

.bs-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  border-radius: 12px 12px 0 0;
  z-index: 1051;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  transform: translateY(100%);
  transition: transform 0.32s cubic-bezier(0.32, 0.72, 0, 1);
  box-shadow: 0 -4px 32px rgba(0, 0, 0, 0.18);
  pointer-events: none;
  overflow: hidden;
  padding: 0;
}

.bs-sheet--visible {
  transform: translateY(0);
  pointer-events: auto;
}

/* Desktop: centered modal — mateix breakpoint que PrimeVue (720px) */
@media (min-width: 720px) {
  .bs-sheet {
    bottom: auto;
    left: 50%;
    right: auto;
    top: 50%;
    width: 480px;
    height: min(82vh, 640px);
    border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    transform: translate(-50%, -44%) scale(0.97);
    opacity: 0;
    transition: transform 0.22s ease, opacity 0.22s ease;
    pointer-events: none;
  }
  .bs-sheet--visible {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
    pointer-events: auto;
  }
}

.bs-drag-handle {
  display: none;
}

/* Header — mateix estil que p-dialog-header de PrimeVue (lara-light-blue) */
.bs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 0 none;
  background: #ffffff;
  color: #374151;
  flex-shrink: 0;
}

/* Títol — rèplica de p-dialog-title */
.bs-header .p-dialog-title {
  font-weight: 700;
  font-size: 1.25rem;
  color: #374151;
}

/* Botó tancar — rèplica de p-dialog-header-icon */
.bs-close-btn {
  width: 2rem;
  height: 2rem;
  color: #6b7280;
  border: 0 none;
  background: transparent;
  border-radius: 50%;
  transition: background-color 0.2s, color 0.2s, box-shadow 0.2s;
  outline-color: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  padding: 0;
  flex-shrink: 0;
}
.bs-close-btn:hover {
  color: #374151;
  background: #f3f4f6;
}
.bs-close-btn:focus,
.bs-close-btn:focus-visible {
  outline: 0 none;
  box-shadow: 0 0 0 0.2rem #BFDBFE;
}

/* Scrollable content */
.bs-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Field */
.bs-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.bs-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}
.bs-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.bs-sel-all-btn {
  font-size: 0.75rem;
  font-weight: 500;
  color: #0369a1;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.bs-sel-all-btn--servei { color: #7c3aed; }
.bs-sel-all-btn:hover { opacity: 0.7; }

/* date input per al rang */
.bs-input {
  width: 100%;
  height: 48px;
  padding: 0 1rem;
  border: 1.5px solid #d1d5db;
  border-radius: 10px;
  font-size: 1rem;
  color: #1f2937;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}
.bs-input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.12);
}

/* Opció professor al Dropdown */
.bs-prof-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 0.5rem;
}
.bs-prof-option--absencies {
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  margin-left: -0.75rem;
  padding-left: calc(0.75rem - 3px);
  margin-right: -0.75rem;
  padding-right: 0.75rem;
}

.bs-badge-hores {
  font-size: 0.78rem;
  font-weight: 600;
  color: #92400e;
  background: #fef3c7;
  padding: 0.15rem 0.5rem;
  border-radius: 99px;
  flex-shrink: 0;
}


/* Badges de tipus al label */
.bs-type-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.5rem;
  border-radius: 99px;
  vertical-align: middle;
  margin-left: 0.3rem;
}
.bs-type-badge--normal {
  background: #e0e3f8;
  color: var(--primary-color-dark);
}
.bs-type-badge--servei {
  background: #ede9fe;
  color: #6d28d9;
}

/* Hours grid */
.bs-hours-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.bs-hour-btn {
  min-height: 36px;
  min-width: 68px;
  padding: 0 0.9rem;
  border: 1.5px solid #d1d5db;
  border-radius: 8px;
  background: #f9fafb;
  color: #374151;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.12s;
  white-space: nowrap;
}
.bs-hour-btn:disabled {
  opacity: 0.28;
  cursor: not-allowed;
}
.bs-hour-btn:not(:disabled):hover {
  border-color: var(--primary-color);
  background: #eef0fd;
  color: var(--primary-color-dark);
}

/* Botons Servei */
.bs-hour-btn--servei-base {
  border-color: #ddd6fe;
  background: #faf5ff;
  color: #4c1d95;
}
.bs-hour-btn--servei-base:not(:disabled):hover {
  border-color: #7c3aed;
  background: #ede9fe;
  color: #5b21b6;
}

/* Colors d'horari (al centre / fora) — després de servei-base per sobreescriure'l */
.bs-hour-btn--al-centre {
  background: #ffffff;
  border-color: #fed7aa;
  color: #c2410c;
}
.bs-hour-btn--al-centre:not(:disabled):hover {
  border-color: var(--primary-color);
  background: #eef0fd;
  color: var(--primary-color-dark);
}
.bs-hour-btn--fora {
  background: #f3f4f6;
  border-color: #e5e7eb;
  color: #9ca3af;
}
.bs-hour-btn--fora:not(:disabled):hover {
  border-color: var(--primary-color);
  background: #eef0fd;
  color: var(--primary-color-dark);
}

/* Seleccionats — han d'anar AL FINAL per guanyar sempre */
.bs-hour-btn--selected {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
  font-weight: 600;
}
.bs-hour-btn--selected:not(:disabled):hover {
  background: var(--primary-color-dark);
  border-color: var(--primary-color-dark);
}
.bs-hour-btn--servei-selected {
  background: #7c3aed;
  border-color: #7c3aed;
  color: white;
  font-weight: 600;
}
.bs-hour-btn--servei-selected:not(:disabled):hover {
  background: #6d28d9;
  border-color: #6d28d9;
}

/* Segmented toggle */
.bs-toggle-segment {
  display: inline-flex;
  background: #f3f4f6;
  border-radius: 10px;
  padding: 3px;
  gap: 3px;
}
.bs-toggle-opt {
  min-height: 40px;
  padding: 0 1.5rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #6b7280;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.bs-toggle-opt--active {
  background: white;
  color: #1f2937;
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
}

/* Absències del dia */
.bs-absencies-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.bs-section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin: 0;
}
.bs-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 0.65rem 0.9rem;
  gap: 0.75rem;
}
.bs-card--clickable {
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s;
}
.bs-card--clickable:hover { background: #f0f9ff; border-color: #bae6fd; }
.bs-card-info {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}
.bs-card-prof {
  font-weight: 600;
  font-size: 0.875rem;
  color: #1f2937;
}
.bs-card-hora {
  font-size: 0.8rem;
  color: #6b7280;
  background: #e5e7eb;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  white-space: nowrap;
}
.bs-card-tipus {
  font-size: 0.78rem;
  font-weight: 500;
  background: #e0f2fe;
  color: #0369a1;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
}
.bs-card-tipus--servei {
  background: #f3e8ff;
  color: #7c3aed;
}
.bs-card-del {
  width: 34px;
  height: 34px;
  border: 1px solid #fee2e2;
  background: #fff5f5;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  transition: all 0.12s;
  flex-shrink: 0;
}
.bs-card-del:hover { background: #fee2e2; border-color: #fca5a5; }
.bs-card-del:disabled { opacity: 0.45; cursor: not-allowed; }
.bs-card-hores-detall {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin-top: 0.1rem;
}
.bs-card-hores-normal {
  font-size: 0.8rem;
  color: #0369a1;
  background: #e0f2fe;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  white-space: nowrap;
}
.bs-card-hores-servei {
  font-size: 0.8rem;
  color: #7c3aed;
  background: #f3e8ff;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  white-space: nowrap;
}
.bs-card-actions {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}
.bs-card-edit {
  width: 34px;
  height: 34px;
  border: 1px solid #e0f2fe;
  background: #f0f9ff;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  transition: all 0.12s;
  flex-shrink: 0;
}
.bs-card-edit:hover { background: #bae6fd; border-color: #7dd3fc; }
.bs-card-edit:disabled { opacity: 0.45; cursor: not-allowed; }

/* Footer sticky */
.bs-footer {
  padding: 0.75rem 1rem;
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
  border-top: 1px solid #f1f5f9;
  flex-shrink: 0;
  background: white;
  border-radius: 0;
}
@media (min-width: 640px) {
  .bs-footer { border-radius: 0 0 16px 16px; }
}

.bs-btn-primary {
  width: 100%;
  height: 52px;
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}
.bs-btn-primary:hover:not(:disabled) { background: #15803d; }
.bs-btn-primary:disabled {
  background: #d1d5db;
  color: #9ca3af;
  cursor: not-allowed;
}

/* Spinner al botó */
.bs-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: white;
  border-radius: 50%;
  animation: bs-spin 0.6s linear infinite;
}
@keyframes bs-spin {
  to { transform: rotate(360deg); }
}

/* Rang de dates */
.bs-field--rang { gap: 0.5rem; }
.bs-rang-toggle {
  display: flex;
  gap: 3px;
  background: #f3f4f6;
  border-radius: 8px;
  padding: 3px;
}
.bs-rang-opt {
  flex: 1; padding: 0.4rem 0.75rem;
  border: none; border-radius: 6px;
  font-size: 0.875rem; cursor: pointer;
  background: transparent; color: #6b7280;
  transition: all 0.15s;
}
.bs-rang-opt--active {
  background: white; color: var(--primary-color);
  font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.bs-rang-dates {
  display: flex; align-items: center;
  gap: 0.5rem; margin-top: 0.25rem;
}
.bs-rang-inici { font-size: 0.875rem; color: #6b7280; font-weight: 500; }
.bs-rang-arrow { color: #9ca3af; }
.bs-rang-fi { flex: 1; height: 36px; font-size: 0.875rem; }
.bs-rang-resum {
  font-size: 0.8rem; color: var(--primary-color);
  font-weight: 600; text-align: center;
}
</style>
