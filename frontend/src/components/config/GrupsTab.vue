<template>
  <div class="tab-content">
    <!-- Grups del centre: mostra tots i permet amagar-ne -->
    <div class="field" style="margin-bottom: 1.5rem;">
      <div class="toolbar" style="margin-bottom: 0.5rem;">
        <label>{{ $t('config.groups.groupsLabel') }}</label>
        <Button
          icon="pi pi-refresh"
          :label="$t('config.groups.detectButton')"
          @click="detectarGrupsXML"
          class="p-button-secondary"
          size="small"
        />
      </div>

      <!-- Indicador de quin XML/data s'està configurant -->
      <p class="xml-indicator">
        <i class="pi pi-calendar"></i>
        <span>{{ $t('config.groups.xmlContext', { data: dataText }) }}</span>
        <span v-if="xmlDataInici"> · {{ $t('config.groups.xmlVersion', { versio: xmlVersioText }) }}</span>
      </p>

      <p class="info-text" style="margin-top: 0.25rem;">
        <i class="pi pi-info-circle"></i>
        {{ $t('config.groups.hideHint') }}
      </p>

      <div v-if="grupsDetectats.length > 0">
        <div class="working-toolbar">
          <Button :label="$t('config.groups.showAllBtn')" @click="mostrarTots" text size="small" />
          <span v-if="grupsAmagats.length" class="working-count">
            {{ $t('config.groups.hiddenCount', { n: grupsAmagats.length }) }}
          </span>
        </div>
        <div class="grups-detectats">
          <Tag
            v-for="grup in grupsDetectats"
            :key="grup"
            :value="grup"
            :severity="grupsAmagats.includes(grup) ? 'secondary' : 'success'"
            :class="['grup-chip', { 'grup-amagat': grupsAmagats.includes(grup) }]"
            @click="toggleAmagat(grup)"
          />
        </div>
        <Button
          :label="$t('config.groups.saveHidden')"
          icon="pi pi-save"
          @click="desarGrupsAmagats"
          :loading="desantAmagats"
          class="p-button-success"
          size="small"
          style="margin-top: 0.9rem;"
        />
      </div>
      <div v-else class="empty-message" style="margin-top: 0.5rem;">
        {{ $t('config.groups.detectHint') }}
      </div>
    </div>

    <Divider />

    <!-- Abreviatures -->
    <div class="field">
      <div class="toolbar">
        <label>{{ $t('config.groups.abbrevLabel') }}</label>
        <Button
          :label="$t('config.groups.addAbbrev')"
          icon="pi pi-plus"
          @click="mostrarDialogAfegirAbreviatura = true"
          size="small"
          class="p-button-success"
        />
      </div>

      <div class="abreviatures-list">
        <div
          v-for="abr in abreviatures"
          :key="abr.id"
          class="abreviatura-card"
        >
          <div class="abreviatura-content">
            <span class="grups-originals">{{ abr.grups_originals }}</span>
            <i class="pi pi-arrow-right arrow-icon"></i>
            <span class="abreviatura-text">{{ abr.abreviatura }}</span>
          </div>
          <div class="abreviatura-actions">
            <Button
              icon="pi pi-pencil"
              @click="editarAbreviatura(abr)"
              class="p-button-rounded p-button-text p-button-sm"
              v-tooltip.top="$t('common.edit')"
            />
            <Button
              icon="pi pi-trash"
              @click="eliminarAbreviatura(abr.id)"
              class="p-button-rounded p-button-text p-button-danger p-button-sm"
              v-tooltip.top="$t('common.delete')"
            />
          </div>
        </div>
        <div v-if="abreviatures.length === 0" class="empty-message">
          {{ $t('config.groups.noAbbrev') }}
        </div>
      </div>

      <p class="info-text">
        <i class="pi pi-info-circle"></i>
        {{ $t('config.groups.abbrevHint') }}
      </p>
    </div>

    <!-- Diàleg afegir/editar abreviatura -->
    <Dialog
      v-model:visible="mostrarDialogAfegirAbreviatura"
      :header="abreviaturaEditant ? $t('config.groups.editAbbrevTitle') : $t('config.groups.addAbbrevTitle')"
      :modal="true"
      :style="{ width: '500px' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.groups.originalGroups') }}</label>
          <MultiSelect
            v-model="grupsSeleccionats"
            :options="grupsDetectats"
            :placeholder="$t('config.groups.selectGroups')"
            display="chip"
            :filter="true"
            class="w-full"
          />
          <small class="field-hint">
            {{ $t('config.groups.selectGroupsHint') }}
            <a @click="detectarGrupsXML" style="cursor: pointer; text-decoration: underline;">{{ $t('config.groups.detectInline') }}</a>
          </small>
        </div>

        <div class="field">
          <label>{{ $t('config.groups.abbrevLabel') }}</label>
          <InputText
            v-model="novaAbreviatura.abreviatura"
            :placeholder="$t('config.groups.abbrevPlaceholder')"
            @keyup.enter="desarAbreviatura"
          />
          <small class="field-hint">{{ $t('config.groups.abbrevHintShort') }}</small>
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="cancelarAbreviatura"
          class="p-button-text"
        />
        <Button
          :label="$t('common.save')"
          @click="desarAbreviatura"
          class="p-button-success"
          :disabled="grupsSeleccionats.length === 0 || !novaAbreviatura.abreviatura"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import Dialog from 'primevue/dialog'
