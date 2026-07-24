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
              v-model="slotProps.data.activa"
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
                  v-model="pesos[assignatura]"
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
        <Tag severity="info" :value="$t('config.priorities.noSubstCount', { count: noSubstituir.length })" />
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
        >
          <template #default>
            {{ item || $t('common.empty') }}
            <i class="pi pi-times" style="margin-left: 0.5rem; cursor: pointer;" @click="eliminarNoSubstituir(item)"></i>
          </template>
        </Tag>
      </div>
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
          <label style="font-size: 0.875rem; font-weight: 600; color: #374151; white-space: nowrap;">
            {{ $t('config.priorities.startDate') }}
          </label>
          <input
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
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.priorities.selectSubjectXml') }}</label>
          <MultiSelect
            v-model="novesNoSubstituir"
            :options="opcionsNoSubst"
            optionLabel="label"
            optionValue="value"
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
          <label>{{ $t('config.priorities.subjectsComma') }}</label>
          <InputText
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
          <label>{{ $t('config.priorities.selectSubjectXml') }}</label>
          <MultiSelect
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
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
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

const toast = useToast()
const { t, locale } = useI18n()
const confirm = useConfirm()

const props = defineProps({
  // Data del calendari general: la configuració detecta les assignatures sobre
  // l'XML vigent per aquesta data (evita barrejar XML de cursos diferents).
  dataGlobal: { type: Date, default: () => new Date() }
})

// Data en format ISO (per l'endpoint) i text (per mostrar), + versió d'XML vigent
const dataISO = computed(() => {
  const d = props.dataGlobal || new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
})
const dataText = computed(() =>
  (props.dataGlobal || new Date()).toLocaleDateString(locale.value || 'ca-ES',
    { day: '2-digit', month: '2-digit', year: 'numeric' })
)
const xmlDataInici = ref(null)
const teBuits = ref(false)
const xmlVersioText = computed(() => {
  if (!xmlDataInici.value) return ''
  const [y, m, d] = xmlDataInici.value.split('-')
  return `${d}/${m}/${y}`
})

// Assignatures que no surten a l'XML però es poden assignar (grups sense classe)
const ASSIGNATURES_SINTETIQUES = ['alliberat']

// No substituir
const noSubstituir = ref([])
const mostrarDialogNoSubstituir = ref(false)
const novesNoSubstituir = ref([])

// Prioritats
const ordreCategories = ref([])  // Array de {categories: ["Reforç", "alliberat"], activa: true}
const pesos = ref({})  // {assignatura: pes}
const prioritiesSnapshot = ref('')
const categoriaSeleccionada = ref(null)
const categoriaSeleccionadaIndex = ref(null)
const accordionActiveIndexes = ref([])  // Índexos dels accordions oberts
const mostrarDialogAfegirCategoria = ref(false)
const novaCategoria = ref('')
const desantPrioritats = ref(false)

// Diàleg afegir assignatura a categoria
const mostrarDialogAfegirAssignatura = ref(false)
const categoriaAfegirAssignaturaIdx = ref(null)
const assignaturesDisponibles = ref([])

// Opcions dels desplegables: assignatures de l'XML + les sintètiques
// (alliberat…) + les que ja estan configurades (encara que vinguin d'un altre
// XML), perquè totes es mostrin marcades i no se'n perdi cap en canviar de data.
const opcionsCategoria = computed(() => {
  const idx = categoriaAfegirAssignaturaIdx.value
  const existents = idx !== null ? (ordreCategories.value[idx]?.categories || []) : []
  return Array.from(new Set([
    ...assignaturesDisponibles.value,
    ...ASSIGNATURES_SINTETIQUES,
    ...existents,
  ])).sort()
})
// El «no substituir» pot incloure l'opció BUIDA (hores amb Subject buit), que
// necessita etiqueta pròpia; per això les opcions són objectes {label, value}.
const opcionsNoSubst = computed(() => {
  const vals = new Set([
    ...assignaturesDisponibles.value,
    ...ASSIGNATURES_SINTETIQUES,
    ...noSubstituir.value,
  ])
  if (teBuits.value || noSubstituir.value.includes('')) vals.add('')
  return Array.from(vals).sort().map(v => ({
    label: v === '' ? t('common.empty') : v,
    value: v,
  }))
})
const assignaturesSeleccionades = ref([])

