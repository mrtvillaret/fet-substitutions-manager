<template>
  <div class="tab-content">
    <div class="toolbar">
      <Tag severity="info" :value="$t('config.absences.count', { count: professorsBaixa.length })" />
      <Button
        :label="$t('common.add')"
        icon="pi pi-plus"
        @click="mostrarDialogProfessorBaixa = true"
        size="small"
        class="p-button-success"
      />
    </div>

    <div class="baixa-list">
      <div
        v-for="baixa in professorsBaixa"
        :key="baixa.id"
        class="baixa-card"
      >
        <div class="baixa-info">
          <span class="professor-nom">{{ baixa.professor }}</span>
          <span class="baixa-dates">{{ baixa.data_inici }} → {{ baixa.data_final }}</span>
          <span v-if="baixa.motiu" class="baixa-motiu">{{ baixa.motiu }}</span>
        </div>
        <div class="baixa-actions">
          <Button
            icon="pi pi-pencil"
            @click="editarProfessorBaixa(baixa)"
            class="p-button-rounded p-button-text p-button-sm"
            v-tooltip.top="$t('common.edit')"
          />
          <Button
            icon="pi pi-trash"
            @click="eliminarProfessorBaixa(baixa.id)"
            class="p-button-rounded p-button-text p-button-danger p-button-sm"
            v-tooltip.top="$t('common.delete')"
          />
        </div>
      </div>
      <div v-if="professorsBaixa.length === 0" class="empty-message">
        {{ $t('config.absences.none') }}
      </div>
    </div>

    <p class="info-text">
      <i class="pi pi-info-circle"></i>
      {{ $t('config.absences.hint') }}
    </p>

    <!-- Diàleg afegir/editar professor de baixa -->
    <Dialog
      v-model:visible="mostrarDialogProfessorBaixa"
      :header="professorBaixaEditant ? $t('config.absences.editTitle') : $t('config.absences.addTitle')"
      :modal="true"
      :style="{ width: '500px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
    >
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.absences.teacher') }}</label>
          <Dropdown
            v-model="novaProfessorBaixa.professor"
            :options="professorsAll"
            :placeholder="$t('config.absences.selectTeacher')"
            :filter="true"
            :editable="true"
            class="w-full"
          />
        </div>

        <div class="field">
          <label>{{ $t('config.absences.startDate') }}</label>
          <Calendar
            v-model="novaProfessorBaixa.data_inici"
            dateFormat="yy-mm-dd"
            :showIcon="true"
            class="w-full"
          />
        </div>

        <div class="field">
          <label>{{ $t('config.absences.endDate') }}</label>
          <Calendar
            v-model="novaProfessorBaixa.data_final"
            dateFormat="yy-mm-dd"
            :showIcon="true"
            class="w-full"
          />
        </div>

        <div class="field">
          <label>{{ $t('config.absences.reasonOptional') }}</label>
          <InputText
            v-model="novaProfessorBaixa.motiu"
            :placeholder="$t('config.absences.reasonPlaceholder')"
          />
        </div>
      </div>

      <template #footer>
        <Button
          :label="$t('common.cancel')"
          @click="cancelarProfessorBaixa"
          class="p-button-text"
        />
        <Button
          :label="$t('common.save')"
          @click="desarProfessorBaixa"
          class="p-button-success"
          :disabled="!novaProfessorBaixa.professor || !novaProfessorBaixa.data_inici || !novaProfessorBaixa.data_final"
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
import Dialog from 'primevue/dialog'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

const toast = useToast()
const { t } = useI18n()

const professorsAll = ref([])
const professorsBaixa = ref([])
const mostrarDialogProfessorBaixa = ref(false)
const professorBaixaEditant = ref(null)
const novaProfessorBaixa = ref({
  professor: '',
  data_inici: null,
  data_final: null,
  motiu: ''
})

