<template>
  <div v-if="loading" class="loading">
    <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
    <p>{{ $t('common.loadingConfig') }}</p>
  </div>

  <div v-else class="tab-content">
    <!-- Institucio i idioma -->
    <div v-if="isSuperAdmin" class="field">
      <label for="institucio">{{ $t('config.system.institutionCode') }}</label>
      <InputText
        id="institucio"
        v-model="settings.institucio"
        :placeholder="$t('config.system.institutionPlaceholder')"
        class="w-full logo-field"
        readonly
        disabled
      />
      <small class="field-hint">{{ $t('config.system.institutionCodeHint') }}</small>
    </div>

    <div class="field">
      <label for="institucio_display">{{ $t('config.system.institutionName') }}</label>
      <InputText
        id="institucio_display"
        v-model="settings.institucio_display_name"
        :placeholder="$t('config.system.institutionNamePlaceholder')"
        class="w-full logo-field"
        :disabled="!isSuperAdmin"
      />
      <small class="field-hint">{{ $t('config.system.institutionNameHint') }}</small>
    </div>

    <div class="field">
      <label for="logo">{{ $t('config.system.logoLabel') }}</label>
      <div class="p-inputgroup logo-inputgroup uniform-inputgroup">
        <InputText
          id="logo"
          v-model="logoNom"
          :placeholder="$t('config.system.logoPlaceholder')"
          readonly
          class="w-full logo-field"
        />
        <Button icon="pi pi-upload" @click="$refs.logoInput.click()" v-tooltip.top="$t('common.upload')" class="logo-upload-btn" />
      </div>
      <input
        ref="logoInput"
        type="file"
        accept=".png,.jpg,.jpeg"
        style="display: none"
        @change="pujarLogo"
      />
      <div v-if="logoUrl" class="logo-preview">
        <img :src="logoUrl" :alt="$t('config.system.logoAlt')" />
      </div>
      <small class="field-hint">{{ $t('config.system.logoHint') }}</small>
    </div>

    <div class="field">
      <label for="idioma">{{ $t('config.system.language') }}</label>
      <Dropdown
        id="idioma"
        v-model="settings.idioma"
        :options="idiomes"
        optionLabel="name"
        optionValue="code"
        :placeholder="$t('config.system.languagePlaceholder')"
        class="w-full logo-field"
      />
    </div>

    <Divider />

    <!-- Fitxer XML -->
    <div class="field">
      <label for="xml_path">{{ $t('config.system.xmlLabel') }}</label>
      <div class="p-inputgroup uniform-inputgroup">
        <InputText
          id="xml_path"
          v-model="settings.xml_horari_path"
          :placeholder="$t('config.system.xmlPlaceholder')"
          readonly
          class="w-full"
        />
        <Button icon="pi pi-upload" @click="$refs.fileInput.click()" v-tooltip.top="$t('config.system.xmlUpload')" />
      </div>
      <input
        ref="fileInput"
        type="file"
        accept=".xml"
        style="display: none"
        @change="pujarXML"
      />
      <small class="field-hint">{{ $t('config.system.xmlHint') }}</small>

      <!-- Avís: un curs arrencaria amb l'horari del curs anterior -->
      <div
        v-for="avis in avisosXml"
        :key="avis.curs_id"
        class="xml-avis-desync"
      >
        <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
        <div class="xml-avis-text">
          {{ $t('config.system.xmlCourseDesync', {
            curs: avis.curs_nom,
            inici: avis.curs_inici,
            xmlInici: avis.xml_inici
          }) }}
        </div>
        <Button
          :label="$t('config.system.xmlFixDesync')"
          class="p-button-sm p-button-warning"
          @click="xmlVigentDesDe = parseIsoDate(avis.curs_inici)"
        />
      </div>

      <!-- Data de vigència: permet PREPARAR l'horari d'un curs futur -->
      <div class="xml-vigencia">
        <label class="date-inline-label">{{ $t('config.system.xmlEffectiveFrom') }}:</label>
        <Calendar
          v-model="xmlVigentDesDe"
          dateFormat="yy-mm-dd"
          :showIcon="true"
          :showButtonBar="true"
          class="xml-date"
        />
        <Button
          v-if="cursFuturSuggerit"
          :label="$t('config.system.xmlUseCourseStart', { nom: cursFuturSuggerit.nom })"
          class="p-button-text p-button-sm"
          @click="xmlVigentDesDe = parseIsoDate(cursFuturSuggerit.data_inici)"
        />
      </div>
      <small class="field-hint">{{ $t('config.system.xmlEffectiveHint') }}</small>
    </div>

    <!-- Versions XML -->
    <div class="field">
      <div class="toolbar" style="margin-bottom: 0.5rem;">
        <label>{{ $t('config.system.xmlVersions') }}</label>
        <Button
          icon="pi pi-refresh"
          @click="carregarXmlVersions"
          size="small"
          class="p-button-secondary"
          v-tooltip.top="$t('common.reload')"
        />
      </div>

      <div v-if="xmlVersionsLoading" class="loading-inline">
        <i class="pi pi-spin pi-spinner" />
        <span>{{ $t('common.loading') }}</span>
      </div>

      <div v-else-if="xmlVersions.length === 0" class="empty-inline">
        {{ $t('config.system.noXmlVersions') }}
      </div>

      <div v-else class="xml-versions">
        <div v-for="version in xmlVersionsDisplay" :key="version.id" class="xml-version-card">
          <div class="xml-version-header">
            <span class="xml-path">{{ version.path }}</span>
            <span v-if="!version.data_fi" class="xml-current">
              {{ $t('config.system.xmlCurrent') }}
            </span>
          </div>

          <div class="xml-version-row">
            <div class="xml-version-dates">
              <div class="date-field">
                <label class="date-inline-label">{{ $t('config.system.xmlStart') }}:</label>
                <Calendar
                  :modelValue="parseIsoDate(version.data_inici)"
                  @update:modelValue="value => { version.data_inici = formatIsoDate(value) }"
                  dateFormat="yy-mm-dd"
                  :showIcon="true"
                  class="xml-date"
                />
              </div>
              <div class="date-field">
                <label class="date-inline-label">{{ $t('config.system.xmlEnd') }}:</label>
                <Calendar
                  :modelValue="parseIsoDate(version.data_fi)"
                  dateFormat="yy-mm-dd"
                  :showIcon="true"
                  class="xml-date"
                  :disabled="true"
                />
              </div>
            </div>

            <div class="xml-version-actions">
              <Button
                icon="pi pi-save"
                :label="$t('common.save')"
                class="p-button-sm p-button-primary"
                @click="desarXmlVersion(version)"
              />
              <Button
                icon="pi pi-trash"
                :label="$t('common.delete')"
                class="p-button-sm p-button-danger"
                @click="eliminarXmlVersion(version)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Últim professor -->
    <div class="field">
      <label for="ultim_professor">{{ $t('config.system.lastTeacher') }}</label>
      <Dropdown
        id="ultim_professor"
        v-model="settings.ultim_professor_subs"
        :options="ultimProfessorOptions"
        optionLabel="label"
        optionValue="value"
        :placeholder="$t('config.system.allTeachers')"
        :filter="true"
        class="w-full logo-field"
      />
      <small class="field-hint">
        {{ $t('config.system.lastTeacherHintLine1') }}
        {{ $t('config.system.lastTeacherHintLine2') }}
      </small>
    </div>

    <Divider />

    <!-- PDFs generats -->
    <div class="field">
      <div class="toolbar" style="margin-bottom: 0.5rem;">
        <label>{{ $t('config.system.generatedPdfs') }}</label>
        <Button
          icon="pi pi-refresh"
          @click="carregarPDFs"
          size="small"
          class="p-button-secondary"
          v-tooltip.top="$t('common.reload')"
        />
      </div>

      <div class="pdfs-list" v-if="pdfs.length > 0">
        <div v-for="pdf in pdfs" :key="pdf.filename" class="pdf-card">
          <div class="pdf-info">
            <i class="pi pi-file-pdf" style="color: #ef4444; font-size: 1.2rem;"></i>
            <span class="pdf-name">{{ pdf.filename }}</span>
            <span class="pdf-size">{{ formatFileSize(pdf.size) }}</span>
          </div>
          <div class="pdf-actions">
            <Button
              icon="pi pi-download"
              @click="descarregarPDF(pdf.filename)"
              class="p-button-rounded p-button-text p-button-sm"
              v-tooltip.top="$t('common.download')"
            />
            <Button
              icon="pi pi-trash"
              @click="eliminarPDF(pdf.filename)"
              class="p-button-rounded p-button-text p-button-danger p-button-sm"
              v-tooltip.top="$t('common.delete')"
            />
          </div>
        </div>
      </div>
      <div v-else class="empty-message" style="margin-top: 0.5rem;">
        {{ $t('config.system.noPdfs') }}
      </div>
    </div>

    <div class="config-save-actions">
      <Tag v-if="teCanvis" severity="warning" :value="$t('common.unsavedChanges')" />
      <Button
        :label="$t('common.save')"
        icon="pi pi-save"
        @click="desar"
        class="p-button-success"
        :loading="desant"
        :disabled="!teCanvis"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import { useCursos } from './useCursos.js'
