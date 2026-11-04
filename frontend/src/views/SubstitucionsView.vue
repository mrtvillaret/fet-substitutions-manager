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
      <AvisErrorCarrega v-if="errorCarregaSubstitucions" :missatge="$t('substitutions.errors.loadAvailable')" @reintenta="carregarSubstitucions" />
      <TaulaSubstitucions
        :files="substitucionsFiltrades"
        :data="dataISO"
        :disponibles-de="disponiblesDe"
        :ordre="ordreFiles"
        :carregant="loading"
        @canvi="canviaCamp"
        @edita="editarAbsenciesProfessor"
        @esborra="esborraAbsenciesDeFila"
        @canvia-ordre="canviaOrdre"
      />
    </div>

    <GestioAbsenciesSubstitucions
      v-model:dropdownProfValue="dropdownProfValue"
      v-model:modeRang="modeRang"
      v-model:dataFinalRang="dataFinalRang"
      :mostrarDialogGestio="mostrarDialogGestio"
      :gestioAbsencies="gestioAbsencies"
      :professorsAmbInfo="professorsAmbInfo"
      :dataISOCurta="dataISOCurta"
      :dataISO="dataISO"
      :datesDelRang="datesDelRang"
      :horesDisponibles="horesDisponibles"
      :horesCarregades="horesCarregades"
      :horesAmbClasse="horesAmbClasse"
      :horesAlCentre="horesAlCentre"
      :totesTrnadesAbsencia="totesTrnadesAbsencia"
      :totesTrnadesServei="totesTrnadesServei"
      :absenciesDelDiaAgrupades="absenciesDelDiaAgrupades"
      :loading="loading"
      @tancarDialogGestio="tancarDialogGestio"
      @seleccionarProfessorDropdown="seleccionarProfessorDropdown"
      @toggleTotesAbsencia="toggleTotesAbsencia"
      @toggleHoraAbsencia="toggleHoraAbsencia"
      @toggleTotesServei="toggleTotesServei"
      @toggleHoraServei="toggleHoraServei"
      @editarAbsenciesProfessor="editarAbsenciesProfessor"
      @confirmarEliminarAbsenciesProf="confirmarEliminarAbsenciesProf"
      @afegirAbsenciaImmediata="afegirAbsenciaImmediata"
    />

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

    <PdfSubstitucionsDialogs
      v-model:mostrarDialogValidacions="mostrarDialogValidacions"
      v-model:mostrarDialogPDF="mostrarDialogPDF"
      v-model:pdfConfig="pdfConfig"
      :validacions="validacions"
      :warningsFiltrats="warningsFiltrats"
      :totalIssuesFiltrats="totalIssuesFiltrats"
      :reassignChanges="reassignChanges"
      :reassignantProblematics="reassignantProblematics"
      :generantPDF="generantPDF"
      @cancelarPDF="cancelarPDF"
      @reassignarProblematics="reassignarProblematics"
      @continuarPDF="continuarPDF"
      @generarPDFComplet="generarPDFComplet"
    />
  </div>
</template>

<script setup>
import AvisErrorCarrega from '../components/AvisErrorCarrega.vue'
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useEdicioSubstitucions } from '../composables/useEdicioSubstitucions.js'
import { usePdfSubstitucions } from '../composables/usePdfSubstitucions.js'
import { dataTreball } from '../dataTreball'
import * as apiSubstitucions from '../api/substitucions'
import { useDadesSubstitucions } from '../composables/useDadesSubstitucions.js'

// Components PrimeVue
import PdfSubstitucionsDialogs from '../components/substitucions/PdfSubstitucionsDialogs.vue'
import Button from 'primevue/button'
import GestioAbsenciesSubstitucions from '../components/substitucions/GestioAbsenciesSubstitucions.vue'
import Badge from 'primevue/badge'
import ConfirmDialog from 'primevue/confirmdialog'
import { useToast } from 'primevue/usetoast'
import { useAbsenciesSubstitucions } from '../composables/useAbsenciesSubstitucions.js'
import { useConfirm } from 'primevue/useconfirm'
import { useConfirmaEsborrar } from '../composables/useConfirmaEsborrar'
import ConflicteDialog from '../components/ConflicteDialog.vue'
import TaulaSubstitucions from '../components/substitucions/TaulaSubstitucions.vue'

