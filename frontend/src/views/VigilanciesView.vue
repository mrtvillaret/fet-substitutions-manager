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

    <!-- Titulars que no s'han posat perquè tenien l'hora lliure: ho decideix qui fa les vigilàncies -->
    <Message
      v-if="!loading && !error && titularsHoraLliure.length"
      severity="warn"
      :closable="true"
      class="titulars-hora-lliure"
      @close="titularsHoraLliure = []"
    >
      <div>{{ $t('vigilancies.freeHourOwners.title', { count: titularsHoraLliure.length }, titularsHoraLliure.length) }}</div>
      <ul>
        <li v-for="item in titularsHoraLliure" :key="item.vigilancia_id">
          {{ item.hora }} · {{ item.grups }} · {{ item.tipus }} — <strong>{{ item.titular }}</strong>
          <Button
            :label="$t('vigilancies.freeHourOwners.assign')"
            size="small"
            text
            :loading="posantTitular === item.vigilancia_id"
            @click="posaTitularHoraLliure(item)"
          />
        </li>
      </ul>
    </Message>

    <!-- Vigilàncies que la configuració d'exàmens no deixa definides -->
    <Message
      v-if="!loading && !error && vigilanciesSenseTitular.length"
      severity="info"
      :closable="true"
      class="titulars-hora-lliure"
      @close="vigilanciesSenseTitular = []"
    >
      <div>{{ $t('vigilancies.withoutOwner.title', { count: vigilanciesSenseTitular.length }, vigilanciesSenseTitular.length) }}</div>
      <ul>
        <li v-for="item in vigilanciesSenseTitular" :key="item.vigilancia_id">
          {{ item.hora }} · {{ item.grups }} · {{ item.tipus }} — {{ $t(`vigilancies.withoutOwner.${item.motiu}`) }}
        </li>
      </ul>
      <Button
        :label="$t('vigilancies.withoutOwner.openConfig')"
        icon="pi pi-cog"
        size="small"
        text
        @click="obreConfiguracioExamens"
      />
    </Message>

    <!-- Carregant: només la primera vegada; amb files ja carregades, la taula es
         queda i mostra la càrrega a sobre (tornar-la a crear costava 1,5 s) -->
    <div v-if="loading && !vigilancies.length" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('vigilancies.loading') }}</p>
    </div>

    <div v-else-if="error" class="error-message">
      <Message severity="error" :closable="false">{{ error }}</Message>
    </div>

    <!-- Taula de vigilàncies: agrupada per hores, en l'ordre desat -->
    <template v-else>
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

        <PdfOpcionsComunes
          v-model:config="pdfConfig"
          prefix="vig"
          :opcions-propies="[{ clau: 'includeSubstitucions', etiqueta: 'vigilancies.dialogs.includeSubstitucions' }]"
        />
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

        <PdfOpcionsComunes
          v-model:config="intervalConfig"
          prefix="interval"
          amb-dia-per-pagina
          :opcions-propies="[
            { clau: 'includeWeekends', etiqueta: 'vigilancies.dialogs.includeWeekends' },
            { clau: 'includeEmptyDays', etiqueta: 'vigilancies.dialogs.includeEmpty' },
            { clau: 'includeSubstitucions', etiqueta: 'vigilancies.dialogs.includeSubstitucions' }
          ]"
        />
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
import { ambDataTreball, dataTreball } from '../dataTreball'
import { dataIso } from '../dates'
import { jaAvisat } from '../errorsApi'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useConfirmaEsborrar } from '../composables/useConfirmaEsborrar'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import Message from 'primevue/message'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import MultiSelect from 'primevue/multiselect'
import Calendar from 'primevue/calendar'
import PdfOpcionsComunes from '../components/PdfOpcionsComunes.vue'
import { aplicaPreferencies, midaPerDefecte, parametresComuns } from '../pdfOpcions'
import Badge from 'primevue/badge'
import ConflicteDialog from '../components/ConflicteDialog.vue'
import FiltreAula from '../components/vigilancies/FiltreAula.vue'
import FormulariVigilancia from '../components/vigilancies/FormulariVigilancia.vue'
import TaulaVigilancies from '../components/vigilancies/TaulaVigilancies.vue'
import * as apiVigilancies from '../api/vigilancies'
import { useAjudaVigilant } from '../composables/useAjudaVigilant'
import { useOrdreFiles } from '../composables/useOrdreFiles'

const emit = defineEmits(['anar-substitucions'])
const toast = useToast()
const confirm = useConfirm()
const confirmaEsborrar = useConfirmaEsborrar()
const { t, locale } = useI18n()