// Llista de disponibles (PDF)
const generantPDFDisponibles = ref(false)
const dataInicialPDF = ref('')

// Estat collapsed dels Panels de prioritats (guardat a localStorage)
const panelsPrioritatsCollapsed = ref({
  ordre: false,
  pesos: false,
  noSubst: false,
  disponibles: true
})

// Carregar estat dels panels des de localStorage
const carregarEstatPanels = () => {
  try {
    const saved = localStorage.getItem('prioritats_panels_collapsed')
    if (saved) {
      panelsPrioritatsCollapsed.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('Error carregant estat panels:', e)
  }
}

// Guardar estat dels panels a localStorage
const guardarEstatPanels = () => {
  try {
    localStorage.setItem('prioritats_panels_collapsed', JSON.stringify(panelsPrioritatsCollapsed.value))
  } catch (e) {
    console.error('Error guardant estat panels:', e)
  }
}

const getPrioritatsSnapshot = () => JSON.stringify({
  ordreCategories: ordreCategories.value,
  pesos: pesos.value
})

const teCanvisPrioritats = computed(() => {
  if (!prioritiesSnapshot.value) return false
  return getPrioritatsSnapshot() !== prioritiesSnapshot.value
})

// ===== FUNCIONS PRIORITATS =====

const onCategoriaSelect = (event) => {
  categoriaSeleccionadaIndex.value = ordreCategories.value.indexOf(event.data)
}

const onCategoriaUnselect = () => {
  categoriaSeleccionadaIndex.value = null
}

const moureCategoriaAmunt = () => {
  if (categoriaSeleccionadaIndex.value === null || categoriaSeleccionadaIndex.value === 0) return

  const idx = categoriaSeleccionadaIndex.value
  const temp = ordreCategories.value[idx]
  ordreCategories.value[idx] = ordreCategories.value[idx - 1]
  ordreCategories.value[idx - 1] = temp

  categoriaSeleccionadaIndex.value = idx - 1
  categoriaSeleccionada.value = ordreCategories.value[idx - 1]
}

const moureCategoriaAvall = () => {
  if (categoriaSeleccionadaIndex.value === null || categoriaSeleccionadaIndex.value >= ordreCategories.value.length - 1) return

  const idx = categoriaSeleccionadaIndex.value
  const temp = ordreCategories.value[idx]
  ordreCategories.value[idx] = ordreCategories.value[idx + 1]
  ordreCategories.value[idx + 1] = temp

  categoriaSeleccionadaIndex.value = idx + 1
  categoriaSeleccionada.value = ordreCategories.value[idx + 1]
}

const afegirCategoriaDialog = () => {
  if (!novaCategoria.value.trim()) return

  // Dividir per comes i netejar
  const categories = novaCategoria.value.split(',').map(c => c.trim()).filter(c => c)

  if (categories.length === 0) return

  ordreCategories.value.push({ categories, activa: true })  // Per defecte activa

  // Inicialitzar pesos a 1 per a cada assignatura nova
  categories.forEach(cat => {
    if (!pesos.value[cat]) {
      pesos.value[cat] = 1
    }
  })

  toast.add({
    severity: 'success',
    summary: t('common.added'),
    detail: t('config.priorities.categoryAdded', { count: categories.length }),
    life: 3000
  })

  mostrarDialogAfegirCategoria.value = false
  novaCategoria.value = ''
}

const eliminarCategoria = () => {
  if (categoriaSeleccionadaIndex.value === null) return

  const idx = categoriaSeleccionadaIndex.value
  const categoria = ordreCategories.value[idx]

  confirm.require({
    message: t('config.priorities.deleteCategoryConfirm', {
      index: idx + 1,
      count: categoria.categories.length
    }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: () => {
      ordreCategories.value.splice(idx, 1)
      categoriaSeleccionada.value = null
      categoriaSeleccionadaIndex.value = null

      toast.add({
        severity: 'success',
        summary: t('common.deleted'),
        detail: t('config.priorities.categoryDeleted'),
        life: 3000
      })
    }
  })
}

const afegirAssignaturaCategoria = async (categoriaIdx) => {
  // Obrir diàleg amb les assignatures actuals ja marcades (desmarcar-les les treu)
  categoriaAfegirAssignaturaIdx.value = categoriaIdx
  assignaturesSeleccionades.value = [...(ordreCategories.value[categoriaIdx]?.categories || [])]
  mostrarDialogAfegirAssignatura.value = true
}

const desarAssignaturaCategoria = () => {
  const categoriaIdx = categoriaAfegirAssignaturaIdx.value
  const categoria = ordreCategories.value[categoriaIdx]
  const seleccio = assignaturesSeleccionades.value
  const previes = categoria.categories

  // Les que segueixen marcades (preservant l'ordre existent) + les noves al final.
  // Desmarcar-ne una equival a treure-la de la categoria.
  const mantingudes = previes.filter(a => seleccio.includes(a))
  const nous = seleccio.filter(a => !previes.includes(a))
  categoria.categories = [...mantingudes, ...nous]

  // Pes 1 per a les noves que no en tinguin (preserva els valors ja configurats)
  for (const assignatura of nous) {
    if (!pesos.value[assignatura]) {
      pesos.value[assignatura] = 1
    }
  }

  toast.add({
    severity: 'success',
    summary: t('common.updated'),
    detail: t('config.priorities.categoryUpdated', { index: categoriaIdx + 1 }),
    life: 3000
  })

  // Tancar diàleg
  mostrarDialogAfegirAssignatura.value = false
  assignaturesSeleccionades.value = []
}

const eliminarAssignaturaCategoria = (assignatura, categoriaIdx) => {
  confirm.require({
    message: t('config.priorities.deleteSubjectConfirm', { subject: assignatura, index: categoriaIdx + 1 }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: () => {
      const idx = ordreCategories.value[categoriaIdx].categories.indexOf(assignatura)
      if (idx !== -1) {
        ordreCategories.value[categoriaIdx].categories.splice(idx, 1)

        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('config.priorities.subjectDeleted', { subject: assignatura }),
          life: 3000
        })
      }
    }
  })
}

const carregarAssignaturesXML = async () => {
  try {
    const response = await axios.get('/api/horari/assignatures/detectar', {
      params: { data: dataISO.value }
    })
    assignaturesDisponibles.value = response.data.assignatures || []
    xmlDataInici.value = response.data.xml_data_inici || null
    teBuits.value = !!response.data.te_buits
  } catch (error) {
    console.error('Error carregant assignatures XML:', error)
  }
}

// Si canvia la data del calendari general, tornar a detectar sobre el nou XML
watch(dataISO, () => { carregarAssignaturesXML() })

const carregarNoSubstituir = async () => {
  try {
    const response = await axios.get('/api/prioritats/no-substituir')
    noSubstituir.value = response.data.assignatures
  } catch (error) {
    console.error('Error carregant no substituir:', error)
  }
}

const carregarPrioritats = async () => {
  try {
    const [assignaturesResp, categoriesResp] = await Promise.all([
      axios.get('/api/prioritats/assignatures'),
      axios.get('/api/prioritats/categories'),
      carregarAssignaturesXML()  // Carregar assignatures de l'XML
    ])

    // Crear mapa de categories per obtenir l'estat activa
    const categoriesMap = {}
    categoriesResp.data.categories.forEach(cat => {
      categoriesMap[cat.id] = {
        activa: cat.activa,
        ordre: cat.ordre
      }
    })

    // Agrupar assignatures per categoria_id
    const categoriesById = {}

    assignaturesResp.data.assignatures.forEach(assig => {
      if (!categoriesById[assig.categoria_id]) {
        categoriesById[assig.categoria_id] = {
          id: assig.categoria_id,
          assignatures: [],
          activa: categoriesMap[assig.categoria_id]?.activa || true
        }
      }

      categoriesById[assig.categoria_id].assignatures.push({
        nom: assig.assignatura,
        pes: assig.pes,
        ordre: assig.ordre,
        auto_assignada: assig.auto_assignada
      })

      // Guardar pes
      pesos.value[assig.assignatura] = assig.pes
    })

    // Convertir a ordreCategories: array de {categories: [...], activa: true/false}
    // Ordenar categories per ID (que correspon a l'ordre)
    ordreCategories.value = Object.keys(categoriesById)
      .sort((a, b) => parseInt(a) - parseInt(b))
      .map(catId => {
        const cat = categoriesById[catId]
        // Ordenar assignatures dins la categoria per ordre
        const assignaturesOrdenades = cat.assignatures
          .sort((a, b) => a.ordre - b.ordre)
          .map(a => a.nom)

        // Determinar si la categoria està activa: totes les assignatures tenen auto_assignada=true
        const activa = cat.assignatures.every(a => a.auto_assignada === true)

        return {
          categories: assignaturesOrdenades,
          activa: activa
        }
      })

    prioritiesSnapshot.value = getPrioritatsSnapshot()
  } catch (error) {
    console.error('Error carregant prioritats:', error)
  }
}

const desarPrioitats = async () => {
  desantPrioritats.value = true

  try {
    // Preparar dades per enviar
    const ordreCategoriesArray = ordreCategories.value.map(cat => cat.categories)
    const categoriesActives = ordreCategories.value.map(cat => cat.activa !== false)  // Default true si no està definit

    const response = await axios.put('/api/prioritats/desar-tot', {
      ordre_categories: ordreCategoriesArray,
      pesos: pesos.value,
      categories_actives: categoriesActives
    })

    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: response.data.message,
      life: 3000
    })

    // Recarregar prioritats per assegurar sincronització
    await carregarPrioritats()
  } catch (error) {
    console.error('Error desant prioritats:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.savePriorities'),
      life: 3000
    })
  } finally {
    desantPrioritats.value = false
  }
}

