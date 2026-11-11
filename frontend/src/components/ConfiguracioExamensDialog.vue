<template>
  <Dialog
    class="dialog-stable-height"
    :visible="visible"
    @update:visible="canviaVisible"
    :header="$t('examConfig.title')"
    :modal="true"
    :style="{ width: '900px', maxHeight: '90vh' }"
    :closable="true"
  >
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('common.loadingConfig') }}</p>
    </div>

    <div v-else class="config-container">
      <!-- Horari d'on surten professors i propostes: el de la primera data planificada -->
      <Message v-if="horariPlanificacio?.versio_des_de && !horariPlanificacio.sense_dates" severity="info" :closable="false">
        {{ $t('scheduler.view.scheduleUsed', { data: dataAmbAny(horariPlanificacio.data_referencia), desDe: dataAmbAny(horariPlanificacio.versio_des_de) }) }}
      </Message>
      <TabView class="app-tabview app-tabview--dialog">
        <!-- TAB 0: IMPORTACIÓ / EXPORTACIÓ -->
        <TabPanel :header="$t('examConfig.tabs.import')">
          <div class="tab-content">
            <Message severity="info" :closable="false">
              {{ $t('examConfig.import.tabIntro') }}
            </Message>

            <div class="import-section">
              <h4>{{ $t('examConfig.import.mainTitle') }}</h4>
              <p class="import-section-desc">{{ $t('examConfig.import.mainDesc') }}</p>
              <div class="import-buttons-row">
                <Button
                  :label="$t('examConfig.import.button')"
                  icon="pi pi-download"
                  @click="obrirImportacio"
                  class="p-button-help"
                />
                <Button
                  :label="$t('examConfig.import.exportCsv')"
                  icon="pi pi-file-export"
                  @click="exportarAssignacionsCsv"
                  class="p-button-secondary"
                  :disabled="assignacions.length === 0"
                />
                <Button
                  :label="$t('examConfig.import.importCsv')"
                  icon="pi pi-file-import"
                  @click="triarFitxerCsv"
                  class="p-button-secondary"
                />
                <input
                  :aria-label="$t('examConfig.import.importCsv')" ref="inputCsvRef"
                  type="file"
                  accept=".csv"
                  style="display: none"
                  @change="onFitxerCsvSeleccionat"
                />
              </div>
            </div>
          </div>
        </TabPanel>

        <!-- TAB 1: NIVELLS -->
        <TabPanel :header="$t('examConfig.tabs.levels')">
          <NivellsExamens
            v-model:mostrarDialogAfegirNivell="mostrarDialogAfegirNivell"
            v-model:nouNivell="nouNivell"
            :nivells="nivells"
            :afegir-nivell="afegirNivell"
            :eliminar-nivell="eliminarNivell"
          />
        </TabPanel>

        <!-- TAB 2: GRUPS -->
        <TabPanel :header="$t('examConfig.tabs.groups')">
          <GrupsExamens
            v-model:nivellSeleccionatGrups="nivellSeleccionatGrups"
            v-model:mostrarDialogAfegirGrup="mostrarDialogAfegirGrup"
            v-model:nouGrup="nouGrup"
            :nivells="nivells"
            :grups="grups"
            :carregar-grups="carregarGrups"
            :afegir-grup="afegirGrup"
            :preparar-renom-grup="prepararRenomGrup"
            :eliminar-grup="eliminarGrup"
          />
        </TabPanel>

        <!-- TAB 3: ASSIGNATURES -->
        <TabPanel :header="$t('examConfig.tabs.subjects')">
          <AssignaturesExamens
            v-model:nivellSeleccionat="nivellSeleccionat"
            v-model:mostrarDialogAfegirAssignatura="mostrarDialogAfegirAssignatura"
            v-model:novaAssignatura="novaAssignatura"
            :nivells="nivells"
            :assignatures="assignatures"
            :carregar-assignatures="carregarAssignatures"
            :afegir-assignatura="afegirAssignatura"
            :preparar-renom-assignatura="prepararRenomAssignatura"
            :eliminar-assignatura="eliminarAssignatura"
          />
        </TabPanel>

        <!-- TAB 4: AULES -->
        <TabPanel :header="$t('examConfig.tabs.rooms')">
          <AulesExamens
            v-model:mostrarDialogAfegirAula="mostrarDialogAfegirAula"
            v-model:novaAula="novaAula"
            :aules="aules"
            :afegir-aula="afegirAula"
            :preparar-renom-aula="prepararRenomAula"
            :eliminar-aula="eliminarAula"
          />
        </TabPanel>

        <!-- TAB 5: ASSIGNACIONS PROFESSOR-TITULAR -->
        <TabPanel :header="$t('examConfig.tabs.assignments')">
          <AssignacionsExamens
            v-model:filtreNivellAssignacions="filtreNivellAssignacions"
            v-model:filtreAssignaturaAssignacions="filtreAssignaturaAssignacions"
            v-model:filtreAulaAssignacions="filtreAulaAssignacions"
            :assignacions-obsoletes="assignacionsObsoletes"
            :assignacions="assignacions"
            :assignacions-filtrades="assignacionsFiltrades"
            :nivells="nivells"
            :assignatures-uniques="assignaturesUniques"
            :aules-del-filtre="aulesDelFiltre"
            :totes-assignatures="totesAssignatures"
            :tots-grups="totsGrups"
            :professors="professors"
            :aules="aules"
            :filtrar-assignacions="filtrarAssignacions"
            :treure-assignacions-obsoletes="treureAssignacionsObsoletes"
            :afegir-fila-assignacio="afegirFilaAssignacio"
            :eliminar-assignacions-filtrades="eliminarAssignacionsFiltrades"
            :eliminar-totes-assignacions="eliminarTotesAssignacions"
            :eliminar-assignacio="eliminarAssignacio"
            :on-cell-edit-complete="onCellEditComplete"
          />
        </TabPanel>

        <!-- TAB 6: AFINITATS -->
        <TabPanel :header="$t('examConfig.tabs.affinities')">
          <AfinitatsExamens
            v-model:afinitats="afinitats"
            :afegir-fila-afinitat="afegirFilaAfinitat"
            :eliminar-fila-afinitat="eliminarFilaAfinitat"
            :desar-afinitats="desarAfinitats"
          />
        </TabPanel>

      </TabView>
    </div>

    <EdicioCatalegsExamensDialogs
      v-model:esborrantAmbAssignacions="esborrantAmbAssignacions"
      v-model:mostrarDialogRenomItem="mostrarDialogRenomItem"
      v-model:renomValor="renomValor"
      :ELIMINAR="ELIMINAR"
      :item-editant="itemEditant"
      :esborra="esborra"
      :reanomenar-item="reanomenarItem"
    />

    <ImportacioExamensDialogs
      v-model:mostrarDialegImport="mostrarDialegImport"
      v-model:filtreNivellImport="filtreNivellImport"
      v-model:filtreAssignaturaImport="filtreAssignaturaImport"
      v-model:filtreEstatImport="filtreEstatImport"
      v-model:sobreescriuImportacio="sobreescriuImportacio"
      v-model:mostrarResumPrevi="mostrarResumPrevi"
      v-model:mostrarResumFinal="mostrarResumFinal"
      :carregant-propostes="carregantPropostes"
      :nivells-import="nivellsImport"
      :assignatures-import="assignaturesImport"
      :propostes-seleccionades="propostesSeleccionades"
      :propostes="propostes"
      :propostes-filtrades="propostesFiltrades"
      :drag-select-assignacions="dragSelectAssignacions"
      :previsualitzar-importacio="previsualitzarImportacio"
      :calculant-resum-previ="calculantResumPrevi"
      :resum-previ="resumPrevi"
      :resum-previ-sobreescriu="resumPreviSobreescriu"
      :exportar-assignacions-csv="exportarAssignacionsCsv"
      :confirmar-importacio-definitiva="confirmarImportacioDefinitiva"
      :important="important"
      :resum-final="resumFinal"
    />
    <template #footer>
      <Button
        :label="$t('common.close')"
        icon="pi pi-times"
        @click="tancar"
        class="p-button-text"
      />
    </template>
  </Dialog>
