<template>
  <div class="tab-content" @click="handlePanelHeaderClick">
    <p class="info-text" style="margin-bottom: 1rem;">
      <i class="pi pi-info-circle"></i>
      {{ $t('config.priorities.introLine1') }}
      {{ $t('config.priorities.introLine2') }}
    </p>

    <!-- Indicador de quin XML/data s'està configurant (assignatures del selector) -->
    <p class="xml-indicator">
      <i class="pi pi-calendar"></i>
      <span>{{ $t('config.groups.xmlContext', { data: dataText }) }}</span>
      <span v-if="xmlDataInici"> · {{ $t('config.groups.xmlVersion', { versio: xmlVersioText }) }}</span>
    </p>

    <!-- SECCIÓ 1: Ordre de Categories -->
    <Panel
      :header="$t('config.priorities.orderTitle')"
      :toggleable="true"
      v-model:collapsed="panelsPrioritatsCollapsed.ordre"
      @toggle="guardarEstatPanels"
    >
      <div class="toolbar" style="margin-bottom: 0.5rem;">
        <Button
          :label="$t('config.priorities.moveUp')"
          @click="moureCategoriaAmunt"
          size="small"
          :disabled="categoriaSeleccionadaIndex === null || categoriaSeleccionadaIndex === 0"
          v-tooltip.top="$t('config.priorities.moveUpHint')"
        />
        <Button
          :label="$t('config.priorities.moveDown')"
          @click="moureCategoriaAvall"
          size="small"
          :disabled="categoriaSeleccionadaIndex === null || categoriaSeleccionadaIndex >= ordreCategories.length - 1"
          v-tooltip.top="$t('config.priorities.moveDownHint')"
        />
        <Button
          :label="$t('config.priorities.addCategory')"
          @click="mostrarDialogAfegirCategoria = true"
          size="small"
          class="p-button-success"
        />
        <Button
          :label="$t('common.delete')"
          @click="eliminarCategoria"
          size="small"
          class="p-button-danger"
          :disabled="categoriaSeleccionadaIndex === null"
        />
      </div>

      <DataTable
        :value="ordreCategories"
        v-model:selection="categoriaSeleccionada"
        selectionMode="single"
        @row-select="onCategoriaSelect"
        @row-unselect="onCategoriaUnselect"
        :stripedRows="true"
        class="p-datatable-sm"
      >
        <Column field="ordre" :header="$t('config.priorities.order')" style="width: 80px;">
          <template #body="slotProps">
            {{ slotProps.index + 1 }}
          </template>
        </Column>
        <Column field="activa" :header="$t('config.priorities.active')" style="width: 100px;">
          <template #body="slotProps">
            <Checkbox
              :aria-label="`${$t('config.priorities.active')} · ${slotProps.data.nom}`" v-model="slotProps.data.activa"
              :binary="true"
            />
          </template>
        </Column>
        <Column field="categories" :header="$t('config.priorities.categories')">
          <template #body="slotProps">
            {{ slotProps.data.categories.join(', ') }}
          </template>
        </Column>
      </DataTable>
    </Panel>

    <Divider />

    <!-- SECCIÓ 2: Pesos d'Aleatorietat per Categoria -->
    <Panel
      :header="$t('config.priorities.weightsTitle')"
      :toggleable="true"
      v-model:collapsed="panelsPrioritatsCollapsed.pesos"
      @toggle="guardarEstatPanels"
    >
      <p class="info-text" style="margin-bottom: 1rem;">
        <i class="pi pi-info-circle"></i>
        {{ $t('config.priorities.weightsHint') }}
      </p>

      <Accordion :multiple="true" :activeIndex="accordionActiveIndexes">
        <AccordionTab
          v-for="(cat, idx) in ordreCategories"
          :key="idx"
          :header="$t('config.priorities.categoryHeader', { index: idx + 1, items: cat.categories.join(', ') })"
        >
          <div class="categoria-pesos">
            <div v-for="(assignatura, aIdx) in cat.categories" :key="aIdx" class="assignatura-row">
              <div class="assignatura-header">
                <label>{{ assignatura || $t('common.empty') }}</label>
              </div>
              <div class="assignatura-controls">
                <InputNumber
                  :aria-label="assignatura" v-model="pesos[assignatura]"
                  :min="1"
                  :max="10"
                  suffix=" pes"
                  showButtons
                  buttonLayout="horizontal"
                  :step="1"
                />
                <Button
                  icon="pi pi-trash"
                  class="p-button-rounded p-button-text p-button-danger p-button-sm"
                  @click="eliminarAssignaturaCategoria(assignatura, idx)"
                  v-tooltip.top="$t('config.priorities.deleteSubject')"
                />
              </div>
              <small v-if="assignatura.toLowerCase() === 'alliberat'" class="field-hint">
                {{ $t('config.priorities.freeHint') }}
              </small>
            </div>

            <Button
              :label="$t('config.priorities.addSubjectToCategory', { index: idx + 1 })"
              @click="afegirAssignaturaCategoria(idx)"
              size="small"
              class="p-button-text"
              style="margin-top: 0.5rem;"
            />
          </div>
        </AccordionTab>
      </Accordion>
    </Panel>

    <Divider />

    <!-- SECCIÓ 3: Activitats No Substituibles -->
    <Panel
      :header="$t('config.priorities.noSubstTitle')"
      :toggleable="true"
      v-model:collapsed="panelsPrioritatsCollapsed.noSubst"
      @toggle="guardarEstatPanels"
    >
      <p class="info-text" style="margin-bottom: 1rem;">
        <i class="pi pi-info-circle"></i>
        {{ $t('config.priorities.noSubstHint') }}
      </p>

      <div class="toolbar" style="margin-bottom: 0.5rem;">
        <Tag severity="info" :value="$t('config.priorities.noSubstCount', { count: noSubstituir.length }, noSubstituir.length)" />
        <Button
          :label="$t('common.add')"
          icon="pi pi-plus"
          @click="obrirDialogNoSubstituir"
          size="small"
          class="p-button-success"
        />
      </div>

      <div class="no-subst-list">
        <Tag
          v-for="(item, idx) in noSubstituir"
          :key="idx"
          :value="item || $t('common.empty')"
          severity="secondary"
          v-tooltip.top="item === '' ? $t('config.priorities.noSubstEmptyHint') : null"
        >
          <template #default>
            {{ item || $t('common.empty') }}
            <small v-if="fiNoSubstituir[item]" class="no-subst-data">{{ $t('config.priorities.noSubstUntil', { data: fiNoSubstituir[item] }) }}</small>
            <i class="pi pi-times" style="margin-left: 0.5rem; cursor: pointer;" @click="eliminarNoSubstituir(item)"></i>
          </template>
        </Tag>
        <!-- Les que comencen més endavant: encara no valen avui -->
        <Tag
          v-for="entrada in futuresNoSubstituir"
          :key="'futura-' + entrada.assignatura + entrada.vigent_des_de"
          severity="warning"
        >
          <template #default>
            {{ entrada.assignatura || $t('common.empty') }}
            <small class="no-subst-data">{{ $t('config.priorities.noSubstFrom', { data: dataAmbAny(entrada.vigent_des_de) }) }}</small>
            <i class="pi pi-times" style="margin-left: 0.5rem; cursor: pointer;" @click="eliminarNoSubstituir(entrada.assignatura, entrada.vigent_des_de)"></i>
          </template>
        </Tag>
      </div>
    </Panel>

    <Divider />

    <!-- SECCIÓ 3b: Activitats alliberables (surten a «Grups i professors alliberats») -->
    <Panel
      :header="$t('config.priorities.freeableTitle')"
      :toggleable="true"
      v-model:collapsed="panelsPrioritatsCollapsed.alliberables"
      @toggle="guardarEstatPanels"
    >
      <p class="info-text" style="margin-bottom: 1rem;">
        <i class="pi pi-info-circle"></i>
        {{ $t('config.priorities.freeableHint') }}
      </p>
      <div class="freeable-toolbar">
        <InputText :aria-label="$t('config.priorities.freeableFilter')" v-model="filtreAlliberables" :placeholder="$t('config.priorities.freeableFilter')" class="freeable-filter" />
        <Button
          :label="$t('common.save')"
          icon="pi pi-check"
          size="small"
          class="p-button-success"
          :loading="desantAlliberables"
          @click="desarActivitatsAlliberables"
        />
      </div>
      <div class="freeable-list">
        <div v-for="act in activitatsFiltrades" :key="act" class="freeable-row">
          <div class="freeable-name">
            <Checkbox v-model="activitatsAlliberables" :inputId="`allib-${act}`" :value="act" />
            <label :for="`allib-${act}`">{{ act }}</label>
          </div>
          <div v-if="activitatsAlliberables.includes(act)">
            <Checkbox v-model="activitatsPerDefecte" :inputId="`perdef-${act}`" :value="act" />
            <label :for="`perdef-${act}`">{{ $t('config.priorities.freeableDefault') }}</label>
          </div>
        </div>
        <p v-if="!activitatsFiltrades.length" class="info-text">{{ $t('config.priorities.freeableNone') }}</p>
      </div>
      <p class="info-text" style="margin-top: 0.75rem;">{{ $t('config.priorities.freeableDefaultHint') }}</p>
    </Panel>

    <Divider />

    <!-- SECCIÓ 4: Llista de Disponibles (PDF) -->
    <Panel
      :header="$t('config.priorities.availableListTitle')"
      :toggleable="true"
      v-model:collapsed="panelsPrioritatsCollapsed.disponibles"
      @toggle="guardarEstatPanels"
    >
      <p class="info-text" style="margin-bottom: 1rem;">
        <i class="pi pi-info-circle"></i>
        {{ $t('config.priorities.availableListHint') }}
      </p>

      <div style="display: flex; flex-direction: column; align-items: center; gap: 0.75rem; padding: 2rem 0;">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <label :for="prefixEtiquetes + '-camp-1'" style="font-size: 0.875rem; font-weight: 600; color: #374151; white-space: nowrap;">
            {{ $t('config.priorities.startDate') }}
          </label>
          <input :id="prefixEtiquetes + '-camp-1'"
            type="date"
            v-model="dataInicialPDF"
            style="height: 36px; padding: 0 0.75rem; border: 1.5px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; outline: none;"
          />
          <span style="font-size: 0.8rem; color: #9ca3af;">
            {{ $t('config.priorities.startDateHint') }}
          </span>
        </div>
        <Button
          :label="$t('config.priorities.generateAllDaysPDF')"
          icon="pi pi-file-pdf"
          @click="generarPDFDisponiblesTotsDies"
          severity="danger"
          :loading="generantPDFDisponibles"
          size="large"
        />
      </div>
    </Panel>

    <!-- Botó desar -->
    <div style="display: flex; justify-content: center; margin-top: 1.5rem;">
      <Button
        :label="$t('config.priorities.saveAll')"
        @click="desarPrioitats"
        class="p-button-lg p-button-success"
        :loading="desantPrioritats"
        :disabled="!teCanvisPrioritats"
      />
    </div>

    <!-- Diàleg afegir no substituir -->
    <Dialog
      v-model:visible="mostrarDialogNoSubstituir"
      :header="$t('config.priorities.addNoSubstTitle')"
      :modal="true"
      :style="{ width: '500px' }"
      :breakpoints="{ '720px': '95vw' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-2'">{{ $t('config.priorities.selectSubjectXml') }}</label>
          <MultiSelect :filterInputProps="{ 'aria-label': $t('common.filterOptions') }" :aria-label="$t('config.priorities.selectSubjectXml')" :inputId="prefixEtiquetes + '-camp-2'"
            v-model="novesNoSubstituir"
            :options="opcionsNoSubst"
            optionLabel="label"
            optionValue="value"
            :placeholder="$t('config.priorities.selectSubjectPlaceholder')"
            :filter="true"
            display="chip"
            class="w-full"
          >
            <template #option="{ option }">
              <span v-tooltip.right="option.value === '' ? $t('config.priorities.noSubstEmptyHint') : null">
                {{ option.label }}
              </span>
            </template>
          </MultiSelect>
          <small class="field-hint">{{ $t('config.priorities.synthHint') }}</small>
          <!-- Informatiu: no impedeix desar -->
          <p v-if="avisAmbGrup.length" class="avis-amb-grup" role="status">
            <i class="pi pi-exclamation-triangle"></i>
            {{ $t('config.priorities.noSubstWithGroupWarning', { activitats: avisAmbGrup.join(', ') }, avisAmbGrup.length) }}
          </p>
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-data-no-subst'">{{ $t('config.priorities.noSubstChangeDate') }}</label>
          <Calendar :inputId="prefixEtiquetes + '-camp-data-no-subst'"
            v-model="dataCanvisNoSubst"
            dateFormat="dd/mm/yy"
            :showIcon="true"
            class="w-full"
          />
          <small class="field-hint">{{ $t('config.priorities.noSubstChangeDateHint') }}</small>
          <p v-if="dataCanvisNoSubstPassada" class="avis-amb-grup" role="status">
            <i class="pi pi-exclamation-triangle"></i>
            {{ $t('config.priorities.noSubstPastDateWarning') }}
          </p>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="cancelarNoSubstituir"
          class="p-button-text"
        />
        <Button
          :label="$t('common.save')"
          @click="desarNoSubstituir"
          class="p-button-success"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir categoria -->
    <Dialog
      v-model:visible="mostrarDialogAfegirCategoria"
      :header="$t('config.priorities.addCategoryTitle')"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-3'">{{ $t('config.priorities.subjectsComma') }}</label>
          <InputText :id="prefixEtiquetes + '-camp-3'"
            v-model="novaCategoria"
            :placeholder="$t('config.priorities.categoryPlaceholder')"
            @keyup.enter="afegirCategoriaDialog"
          />
          <small class="field-hint">{{ $t('config.priorities.subjectsCommaHint') }}</small>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="mostrarDialogAfegirCategoria = false; novaCategoria = ''"
          class="p-button-text"
        />
        <Button
          :label="$t('common.add')"
          @click="afegirCategoriaDialog"
          class="p-button-success"
          :disabled="!novaCategoria.trim()"
        />
      </template>
    </Dialog>

    <!-- Diàleg afegir assignatura a categoria -->
    <Dialog
      v-model:visible="mostrarDialogAfegirAssignatura"
      :header="$t('config.priorities.addSubjectTitle', { index: categoriaAfegirAssignaturaIdx !== null ? categoriaAfegirAssignaturaIdx + 1 : '' })"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-4'">{{ $t('config.priorities.selectSubjectXml') }}</label>
          <MultiSelect :filterInputProps="{ 'aria-label': $t('common.filterOptions') }" :aria-label="$t('config.priorities.selectSubjectXml')" :inputId="prefixEtiquetes + '-camp-4'"
            v-model="assignaturesSeleccionades"
            :options="opcionsCategoria"
            :placeholder="$t('config.priorities.selectSubjectPlaceholder')"
            :filter="true"
            display="chip"
            class="w-full"
          />
          <small class="field-hint">{{ $t('config.priorities.synthHint') }}</small>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="mostrarDialogAfegirAssignatura = false; assignaturesSeleccionades = []"
          class="p-button-text"
        />
        <Button
          :label="$t('common.save')"
          @click="desarAssignaturaCategoria"
          class="p-button-success"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import { useConfirmaEsborrar } from '../../composables/useConfirmaEsborrar'