// State
const vigilancies = ref([])
// Titulars que «Assigna titulars» no ha posat perquè tenien l'hora lliure
const titularsHoraLliure = ref([])
// Vigilàncies sense un titular definit a la configuració d'exàmens (motiu)
const vigilanciesSenseTitular = ref([])
const obreConfiguracioExamens = () => window.dispatchEvent(new CustomEvent('obre-configuracio-examens'))
const posantTitular = ref(null)
const seleccionades = ref([])
const substitucionsCount = ref(0)
const loading = ref(false)
const error = ref(null)
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
  format: 'hores',
  midaLletra: midaPerDefecte('hores'),
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
  format: 'hores',
  midaLletra: midaPerDefecte('hores'),
  diaPerPagina: false,
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
const filtreAula = ref(allLabel.value)
// El nom del filtre dins del seu valor: «Nivell: tots», «Hora: 08:00»...
const etiquetaFiltre = (clau, valor) =>
  !valor || valor === allLabel.value
    ? t(`vigilancies.filters.${clau}All`)
    : t(`vigilancies.filters.${clau}Value`, { valor })
// Amb un filtre posat no es pot canviar l'ordre: no és clar on aniria la fila
const filtresActius = computed(() =>
  [filtreLevell.value, filtreHora.value, filtreEstat.value, filtreAula.value].some(f => f && f !== allLabel.value)
)

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
  if (filtreAula.value === oldVal) {
    filtreAula.value = newVal
  }
})

// Computed
const dataISO = computed(() => dataIso(dataTreball.value))

