<template>
  <Dialog
    :visible="visible"
    modal
    :header="$t('scheduler.publish.title')"
    :style="{ width: '720px' }"
    @update:visible="$emit('update:visible', $event)"
  >
    <!-- Pas 1: Formulari pre-publicació -->
    <div v-if="!previsualitzacio && !resultat" class="publicar-content">
      <div v-if="carregant" class="flex justify-content-center p-4">
        <ProgressSpinner style="width: 40px; height: 40px" />
      </div>
      <template v-else>
        <!-- Resum dates -->
        <p class="mb-3">{{ $t('scheduler.publish.description') }}</p>
        <div v-for="(setmana, idx) in resum" :key="idx" class="mb-3">
          <div v-if="resum.length > 1" class="font-semibold mb-2">{{ $t('scheduler.publish.week') }} {{ idx + 1 }}</div>
          <DataTable :value="setmana.dies" size="small" class="p-datatable-sm">
            <Column field="dia" :header="$t('scheduler.publish.day')" />
            <Column field="data" :header="$t('scheduler.publish.date')" />
            <Column field="examens" :header="$t('scheduler.publish.exams')" />
            <Column field="grups" :header="$t('scheduler.publish.examGroups')" />
          </DataTable>
        </div>

        <!-- Durada examen -->
        <Divider />
        <div class="mb-3">
          <div class="font-semibold mb-2">{{ $t('scheduler.publish.durationTitle') }}</div>
          <p class="text-sm text-color-secondary mt-0 mb-2">
            {{ $t('scheduler.publish.durationDesc') }}
          </p>
          <div class="flex align-items-center gap-2">
            <InputNumber v-model="duradaExamen" :min="1" :max="maxDurada" showButtons :step="1" style="width: 6rem" />
            <span class="text-sm">{{ duradaExamen === 1 ? $t('scheduler.publish.hourSingular') : $t('scheduler.publish.hourPlural') }}</span>
          </div>
          <div v-if="horesLectives.length > 0" class="text-sm text-color-secondary mt-2">
            {{ $t('scheduler.publish.schoolHours') }} {{ horesLectives.join(', ') }}
          </div>
        </div>

        <!-- Opcions -->
        <Divider />
        <div class="flex flex-column gap-2">
          <div class="flex align-items-center gap-2">
            <Checkbox v-model="opcions.auto_assign_titulars" :binary="true" inputId="opt-titulars" />
            <label for="opt-titulars">{{ $t('scheduler.publish.optionAutoAssign') }}</label>
          </div>
          <div class="flex align-items-center gap-2 mt-2 p-2 border-round" style="background: #fff3cd; border: 1px solid #ffc107;">
            <Checkbox v-model="opcions.netejar_existents" :binary="true" inputId="opt-netejar" />
            <label for="opt-netejar" style="color: #856404;">
              ⚠️ {{ $t('scheduler.publish.optionClear') }}
            </label>
          </div>
        </div>
      </template>
    </div>

    <!-- Pas 2: Previsualització (dry-run) -->
    <div v-else-if="previsualitzacio && !resultat" class="publicar-content">
      <div class="flex align-items-center gap-2 mb-3">
        <i class="pi pi-eye" style="font-size: 1.5rem; color: var(--blue-500)" />
        <span class="font-semibold text-lg">{{ $t('scheduler.publish.previewTitle') }}</span>
      </div>
      <p class="text-sm text-color-secondary mt-0 mb-3">{{ $t('scheduler.publish.previewDesc') }}</p>

      <div class="flex flex-column gap-1 mb-3">
        <span>{{ $t('scheduler.publish.datesProcessed') }} <strong>{{ previsualitzacio.dates_processades?.length || 0 }}</strong></span>
        <span v-if="previsualitzacio.vigilancies_creades">✅ {{ $t('scheduler.publish.vigilanciesCreated') }} <strong>{{ previsualitzacio.vigilancies_creades }}</strong></span>
        <span v-if="previsualitzacio.vigilancies_actualitzades">🔄 {{ $t('scheduler.publish.vigilanciesUpdated') }} <strong>{{ previsualitzacio.vigilancies_actualitzades }}</strong></span>
        <span v-if="previsualitzacio.vigilancies_sense_canvis">— {{ $t('scheduler.publish.vigilanciesUnchanged') }} <strong>{{ previsualitzacio.vigilancies_sense_canvis }}</strong></span>
        <span v-if="previsualitzacio.vigilancies_eliminades">🗑️ {{ $t('scheduler.publish.vigilanciesDeleted') }} <strong>{{ previsualitzacio.vigilancies_eliminades }}</strong></span>
        <span v-if="previsualitzacio.grups_alliberats_creats">{{ $t('scheduler.publish.freeGroupsCreated') }} <strong>{{ previsualitzacio.grups_alliberats_creats }}</strong></span>
      </div>

      <div v-if="previsualitzacio.errors?.length" class="mb-3">
        <div class="font-semibold text-red-500 mb-1">{{ $t('scheduler.publish.errors') }}</div>
        <ul class="pl-3 m-0">
          <li v-for="(err, i) in previsualitzacio.errors" :key="i" class="text-red-600 text-sm">{{ err }}</li>
        </ul>
      </div>

      <Message v-if="opcions.netejar_existents" severity="warn" :closable="false" class="mt-2">
        ⚠️ {{ $t('scheduler.publish.optionClear') }}
      </Message>
    </div>

    <!-- Pas 3: Resultat final -->
    <div v-else-if="resultat" class="publicar-resultat">
      <div v-if="resultat.success" class="flex align-items-center gap-2 mb-3">
        <i class="pi pi-check-circle" style="font-size: 1.5rem; color: var(--green-500)" />
        <span class="font-semibold text-lg">{{ $t('scheduler.publish.successTitle') }}</span>
      </div>
      <div v-else class="flex align-items-center gap-2 mb-3">
        <i class="pi pi-exclamation-triangle" style="font-size: 1.5rem; color: var(--red-500)" />
        <span class="font-semibold text-lg">{{ $t('scheduler.publish.errorTitle') }}</span>
      </div>

      <div class="flex flex-column gap-1 mb-3">
        <span>{{ $t('scheduler.publish.datesProcessed') }} <strong>{{ resultat.dates_processades?.length || 0 }}</strong></span>
        <span v-if="resultat.vigilancies_creades">✅ {{ $t('scheduler.publish.vigilanciesCreated') }} <strong>{{ resultat.vigilancies_creades }}</strong></span>
        <span v-if="resultat.vigilancies_actualitzades">🔄 {{ $t('scheduler.publish.vigilanciesUpdated') }} <strong>{{ resultat.vigilancies_actualitzades }}</strong></span>
        <span v-if="resultat.vigilancies_sense_canvis">— {{ $t('scheduler.publish.vigilanciesUnchanged') }} <strong>{{ resultat.vigilancies_sense_canvis }}</strong></span>
        <span v-if="resultat.vigilancies_eliminades">🗑️ {{ $t('scheduler.publish.vigilanciesDeleted') }} <strong>{{ resultat.vigilancies_eliminades }}</strong></span>
        <span v-if="resultat.grups_alliberats_creats">{{ $t('scheduler.publish.freeGroupsCreated') }} <strong>{{ resultat.grups_alliberats_creats }}</strong></span>
        <span v-if="resultat.titulars_assignats">{{ $t('scheduler.publish.titularsAssigned') }} <strong>{{ resultat.titulars_assignats }}</strong></span>
      </div>

      <div v-if="resultat.errors?.length" class="mb-3">
        <div class="font-semibold text-red-500 mb-1">{{ $t('scheduler.publish.errors') }}</div>
        <ul class="pl-3 m-0">
          <li v-for="(err, i) in resultat.errors" :key="i" class="text-red-600 text-sm">{{ err }}</li>
        </ul>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-content-between w-full">
        <div>
          <Button
            v-if="resultat?.success && primeraData"
            :label="$t('scheduler.publish.goToVigilancies')"
            icon="pi pi-external-link"
            class="p-button-text"
            @click="anarAVigilancies"
          />
        </div>
        <div class="flex gap-2">
          <!-- Pas 1: Cancel·la -->
          <Button
            v-if="!previsualitzacio && !resultat"
            :label="$t('scheduler.publish.cancel')"
            class="p-button-text"
            @click="tancar"
          />
          <!-- Pas 2: Torna enrere o Confirma -->
          <template v-else-if="previsualitzacio && !resultat">
            <Button
              :label="$t('scheduler.publish.back')"
              icon="pi pi-arrow-left"
              class="p-button-text"
              :disabled="publicant"
              @click="previsualitzacio = null"
            />
            <Button
              :label="$t('scheduler.publish.confirmPublish')"
              icon="pi pi-check"
              class="p-button-success"
              :loading="publicant"
              :disabled="!previsualitzacio.success"
              @click="confirmarPublicar"
            />
          </template>
          <!-- Pas 3: Tanca -->
          <Button
            v-else-if="resultat"
            :label="$t('scheduler.publish.close')"
            class="p-button-text"
            @click="tancar"
          />

          <!-- Pas 1: Previsualitza -->
          <Button
            v-if="!previsualitzacio && !resultat"
            :label="$t('scheduler.publish.previewButton')"
            icon="pi pi-eye"
            class="p-button-primary"
            :loading="previsualitzant"
            :disabled="carregant"
            @click="previsualitzar"
          />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'