import { setLocale } from '../../i18n'

const toast = useToast()
const { t } = useI18n()
const confirm = useConfirm()

const props = defineProps({
  currentRole: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['update:dirty'])

const loading = ref(false)
const xmlMissingNotified = ref(false)
const xmlVersionsLoading = ref(false)
const xmlVersions = ref([])
const desant = ref(false)
const settingsOriginal = ref(null)
const settings = ref({
  institucio: null,
  idioma: 'ca',
  xml_horari_path: '',
  export_dir: 'exports',
  ultim_professor_subs: '',
  institucio_display_name: '',
  data_dir: '',
  no_substituir: [],
  logo_path: ''
})

const idiomes = ref([])
const professors = ref([])
const professorsAll = ref([])
const pdfs = ref([])

const logoUrl = ref('')
let logoObjectUrl = ''
const logoNom = ref('')

const canManageUsers = computed(() => ['admin', 'super_admin'].includes(props.currentRole || ''))
const isSuperAdmin = computed(() => props.currentRole === 'super_admin')

const ultimProfessorOptions = computed(() => ([
  { label: t('common.all'), value: '' },
  ...professorsAll.value.map((prof) => ({ label: prof, value: prof }))
]))

// Cursos: estat compartit (avisos XML + suggeriment de curs futur).
const {
  avisosXml,
  parseIsoDate,
  formatIsoDate,
  carregarCursos,
  carregarAvisosXml,
  cursFuturSuggerit,
} = useCursos()

// Data de vigència del pròxim XML que es pugi (null = avui)
const xmlVigentDesDe = ref(null)

const getSettingsSnapshot = () => JSON.stringify({
  institucio: settings.value.institucio || '',
  institucio_display_name: settings.value.institucio_display_name || '',
  idioma: settings.value.idioma || '',
  xml_horari_path: settings.value.xml_horari_path || '',
  export_dir: settings.value.export_dir || '',
  ultim_professor_subs: settings.value.ultim_professor_subs || '',
  logo_path: settings.value.logo_path || ''
})

const teCanvis = computed(() => {
  if (!settingsOriginal.value) return false
  return getSettingsSnapshot() !== settingsOriginal.value
})

// Comunicar l'estat "hi ha canvis sense desar" al pare, que gestiona la
// confirmació de tancament del diàleg.
watch(teCanvis, (value) => emit('update:dirty', value), { immediate: true })

const actualitzarSnapshot = () => {
  settingsOriginal.value = getSettingsSnapshot()
}

const carregarSettings = async () => {
  loading.value = true
  try {
    const [
      settingsResp,
      idiomesResp,
      professorsResp,
      professorsAllResp,
      xmlVersionsResp
    ] = await Promise.all([
      axios.get('/api/settings'),
      axios.get('/api/settings/idiomes'),
      axios.get('/api/professors'),
      axios.get('/api/horari/professors/all'),
      axios.get('/api/settings/xml-versions')
    ])

    settings.value = settingsResp.data
    if (settingsResp.data?.xml_missing && !xmlMissingNotified.value) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('common.xmlMissing'),
        life: 4000
      })
      xmlMissingNotified.value = true
    }
    if (!settings.value.institucio_display_name) {
      settings.value.institucio_display_name = settings.value.institucio || ''
    }
    await carregarLogo()
    logoNom.value = settings.value.logo_path ? settings.value.logo_path.split('/').pop() : ''
    idiomes.value = idiomesResp.data.idiomes
    professors.value = professorsResp.data.professors
    professorsAll.value = professorsAllResp.data.professors
    xmlVersions.value = xmlVersionsResp.data.versions || []

    if (canManageUsers.value) {
      await carregarCursos()
      await carregarAvisosXml()
    }

    actualitzarSnapshot()
  } catch (error) {
    console.error('Error carregant configuració:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.loadConfig'),
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const carregarXmlVersions = async () => {
  xmlVersionsLoading.value = true
  try {
    const resp = await axios.get('/api/settings/xml-versions')
    xmlVersions.value = resp.data.versions || []
  } catch (error) {
    console.error('Error carregant versions XML:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.loadXmlVersions'),
      life: 3000
    })
  } finally {
    xmlVersionsLoading.value = false
  }
}

