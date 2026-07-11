<template>
  <div class="gestio-dades">
    <!-- ANONIMITZAR PROFESSOR -->
    <div class="anon-section">
      <h3><i class="pi pi-user-edit" style="color: #3b82f6;" /> {{ $t('config.dataManagement.anonTitle') }}</h3>
      <p class="descripcio">{{ $t('config.dataManagement.anonDescription') }}</p>

      <div v-if="professorsInactius.length" class="anon-form">
        <div class="field">
          <label>{{ $t('config.dataManagement.anonSelect') }}</label>
          <Dropdown
            v-model="profSeleccionat"
            :options="professorsInactius"
            optionLabel="nom"
            optionValue="nom"
            filter
            @change="suggerirNom"
          />
        </div>
        <div class="field">
          <label>{{ $t('config.dataManagement.anonNewName') }}</label>
          <InputText v-model="nomNou" />
        </div>
        <Button
          :label="$t('config.dataManagement.anonButton')"
          icon="pi pi-user-edit"
          @click="confirmarAnon"
          :loading="carregantAnon"
          :disabled="!profSeleccionat || !nomNou.trim()"
        />
      </div>
      <p v-else class="res-buit">{{ $t('config.dataManagement.anonNoInactive') }}</p>
      <small class="anon-hint">{{ $t('config.dataManagement.anonHint') }}</small>
    </div>

    <Divider />

    <h3><i class="pi pi-trash" style="color: #ef4444;" /> {{ $t('config.dataManagement.title') }}</h3>
    <p class="descripcio">{{ $t('config.dataManagement.description') }}</p>

    <div class="interval-selector">
      <div class="field">
        <label>{{ $t('config.dataManagement.startDate') }}</label>
        <Calendar v-model="dataInici" dateFormat="dd/mm/yy" :showIcon="true" :manualInput="false" />
      </div>
      <div class="field">
        <label>{{ $t('config.dataManagement.endDate') }}</label>
        <Calendar v-model="dataFinal" dateFormat="dd/mm/yy" :showIcon="true" :manualInput="false" />
      </div>
      <Button
        :label="$t('config.dataManagement.analyze')"
        icon="pi pi-search"
        @click="analitzar"
        :loading="carregant"
        :disabled="!dataInici || !dataFinal"
      />
    </div>

    <!-- MANIFEST -->
    <div v-if="manifest" class="manifest">
      <h4>{{ $t('config.dataManagement.manifestTitle', { start: manifest.interval.inici, end: manifest.interval.final }) }}</h4>

      <ul class="bd-list">
        <li>{{ $t('config.dataManagement.substitutions') }}: <strong>{{ manifest.bd.substitucions }}</strong></li>
        <li>{{ $t('config.dataManagement.vigilances') }}: <strong>{{ manifest.bd.vigilancies }}</strong></li>
        <li>{{ $t('config.dataManagement.freedGroups') }}: <strong>{{ manifest.bd.grups_alliberats }}</strong></li>
        <li>{{ $t('config.dataManagement.absences') }}: <strong>{{ manifest.bd.baixes }}</strong></li>
      </ul>

      <p>
        {{ $t('config.dataManagement.pdfsToDelete') }}: <strong>{{ manifest.pdfs_a_esborrar.length }}</strong>
        · {{ $t('config.dataManagement.pdfsManual') }}: <strong>{{ manifest.pdfs_revisio_manual.length }}</strong>
      </p>

      <div v-if="manifest.xml_versions.length" class="xml-list">
        <p>{{ $t('config.dataManagement.xmlAffected') }}</p>
        <ul>
          <li v-for="v in manifest.xml_versions" :key="v.id">
            {{ v.data_inici }} → {{ v.data_fi || $t('config.dataManagement.xmlOpen') }}
            <Tag v-if="v.bloquejat" severity="warning" :value="$t('config.dataManagement.xmlKept')" />
            <Tag v-else severity="danger" :value="$t('config.dataManagement.xmlWillDelete')" />
          </li>
        </ul>
      </div>

      <Message
        v-for="(av, i) in avisos"
        :key="i"
        severity="warn"
        :closable="false"
      >{{ av }}</Message>

      <div class="accions-purga">
        <Button
          :label="$t('config.dataManagement.purgeButton')"
          icon="pi pi-trash"
          severity="danger"
          @click="confirmarPurga"
          :loading="carregant"
          :disabled="!hiHaResPerEsborrar"
        />
        <span v-if="!hiHaResPerEsborrar" class="res-buit">{{ $t('config.dataManagement.nothingToDelete') }}</span>
      </div>
    </div>

    <!-- RESULTAT -->
    <div v-if="resultat" class="resultat">
      <Message severity="success" :closable="false">
        {{ $t('config.dataManagement.resultSuccess', {
          start: resultat.interval.inici,
          end: resultat.interval.final,
          bd: resultat.total_bd,
          pdf: resultat.pdfs_esborrats.length,
          xml: resultat.xml_esborrats.length,
        }) }}
      </Message>
      <Message v-if="resultat.errors.length" severity="error" :closable="false">
        {{ $t('config.dataManagement.resultErrors', { errors: resultat.errors.join('; ') }) }}
      </Message>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Divider from 'primevue/divider'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'

const { t } = useI18n()
const toast = useToast()
const confirm = useConfirm()

// --- Anonimitzar professor ---
const professors = ref([])
const profSeleccionat = ref(null)
const nomNou = ref('')
const carregantAnon = ref(false)

const professorsInactius = computed(() => professors.value.filter(p => !p.actiu))