// Llista de disponibles - PDF de tots els dies
const generarPDFDisponiblesTotsDies = async () => {
  generantPDFDisponibles.value = true

  try {
    const response = await axios.post('/api/pdf/disponibles-tots-dies',
      { data_inici: dataInicialPDF.value || null },
      { responseType: 'blob' }
    )

    // Crear link de descàrrega
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    const filename = response.headers['content-disposition']?.split('filename=')[1]?.replace(/"/g, '') ||
                     `disponibles_tots_dies_${new Date().toISOString().split('T')[0]}.pdf`

    link.download = filename
    link.click()
    window.URL.revokeObjectURL(url)

    toast.add({
      severity: 'success',
      summary: t('common.success'),
      detail: t('config.priorities.pdfGenerated'),
      life: 3000
    })
  } catch (error) {
    console.error('Error generant PDF:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.generatePDF'),
      life: 3000
    })
  } finally {
    generantPDFDisponibles.value = false
  }
}

// ===== FUNCIONS NO SUBSTITUIR =====

const obrirDialogNoSubstituir = () => {
  // Obrir amb les assignatures actuals ja marcades (desmarcar-les les treu)
  novesNoSubstituir.value = [...noSubstituir.value]
  mostrarDialogNoSubstituir.value = true
}

const desarNoSubstituir = async () => {
  const seleccio = novesNoSubstituir.value
  const previes = noSubstituir.value

  const afegir = seleccio.filter(a => !previes.includes(a))
  const treure = previes.filter(a => !seleccio.includes(a))

  try {
    for (const assignatura of afegir) {
      await axios.post('/api/prioritats/no-substituir', { assignatura })
    }
    for (const assignatura of treure) {
      await axios.delete(`/api/prioritats/no-substituir/${encodeURIComponent(assignatura)}`)
    }

    // Recarregar no substituir
    const response = await axios.get('/api/prioritats/no-substituir')
    noSubstituir.value = response.data.assignatures

    toast.add({
      severity: 'success',
      summary: t('common.updated'),
      detail: t('config.priorities.noSubstUpdated'),
      life: 3000
    })

    cancelarNoSubstituir()
  } catch (error) {
    console.error('Error desant no substituir:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.addNoSubst'),
      life: 3000
    })
  }
}