import Dialog from 'primevue/dialog'
import MultiSelect from 'primevue/multiselect'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import Panel from 'primevue/panel'
import Accordion from 'primevue/accordion'
import AccordionTab from 'primevue/accordiontab'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'
import Calendar from 'primevue/calendar'
import { dataAmbAny } from '../../dates'
import { usePrioritats } from '../../composables/usePrioritats'

const prefixEtiquetes = useId()

const toast = useToast()
const { t, locale } = useI18n()
const confirmaEsborrar = useConfirmaEsborrar()

const {
  dataText,
  xmlDataInici,
  xmlVersioText,
  noSubstituir,
  mostrarDialogNoSubstituir,
  novesNoSubstituir,
  dataCanvisNoSubst,
  dataCanvisNoSubstPassada,
  fiNoSubstituir,
  futuresNoSubstituir,
  ordreCategories,
  pesos,
  categoriaSeleccionada,
  categoriaSeleccionadaIndex,
  accordionActiveIndexes,
  mostrarDialogAfegirCategoria,
  novaCategoria,
  desantPrioritats,
  mostrarDialogAfegirAssignatura,
  categoriaAfegirAssignaturaIdx,
  opcionsCategoria,
  opcionsNoSubst,
  assignaturesSeleccionades,
  avisAmbGrup,
  activitatsAlliberables,
  activitatsPerDefecte,
  desantAlliberables,
  filtreAlliberables,
  activitatsFiltrades,
  desarActivitatsAlliberables,
  generantPDFDisponibles,
  dataInicialPDF,
  panelsPrioritatsCollapsed,
  guardarEstatPanels,
  teCanvisPrioritats,
  onCategoriaSelect,
  onCategoriaUnselect,
  moureCategoriaAmunt,
  moureCategoriaAvall,
  afegirCategoriaDialog,
  eliminarCategoria,
  afegirAssignaturaCategoria,
  desarAssignaturaCategoria,
  eliminarAssignaturaCategoria,
  desarPrioitats,
  generarPDFDisponiblesTotsDies,
  obrirDialogNoSubstituir,
  desarNoSubstituir,
  eliminarNoSubstituir,
  cancelarNoSubstituir,
  handlePanelHeaderClick,
} = usePrioritats({ t, locale, toast, confirmaEsborrar })
</script>

<style scoped src="./prioritatsTab.css"></style>
