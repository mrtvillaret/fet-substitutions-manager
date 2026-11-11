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
            :aria-label="$t('vigilancies.filters.level')"
            class="p-inputtext-sm"
            style="width: 180px;"
          >
            <template #value="{ value }">{{ etiquetaFiltre('level', value) }}</template>
          </Dropdown>
          <Dropdown
            v-model="filtreHora"
            :options="[allLabel, ...hores]"
            :placeholder="$t('vigilancies.filters.hour')"
            :aria-label="$t('vigilancies.filters.hour')"
            class="p-inputtext-sm"
            style="width: 150px;"
          >
            <template #value="{ value }">{{ etiquetaFiltre('hour', value) }}</template>
          </Dropdown>
          <Dropdown
            v-model="filtreEstat"
            :options="statusOptions"
            :placeholder="$t('vigilancies.filters.status')"
            :aria-label="$t('vigilancies.filters.status')"
            class="p-inputtext-sm"
            style="width: 150px;"
          >
            <template #value="{ value }">{{ etiquetaFiltre('status', value) }}</template>
          </Dropdown>
          <FiltreAula v-model="filtreAula" :aules="aulesDelFiltre" :etiqueta-totes="allLabel" amb-nom />
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

    <!-- Sense nivells configurats (abans, una llista fixa): es creen a la configuració d'exàmens -->
    <Message v-if="configCarregada && !nivells.length" severity="info" :closable="false" class="sense-nivells">
      <span>{{ $t('vigilancies.noLevels') }}</span>
      <Button
        :label="$t('vigilancies.withoutOwner.openConfig')"
        icon="pi pi-cog"
        size="small"
        text
        @click="obreConfiguracioExamens"
      />
    </Message>

    <AvisosTitularsVigilancies
      v-model:titularsHoraLliure="titularsHoraLliure"
      v-model:vigilanciesSenseTitular="vigilanciesSenseTitular"
      :loading="loading"
      :error="error"
      :posant-titular="posantTitular"
      :posa-titular-hora-lliure="posaTitularHoraLliure"
      :obre-configuracio-examens="obreConfiguracioExamens"
    />

    <!-- Carregant: només la primera vegada; amb files ja carregades, la taula es
         queda i mostra la càrrega a sobre (tornar-la a crear costava 1,5 s) -->
    <div v-if="loading && !vigilancies.length" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('vigilancies.loading') }}</p>
    </div>

    <div v-else-if="error" class="error-message">
      <AvisErrorCarrega :missatge="error" @reintenta="carregarVigilancies" />
    </div>

    <!-- Taula de vigilàncies: agrupada per hores, en l'ordre desat -->
    <template v-else>
    <div class="problemes-vigilancies" aria-live="polite">
      <Message v-for="(problema, index) in problemesVisibles" :key="index"
        :severity="{ important: 'error', avis: 'warn', informacio: 'info' }[problema.gravetat]"
        :closable="false">
        {{ problema.missatge }}
      </Message>
    </div>

      <Message v-if="filtresActius && vigilancies.length" severity="info" :closable="false" class="avis-ordre-filtres">
        {{ $t('vigilancies.table.orderDisabledByFilter') }}
      </Message>
      <TaulaVigilancies
        v-model:seleccionades="seleccionades"
        :files="vigilanciesFiltrades"
        :hores="hores"
        :data="dataISO"
        :opcions="opcionsFiles"
        :disponibles-de="disponiblesDe"
        :etiqueta-vigilant-de="etiquetaVigilantDe"
        :ressaltades="ressaltades"
        :titulars-lliures="idsTitularsHoraLliure"
        :ordre-editable="!filtresActius"
        :carregant="loading"
        @canvi="canviaCamp"
        @afegeix="afegirVigilanciaDesprés"
        @esborra="confirmarEliminar"
        @mou="mouFiles"
      />
    </template>

    <FormulariVigilancia
      v-model:visible="mostrarFormulariNova"
      :data="dataISO"
      :opcions="opcionsFiles"
      :proposta="propostaNova"
      :carrega-disponibles="disponiblesDelFormulari"
      :desant="creantVigilancia"
      @desa="creaVigilancia"
    />

    <PdfVigilanciesDialogs
      v-model:confirmacioImportants="confirmacioImportants"
      v-model:mostrarDialogValidacionsVig="mostrarDialogValidacionsVig"
      v-model:mostrarDialogPDF="mostrarDialogPDF"
      v-model:mostrarDialogInterval="mostrarDialogInterval"
      v-model:pdfConfig="pdfConfig"
      v-model:intervalConfig="intervalConfig"
      :validacions-vig="validacionsVig"
      :conflictes-vig-filtrats="conflictesVigFiltrats"
      :warnings-vig-filtrats="warningsVigFiltrats"
      :informatius-vig-filtrats="informatiusVigFiltrats"
      :generant-p-d-f="generantPDF"
      :opcions-nivells-pdf-dia="opcionsNivellsPdfDia"
      :opcions-nivells-pdf-interval="opcionsNivellsPdfInterval"
      :generant-p-d-f-interval="generantPDFInterval"
      :cancelar-p-d-f-vig="cancelarPDFVig"
      :continuar-p-d-f-vig="continuarPDFVig"
      :generar-p-d-f="generarPDF"
      :generar-p-d-f-interval="generarPDFInterval"
    />

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
import AvisosTitularsVigilancies from '../components/vigilancies/AvisosTitularsVigilancies.vue'
import AvisErrorCarrega from '../components/AvisErrorCarrega.vue'
import { useCarregaVigilancies } from '../composables/useCarregaVigilancies'
import { useAssignacioVigilancies } from '../composables/useAssignacioVigilancies.js'
import { useEdicioVigilancies } from '../composables/useEdicioVigilancies.js'
import { useFiltresVigilancies } from '../composables/useFiltresVigilancies.js'
import { useDisponiblesVigilancies } from '../composables/useDisponiblesVigilancies.js'
import PdfVigilanciesDialogs from '../components/vigilancies/PdfVigilanciesDialogs.vue'
import { usePdfVigilancies } from '../composables/usePdfVigilancies.js'
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { dataTreball } from '../dataTreball'
import { dataIso } from '../dates'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useConfirmaEsborrar } from '../composables/useConfirmaEsborrar'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import Message from 'primevue/message'
import ConfirmDialog from 'primevue/confirmdialog'
import Badge from 'primevue/badge'
import ConflicteDialog from '../components/ConflicteDialog.vue'
import FiltreAula from '../components/vigilancies/FiltreAula.vue'
import FormulariVigilancia from '../components/vigilancies/FormulariVigilancia.vue'
import TaulaVigilancies from '../components/vigilancies/TaulaVigilancies.vue'
import { useAjudaVigilant } from '../composables/useAjudaVigilant'
import { useOrdreFiles } from '../composables/useOrdreFiles'
import { useDialegsInterns } from '../dialegsInterns'

