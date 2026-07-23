<template>
  <div class="grups-view">
    <div class="view-header">
      <h2>{{ $t('groups.title') }}</h2>
      <p class="subtitle">{{ dataFormatada }}</p>
      <p class="instructions">
        {{ $t('groups.instructionsLine1') }}
        {{ $t('groups.instructionsLine2') }}
      </p>
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
                  <Checkbox
                    v-model="checkboxes[grup][hora]"
                    :binary="true"
                    @change="onCheckboxChange"
                  />
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

    <!-- Diàleg de confirmació -->
    <ConfirmDialog></ConfirmDialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import ConfirmDialog from 'primevue/confirmdialog'

const toast = useToast()
const confirm = useConfirm()
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
const loading = ref(false)
const desant = ref(false)
const error = ref(null)

const dataFormatada = computed(() => {
  return props.dataGlobal.toLocaleDateString(locale.value || 'ca-ES', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
})

const dataISO = computed(() => {
  const year = props.dataGlobal.getFullYear()
  const month = String(props.dataGlobal.getMonth() + 1).padStart(2, '0')
  const day = String(props.dataGlobal.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
})

const teCanvis = computed(() => {
  return JSON.stringify(checkboxes) !== JSON.stringify(checkboxesOriginals.value)
})

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
    const response = await axios.get(`/api/grups/${dataISO.value}`)

    hores.value = response.data.hores
    grupsDisponibles.value = response.data.grups_disponibles

    inicialitzarCheckboxes(
      response.data.grups_disponibles,
      response.data.hores,
      response.data.grups_seleccionats_per_hora
    )
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

    const response = await axios.put(`/api/grups/${dataISO.value}`, grupsPerHora)

    // Actualitzar originals
    checkboxesOriginals.value = JSON.parse(JSON.stringify(checkboxes))

    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: response.data.message,
      life: 3000
    })
  } catch (err) {
    console.error('Error desant configuració:', err)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('groups.errors.save'),
      life: 5000
    })
  } finally {
    desant.value = false
  }
}

// Carregar quan canvia la data
watch(() => props.dataGlobal, () => {
  if (teCanvis.value) {
    confirm.require({
      message: t('common.unsavedChangesSwitchDay'),
      header: t('common.unsavedChangesTitle'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.discard'),
      rejectLabel: t('common.cancel'),
      accept: () => {
        carregarConfiguracio()
      }
    })
  } else {
    carregarConfiguracio()
  }
}, { immediate: true })

onMounted(() => {
  carregarConfiguracio()
})
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

/* Resum */
.summary {
  display: flex;
  justify-content: center;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
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