const carregarLogo = async () => {
  if (logoObjectUrl) {
    URL.revokeObjectURL(logoObjectUrl)
    logoObjectUrl = ''
  }

  try {
    const response = await axios.get('/api/files/logo', {
      responseType: 'blob',
      params: { ts: Date.now() },
      _silent: true,
    })
    logoObjectUrl = URL.createObjectURL(response.data)
    logoUrl.value = logoObjectUrl
  } catch (error) {
    if (error.response?.status !== 404) {
      console.error('Error carregant logo:', error)
    }
    logoUrl.value = ''
  }
}

const xmlVersionsDisplay = computed(() => {
  const sorted = [...xmlVersions.value].sort((a, b) => (a.data_inici || '').localeCompare(b.data_inici || ''))
  return sorted.map((version, index) => {
    const next = sorted[index + 1]
    let dataFi = version.data_fi
    if (next?.data_inici) {
      const nextDate = parseIsoDate(next.data_inici)
      if (nextDate) {
        const prevDay = new Date(nextDate)
        prevDay.setDate(prevDay.getDate() - 1)
        dataFi = formatIsoDate(prevDay)
      }
    }
    version.data_fi = dataFi
    version._previousId = index > 0 ? sorted[index - 1].id : null
    return version
  })
})

const desarXmlVersion = async (version) => {
  try {
    await axios.put(`/api/settings/xml-versions/${version.id}`, {
      data_inici: version.data_inici || null,
      data_fi: version.data_fi || null
    })

    if (version._previousId) {
      const prevEnd = version.data_inici ? (() => {
        const d = parseIsoDate(version.data_inici)
        if (!d) return null
        d.setDate(d.getDate() - 1)
        return formatIsoDate(d)
      })() : null

      if (prevEnd) {
        await axios.put(`/api/settings/xml-versions/${version._previousId}`, {
          data_fi: prevEnd
        })
      }
    }
    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: t('config.system.xmlSaved'),
      life: 2500
    })
    await carregarXmlVersions()
  } catch (error) {
    console.error('Error desant versió XML:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.saveXmlVersion'),
      life: 3000
    })
  }
}