</template>

<script setup>
import ImportacioExamensDialogs from './examens/ImportacioExamensDialogs.vue'
import EdicioCatalegsExamensDialogs from './examens/EdicioCatalegsExamensDialogs.vue'
import AfinitatsExamens from './examens/AfinitatsExamens.vue'
import AssignacionsExamens from './examens/AssignacionsExamens.vue'
import AulesExamens from './examens/AulesExamens.vue'
import AssignaturesExamens from './examens/AssignaturesExamens.vue'
import GrupsExamens from './examens/GrupsExamens.vue'
import NivellsExamens from './examens/NivellsExamens.vue'
import { useAfinitatsExamens } from '../composables/useAfinitatsExamens.js'
import { useImportacioExamens } from '../composables/useImportacioExamens.js'
import { useAssignacionsExamens } from '../composables/useAssignacionsExamens.js'
import { useCatalegsExamens } from '../composables/useCatalegsExamens.js'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { dataAmbAny } from '../dates'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useConfirmaEsborrar } from '../composables/useConfirmaEsborrar'
import { useConfirmaSortida, useAvisTancarPestanya } from '../composables/useConfirmaSortida'
import Dialog from 'primevue/dialog'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Button from 'primevue/button'
import Message from 'primevue/message'

const toast = useToast()
const { t } = useI18n()
const confirm = useConfirm()
const confirmaEsborrar = useConfirmaEsborrar()