import Divider from 'primevue/divider'
import InputNumber from 'primevue/inputnumber'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'

const props = defineProps({
  visible: { type: Boolean, default: false },
  horari: { type: Object, default: null },
  setmanes: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:visible', 'publicat'])

const opcions = ref({
  netejar_existents: false,
  auto_assign_titulars: true
})
const previsualitzant = ref(false)
const publicant = ref(false)
const previsualitzacio = ref(null)
const resultat = ref(null)
const carregant = ref(false)

const grupsPerNivell = ref({})
const horesLectives = ref([])
const duradaExamen = ref(1)
const maxDurada = computed(() => Math.max(1, horesLectives.value.length || 4))

watch(() => props.visible, async (val) => {
  if (!val) return
  resultat.value = null
  previsualitzacio.value = null
  carregant.value = true
  try {
    const { data } = await axios.get('/api/scheduler/grups-nivells')
    grupsPerNivell.value = data.grups_per_nivell || {}
    horesLectives.value = data.hores_lectives || []
    duradaExamen.value = data.durada_examen || data.durada_titular || 1
  } catch (e) {
    console.error('Error carregant grups:', e)
  } finally {
    carregant.value = false
  }
})

const resum = computed(() => {
  if (!props.horari?.dies) return []

  const setmanesMap = new Map()
  for (const diaInfo of props.horari.dies) {
    const dataIso = diaInfo.data
    if (!dataIso) continue

    let weekIdx = 0
    if (props.setmanes?.length) {
      for (let i = 0; i < props.setmanes.length; i++) {
        if (Object.values(props.setmanes[i]).includes(dataIso)) {
          weekIdx = i
          break
        }
      }
    }

    if (!setmanesMap.has(weekIdx)) setmanesMap.set(weekIdx, [])

    let totalExamens = 0
    const grupsSet = new Set()
    for (const slot of diaInfo.sessions || []) {
      for (const sessio of slot.sessions_simultanees || []) {
        for (const examen of sessio.examens || []) {
          totalExamens++
          if (examen.grup) grupsSet.add(examen.grup)
        }
      }
    }
    setmanesMap.get(weekIdx).push({
      dia: diaInfo.dia,
      data: dataIso,
      examens: totalExamens,
      grups: grupsSet.size
    })
  }

  return [...setmanesMap.entries()].sort((a, b) => a[0] - b[0]).map(([, dies]) => ({ dies }))
})

const primeraData = computed(() => {
  if (!resultat.value?.dates_processades?.length) return null
  return resultat.value.dates_processades[0]
})

const _payload = () => ({
  horari: props.horari,
  setmanes: props.setmanes,
  grups_sense_classe: [],
  durada_examen: duradaExamen.value,
  opcions: opcions.value
})

const previsualitzar = async () => {
  previsualitzant.value = true
  try {
    const { data } = await axios.post('/api/scheduler/publicar', {
      ..._payload(),
      dry_run: true
    })
    previsualitzacio.value = data
  } catch (e) {
    previsualitzacio.value = {
      success: false,
      errors: [e.response?.data?.detail || e.message || 'Error desconegut']
    }
  } finally {
    previsualitzant.value = false
  }
}

const confirmarPublicar = async () => {
  publicant.value = true
  resultat.value = null
  try {
    const { data } = await axios.post('/api/scheduler/publicar', {
      ..._payload(),
      dry_run: false
    })
    resultat.value = data
    if (data.success) {
      emit('publicat', data)
    }
  } catch (e) {
    resultat.value = {
      success: false,
      errors: [e.response?.data?.detail || e.message || 'Error desconegut']
    }
  } finally {
    publicant.value = false
  }
}

const tancar = () => {
  resultat.value = null
  previsualitzacio.value = null
  emit('update:visible', false)
}

const anarAVigilancies = () => {
  tancar()
  window.history.pushState({}, '', '/')
  window.dispatchEvent(new PopStateEvent('popstate'))
}
</script>

<style scoped>
.publicar-content,
.publicar-resultat {
  min-height: 120px;
}
</style>