const dataFormatada = computed(() => {
  return dataTreball.value.toLocaleDateString(locale.value || 'ca-ES', {
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

// Les vigilàncies que es veuen, en l'ordre desat (el backend les dona per
// hora i, dins de cada hora, per l'ordre de les files). La taula les agrupa
// per hores; no s'hi reordena res.
const vigilanciesFiltrades = computed(() => {
  let result = vigilancies.value

  if (filtreLevell.value && filtreLevell.value !== allLabel.value) {
    result = result.filter(v => v.nivell === filtreLevell.value)
  }
  if (filtreHora.value && filtreHora.value !== allLabel.value) {
    result = result.filter(v => v.hora === filtreHora.value)
  }
  if (filtreEstat.value === statusAssignedLabel.value) {
    result = result.filter(v => v.vigilant && v.vigilant.trim())
  } else if (filtreEstat.value === statusPendingLabel.value) {
    result = result.filter(v => !v.vigilant || !v.vigilant.trim())
  }
  if (filtreAula.value && filtreAula.value !== allLabel.value) {
    result = result.filter(v => v.aula === filtreAula.value)
  }
  return result
})

const { ressaltades, ressalta } = useOrdreFiles()
const { oblida: oblidaAjudes } = useAjudaVigilant()

// El que necessita cada fila per als seus desplegables
const opcionsFiles = computed(() => ({
  hores: hores.value,
  nivells: nivells.value,
  aules: aules.value,
  tipusDe: (nivell) => getTipusOptions(nivell, true),
  grupsDe: (nivell) => getGrupsPerNivell(nivell)
}))
// La mateixa llista per a les files amb els mateixos disponibles (veure getDisponiblesPerHora)
const disponiblesDe = (fila) => getDisponiblesPerHora(fila.hora, fila.tipus, fila.grups, fila.aula)
const etiquetaVigilantDe = (fila) =>
  fila.vigilant ? getVigilantLabel(fila.hora, fila.vigilant, fila.tipus, fila.grups, fila.aula) : ''
// Les aules de la configuració i les que ja surten a les files (p.ex. «ENLLAÇ»)
const aulesDelFiltre = computed(() =>
  [...new Set([...aules.value, ...vigilancies.value.map(v => v.aula)].filter(Boolean))]
    .sort((a, b) => collator.value.compare(a, b))
)
const idsTitularsHoraLliure = computed(() => new Set(titularsHoraLliure.value.map(item => String(item.vigilancia_id))))

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

// `substitueix`: la memòria es refà sencera amb la resposta (en recarregar el
// dia); si no, s'hi afegeixen les claus noves. `alhora`: el que s'ha d'aplicar
// en el mateix moment que els disponibles (el llistat nou), perquè la taula es
// pinti un sol cop.
const carregarDisponiblesPerLlista = async (llistaVigilancies = [], { substitueix = false, alhora = null } = {}) => {
  if (!llistaVigilancies.length) {
    alhora?.()
    if (substitueix) disponiblesPerHora.value = {}
    return
  }

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
  if (!queries.length) {
    alhora?.()
    return
  }

  try {
    const response = await axios.post(`/api/vigilancies/${dataISO.value}/disponibles-batch`, {
      queries
    })
    const results = response.data?.results || {}
    const novaCache = substitueix ? {} : { ...disponiblesPerHora.value }

    for (const [key, value] of Object.entries(results)) {
      const disponibles = Array.isArray(value) ? value : []
      novaCache[key] = disponibles
      const horaKey = key.includes('|') ? key.split('|')[0] : key
      if (!novaCache[horaKey]) {
        novaCache[horaKey] = disponibles
      }
    }
    alhora?.()
    disponiblesPerHora.value = novaCache
  } catch (err) {
    console.error('Error en batch de disponibles, fallback a crides individuals:', err)
    alhora?.()
    if (substitueix) disponiblesPerHora.value = {}
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

// Les opcions ordenades de cada llista de disponibles, calculades un sol cop:
// la mateixa llista per a totes les files que la fan servir. Així, quan es
// recarreguen els disponibles d'una hora, les files de les altres hores reben
// la mateixa llista i no es tornen a pintar.
const opcionsOrdenades = new WeakMap()
const SENSE_DISPONIBLES = []

const getDisponiblesPerHora = (hora, tipus = null, grups = null, aula = null) => {
  // Retornar disponibles amb tipus, grups i aula per detectar titulars
  const horaNorm = String(hora || '').trim()
  const cacheKey = getDisponiblesCacheKey(horaNorm, tipus, grups, aula)

  // Buscar primer amb la clau específica (amb titular), sinó la genèrica
  const disponibles = disponiblesPerHora.value[cacheKey] || disponiblesPerHora.value[horaNorm] || SENSE_DISPONIBLES
  const desades = opcionsOrdenades.get(disponibles)
  if (desades && desades.idioma === locale.value) return desades.opcions

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
  const opcions = [
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
  opcionsOrdenades.set(disponibles, { idioma: locale.value, opcions })
  return opcions
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
    const response = await axios.get('/api/vigilancies/config', ambDataTreball())
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
  seleccionades.value = []
  oblidaAjudes()

  try {
    const llista = await apiVigilancies.llista(dataISO.value)

    // Disponibles de totes les files, recalculats amb les noves assignacions.
    // La memòria se substitueix en arribar la resposta (buidar-la abans feia
    // parpellejar els noms dels vigilants), i el llistat es posa en el mateix
    // moment: la taula es pinta un sol cop.
    await carregarDisponiblesPerLlista(llista, { substitueix: true, alhora: () => { vigilancies.value = llista } })
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

// Només el llistat (l'ordre i els updated_at nous), sense recalcular els disponibles
const recarregaLlistat = async () => {
  vigilancies.value = await apiVigilancies.llista(dataISO.value)
}

// Un camp d'una fila de la taula: es canvia i es desa
const canviaCamp = async (fila, camp, valor) => {
  const horaAbans = fila.hora
  fila[camp] = valor
  await actualitzarVigilancia(fila, { horaAbans })
}

// `horaAbans`: si la fila canvia d'hora, va al final del bloc de l'hora nova
// (ho fa el backend), es ressalta i la pantalla s'hi desplaça
const actualitzarVigilancia = async (vigilancia, { horaAbans = vigilancia.hora } = {}) => {
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

    oblidaAjudes()
    if (horaAbans !== vigilancia.hora) {
      await recarregaLlistat()
      await refrescarDisponiblesHora(horaAbans)
      await refrescarDisponiblesHora(vigilancia.hora)
      ressalta(vigilancia.id)
    } else {
      // Disponibles de l'hora afectada, perquè els candidats siguin coherents
      await refrescarDisponiblesHora(vigilancia.hora)
    }

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

const confirmarEliminar = (vigilancia) => {
  confirmaEsborrar({
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
  confirmaEsborrar({
    message: t('vigilancies.confirm.deleteSelectedMessage', { count }, count),
    header: t('common.confirmDelete'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('vigilancies.actions.deleteSelected', { count }),
    rejectLabel: t('common.cancel'),
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
          detail: t('vigilancies.messages.deletedSelected', { count: llistaAEliminar.length }, llistaAEliminar.length),
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

// Posa com a vigilant, només en aquella fila, un titular que tenia l'hora lliure
const posaTitularHoraLliure = async (item) => {
  const vigilancia = vigilancies.value.find(v => String(v.id) === String(item.vigilancia_id))
  posantTitular.value = item.vigilancia_id
  try {
    await axios.put(`/api/vigilancies/${dataISO.value}/${item.vigilancia_id}`, {
      vigilant: item.titular,
      updated_at: vigilancia?.updated_at
    })
    titularsHoraLliure.value = titularsHoraLliure.value.filter(x => x.vigilancia_id !== item.vigilancia_id)
    toast.add({ severity: 'success', summary: t('vigilancies.freeHourOwners.assigned'), detail: `${item.titular} · ${item.hora} · ${item.grups}`, life: 3000 })
    await carregarVigilancies()
  } catch (err) {
    console.error('Error posant el titular:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: err.response?.status === 409 ? t('vigilancies.freeHourOwners.conflict') : (err.response?.data?.detail || t('vigilancies.errors.assignOwners')),
      life: 5000
    })
    await carregarVigilancies()
  } finally {
    posantTitular.value = null
  }
}

// «Nova vigilància»: el formulari, amb l'hora, el nivell i el tipus de la darrera fila
const mostrarFormulariNova = ref(false)
const creantVigilancia = ref(false)
const propostaNova = ref({})

const afegirNovaVigilancia = () => {
  const darrera = vigilanciesFiltrades.value[vigilanciesFiltrades.value.length - 1]
  propostaNova.value = {
    hora: darrera?.hora || hores.value[0] || '',
    nivell: darrera?.nivell || '',
    tipus: darrera?.tipus || ''
  }
  mostrarFormulariNova.value = true
}

// Els disponibles d'una consulta del formulari (hora i examen), amb l'opció buida
const disponiblesDelFormulari = async ({ hora, tipus, grups, aula }) => {
  await carregarDisponibles(hora, false, tipus, grups, aula)
  return getDisponiblesPerHora(hora, tipus, grups, aula)
}

const creaVigilancia = async (fila) => {
  creantVigilancia.value = true
  try {
    const nova = await apiVigilancies.crea(dataISO.value, fila)
    mostrarFormulariNova.value = false
    toast.add({ severity: 'success', summary: t('common.created'), detail: t('vigilancies.messages.added'), life: 2000 })
    await carregarVigilancies()
    if (nova?.id) ressalta(nova.id)
  } catch (err) {
    console.error('Error creant vigilància:', err)
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('vigilancies.errors.create'), life: 3000 })
  } finally {
    creantVigilancia.value = false
  }
}

// El «+» de cada fila: una còpia just a sota («Nova vigilància» la posa al final del bloc)
const afegirVigilanciaDesprés = async (vigilancia) => {
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
      tipus: esPlaceholder(novaVig.tipus, t('vigilancies.placeholders.type')) ? '' : (novaVig.tipus || ''),
      despres_de: String(vigilancia.id)
    }

    // La còpia va just a sota de la fila que copia (`despres_de`) i es ressalta
    const nova = await apiVigilancies.crea(dataISO.value, payload)

    toast.add({
      severity: 'success',
      summary: t('common.created'),
      detail: t('vigilancies.messages.added'),
      life: 2000
    })

    await carregarVigilancies()
    if (nova?.id) ressalta(nova.id)
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

// Nou ordre de les files d'una hora (arrossegant o amb ↑/↓). Es mostra de
// seguida; si el servidor no l'accepta (la taula ha canviat), es recarrega.
const mouFiles = async (hora, ids) => {
  const posicio = new Map(ids.map((id, i) => [String(id), i]))
  const deLhora = vigilancies.value.filter(v => v.hora === hora)
    .sort((a, b) => posicio.get(String(a.id)) - posicio.get(String(b.id)))
  let k = 0
  vigilancies.value = vigilancies.value.map(v => (v.hora === hora ? deLhora[k++] : v))
  try {
    await apiVigilancies.desaOrdre(dataISO.value, hora, ids)
    await recarregaLlistat() // desar l'ordre canvia els updated_at
  } catch (err) {
    console.error('Error desant l\'ordre:', err)
    toast.add({
      severity: err.response?.status === 409 ? 'warn' : 'error',
      summary: err.response?.status === 409 ? t('common.warning') : t('common.error'),
      detail: err.response?.status === 409 ? t('vigilancies.messages.orderChanged') : t('vigilancies.errors.order'),
      life: 4000
    })
    await carregarVigilancies()
  }
}

// Mètodes d'assignació automàtica

const assignarTitulars = async () => {
  assignantTitulars.value = true

  try {
    const response = await axios.post(`/api/vigilancies/${dataISO.value}/assign/titulars`)
    titularsHoraLliure.value = response.data.titulars_hora_lliure || []
    vigilanciesSenseTitular.value = response.data.vigilancies_sense_titular || []

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
        detail: t('vigilancies.messages.assignedFreeDetail', { count: assignats }, assignats),
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
        acceptLabel: t('vigilancies.confirm.assignAvailableAccept', { count: pendents }, pendents),
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
  confirmaEsborrar({
    message: t('vigilancies.confirm.clearMessage'),
    header: t('vigilancies.confirm.clearTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('vigilancies.confirm.clearAccept'),
    rejectLabel: t('common.cancel'),
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

// «Ordena» desa l'ordre automàtic: si hi havia retocs fets a mà, ho demana abans
const ordenarPerHora = async () => {
  let manual = false
  try {
    manual = await apiVigilancies.teOrdreManual(dataISO.value)
  } catch (err) {
    console.error('Error consultant l\'ordre:', err)
  }
  if (!manual) return ordena()
  confirm.require({
    header: t('vigilancies.confirm.sortManualTitle'),
    message: t('vigilancies.confirm.sortManualMessage'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('vigilancies.actions.sort'),
    rejectLabel: t('common.cancel'),
    accept: ordena
  })
}

const ordena = async () => {
  ordenant.value = true

  try {
    const response = await axios.post(`/api/vigilancies/${dataISO.value}/sort`)

    toast.add({
      severity: 'success',
      summary: t('vigilancies.messages.sortedTitle'),
      detail: response.data.message,
      life: 3000
    })

    // Ordenar no canvia qui està disponible ni les substitucions: només cal
    // el llistat (amb l'ordre i els updated_at nous)
    const llistat = await axios.get(`/api/vigilancies/${dataISO.value}`)
    vigilancies.value = llistat.data
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
const carregarPreferenciesPdf = async () => {
  try {
    const response = await axios.get('/api/pdf/preferences', { _silent: true })
    aplicaPreferencies(
      pdfConfig,
      response.data?.vigilancies,
      ['format', 'midaLletra', 'showComments', 'showHours', 'compress', 'includeSubstitucions']
    )
    aplicaPreferencies(
      intervalConfig,
      response.data?.vigilancies_interval,
      ['format', 'midaLletra', 'diaPerPagina', 'includeWeekends', 'includeEmptyDays', 'showComments', 'showHours', 'compress', 'includeSubstitucions']
    )
  } catch (error) {
    console.error('Error carregant preferències PDF:', error)
  }
}

const desarPreferenciesPdf = async (tipus) => {
  try {
    if (tipus === 'vigilancies') {
      await axios.put('/api/pdf/preferences', {
        vigilancies: {
          format: pdfConfig.value.format,
          midaLletra: pdfConfig.value.midaLletra,
          showComments: pdfConfig.value.showComments,
          showHours: pdfConfig.value.showHours,
          compress: pdfConfig.value.compress,
          includeSubstitucions: pdfConfig.value.includeSubstitucions
        }
      }, { _silent: true })
      return
    }
    if (tipus === 'interval') {
      await axios.put('/api/pdf/preferences', {
        vigilancies_interval: {
          format: intervalConfig.value.format,
          midaLletra: intervalConfig.value.midaLletra,
          diaPerPagina: intervalConfig.value.diaPerPagina,
          includeWeekends: intervalConfig.value.includeWeekends,
          includeEmptyDays: intervalConfig.value.includeEmptyDays,
          showComments: intervalConfig.value.showComments,
          showHours: intervalConfig.value.showHours,
          compress: intervalConfig.value.compress,
          includeSubstitucions: intervalConfig.value.includeSubstitucions
        }
      }, { _silent: true })
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
  intervalConfig.value.dataInici = dataTreball.value
  intervalConfig.value.dataFinal = dataTreball.value
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
    // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
    if (!jaAvisat(err)) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: err.response?.data?.detail || t('vigilancies.errors.generatePdf'),
        life: 5000
      })
    }
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
      ...parametresComuns(pdfConfig.value),
      nivells: nivellsParam,
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
    // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
    if (!jaAvisat(err)) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: err.response?.data?.detail || t('vigilancies.errors.generatePdf'),
        life: 5000
      })
    }
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
        const formatDate = dataIso

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
      ...parametresComuns(intervalConfig.value),
      include_weekends: intervalConfig.value.includeWeekends,
      include_empty_days: intervalConfig.value.includeEmptyDays,
      dia_per_pagina: intervalConfig.value.diaPerPagina,
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
    // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
    if (!jaAvisat(err)) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: err.response?.data?.detail || t('vigilancies.errors.generatePdfInterval'),
        life: 5000
      })
    }
  } finally {
    generantPDFInterval.value = false
  }
}

// Watch per canvis de data
watch(dataTreball, async () => {
  titularsHoraLliure.value = []
  vigilanciesSenseTitular.value = []
  await carregarConfig()   // professors i hores de l'horari vigent aquell dia
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
