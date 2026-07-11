<template>
  <div class="tab-content">
    <div class="toolbar" style="margin-bottom: 0.75rem;">
      <label>{{ $t('config.users.title') }}</label>
      <div class="user-tools">
        <Dropdown
          v-if="props.currentRole === 'super_admin'"
          v-model="userInstitutionFilter"
          :options="userInstitutionOptions"
          optionLabel="label"
          optionValue="value"
          :placeholder="$t('config.users.filterInstitution')"
          class="p-inputtext-sm"
        />
        <Button
          :icon="userSortAsc ? 'pi pi-sort-alpha-down' : 'pi pi-sort-alpha-up'"
          class="p-button-sm p-button-text"
          v-tooltip.top="$t('config.users.sort')"
          @click="toggleUserSort"
        />
        <Button
          icon="pi pi-plus"
          class="p-button-sm"
          :label="$t('config.users.add')"
          iconPos="left"
          @click="obrirNouUsuari"
        />
      </div>
    </div>

    <DataTable
      :value="usersFiltered"
      dataKey="id"
      :loading="usersLoading"
      class="p-datatable-sm"
    >
      <Column field="username" :header="$t('config.users.username')" />
      <Column field="role" :header="$t('config.users.role')" style="min-width: 7.5rem" />
      <Column v-if="props.currentRole === 'super_admin'" :header="$t('config.users.institucio')">
        <template #body="{ data }">
          {{ data.institucio_display_name || data.institucio }}
        </template>
      </Column>
      <Column :header="$t('config.users.active')" bodyClass="text-center">
        <template #body="{ data }">
          {{ data.active ? $t('config.users.activeYes') : $t('config.users.activeNo') }}
        </template>
      </Column>
      <Column :header="$t('common.actions')" bodyClass="text-center">
        <template #body="{ data }">
          <div class="table-actions">
            <Button
              icon="pi pi-pencil"
              class="p-button-text p-button-sm"
              :disabled="data.role === 'super_admin'"
              v-tooltip.top="data.role === 'super_admin' ? $t('config.users.superAdminLocked') : $t('common.edit')"
              @click="editarUsuari(data)"
            />
            <Button
              icon="pi pi-ban"
              class="p-button-text p-button-sm p-button-danger"
              :disabled="data.role === 'super_admin'"
              v-tooltip.top="data.role === 'super_admin' ? $t('config.users.superAdminLocked') : $t('config.users.deactivateTitle')"
              @click="desactivarUsuari(data)"
            />
            <Button
              v-if="isSuperAdmin"
              icon="pi pi-trash"
              class="p-button-text p-button-sm p-button-danger"
              :disabled="data.role === 'super_admin'"
              v-tooltip.top="data.role === 'super_admin' ? $t('config.users.superAdminLocked') : $t('config.users.deleteTitle')"
              @click="eliminarUsuari(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <!-- Diàleg crear/editar usuari -->
    <Dialog
      v-model:visible="mostrarDialogUsuari"
      :modal="true"
      :style="{ width: '480px' }"
      :contentStyle="{ padding: '1rem 1.25rem' }"
      class="user-dialog"
      :key="userDialogKey"
    >
      <template #header>
        <span class="dialog-header">
          <i
            :class="usuariEditant ? 'pi pi-user-edit' : 'pi pi-user-plus'"
            aria-hidden="true"
          ></i>
          <span>{{ usuariEditant ? $t('config.users.editTitle') : $t('config.users.addTitle') }}</span>
        </span>
      </template>
      <div class="p-fluid">
        <div class="field">
          <label>{{ $t('config.users.username') }}</label>
          <InputText v-model="usuariForm.username" autocomplete="new-username" name="new-username" />
        </div>
        <div class="field">
          <label>{{ $t('config.users.password') }}</label>
          <Password
            v-model="usuariForm.password"
            :feedback="false"
            toggleMask
            :placeholder="usuariEditant ? $t('config.users.passwordOptional') : ''"
            class="w-full password-with-eye"
            :inputProps="{ autocomplete: 'new-password', name: 'new-password' }"
          />
        </div>
        <div class="field">
          <label>{{ $t('config.users.role') }}</label>
          <Dropdown
            v-model="usuariForm.role"
            :options="roleOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full user-role-dropdown"
          />
        </div>
        <div v-if="props.currentRole === 'super_admin'" class="field">
          <label>{{ $t('config.users.institucio') }}</label>
          <Dropdown
            v-model="usuariForm.institucio"
            :options="institucionsOptions"
            class="w-full"
          />
        </div>
        <div class="field checkbox-field">
          <Checkbox v-model="usuariForm.active" binary />
          <span>{{ $t('config.users.active') }}</span>
        </div>
      </div>

      <template #footer>
        <Button :label="$t('common.cancel')" class="p-button-text" @click="tancarDialogUsuari" />
        <Button
          :label="$t('common.save')"
          class="p-button-success"
          :disabled="!usuariForm.username || (!usuariEditant && !usuariForm.password)"
          @click="desarUsuari"
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
import { useConfirm } from 'primevue/useconfirm'
import Dialog from 'primevue/dialog'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'