// Convertir string YYYY-MM-DD a Date object
const stringToDate = (dateStr) => {
  if (!dateStr) return null
  const [year, month, day] = dateStr.split('-')
  return new Date(parseInt(year), parseInt(month) - 1, parseInt(day))
}

const dateToString = (dateObj) => {
  if (!dateObj) return null
  const year = dateObj.getFullYear()
  const month = String(dateObj.getMonth() + 1).padStart(2, '0')
  const day = String(dateObj.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const carregarProfessorsAll = async () => {
  try {
    const response = await axios.get('/api/horari/professors/all')
    professorsAll.value = response.data.professors
  } catch (error) {
    console.error('Error carregant professors:', error)
  }
}

const carregarProfessorsBaixa = async () => {
  try {
    const response = await axios.get('/api/prioritats/professors-baixa')
    professorsBaixa.value = response.data.professors_baixa
  } catch (error) {
    console.error('Error carregant professors de baixa:', error)
  }
}

const desarProfessorBaixa = async () => {
  if (!novaProfessorBaixa.value.professor || !novaProfessorBaixa.value.data_inici || !novaProfessorBaixa.value.data_final) {
    return
  }

  try {
    const baixaData = {
      professor: novaProfessorBaixa.value.professor,
      data_inici: dateToString(novaProfessorBaixa.value.data_inici),
      data_final: dateToString(novaProfessorBaixa.value.data_final),
      motiu: novaProfessorBaixa.value.motiu || ''
    }

    if (professorBaixaEditant.value) {
      // Actualitzar existent
      await axios.put(`/api/prioritats/professors-baixa/${professorBaixaEditant.value}`, baixaData)
      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('config.absences.updated'),
        life: 3000
      })
    } else {
      // Crear nou
      await axios.post('/api/prioritats/professors-baixa', baixaData)
      toast.add({
        severity: 'success',
        summary: t('common.added'),
        detail: t('config.absences.added'),
        life: 3000
      })
    }

    // Recarregar professors baixa
    const response = await axios.get('/api/prioritats/professors-baixa')
    professorsBaixa.value = response.data.professors_baixa

    // Tancar diàleg i netejar
    cancelarProfessorBaixa()
  } catch (error) {
    console.error('Error desant professor baixa:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.saveAbsence'),
      life: 3000
    })
  }
}

const editarProfessorBaixa = (baixa) => {
  professorBaixaEditant.value = baixa.id
  novaProfessorBaixa.value = {
    professor: baixa.professor,
    data_inici: stringToDate(baixa.data_inici),
    data_final: stringToDate(baixa.data_final),
    motiu: baixa.motiu || ''
  }
  mostrarDialogProfessorBaixa.value = true
}

const eliminarProfessorBaixa = async (id) => {
  try {
    await axios.delete(`/api/prioritats/professors-baixa/${id}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.absences.deleted'),
      life: 3000
    })

    // Recarregar professors baixa
    const response = await axios.get('/api/prioritats/professors-baixa')
    professorsBaixa.value = response.data.professors_baixa
  } catch (error) {
    console.error('Error eliminant professor baixa:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.deleteAbsence'),
      life: 3000
    })
  }
}

const cancelarProfessorBaixa = () => {
  mostrarDialogProfessorBaixa.value = false
  professorBaixaEditant.value = null
  novaProfessorBaixa.value = {
    professor: '',
    data_inici: null,
    data_final: null,
    motiu: ''
  }
}

onMounted(() => {
  carregarProfessorsAll()
  carregarProfessorsBaixa()
})
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

.baixa-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 1rem 0;
  max-height: 400px;
  overflow-y: auto;
}

.baixa-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s;
}

.baixa-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.baixa-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.professor-nom {
  font-weight: 600;
  color: #374151;
  font-size: 1.05rem;
}

.baixa-dates {
  color: #6b7280;
  font-size: 0.9rem;
}

.baixa-motiu {
  color: #9ca3af;
  font-size: 0.85rem;
  font-style: italic;
}

.baixa-actions {
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

.w-full {
  width: 100%;
}
</style>