const eliminarXmlVersion = async (version) => {
  confirm.require({
    message: t('config.confirm.deleteXmlMessage', { path: version.path }),
    header: t('config.confirm.deleteXmlTitle'),
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: t('common.delete'),
    rejectLabel: t('common.cancel'),
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await axios.delete(`/api/settings/xml-versions/${version.id}`)
        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('config.system.xmlDeleted'),
          life: 2500
        })
        await carregarXmlVersions()
      } catch (error) {
        console.error('Error eliminant versió XML:', error)
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('config.errors.deleteXmlVersion'),
          life: 3000
        })
      }
    }
  })
}

const pujarLogo = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await axios.post('/api/files/upload-logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    settings.value.logo_path = response.data.path
    logoNom.value = response.data.filename
    await carregarLogo()
    actualitzarSnapshot()
    toast.add({
      severity: 'success',
      summary: t('config.system.logoUploaded'),
      detail: response.data.message,
      life: 3000
    })
  } catch (error) {
    console.error('Error pujant logo:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.uploadLogo'),
      life: 3000
    })
  } finally {
    event.target.value = ''
  }
}

const desar = async () => {
  desant.value = true
  try {
    const response = await axios.put('/api/settings', {
      institucio: settings.value.institucio,
      ...(isSuperAdmin.value ? { institucio_display_name: settings.value.institucio_display_name } : {}),
      idioma: settings.value.idioma,
      xml_horari_path: settings.value.xml_horari_path,
      export_dir: settings.value.export_dir,
      ultim_professor_subs: settings.value.ultim_professor_subs || null
    })

    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: response.data.message,
      life: 3000
    })

    actualitzarSnapshot()
    setLocale(settings.value.idioma)
    // Mantindre obert: permet continuar configurant
  } catch (error) {
    console.error('Error desant configuració:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.saveConfig'),
      life: 3000
    })
  } finally {
    desant.value = false
  }
}