import MultiSelect from 'primevue/multiselect'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Divider from 'primevue/divider'

const props = defineProps({
  // Data del calendari general: la configuració detecta els grups sobre l'XML
  // vigent per aquesta data (el mateix que veurà la vista de sense classe).
  dataGlobal: { type: Date, default: () => new Date() }
})

const toast = useToast()
const { t, locale } = useI18n()

// Data en format ISO (per l'endpoint) i text (per mostrar)
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
const xmlVersioText = computed(() => {
  if (!xmlDataInici.value) return ''
  const [y, m, d] = xmlDataInici.value.split('-')
  return `${d}/${m}/${y}`
})

const abreviatures = ref([])
const mostrarDialogAfegirAbreviatura = ref(false)
const abreviaturaEditant = ref(null)
const novaAbreviatura = ref({
  grups_originals: '',
  abreviatura: ''
})

// Grups detectats de l'XML
const grupsDetectats = ref([])
const grupsSeleccionats = ref([])

// Grups amagats: llista d'exclusió (es mostren tots menys aquests)
const grupsAmagats = ref([])
const desantAmagats = ref(false)

const carregarAbreviatures = async () => {
  try {
    const response = await axios.get('/api/config/abreviatures')
    abreviatures.value = response.data.abreviatures
  } catch (error) {
    console.error('Error carregant abreviatures:', error)
  }
}

const detectarGrupsXML = async (silent = false) => {
  try {
    // Detecta sobre l'XML vigent per la data del calendari general
    const response = await axios.get('/api/horari/grups/detectar', {
      params: { data: dataISO.value }
    })

    // Guardar grups detectats (usem grups_raw, els grups originals sense abreviar)
    grupsDetectats.value = response.data.grups_raw
    xmlDataInici.value = response.data.xml_data_inici || null

    if (!silent) {
      toast.add({
        severity: 'success',
        summary: t('common.detected'),
        detail: t('config.groups.detectedCount', { count: response.data.total_raw }),
        life: 3000
      })
    }
  } catch (error) {
    console.error('Error detectant grups:', error)
    if (!silent) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('config.errors.detectGroups'),
        life: 3000
      })
    }
  }
}

// ===== Grups amagats (llista d'exclusió) =====
const carregarGrupsAmagats = async () => {
  try {
    const response = await axios.get('/api/grups-amagats')
    grupsAmagats.value = response.data.grups || []
  } catch (error) {
    console.error('Error carregant grups amagats:', error)
  }
}

const toggleAmagat = (grup) => {
  const idx = grupsAmagats.value.indexOf(grup)
  if (idx >= 0) grupsAmagats.value.splice(idx, 1)
  else grupsAmagats.value.push(grup)
}

const mostrarTots = () => {
  grupsAmagats.value = []
}

const desarGrupsAmagats = async () => {
  desantAmagats.value = true
  try {
    await axios.put('/api/grups-amagats', { grups: grupsAmagats.value })
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.groups.hiddenSaved'),
      life: 3000
    })
  } catch (error) {
    console.error('Error desant grups amagats:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.groups.hiddenSaveError'),
      life: 3000
    })
  } finally {
    desantAmagats.value = false
  }
}