const eliminarNoSubstituir = async (assignatura) => {
  try {
    await axios.delete(`/api/prioritats/no-substituir/${encodeURIComponent(assignatura)}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.priorities.noSubstDeleted'),
      life: 3000
    })

    // Recarregar no substituir
    const response = await axios.get('/api/prioritats/no-substituir')
    noSubstituir.value = response.data.assignatures
  } catch (error) {
    console.error('Error eliminant no substituir:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.deleteNoSubst'),
      life: 3000
    })
  }
}

const cancelarNoSubstituir = () => {
  mostrarDialogNoSubstituir.value = false
  novesNoSubstituir.value = []
}

// Fer que tot el header dels panels sigui clicable
const handlePanelHeaderClick = (event) => {
  const header = event.target.closest('.p-panel-header')
  if (!header) return

  // Si ja s'ha clicat al botó toggle directament, no fer res
  if (event.target.closest('.p-panel-toggler')) return

  // Trobar el botó toggle i fer-hi clic
  const toggleBtn = header.querySelector('.p-panel-toggler')
  if (toggleBtn) {
    toggleBtn.click()
  }
}

onMounted(() => {
  carregarEstatPanels()
  carregarNoSubstituir()
  carregarPrioritats()
})
</script>

<style scoped>
.tab-content {
  padding: 0.5rem 0;
  min-height: 400px;
}

.info-text {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  color: #1e40af;
  font-size: 0.9rem;
  margin-top: 1rem;
}

.info-text i {
  color: #3b82f6;
}

.xml-indicator {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin: 0.5rem 0 0;
  padding: 0.4rem 0.6rem;
  background: #f1f5f9;
  border-radius: 6px;
  color: #475569;
  font-size: 0.85rem;
}

.xml-indicator i {
  color: #64748b;
}

.field-hint {
  display: block;
  margin-top: 0.35rem;
  color: #6b7280;
  font-size: 0.85rem;
  font-style: italic;
}

.field {
  margin-bottom: 1.5rem;
}

.field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
  font-size: 0.95rem;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 6px;
}

.w-full {
  width: 100%;
}

/* Prioritats */
.categoria-pesos {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.assignatura-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.assignatura-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.assignatura-header label {
  font-weight: 500;
  color: #374151;
  margin: 0;
  min-width: 150px;
}

.assignatura-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.no-subst-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  min-height: 60px;
  margin-top: 0.5rem;
}

.no-subst-list:empty::before {
  content: 'Cap activitat configurada';
  color: #9ca3af;
  font-style: italic;
}

/* Fer que tota la capçalera del Panel sigui clicable */
:deep(.p-panel-header) {
  cursor: pointer;
  user-select: none;
}

:deep(.p-panel-header:hover) {
  background: rgba(0, 0, 0, 0.02);
}

/* Fer que el clic a qualsevol lloc del header dispari el toggle */
:deep(.p-panel-header .p-panel-title) {
  flex: 1;
  cursor: pointer;
}

:deep(.p-panel-header .p-panel-title):active {
  opacity: 0.7;
}
</style>
