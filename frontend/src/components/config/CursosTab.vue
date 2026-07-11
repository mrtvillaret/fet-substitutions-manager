<template>
  <div class="tab-content">
    <div class="toolbar" style="margin-bottom: 0.75rem;">
      <label>{{ $t('config.courses.title') }}</label>
      <Button
        :label="$t('config.courses.new')"
        icon="pi pi-plus"
        size="small"
        @click="obrirNouCurs"
      />
    </div>

    <p class="camp-ajuda" style="margin-bottom: 0.75rem;">
      {{ $t('config.courses.help') }}
    </p>

    <DataTable :value="cursos" size="small" dataKey="id" :loading="carregantCursos">
      <template #empty>{{ $t('config.courses.empty') }}</template>

      <Column field="nom" :header="$t('config.courses.name')" />

      <Column :header="$t('config.courses.start')">
        <template #body="{ data }">{{ data.data_inici }}</template>
      </Column>

      <Column :header="$t('config.courses.end')">
        <template #body="{ data }">
          <span v-if="data.data_fi">{{ data.data_fi }}</span>
          <Tag v-else severity="success" :value="$t('config.courses.open')" />
        </template>
      </Column>

      <Column :header="$t('common.actions')" style="width: 110px;">
        <template #body="{ data }">
          <Button
            icon="pi pi-pencil"
            class="p-button-text p-button-sm"
            v-tooltip.top="$t('common.edit')"
            @click="obrirEditarCurs(data)"
          />
          <Button
            icon="pi pi-trash"
            class="p-button-text p-button-sm p-button-danger"
            v-tooltip.top="$t('common.delete')"
            @click="eliminarCurs(data)"
          />
        </template>
      </Column>
    </DataTable>

    <!-- Diàleg: nou / editar curs -->
    <Dialog
      v-model:visible="mostrarDialegCurs"
      :modal="true"
      :style="{ width: '460px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
    >
      <template #header>
        <span class="dialog-header">
          <i class="pi pi-calendar" aria-hidden="true"></i>
          <span>{{ cursForm.id ? $t('config.courses.editTitle') : $t('config.courses.newTitle') }}</span>
        </span>
      </template>

      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.courses.name') }}</label>
          <InputText v-model="cursForm.nom" :placeholder="$t('config.courses.namePlaceholder')" />
        </div>
        <div class="field">
          <label>{{ $t('config.courses.start') }}</label>
          <Calendar v-model="cursForm.data_inici" dateFormat="dd/mm/yy" :showIcon="true" />
          <small class="field-hint">{{ $t('config.courses.startHint') }}</small>
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" class="p-button-text" @click="mostrarDialegCurs = false" />
        <Button
          :label="$t('common.save')"
          icon="pi pi-check"
          :disabled="!cursForm.nom || !cursForm.data_inici"
          :loading="desantCurs"
          @click="desarCurs"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { useCursos } from './useCursos.js'

const toast = useToast()
const { t } = useI18n()
const confirm = useConfirm()

const emit = defineEmits(['cursos-canviats'])

const {
  cursos,
  carregantCursos,
  parseIsoDate,
  formatIsoDate,
  carregarCursos,
  carregarAvisosXml,
} = useCursos()

const desantCurs = ref(false)
const mostrarDialegCurs = ref(false)
// Un curs només té nom + data d'inici: la data de fi la deriva el sistema
// (= inici del curs següent − 1 dia; l'últim queda obert).
const cursForm = ref({ id: null, nom: '', data_inici: null })

const carregarCursosAmbToast = async () => {
  try {
    await carregarCursos()
  } catch (error) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: t('config.courses.loadError'), life: 3000 })
  }
}

const obrirNouCurs = () => {
  cursForm.value = { id: null, nom: '', data_inici: null }
  mostrarDialegCurs.value = true
}

const obrirEditarCurs = (curs) => {
  cursForm.value = {
    id: curs.id,
    nom: curs.nom,
    data_inici: parseIsoDate(curs.data_inici)
  }
  mostrarDialegCurs.value = true
}

const desarCurs = async () => {
  desantCurs.value = true
  try {
    const payload = {
      nom: cursForm.value.nom,
      data_inici: formatIsoDate(cursForm.value.data_inici)
    }
    if (cursForm.value.id) {
      await axios.put(`/api/cursos/${cursForm.value.id}`, payload)
    } else {
      await axios.post('/api/cursos', payload)
    }
    mostrarDialegCurs.value = false
    await carregarCursos()
    await carregarAvisosXml()
    emit('cursos-canviats')
    toast.add({ severity: 'success', summary: t('common.saved'), life: 2000 })
  } catch (error) {
    const detail = error?.response?.data?.detail || t('config.courses.saveError')
    toast.add({ severity: 'error', summary: t('common.error'), detail, life: 4000 })
  } finally {
    desantCurs.value = false
  }
}

const eliminarCurs = (curs) => {
  confirm.require({
    message: t('config.courses.deleteConfirm', { nom: curs.nom }),
    header: t('common.confirmation'),
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/cursos/${curs.id}`)
        await carregarCursos()
        await carregarAvisosXml()
        emit('cursos-canviats')
        toast.add({ severity: 'success', summary: t('common.deleted'), life: 2000 })
      } catch (error) {
        toast.add({ severity: 'error', summary: t('common.error'), life: 3000 })
      }
    }
  })
}

onMounted(carregarCursosAmbToast)
</script>

<style scoped>
.tab-content {
  padding: 0.5rem 0;
  min-height: 400px;
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

.dialog-header {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
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

.camp-ajuda {
  color: #6b7280;
  font-size: 0.9rem;
}
</style>