const toast = useToast()
const { t, locale } = useI18n()
const confirm = useConfirm()

const props = defineProps({
  currentRole: {
    type: String,
    default: null
  },
  currentInstitucio: {
    type: String,
    default: null
  }
})

const institucions = ref([])
const users = ref([])
const userInstitutionFilter = ref('')
const userSortAsc = ref(true)
const usersLoading = ref(false)
const mostrarDialogUsuari = ref(false)
const usuariEditant = ref(null)
const userDialogKey = ref(0)
const usuariForm = ref({
  id: null,
  username: '',
  password: '',
  role: 'user',
  institucio: '',
  active: true
})

const isSuperAdmin = computed(() => props.currentRole === 'super_admin')
const institucionsOptions = computed(() => (
  institucions.value
    .filter((inst) => inst.active !== false)
    .map((inst) => ({
      label: inst.display_name || inst.slug,
      value: inst.slug
    }))
))
const userInstitutionOptions = computed(() => ([
  { label: t('common.all'), value: '' },
  ...institucionsOptions.value
]))
const usersFiltered = computed(() => {
  const baseList = users.value
  const filteredList = (props.currentRole === 'super_admin' && userInstitutionFilter.value)
    ? baseList.filter((user) => user.institucio === userInstitutionFilter.value)
    : baseList
  return filteredList.sort((a, b) => {
  const cmp = (a.username || '').localeCompare(
    b.username || '',
    locale.value || 'ca',
    { sensitivity: 'base' }
  )
    return userSortAsc.value ? cmp : -cmp
  })
})
const roleOptions = computed(() => {
  if (props.currentRole === 'super_admin') {
    return [
      { label: 'super_admin', value: 'super_admin' },
      { label: 'admin', value: 'admin' },
      { label: 'user', value: 'user' }
    ]
  }
  return [
    { label: 'admin', value: 'admin' },
    { label: 'user', value: 'user' }
  ]
})

const carregarInstitucions = async () => {
  const resp = await axios.get('/api/settings/institucions')
  institucions.value = resp.data.institucions || []
}

const carregarUsuaris = async () => {
  usersLoading.value = true
  try {
    const response = await axios.get('/api/users')
    users.value = response.data || []
  } catch (error) {
    console.error('Error carregant usuaris:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.users.loadError'),
      life: 3000
    })
  } finally {
    usersLoading.value = false
  }
}

const toggleUserSort = () => {
  userSortAsc.value = !userSortAsc.value
}

const resetUsuariForm = () => {
  const fallbackInstitucio = institucionsOptions.value[0]?.value || ''
  usuariForm.value = {
    id: null,
    username: '',
    password: '',
    role: 'user',
    institucio: props.currentInstitucio || fallbackInstitucio,
    active: true
  }
}