const emit = defineEmits(['anar-substitucions'])
const toast = useToast()
const confirm = useConfirm()
const confirmaEsborrar = useConfirmaEsborrar()
const { t, locale } = useI18n()

const vigilancies = ref([])
const problemes = ref([])

const obreConfiguracioExamens = () => window.dispatchEvent(new CustomEvent('obre-configuracio-examens'))

const seleccionades = ref([])
const substitucionsCount = ref(0)
const loading = ref(false)
const error = ref(null)

const professors = ref([])
const hores = ref([])
const nivells = ref([])

const configCarregada = ref(false)
const aules = ref([])
const grupsPerNivell = ref({})
const tipusExamens = ref([])
const tipusPerNivell = ref({})

const dataISO = computed(() => dataIso(dataTreball.value))

const dataFormatada = computed(() => {
  return dataTreball.value.toLocaleDateString(locale.value || 'ca-ES', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
})

const { informatiusVigFiltrats, confirmacioImportants, mostrarDialogPDF, mostrarDialogInterval, generantPDF, generantPDFInterval, mostrarDialogValidacionsVig, validacionsVig, conflictesVigFiltrats, warningsVigFiltrats, pdfConfig, intervalConfig, opcionsNivellsPdfDia, opcionsNivellsPdfInterval, mostrarDialegPDF, mostrarDialegInterval, generarPDF, continuarPDFVig, cancelarPDFVig, generarPDFInterval } = usePdfVigilancies({
  dataISO, dataTreball, nivells, vigilancies, toast, t
})

const collator = computed(() => new Intl.Collator(locale.value || 'ca', { sensitivity: 'base' }))

const { carregarDisponibles, carregarDisponiblesPerLlista, refrescarDisponiblesHora, getDisponiblesPerHora, getVigilantLabel } = useDisponiblesVigilancies({
  dataISO, professors, vigilancies, locale, collator, t
})

const { allLabel, statusOptions, filtreLevell, filtreHora, filtreEstat, filtreAula, etiquetaFiltre, filtresActius, vigilanciesAssignades, vigilanciesPendents, vigilanciesFiltrades, aulesDelFiltre } = useFiltresVigilancies({
  vigilancies, aules, collator, t
})

const problemesVisibles = computed(() => {
  const ids = new Set(vigilanciesFiltrades.value.map(v => String(v.id)))
  return problemes.value.filter(p => !p.files.length || p.files.some(id => ids.has(id)))
})

const { ressaltades, ressalta } = useOrdreFiles()
const { oblida: oblidaAjudes } = useAjudaVigilant()

const opcionsFiles = computed(() => ({
  hores: hores.value,
  nivells: nivells.value,
  aules: aules.value,
  tipusDe: (nivell) => getTipusOptions(nivell, true),
  grupsDe: (nivell) => getGrupsPerNivell(nivell)
}))
const disponiblesDe = (fila) => getDisponiblesPerHora(fila.hora, fila.tipus, fila.grups, fila.aula, fila.id)
const etiquetaVigilantDe = (fila) =>
  fila.vigilant ? getVigilantLabel(fila.hora, fila.vigilant, fila.tipus, fila.grups, fila.aula, fila.id) : ''

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

const publicaConfig = (config) => {
  professors.value = [...(config.professors || [])].sort((a, b) => collator.value.compare(a, b))
  hores.value = config.hores
  nivells.value = config.nivells
  aules.value = config.aules
  grupsPerNivell.value = config.grups_per_nivell
  tipusExamens.value = config.tipus_examens
  tipusPerNivell.value = config.tipus_per_nivell || {}
  configCarregada.value = true
}
const { carregarVigilancies, carregarSubstitucionsCount } = useCarregaVigilancies({
  dataISO, loading, error, vigilancies, seleccionades, substitucionsCount, problemes,
  carregarDisponiblesPerLlista, publicaConfig, oblidaAjudes, t
})

const anarASubstitucions = () => {
  emit('anar-substitucions')
}

const { mostrarDialogConflicte, gestionarConflicte, executarOverwrite, canviaCamp, confirmarEliminar, confirmarEliminarSeleccionades, mostrarFormulariNova, creantVigilancia, propostaNova, afegirNovaVigilancia, disponiblesDelFormulari, creaVigilancia, afegirVigilanciaDesprés, mouFiles } = useEdicioVigilancies({
  dataISO, vigilancies, seleccionades, vigilanciesFiltrades, hores, opcionsFiles, toast, t, confirmaEsborrar, oblidaAjudes, ressalta, carregarVigilancies, carregarSubstitucionsCount, refrescarDisponiblesHora, carregarDisponibles, getDisponiblesPerHora
})

const { titularsHoraLliure, vigilanciesSenseTitular, posantTitular, assignantTitulars, assignantPendents, ordenant, posaTitularHoraLliure, assignarTitulars, assignarPendents, confirmarNetejar, ordenarPerHora, idsTitularsHoraLliure } = useAssignacioVigilancies({
  dataISO, vigilancies, toast, t, confirm, confirmaEsborrar, carregarVigilancies
})

// «Enrere» tanca aquests diàlegs com la creu (dialegsInterns.js)
useDialegsInterns({
  'vigilancies-nova': mostrarFormulariNova,
  'vigilancies-pdf': mostrarDialogPDF,
  'vigilancies-pdf-avisos': mostrarDialogValidacionsVig,
  'vigilancies-pdf-interval': mostrarDialogInterval,
})

watch(dataTreball, async () => {
  titularsHoraLliure.value = []
  vigilanciesSenseTitular.value = []
  await carregarVigilancies()
})

onMounted(async () => {
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

/* Titulars amb l'hora lliure: l'avís i les seves files, fins que es decideix */
.titulars-hora-lliure ul {
  margin: 0.25rem 0 0;
  padding-left: 1.25rem;
}

/* Amb un filtre posat no es pot canviar l'ordre de les files */
.avis-ordre-filtres {
  margin: 0 0 0.75rem;
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