const props = defineProps({
  visible: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)

// Compartides amb els catàlegs perquè els renoms també actualitzen les files.
const assignacions = ref([])

const {
  nivells,
  itemEditant,
  mostrarDialogRenomItem,
  renomValor,
  mostrarDialogAfegirNivell,
  nouNivell,
  nivellSeleccionat,
  assignatures,
  mostrarDialogAfegirAssignatura,
  novaAssignatura,
  nivellSeleccionatGrups,
  grups,
  mostrarDialogAfegirGrup,
  nouGrup,
  aules,
  mostrarDialogAfegirAula,
  novaAula,
  totesAssignatures,
  totsGrups,
  professors,
  carregarNivells,
  carregarAssignatures,
  afegirNivell,
  ELIMINAR,
  esborrantAmbAssignacions,
  esborra,
  eliminarNivell,
  afegirAssignatura,
  eliminarAssignatura,
  carregarGrups,
  afegirGrup,
  eliminarGrup,
  carregarAules,
  afegirAula,
  eliminarAula,
  carregarTotesAssignatures,
  carregarTotsGrups,
  horariPlanificacio,
  carregarProfessors,
  prepararRenomAssignatura,
  prepararRenomGrup,
  prepararRenomAula,
  reanomenarItem,
} = useCatalegsExamens({
  toast, t, confirmaEsborrar, assignacions,
  carregarAssignacions: (...args) => carregarAssignacions(...args),
  filtrarAssignacions: (...args) => filtrarAssignacions(...args)
})

const {
  assignacionsFiltrades,
  filtreNivellAssignacions,
  filtreAssignaturaAssignacions,
  filtreAulaAssignacions,
  aulesDelFiltre,
  assignaturesUniques,
  assignacionsObsoletes,
  treureAssignacionsObsoletes,
  carregarAssignacions,
  filtrarAssignacions,
  afegirFilaAssignacio,
  onCellEditComplete,
  eliminarAssignacio,
  eliminarAssignacionsFiltrades,
  eliminarTotesAssignacions,
} = useAssignacionsExamens({
  assignacions, aules, toast, t, confirmaEsborrar
})

const {
  mostrarDialegImport,
  carregantPropostes,
  propostes,
  propostesSeleccionades,
  important,
  sobreescriuImportacio,
  filtreNivellImport,
  filtreAssignaturaImport,
  filtreEstatImport,
  nivellsImport,
  assignaturesImport,
  propostesFiltrades,
  dragSelectAssignacions,
  obrirImportacio,
  mostrarResumPrevi,
  resumPrevi,
  resumPreviSobreescriu,
  calculantResumPrevi,
  mostrarResumFinal,
  resumFinal,
  previsualitzarImportacio,
  confirmarImportacioDefinitiva,
  inputCsvRef,
  exportarAssignacionsCsv,
  triarFitxerCsv,
  onFitxerCsvSeleccionat,
} = useImportacioExamens({
  toast, t, confirm, carregarAssignacions
})

const {
  afinitats,
  teCanvis: afinitatsAmbCanvis,
  carregarAfinitats,
  afegirFilaAfinitat,
  eliminarFilaAfinitat,
  desarAfinitats,
} = useAfinitatsExamens({
  toast, t
})

const carregarTot = async () => {
  loading.value = true
  try {
    await carregarNivells()
    await carregarAules()
    await carregarTotesAssignatures()
    await carregarTotsGrups()
    await carregarProfessors()
    await carregarAssignacions()
    await carregarAfinitats()
  } catch (error) {
    console.error('Error carregant configuració:', error)
  } finally {
    loading.value = false
  }
}

// Afinitats sense desar: es pregunta abans de tancar (botó, creu o «Enrere»)
// i el navegador avisa abans de tancar la pestanya
const confirmaSortida = useConfirmaSortida()
const teCanvis = computed(() => props.visible && !loading.value && afinitatsAmbCanvis.value)
useAvisTancarPestanya(() => teCanvis.value)

const canviaVisible = async (visible) => {
  if (visible || await confirmaSortida(teCanvis.value)) emit('update:visible', visible)
}

const tancar = () => canviaVisible(false)

defineExpose({ teCanvis, tanca: tancar })

watch(() => props.visible, (newVal) => {
  if (newVal) {
    carregarTot()
  }
})
</script>

<style scoped src="./examens/configuracioExamens.css"></style>