const desarAbreviatura = async () => {
  // Convertir array de grups seleccionats a string separats per comes
  const grupsOriginalsString = grupsSeleccionats.value.join(',')

  if (!grupsOriginalsString || !novaAbreviatura.value.abreviatura) {
    return
  }

  try {
    if (abreviaturaEditant.value) {
      // Actualitzar existent
      await axios.put(`/api/config/abreviatures/${abreviaturaEditant.value}`, {
        grups_originals: grupsOriginalsString.trim(),
        abreviatura: novaAbreviatura.value.abreviatura.trim()
      })

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('config.groups.abbrevUpdated'),
        life: 3000
      })
    } else {
      // Crear nova
      await axios.post('/api/config/abreviatures', {
        grups_originals: grupsOriginalsString.trim(),
        abreviatura: novaAbreviatura.value.abreviatura.trim()
      })

      toast.add({
        severity: 'success',
        summary: t('common.added'),
        detail: t('config.groups.abbrevAdded'),
        life: 3000
      })
    }

    // Recarregar abreviatures
    const response = await axios.get('/api/config/abreviatures')
    abreviatures.value = response.data.abreviatures

    // Tancar diàleg i netejar
    cancelarAbreviatura()
  } catch (error) {
    console.error('Error desant abreviatura:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.saveAbbrev'),
      life: 3000
    })
  }
}

const editarAbreviatura = (abr) => {
  abreviaturaEditant.value = abr.id
  novaAbreviatura.value = {
    grups_originals: abr.grups_originals,
    abreviatura: abr.abreviatura
  }

  // Convertir string separats per comes a array per al MultiSelect
  grupsSeleccionats.value = abr.grups_originals.split(',').map(g => g.trim())

  mostrarDialogAfegirAbreviatura.value = true
}

const eliminarAbreviatura = async (id) => {
  try {
    await axios.delete(`/api/config/abreviatures/${id}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.groups.abbrevDeleted'),
      life: 3000
    })

    // Recarregar abreviatures
    const response = await axios.get('/api/config/abreviatures')
    abreviatures.value = response.data.abreviatures
  } catch (error) {
    console.error('Error eliminant abreviatura:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.deleteAbbrev'),
      life: 3000
    })
  }
}

const cancelarAbreviatura = () => {
  mostrarDialogAfegirAbreviatura.value = false
  abreviaturaEditant.value = null
  novaAbreviatura.value = {
    grups_originals: '',
    abreviatura: ''
  }
  grupsSeleccionats.value = []
}

onMounted(async () => {
  await carregarAbreviatures()
  await carregarGrupsAmagats()
  await detectarGrupsXML(true)   // silenciós: omple els grups per poder-los amagar
})
</script>

<style scoped>
.tab-content {
  padding: 0.5rem 0;
  min-height: 400px;
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

.field-hint {
  display: block;
  margin-top: 0.35rem;
  color: #6b7280;
  font-size: 0.85rem;
  font-style: italic;
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

.abreviatures-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
  margin-bottom: 1rem;
}

.abreviatura-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.abreviatura-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.abreviatura-content {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
}

.grups-originals {
  font-weight: 500;
  color: #374151;
  min-width: 150px;
}

.arrow-icon {
  color: #667eea;
  font-size: 0.9rem;
}

.abreviatura-text {
  color: #667eea;
  font-weight: 600;
  font-size: 1.05rem;
}

.abreviatura-actions {
  display: flex;
  gap: 0.25rem;
}

.empty-message {
  padding: 2rem;
  text-align: center;
  color: #9ca3af;
  font-style: italic;
  background: #f9fafb;
  border: 1px dashed #e5e7eb;
  border-radius: 6px;
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

.w-full {
  width: 100%;
}

.grups-detectats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.grup-chip {
  cursor: pointer;
  user-select: none;
  transition: opacity 0.15s;
}

.grup-chip:hover {
  opacity: 0.8;
}

.grup-amagat {
  opacity: 0.5;
  text-decoration: line-through;
}

.xml-indicator {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin: 0 0 0.25rem;
  padding: 0.4rem 0.6rem;
  background: #f1f5f9;
  border-radius: 6px;
  color: #475569;
  font-size: 0.85rem;
}

.xml-indicator i {
  color: #64748b;
}

.working-toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}

.working-count {
  margin-left: auto;
  color: #6b7280;
  font-size: 0.85rem;
}
</style>