const pujarXML = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  try {
    const formData = new FormData()
    formData.append('file', file)
    // Si no s'indica, el backend l'aplica des d'avui
    if (xmlVigentDesDe.value) {
      formData.append('data_inici', formatIsoDate(xmlVigentDesDe.value))
    }

    toast.add({
      severity: 'info',
      summary: t('common.uploading'),
      detail: t('config.system.uploadingFile', { name: file.name }),
      life: 2000
    })

    const response = await axios.post('/api/files/upload-xml', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    // El path "actual" només canvia si la versió nova ja és vigent avui.
    // Si s'ha programat per a un curs futur, l'horari vigent segueix sent l'anterior.
    if (response.data.vigent_avui !== false) {
      settings.value.xml_horari_path = response.data.path
      actualitzarSnapshot()
    }

    toast.add({
      severity: 'success',
      summary: t('common.uploaded'),
      detail: response.data.vigent_avui === false
        ? t('config.system.xmlScheduled', { data: response.data.data_inici })
        : response.data.message,
      life: 4000
    })

    // Refrescar versions i avisos (pujar un XML pot resoldre una desincronització)
    await carregarXmlVersions()
    await carregarAvisosXml()
    xmlVigentDesDe.value = null
    event.target.value = ''
  } catch (error) {
    console.error('Error pujant XML:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: error.response?.data?.detail || t('config.errors.uploadXml'),
      life: 3000
    })
  }
}

const carregarPDFs = async () => {
  try {
    const response = await axios.get('/api/files/pdfs')
    pdfs.value = response.data.pdfs
  } catch (error) {
    console.error('Error carregant PDFs:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.loadPdfs'),
      life: 3000
    })
  }
}

const descarregarPDF = async (filename) => {
  try {
    const response = await axios.get(
      `/api/files/pdfs/${encodeURIComponent(filename)}`,
      { responseType: 'blob' }
    )
    const contentType = response.headers['content-type'] || 'application/pdf'
    const blobUrl = window.URL.createObjectURL(new Blob([response.data], { type: contentType }))
    window.open(blobUrl, '_blank', 'noopener')
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000)

    toast.add({
      severity: 'success',
      summary: t('common.downloading'),
      detail: t('config.system.openingPdf', { name: filename }),
      life: 2000
    })
  } catch (error) {
    console.error('Error descarregant PDF:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.downloadPdf'),
      life: 3000
    })
  }
}