const obrirNouUsuari = () => {
  resetUsuariForm()
  usuariEditant.value = null
  userDialogKey.value += 1
  mostrarDialogUsuari.value = true
}

const editarUsuari = (user) => {
  if (user.role === 'super_admin') {
    toast.add({
      severity: 'warn',
      summary: t('common.warning'),
      detail: t('config.users.superAdminLocked'),
      life: 3000
    })
    return
  }
  usuariEditant.value = user
  usuariForm.value = {
    id: user.id,
    username: user.username,
    password: '',
    role: user.role,
    institucio: user.institucio,
    active: user.active
  }
  mostrarDialogUsuari.value = true
}

const tancarDialogUsuari = () => {
  mostrarDialogUsuari.value = false
  resetUsuariForm()
}

const desarUsuari = async () => {
  try {
    const institucioValue = typeof usuariForm.value.institucio === 'object'
      ? usuariForm.value.institucio?.value
      : usuariForm.value.institucio
    if (usuariEditant.value) {
      const payload = {
        username: usuariForm.value.username,
        role: usuariForm.value.role,
        active: usuariForm.value.active
      }
      if (props.currentRole === 'super_admin') {
        payload.institucio = institucioValue
      }
      if (usuariForm.value.password) {
        payload.password = usuariForm.value.password
      }
      await axios.put(`/api/users/${usuariForm.value.id}`, payload)
    } else {
      const payload = {
        username: usuariForm.value.username,
        password: usuariForm.value.password,
        role: usuariForm.value.role
      }
      if (props.currentRole === 'super_admin') {
        payload.institucio = institucioValue
      }
      await axios.post('/api/users', payload)
    }
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.users.saved'),
      life: 2500
    })
    mostrarDialogUsuari.value = false
    await carregarUsuaris()
    resetUsuariForm()
  } catch (error) {
    console.error('Error desant usuari:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.users.saveError'),
      life: 3000
    })
  }
}

const desactivarUsuari = (user) => {
  confirm.require({
    message: t('config.users.deactivateConfirm', { username: user.username }),
    header: t('config.users.deactivateTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('config.users.deactivateAction'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/users/${user.id}`)
        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('config.users.deactivated'),
          life: 2500
        })
        await carregarUsuaris()
      } catch (error) {
        console.error('Error desactivant usuari:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('config.users.deleteError'),
          life: 3000
        })
      }
    }
  })
}

const eliminarUsuari = (user) => {
  confirm.require({
    message: t('config.users.deleteConfirm', { username: user.username }),
    header: t('config.users.deleteTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/users/${user.id}/hard`)
        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('config.users.deleted'),
          life: 2500
        })
        await carregarUsuaris()
      } catch (error) {
        console.error('Error eliminant usuari:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('config.users.deleteError'),
          life: 3000
        })
      }
    }
  })
}

onMounted(() => {
  carregarInstitucions()
  carregarUsuaris()
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

.user-tools {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
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

.checkbox-field {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.w-full {
  width: 100%;
}

.user-role-dropdown {
  width: 100%;
}

:deep(.password-with-eye) {
  width: 100%;
}

:deep(.password-with-eye .p-password),
:deep(.password-with-eye.p-icon-field) {
  position: relative;
  width: 100%;
}

:deep(.password-with-eye .p-password-input),
:deep(.password-with-eye.p-icon-field-right > .p-inputtext) {
  width: 100%;
  height: 2.25rem;
  line-height: 2.25rem;
  padding-right: 2.75rem;
}

:deep(.password-with-eye .p-input-icon),
:deep(.password-with-eye .p-password-show-icon),
:deep(.password-with-eye .p-password-hide-icon) {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  right: 0.75rem;
  line-height: 1;
  cursor: pointer;
}
</style>
