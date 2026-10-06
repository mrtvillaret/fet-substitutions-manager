<template>
  <div class="grups-view">
    <div class="view-header">
      <h2>{{ $t('groups.title') }}</h2>
      <p class="subtitle">{{ dataFormatada }}</p>
      <p class="instructions">
        {{ $t('groups.instructionsLine1') }}
        {{ $t('groups.instructionsLine2') }}
      </p>
      <p class="instructions">{{ $t('groups.instructionsTeachers') }}</p>
    </div>

    <!-- Carregant -->
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('common.loadingConfig') }}</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-message">
      <Message severity="error" :closable="false">{{ error }}</Message>
    </div>

    <!-- Main Content -->
    <div v-else>
      <!-- Toolbar -->
      <div class="toolbar">
        <div class="actions-group">
          <Button :label="$t('groups.all')" @click="marcarTots" severity="secondary" size="small" />
          <Button :label="$t('groups.none')" @click="desmarcarTots" severity="secondary" size="small" outlined />
        </div>

        <div class="save-actions">
          <Tag v-if="teCanvis" severity="warning" :value="$t('common.unsavedChanges')" class="unsaved-tag"></Tag>
          <Button
            :label="$t('common.save')"
            @click="desarGrups"
            severity="success"
            :disabled="!teCanvis"
            :loading="desant"
          />
        </div>
      </div>

      <!-- Editor Card -->
      <div class="content-card">
        <!-- Professors alliberats (sense alliberar el seu grup) -->
        <div v-if="resumProfessors.length" class="teachers-summary">
          <span class="teachers-summary-label">{{ $t('groups.teachersTitle') }}:</span>
          <Chip
            v-for="item in resumProfessors"
            :key="item.professor"
            :label="`${item.professor} (${item.hores.join(', ')})`"
            removable
            @remove="treureProfessor(item.professor)"
          />
        </div>

        <!-- Taula de checkboxes -->
        <div class="table-container">
          <table class="grups-table">
            <thead>
              <tr>
                <th class="grup-col">{{ $t('groups.groupClass') }}</th>
                <th v-for="hora in hores" :key="hora" class="hora-col">{{ hora }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="grup in grupsDisponibles" :key="grup">
                <td class="grup-name" @click="toggleGrupComplet(grup)">
                  <span class="clickable">{{ grup }}</span>
                </td>
                <td v-for="hora in hores" :key="`${grup}-${hora}`" class="checkbox-cell">
                  <div class="cell-inner">
                    <Checkbox
                      v-model="checkboxes[grup][hora]"
                      :binary="true"
                      @change="onCheckboxChange"
                    />
                    <button
                      v-if="professorsDe(grup, hora).length && !checkboxes[grup][hora]"
                      type="button"
                      class="teachers-btn"
                      :class="{ active: alliberatsDe(grup, hora).length }"
                      :title="$t('groups.freeTeachersTitle')"
                      :aria-label="$t('groups.freeTeachersTitle')"
                      @click="obrirProfessors($event, grup, hora)"
                    >
                      <i class="pi pi-user"></i>
                      <span v-if="alliberatsDe(grup, hora).length">{{ alliberatsDe(grup, hora).length }}</span>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Resum -->
        <div class="summary">
          <Tag severity="info" :value="$t('groups.summary', { groups: totalGrupsSeleccionats, hours: totalHoresSeleccionades })"></Tag>
        </div>
      </div>
    </div>

    <!-- Professors d'una franja: alliberar-ne només alguns -->
    <OverlayPanel ref="panellProfessors">
      <div v-if="franja" class="teachers-panel">
        <strong>{{ franja.grup }} · {{ franja.hora }}</strong>
        <p class="teachers-panel-hint">{{ $t('groups.teachersHint') }}</p>
        <div v-for="prof in professorsDe(franja.grup, franja.hora)" :key="prof" class="teachers-panel-row">
          <Checkbox
            :inputId="`prof-${prof}`"
            :modelValue="estaAlliberat(prof, franja.hora)"
            :binary="true"
            @update:modelValue="valor => marcaProfessor(prof, franja.hora, valor)"
          />
          <label :for="`prof-${prof}`">{{ prof }}</label>
        </div>
      </div>
    </OverlayPanel>

    <!-- Canvis sense desar: Desa / No desis / Cancel·la -->
    <Dialog
      v-model:visible="avis.visible"
      :header="$t('common.unsavedChangesTitle')"
      modal
      :style="{ width: '28rem' }"
      @hide="respon('cancel')"
    >
      <p class="unsaved-message">
        <i class="pi pi-exclamation-triangle"></i>
        {{ $t('common.unsavedChangesQuestion', { dia: dataFormatada }) }}
      </p>
      <template #footer>
        <Button :label="$t('common.cancel')" text severity="secondary" @click="respon('cancel')" />
        <Button :label="$t('common.dontSave')" severity="danger" outlined @click="respon('descarta')" />
        <Button :label="$t('common.save')" severity="success" autofocus @click="respon('desa')" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Chip from 'primevue/chip'
import OverlayPanel from 'primevue/overlaypanel'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Dialog from 'primevue/dialog'

const toast = useToast()
const { t, locale } = useI18n()

const props = defineProps({
  dataGlobal: {
    type: Date,
    required: true
  }
})

const hores = ref([])
const grupsDisponibles = ref([])
const checkboxes = reactive({})
const checkboxesOriginals = ref({})
// Professors alliberats sense el seu grup: {hora: [professors]}
const professorsPerGrupHora = ref({})
const professorsAlliberats = reactive({})
const professorsAlliberatsOriginals = ref({})
const panellProfessors = ref(null)
const franja = ref(null)
const loading = ref(false)
const desant = ref(false)
const error = ref(null)

// Dia carregat a la pantalla: és on es desa, encara que el calendari ja
// marqui un altre dia (p.ex. si en canviar de dia s'ha triat «Cancel·la»).
const dataCarregada = ref(props.dataGlobal)

const isoDe = (data) => {
  const year = data.getFullYear()
  const month = String(data.getMonth() + 1).padStart(2, '0')
  const day = String(data.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const dataFormatada = computed(() => {
  return dataCarregada.value.toLocaleDateString(locale.value || 'ca-ES', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
})


const professorsAlliberatsNets = () => {
  const nets = {}
  hores.value.forEach(hora => {
    const profs = [...(professorsAlliberats[hora] || [])].sort()
    if (profs.length) nets[hora] = profs
  })
  return nets
}

const teCanvis = computed(() => {
  return JSON.stringify(checkboxes) !== JSON.stringify(checkboxesOriginals.value) ||
    JSON.stringify(professorsAlliberatsNets()) !== JSON.stringify(professorsAlliberatsOriginals.value)
})

const professorsDe = (grup, hora) => professorsPerGrupHora.value[hora]?.[grup] || []

const estaAlliberat = (prof, hora) => (professorsAlliberats[hora] || []).includes(prof)

const alliberatsDe = (grup, hora) => professorsDe(grup, hora).filter(prof => estaAlliberat(prof, hora))

const marcaProfessor = (prof, hora, valor) => {
  const actuals = (professorsAlliberats[hora] || []).filter(p => p !== prof)
  professorsAlliberats[hora] = valor ? [...actuals, prof] : actuals
}

const treureProfessor = (prof) => {
  for (const hora in professorsAlliberats) {
    professorsAlliberats[hora] = professorsAlliberats[hora].filter(p => p !== prof)
  }
}

const obrirProfessors = (event, grup, hora) => {
  franja.value = { grup, hora }
  panellProfessors.value.toggle(event)
}

// Un xip per professor amb les seves hores, en l'ordre de l'horari
const resumProfessors = computed(() => {
  const perProfessor = {}
  hores.value.forEach(hora => {
    (professorsAlliberats[hora] || []).forEach(prof => {
      (perProfessor[prof] ||= []).push(hora)
    })
  })
  return Object.keys(perProfessor).sort().map(professor => ({ professor, hores: perProfessor[professor] }))
})

const inicialitzarProfessors = (seleccionats = {}) => {
  for (const key in professorsAlliberats) {
    delete professorsAlliberats[key]
  }
  Object.entries(seleccionats).forEach(([hora, profs]) => {
    professorsAlliberats[hora] = [...profs]
  })
  professorsAlliberatsOriginals.value = professorsAlliberatsNets()
}

const totalGrupsSeleccionats = computed(() => {
  const grupsUnics = new Set()
  for (const grup in checkboxes) {
    for (const hora in checkboxes[grup]) {
      if (checkboxes[grup][hora]) {
        grupsUnics.add(grup)
      }
    }
  }
  return grupsUnics.size
})

const totalHoresSeleccionades = computed(() => {
  const horesAmbGrups = new Set()
  for (const grup in checkboxes) {
    for (const hora in checkboxes[grup]) {
      if (checkboxes[grup][hora]) {
        horesAmbGrups.add(hora)
      }
    }
  }
  return horesAmbGrups.size
})

const inicialitzarCheckboxes = (grups, horasList, seleccionats = {}) => {
  // Netejar checkboxes
  for (const key in checkboxes) {
    delete checkboxes[key]
  }

  // Crear estructura de checkboxes
  grups.forEach(grup => {
    checkboxes[grup] = {}
    horasList.forEach(hora => {
      checkboxes[grup][hora] = seleccionats[hora]?.includes(grup) || false
    })
  })

  // Guardar còpia dels originals
  checkboxesOriginals.value = JSON.parse(JSON.stringify(checkboxes))
}

const carregarConfiguracio = async () => {
  loading.value = true
  error.value = null

  try {
    const data = props.dataGlobal
    const response = await axios.get(`/api/grups/${isoDe(data)}`)
    dataCarregada.value = data

    hores.value = response.data.hores
    grupsDisponibles.value = response.data.grups_disponibles

    inicialitzarCheckboxes(
      response.data.grups_disponibles,
      response.data.hores,
      response.data.grups_seleccionats_per_hora
    )
    professorsPerGrupHora.value = response.data.professors_per_grup_hora || {}
    inicialitzarProfessors(response.data.professors_alliberats_per_hora || {})
  } catch (err) {
    console.error('Error carregant configuració:', err)
    error.value = t('groups.errors.load')
  } finally {
    loading.value = false
  }
}

const onCheckboxChange = () => {
  // Aquest mètode es crida quan canvia un checkbox individual
  // El computed teCanvis detectarà automàticament el canvi
}

const toggleGrupComplet = (grup) => {
  // Comprova si alguna hora està marcada
  const algunaMarcada = hores.value.some(hora => checkboxes[grup][hora])

  // Marca/desmarca totes les hores d'aquest grup
  const nouEstat = !algunaMarcada
  hores.value.forEach(hora => {
    checkboxes[grup][hora] = nouEstat
  })
}

const marcarTots = () => {
  grupsDisponibles.value.forEach(grup => {
    hores.value.forEach(hora => {
      checkboxes[grup][hora] = true
    })
  })
}

const desmarcarTots = () => {
  grupsDisponibles.value.forEach(grup => {
    hores.value.forEach(hora => {
      checkboxes[grup][hora] = false
    })
  })
}

// Retorna si s'ha pogut desar
const desarGrups = async () => {
  desant.value = true

  try {
    // Convertir checkboxes a format backend: Dict[hora, List[grups]]
    const grupsPerHora = {}

    hores.value.forEach(hora => {
      const grupsHora = []
      grupsDisponibles.value.forEach(grup => {
        if (checkboxes[grup][hora]) {
          grupsHora.push(grup)
        }
      })
      if (grupsHora.length > 0) {
        grupsPerHora[hora] = grupsHora
      }
    })

    const professorsPerHora = professorsAlliberatsNets()
    const response = await axios.put(`/api/grups/${isoDe(dataCarregada.value)}`, {
      grups: grupsPerHora,
      professors: professorsPerHora
    })

    // Actualitzar originals
    checkboxesOriginals.value = JSON.parse(JSON.stringify(checkboxes))
    inicialitzarProfessors(professorsPerHora)

    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: response.data.message,
      life: 3000
    })
    return true
  } catch (err) {
    console.error('Error desant configuració:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('groups.errors.save'),
      life: 5000
    })
    return false
  } finally {
    desant.value = false
  }
}

// Canvis sense desar: pregunta com els programes d'escriptori i diu si es
// pot continuar (després de desar o de descartar) o no (cancel·lat o error)
const avis = reactive({ visible: false, resolve: null })

const respon = (resposta) => {
  const resolve = avis.resolve
  avis.resolve = null
  avis.visible = false
  resolve?.(resposta)
}

const potSortir = async () => {
  if (!teCanvis.value) return true
  const resposta = await new Promise(resolve => {
    avis.resolve = resolve
    avis.visible = true
  })
  if (resposta === 'desa') return await desarGrups()
  return resposta === 'descarta'
}

// Carregar quan canvia la data
watch(() => props.dataGlobal, async () => {
  if (await potSortir()) {
    carregarConfiguracio()
  }
}, { immediate: true })

// Tancar o recarregar el navegador amb canvis sense desar: avís del navegador
const avisSortida = (event) => {
  if (!teCanvis.value) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => {
  carregarConfiguracio()
  window.addEventListener('beforeunload', avisSortida)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', avisSortida)
})

// App.vue el crida abans de canviar de pestanya
defineExpose({ potSortir })
</script>

<style scoped>
.grups-view {
  width: 100%;
}

.view-header {
  margin-bottom: 1.5rem;
}

.view-header h2 {
  font-size: 2rem;
  color: #1f2937;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: #6b7280;
  font-size: 0.95rem;
  margin-bottom: 0.5rem;
}

.instructions {
  color: #6b7280;
  font-size: 0.9rem;
  font-style: italic;
  margin: 0;
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
  color: #667eea;
}

.error-message {
  margin: 2rem 0;
}

/* Toolbar */
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

.actions-group {
  display: flex;
  gap: 0.5rem;
}

.save-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

/* Editor */
.content-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

/* Taula */
.table-container {
  overflow-x: auto;
  margin-bottom: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.grups-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.grups-table thead {
  background: #f9fafb;
  position: sticky;
  top: 0;
  z-index: 10;
}

.grups-table th {
  padding: 0.75rem 0.5rem;
  text-align: center;
  font-weight: 600;
  color: #374151;
  border-bottom: 2px solid #e5e7eb;
  white-space: nowrap;
}

.grups-table th.grup-col {
  text-align: left;
  padding-left: 1rem;
  min-width: 180px;
  position: sticky;
  left: 0;
  background: #f9fafb;
  z-index: 11;
}

.grups-table th.hora-col {
  min-width: 70px;
}

.grups-table tbody tr {
  border-bottom: 1px solid #f3f4f6;
}

.grups-table tbody tr:hover {
  background: #fafbfc;
}

.grups-table td {
  padding: 0.5rem;
  text-align: center;
}

.grups-table td.grup-name {
  text-align: left;
  padding-left: 1rem;
  font-weight: 500;
  position: sticky;
  left: 0;
  background: white;
  cursor: pointer;
  user-select: none;
}

.grups-table tr:hover td.grup-name {
  background: #fafbfc;
}

.grups-table td.grup-name:hover .clickable {
  color: #667eea;
  text-decoration: underline;
}

.checkbox-cell {
  padding: 0.25rem;
}

.cell-inner {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
}

/* Professors alliberats sense el seu grup */
.teachers-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  padding: 0.15rem 0.25rem;
  border-radius: 6px;
  font-size: 0.75rem;
}

.teachers-btn:hover {
  color: #667eea;
  background: #eef2ff;
}

.teachers-btn.active {
  color: #ffffff;
  background: #16a34a;
}

.teachers-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.teachers-summary-label {
  font-weight: 600;
  color: #374151;
}

.teachers-panel {
  min-width: 220px;
}

.teachers-panel-hint {
  color: #6b7280;
  font-size: 0.85rem;
  margin: 0.25rem 0 0.75rem;
  max-width: 280px;
}

.teachers-panel-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0;
}

/* Resum */
.summary {
  display: flex;
  justify-content: center;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
}

.unsaved-message {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  margin: 0;
  line-height: 1.5;
}

.unsaved-message .pi {
  color: #f59e0b;
  font-size: 1.5rem;
}

.unsaved-tag {
  height: 2.4rem;
  display: inline-flex;
  align-items: center;
  padding: 0 0.75rem;
}

/* Responsiu */
@media (max-width: 768px) {
  .grups-table {
    font-size: 0.8rem;
  }

  .grups-table th,
  .grups-table td {
    padding: 0.4rem 0.3rem;
  }

  .grups-table th.grup-col {
    min-width: 120px;
  }

  .grups-table th.hora-col {
    min-width: 50px;
  }
}
</style>