const eliminarPDF = async (filename) => {
  try {
    await axios.delete(`/api/files/pdfs/${encodeURIComponent(filename)}`)

    toast.add({
      severity: 'success',
      summary: t('common.deleted'),
      detail: t('config.system.pdfDeleted', { name: filename }),
      life: 3000
    })

    // Recarregar llista
    await carregarPDFs()
  } catch (error) {
    console.error('Error eliminant PDF:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('config.errors.deletePdf'),
      life: 3000
    })
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

onMounted(() => {
  carregarSettings()
  carregarPDFs()
})
</script>

<style scoped>
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  text-align: center;
  gap: 1rem;
  color: #667eea;
}

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

.loading-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #6b7280;
  font-size: 0.9rem;
}

.empty-inline {
  color: #6b7280;
  font-size: 0.9rem;
  padding: 0.5rem 0;
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

.xml-versions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.xml-version-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 0.75rem;
  background: #f9fafb;
}

.xml-version-row {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.xml-version-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.xml-path {
  font-size: 0.85rem;
  color: #374151;
  word-break: break-all;
}

.xml-current {
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  white-space: nowrap;
}

.xml-version-dates {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.date-field {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}

.date-inline-label {
  font-size: 0.75rem;
  color: #6b7280;
  white-space: nowrap;
  line-height: 1;
}

.xml-date {
  max-width: 150px;
}

/* Data de vigència del pròxim XML a pujar (preparar curs futur) */
.xml-vigencia {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

/* Avís: un curs arrencaria amb l'horari del curs anterior */
.xml-avis-desync {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid #fcd34d;
  border-left: 4px solid #f59e0b;
  border-radius: 4px;
  background: #fffbeb;
  color: #78350f;
  font-size: 0.85rem;
}

.xml-avis-desync .pi {
  color: #d97706;
  font-size: 1.1rem;
}

.xml-avis-text {
  flex: 1;
  line-height: 1.35;
}

.xml-version-actions {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
  align-self: flex-end;
}

@media (max-width: 720px) {
  .xml-version-row {
    gap: 0.5rem;
  }
  .xml-version-actions {
    width: 100%;
    justify-content: space-between;
  }
  .xml-version-dates {
    width: 100%;
    justify-content: space-between;
  }
  .date-field {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }
  .date-inline-label {
    line-height: 1.2;
  }
  .xml-date {
    max-width: 100%;
    width: 100%;
  }
}

.pdfs-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
  margin-top: 0.5rem;
}

.pdf-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #fff5f5;
  border: 1px solid #fecaca;
  border-radius: 6px;
  transition: all 0.2s;
}

.pdf-card:hover {
  background: #fef2f2;
  border-color: #fca5a5;
}

.pdf-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
}

.pdf-name {
  font-weight: 500;
  color: #374151;
  flex: 1;
}

.pdf-size {
  color: #9ca3af;
  font-size: 0.85rem;
}

.pdf-actions {
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

.config-save-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid #e5e7eb;
}

.logo-preview {
  margin-top: 0.75rem;
  display: flex;
  align-items: center;
}

.logo-preview img {
  max-height: 64px;
  max-width: 220px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: 6px;
  padding: 0.25rem 0.5rem;
}

:deep(.logo-field.p-inputtext),
:deep(.logo-field.p-dropdown) {
  height: 2.4rem !important;
  min-height: 2.4rem !important;
  max-height: 2.4rem !important;
}

:deep(.logo-field.p-inputtext) {
  padding: 0.65rem 0.75rem !important;
}

:deep(.logo-field.p-dropdown .p-dropdown-label) {
  padding: 0.65rem 0.75rem !important;
  line-height: 1.4rem;
}

:deep(.uniform-inputgroup .p-inputtext),
:deep(.uniform-inputgroup .p-button) {
  height: 2.4rem !important;
}

:deep(.uniform-inputgroup .p-button) {
  padding: 0 !important;
  width: 2.4rem !important;
}

.w-full {
  width: 100%;
}
</style>