async function carregarProfessors() {
  try {
    const { data } = await axios.get('/api/dades/professors')
    professors.value = data.professors || []
  } catch (e) {
    toast.add({ severity: 'error', summary: t('config.dataManagement.errorSummary'), detail: e.response?.data?.detail || String(e), life: 5000 })
  }
}

function suggerirNom() {
  const n = professors.value.filter(p => /^Ex-docent/i.test(p.nom)).length + 1
  nomNou.value = `Ex-docent ${n}`
}

function confirmarAnon() {
  confirm.require({
    header: t('config.dataManagement.anonConfirmHeader'),
    message: t('config.dataManagement.anonConfirmMessage', { old: profSeleccionat.value, new: nomNou.value.trim() }),
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-warning',
    acceptLabel: t('config.dataManagement.anonAccept'),
    rejectLabel: t('config.dataManagement.reject'),
    accept: anonimitzar,
  })
}

async function anonimitzar() {
  carregantAnon.value = true
  try {
    const { data } = await axios.post('/api/dades/professors/reanomena', {
      nom_actual: profSeleccionat.value,
      nom_nou: nomNou.value.trim(),
    })
    toast.add({ severity: 'success', summary: t('config.dataManagement.anonSuccessSummary'), detail: t('config.dataManagement.anonSuccessDetail', { n: data.total }), life: 6000 })
    profSeleccionat.value = null
    nomNou.value = ''
    await carregarProfessors()
  } catch (e) {
    toast.add({ severity: 'error', summary: t('config.dataManagement.errorSummary'), detail: e.response?.data?.detail || String(e), life: 6000 })
  } finally {
    carregantAnon.value = false
  }
}

onMounted(carregarProfessors)

const dataInici = ref(null)
const dataFinal = ref(null)
const manifest = ref(null)
const resultat = ref(null)
const carregant = ref(false)

function toIso(d) {
  if (!d) return null
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const hiHaResPerEsborrar = computed(() => {
  const m = manifest.value
  if (!m) return false
  return m.total_bd > 0
    || m.pdfs_a_esborrar.length > 0
    || m.xml_versions.some(v => !v.bloquejat)
})

// Avisos generats al frontend a partir de les dades del manifest (i18n).
const avisos = computed(() => {
  const m = manifest.value
  if (!m) return []
  const out = []
  for (const v of m.xml_versions) {
    if (v.activa) {
      out.push(t('config.dataManagement.warnXmlActive', { start: v.data_inici }))
    } else if (v.s_esten_fora) {
      out.push(t('config.dataManagement.warnXmlExtends', { start: v.data_inici, end: v.data_fi }))
    }
  }
  if (m.pdfs_revisio_manual.length) {
    out.push(t('config.dataManagement.warnPdfsManual', { n: m.pdfs_revisio_manual.length }))
  }
  return out
})

async function analitzar() {
  resultat.value = null
  manifest.value = null
  carregant.value = true
  try {
    const { data } = await axios.post('/api/dades/purga/analitzar', {
      data_inici: toIso(dataInici.value),
      data_final: toIso(dataFinal.value),
    })
    manifest.value = data
  } catch (e) {
    toast.add({ severity: 'error', summary: t('config.dataManagement.errorSummary'), detail: e.response?.data?.detail || String(e), life: 5000 })
  } finally {
    carregant.value = false
  }
}

function confirmarPurga() {
  const m = manifest.value
  const nXml = m.xml_versions.filter(v => !v.bloquejat).length
  confirm.require({
    header: t('config.dataManagement.confirmHeader'),
    message: t('config.dataManagement.confirmMessage', {
      bd: m.total_bd, pdf: m.pdfs_a_esborrar.length, xml: nXml,
      start: m.interval.inici, end: m.interval.final,
    }),
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    acceptLabel: t('config.dataManagement.accept'),
    rejectLabel: t('config.dataManagement.reject'),
    accept: purgar,
  })
}

async function purgar() {
  carregant.value = true
  try {
    const { data } = await axios.post('/api/dades/purga/executar', {
      data_inici: manifest.value.interval.inici,
      data_final: manifest.value.interval.final,
      confirmar: true,
    })
    resultat.value = data
    manifest.value = null
    toast.add({ severity: 'success', summary: t('config.dataManagement.successSummary'), detail: t('config.dataManagement.successDetail', { n: data.total_bd }), life: 6000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: t('config.dataManagement.errorSummary'), detail: e.response?.data?.detail || String(e), life: 6000 })
  } finally {
    carregant.value = false
  }
}
</script>

<style scoped>
.gestio-dades {
  padding: 0.5rem 0.25rem;
}
.gestio-dades :deep(.p-divider.p-divider-horizontal) {
  margin: 2.75rem 0;
}
.anon-hint {
  display: block;
  margin-top: 0.5rem;
  color: var(--text-color-secondary);
}
.anon-form {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
}
.anon-form .field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.descripcio {
  color: var(--text-color-secondary);
  margin-bottom: 1.25rem;
}
.interval-selector {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}
.interval-selector .field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.manifest {
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  background: var(--surface-50);
}
.manifest h4 {
  margin-top: 0;
}
.bd-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 1.5rem;
}
.xml-list ul {
  padding-left: 1.1rem;
}
.xml-list li {
  margin-bottom: 0.35rem;
}
.accions-purga {
  margin-top: 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.res-buit {
  color: var(--text-color-secondary);
  font-style: italic;
}
.resultat {
  margin-top: 1.25rem;
}
</style>
