<template>
  <div class="tab-content">
    <div class="toolbar" style="margin-bottom: 0.75rem;">
      <label>{{ $t('config.institutions.title') }}</label>
      <Button
        icon="pi pi-plus"
        class="p-button-sm"
        :label="$t('config.institutions.add')"
        @click="obrirNovaInstitucio"
      />
    </div>

    <DataTable
      :value="institucions"
      dataKey="slug"
      class="p-datatable-sm"
    >
      <Column field="display_name" :header="$t('config.institutions.name')" />
      <Column field="slug" :header="$t('config.institutions.code')" style="width: 180px;" />
      <Column :header="$t('config.institutions.status')" bodyClass="text-center">
        <template #body="{ data }">
          {{ data.active ? $t('config.institutions.active') : $t('config.institutions.inactive') }}
        </template>
      </Column>
      <Column :header="$t('common.actions')" bodyClass="text-center">
        <template #body="{ data }">
          <div class="table-actions">
            <Button
              icon="pi pi-pencil"
              class="p-button-text p-button-sm"
              v-tooltip.top="$t('common.edit')"
              @click="editarInstitucio(data)"
            />
            <Button
              :icon="data.active ? 'pi pi-ban' : 'pi pi-check-circle'"
              class="p-button-text p-button-sm"
              v-tooltip.top="data.active ? $t('config.institutions.deactivate') : $t('config.institutions.activate')"
              @click="confirmarCanviEstatInstitucio(data)"
            />
            <Button
              icon="pi pi-trash"
              class="p-button-text p-button-sm p-button-danger"
              v-tooltip.top="$t('config.institutions.delete')"
              @click="confirmarEliminarInstitucio(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <!-- Diàleg crear/editar institució -->
    <Dialog
      v-model:visible="mostrarDialogInstitucio"
      :modal="true"
      :style="{ width: '480px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
    >
      <template #header>
        <span class="dialog-header">
          <i
            :class="institucioEditant ? 'pi pi-pencil' : 'pi pi-plus'"
            aria-hidden="true"
          ></i>
          <span>{{ institucioEditant ? $t('config.institutions.editTitle') : $t('config.institutions.addTitle') }}</span>
        </span>
      </template>
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.institutions.code') }}</label>
          <InputText
            v-model="institucioForm.slug"
            :placeholder="$t('config.institutions.codePlaceholder')"
            :disabled="!!institucioEditant"
          />
        </div>
        <div class="field">
          <label>{{ $t('config.institutions.name') }}</label>
          <InputText
            v-model="institucioForm.display_name"
            :placeholder="$t('config.institutions.namePlaceholder')"
          />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" class="p-button-text" @click="tancarDialogInstitucio" />
        <Button
          :label="$t('common.save')"
          class="p-button-success"
          :disabled="!institucioForm.slug || !institucioForm.display_name"
          @click="desarInstitucio"
        />
      </template>
    </Dialog>

    <!-- Diàleg confirmació forta institució -->
    <Dialog
      v-model:visible="mostrarConfirmInstitucio"
      :modal="true"
      :style="{ width: '520px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
    >
      <template #header>
        <span class="dialog-header">
          <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
          <span>{{ confirmInstitucioTitle }}</span>
        </span>
      </template>
      <div class="p-fluid">
        <p class="field-hint">{{ confirmInstitucioMessage }}</p>
        <div class="field">
          <label>{{ $t('config.institutions.confirmLabel') }}</label>
          <InputText v-model="confirmInstitucioInput" />
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" class="p-button-text" @click="tancarConfirmInstitucio" />
        <Button
          :label="confirmInstitucioActionLabel"
          class="p-button-danger"
          :disabled="!confirmInstitucioInput"
          @click="executarAccioInstitucio"
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
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'

const toast = useToast()
const { t } = useI18n()

const institucions = ref([])
const mostrarDialogInstitucio = ref(false)
const institucioEditant = ref(null)
const institucioForm = ref({
  slug: '',
  display_name: ''
})
const mostrarConfirmInstitucio = ref(false)
const confirmInstitucioInput = ref('')
const confirmInstitucioAction = ref('')
const confirmInstitucioTarget = ref(null)