const toast = useToast()
const confirm = useConfirm()
const confirmaEsborrar = useConfirmaEsborrar()
const { t, locale } = useI18n()
const emit = defineEmits(['anar-vigilancies'])

const {
  substitucionsFiltrades,
  totesAbsencies,
  vigilanciesCount,
  professors,
  absenciesCobertes,
  horesDisponibles,
  loading,
  errorCarregaSubstitucions,
  dataISO,
  dataFormatada,
  dataISOCurta,
  collator,
  substitucionsAssignades,
  substitucionsPendents,
  ordreFiles,
  canviaOrdre,
  carregarSubstitucions,
  carregarTotesAbsencies,
  carregarProfessors,
  carregarHores
} = useDadesSubstitucions({ dataTreball, locale, toast, t })

const mostrarDialogConflicte = ref(false)
const conflicteOverwrite = ref(null)

const anarAVigilancies = () => {
  emit('anar-vigilancies')
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

const mostrarAvisos = (avisos) => {
  if (!Array.isArray(avisos) || avisos.length === 0) return
  toast.add({
    severity: 'warn',
    summary: t('substitutions.messages.operationWarnings'),
    detail: avisos.join('\n')
  })
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
  mostrarAvisos(data.avisos)
}

const generarPendents = async () => {
  loading.value = true
  try {
    const data = dataISO.value
    const resposta = await apiSubstitucions.genera(data, false)
    await carregarSubstitucions()
    mostrarResultatGeneracio(resposta)
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
        const resposta = await apiSubstitucions.genera(data, true)

        await carregarSubstitucions()
        mostrarResultatGeneracio(resposta, t('common.regenerated'))
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

const { disponiblesDe, canviaCamp } = useEdicioSubstitucions({
  dataISO, totesAbsencies, substitucionsFiltrades, collator, toast, t, confirm,
  obrirDialogConflicte, mostrarAvisos, carregarSubstitucions
})

// Esborrar des de la fila: totes les absències d'aquell professor aquell dia
// (una sola hora es treu a «Gestionar absències»)
const esborraAbsenciesDeFila = (fila) => confirmarEliminarAbsenciesProf(fila.professor_absent)

const {
  mostrarDialogGestio,
  dropdownProfValue,
  gestioAbsencies,
  horesAmbClasse,
  horesAlCentre,
  horesCarregades,
  modeRang,
  dataFinalRang,
  professorsAmbInfo,
  absenciesDelDiaAgrupades,
  seleccionarProfessorDropdown,
  datesDelRang,
  obrirDialogNou,
  confirmarEliminarAbsenciesProf,
  editarAbsenciesProfessor,
  tancarDialogGestio,
  toggleHoraAbsencia,
  toggleHoraServei,
  totesTrnadesAbsencia,
  totesTrnadesServei,
  toggleTotesAbsencia,
  toggleTotesServei,
  afegirAbsenciaImmediata
} = useAbsenciesSubstitucions({ dataISO, professors, absenciesCobertes, totesAbsencies, horesDisponibles, loading, toast, t, confirmaEsborrar, obrirDialogConflicte, carregarSubstitucions, carregarTotesAbsencies })

const {
  mostrarDialogPDF,
  mostrarDialogValidacions,
  generantPDF,
  reassignantProblematics,
  reassignChanges,
  validacions,
  warningsFiltrats,
  totalIssuesFiltrats,
  pdfConfig,
  mostrarDialegPDF,
  generarPDFComplet,
  continuarPDF,
  cancelarPDF,
  reassignarProblematics
} = usePdfSubstitucions({ dataISO, ordreFiles, horesDisponibles, collator, toast, t, mostrarAvisos, carregarSubstitucions })

defineExpose({ mostrarDialegPDF })

// Watch per canvis de data
watch(dataTreball, async () => {
  await carregarSubstitucions()
  // L'horari (professors i hores) i qui està de baixa depenen del dia
  await carregarHores()
  await carregarProfessors()
})

// Lifecycle

onMounted(async () => {
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

/* La taula fa de targeta ella mateixa (taules.css, .taula-dades), com a Vigilàncies */
.content-card {
  margin-top: 0.5rem;
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

/* Els desplegables de la vista (la taula, a TaulaSubstitucions i taules.css) */
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

}

@media (max-width: 520px) {
  .actions :deep(.p-button) {
    flex: 1 1 100%;
  }

  .stat-card {
    flex: 1 1 100%;
  }
}

</style>