const confirmInstitucioRequired = computed(() => {
  if (!confirmInstitucioTarget.value) return ''
  return confirmInstitucioAction.value === 'delete'
    ? `ELIMINA ${confirmInstitucioTarget.value.slug}`
    : confirmInstitucioTarget.value.slug
})
const confirmInstitucioTitle = computed(() => {
  if (confirmInstitucioAction.value === 'delete') return t('config.institutions.deleteTitle')
  if (confirmInstitucioAction.value === 'deactivate') return t('config.institutions.deactivateTitle')
  if (confirmInstitucioAction.value === 'activate') return t('config.institutions.activateTitle')
  return t('common.confirm')
})
const confirmInstitucioMessage = computed(() => {
  if (!confirmInstitucioTarget.value) return ''
  return confirmInstitucioAction.value === 'delete'
    ? t('config.institutions.deleteMessage', { slug: confirmInstitucioTarget.value.slug, confirm: confirmInstitucioRequired.value })
    : t('config.institutions.deactivateMessage', { slug: confirmInstitucioTarget.value.slug, confirm: confirmInstitucioRequired.value })
})
const confirmInstitucioActionLabel = computed(() => {
  if (confirmInstitucioAction.value === 'delete') return t('config.institutions.delete')
  if (confirmInstitucioAction.value === 'deactivate') return t('config.institutions.deactivate')
  if (confirmInstitucioAction.value === 'activate') return t('config.institutions.activate')
  return t('common.confirm')
})

const carregarInstitucions = async () => {
  const resp = await axios.get('/api/settings/institucions')
  institucions.value = resp.data.institucions || []
}

const obrirNovaInstitucio = () => {
  institucioEditant.value = null
  institucioForm.value = { slug: '', display_name: '' }
  mostrarDialogInstitucio.value = true
}

const editarInstitucio = (inst) => {
  institucioEditant.value = inst
  institucioForm.value = { slug: inst.slug, display_name: inst.display_name || '' }
  mostrarDialogInstitucio.value = true
}

const tancarDialogInstitucio = () => {
  mostrarDialogInstitucio.value = false
  institucioEditant.value = null
  institucioForm.value = { slug: '', display_name: '' }
}

const desarInstitucio = async () => {
  try {
    if (institucioEditant.value) {
      await axios.put(`/api/settings/institucions/${institucioForm.value.slug}`, {
        display_name: institucioForm.value.display_name
      })
    } else {
      await axios.post('/api/settings/institucions', {
        nom: institucioForm.value.slug,
        display_name: institucioForm.value.display_name
      })
    }
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.institutions.saved'),
      life: 2500
    })
    tancarDialogInstitucio()
    await carregarInstitucions()
  } catch (error) {
    console.error('Error desant institució:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.institutions.saveError'),
      life: 3000
    })
  }
}

const confirmarCanviEstatInstitucio = (inst) => {
  confirmInstitucioTarget.value = inst
  confirmInstitucioInput.value = ''
  confirmInstitucioAction.value = inst.active ? 'deactivate' : 'activate'
  mostrarConfirmInstitucio.value = true
}

const confirmarEliminarInstitucio = (inst) => {
  confirmInstitucioTarget.value = inst
  confirmInstitucioInput.value = ''
  confirmInstitucioAction.value = 'delete'
  mostrarConfirmInstitucio.value = true
}

const tancarConfirmInstitucio = () => {
  mostrarConfirmInstitucio.value = false
  confirmInstitucioInput.value = ''
  confirmInstitucioTarget.value = null
  confirmInstitucioAction.value = ''
}

const executarAccioInstitucio = async () => {
  if (!confirmInstitucioTarget.value) return
  if (confirmInstitucioInput.value !== confirmInstitucioRequired.value) {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('config.institutions.confirmMismatch'),
      life: 2500
    })
    return
  }

  try {
    if (confirmInstitucioAction.value === 'delete') {
      await axios.delete(`/api/settings/institucions/${confirmInstitucioTarget.value.slug}`, {
        data: {
          mode: 'hard',
          confirm: confirmInstitucioInput.value
        }
      })
    } else {
      await axios.put(`/api/settings/institucions/${confirmInstitucioTarget.value.slug}/status`, {
        active: confirmInstitucioAction.value === 'activate'
      })
    }
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.institutions.updated'),
      life: 2500
    })
    await carregarInstitucions()
  } catch (error) {
    console.error('Error actualitzant institució:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.institutions.saveError'),
      life: 3000
    })
  } finally {
    tancarConfirmInstitucio()
  }
}

onMounted(carregarInstitucions)
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

.table-actions {
  display: inline-flex;
  gap: 0.25rem;
  align-items: center;
  justify-content: center;
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
</style>
