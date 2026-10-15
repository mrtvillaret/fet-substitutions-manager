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

    <!-- Dia sense classes (p.ex. cap de setmana) -->
    <div v-else-if="!hores.length" class="error-message">
      <Message severity="info" :closable="false">{{ $t('groups.noClassesDay') }}</Message>
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
              <!-- Activitats alliberables (configurades a Prioritats) -->
              <template v-if="activitatsNoms.length || activitatsPerDefecte.length">
                <tr class="section-row">
                  <td :colspan="hores.length + 1">{{ $t('groups.activitiesHeader') }}</td>
                </tr>
                <!-- Alliberades fins que tenen alumnes (p.ex. Reforç): es gestionen per franges -->
                <tr v-for="act in activitatsPerDefecte" :key="`perdef-${act}`">
                  <td class="grup-name"><span>{{ act }}</span></td>
                  <td :colspan="hores.length" class="perdef-cell">
                    <span>{{ $t('groups.reforcRowHint') }}</span>
                    <Button
                      :label="$t('groups.reforcManage')"
                      icon="pi pi-users"
                      size="small"
                      severity="info"
                      outlined
                      @click="obrirReforc(act)"
                    />
                  </td>
                </tr>
                <!-- Reforços d'aquell dia: qui és lliure i qui es pot alliberar només aquell dia -->
                <tr v-for="act in activitatsPerDefecte.filter(a => reforcsDelDia[a])" :key="`perdef-avui-${act}`">
                  <td class="grup-name reforc-avui-nom">{{ $t('groups.reforcTodayRow') }}</td>
                  <td v-for="hora in hores" :key="`perdef-avui-${act}-${hora}`" class="checkbox-cell">
                    <button
                      v-if="professorsReforcAvui(act, hora).length"
                      type="button"
                      class="teachers-btn"
                      :class="{ active: alliberatsReforcAvui(act, hora).length }"
                      :title="$t('groups.reforcTodayTitle')"
                      :aria-label="$t('groups.reforcTodayTitle')"
                      @click="obrirProfessors($event, 'reforc', act, hora)"
                    >
                      <i class="pi pi-user"></i>
                      <span>{{ lliuresReforcAvui(act, hora) }}/{{ professorsReforcAvui(act, hora).length }}</span>
                    </button>
                  </td>
                </tr>
                <tr v-for="act in activitatsNoms" :key="`act-${act}`">
                  <td class="grup-name"><span>{{ act }}</span></td>
                  <td v-for="hora in hores" :key="`act-${act}-${hora}`" class="checkbox-cell">
                    <div v-if="professorsActivitat(act, hora).length" class="cell-inner">
                      <Checkbox v-model="activitatsMarcades[act][hora]" :binary="true" />
                      <button
                        v-if="!activitatsMarcades[act][hora]"
                        type="button"
                        class="teachers-btn"
                        :class="{ active: alliberatsActivitat(act, hora).length }"
                        :title="$t('groups.freeTeachersTitle')"
                        :aria-label="$t('groups.freeTeachersTitle')"
                        @click="obrirProfessors($event, 'activitat', act, hora)"
                      >
                        <i class="pi pi-user"></i>
                        <span v-if="alliberatsActivitat(act, hora).length">{{ alliberatsActivitat(act, hora).length }}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
              <!-- Separació amb els grups, amb la seva pròpia fila d'hores -->
              <tr v-if="activitatsNoms.length || activitatsPerDefecte.length" class="section-row section-hours">
                <td>{{ $t('groups.groupsHeader') }}</td>
                <td v-for="hora in hores" :key="`sep-${hora}`">{{ hora }}</td>
              </tr>
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
                      @click="obrirProfessors($event, 'grup', grup, hora)"
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
        <strong>{{ franja.nom }} · {{ franja.hora }}</strong>
        <p class="teachers-panel-hint">{{ $t('groups.teachersHint') }}</p>
        <div v-for="prof in professorsFranja(franja)" :key="prof" class="teachers-panel-row">
          <!-- Reforç sense alumnes: lliure per defecte; desmarcar = aquell dia sí que en té -->
          <Checkbox
            v-if="franja.tipus === 'reforc' && !reforcAmbAlumnes(franja.nom, franja.hora, prof)"
            :inputId="`prof-${prof}`"
            :modelValue="!estaOcupat(prof, franja.hora)"
            :binary="true"
            @update:modelValue="valor => marcaOcupat(prof, franja.hora, !valor)"
          />
          <Checkbox
            v-else
            :inputId="`prof-${prof}`"
            :modelValue="estaAlliberat(prof, franja.hora)"
            :binary="true"
            @update:modelValue="valor => marcaProfessor(prof, franja.hora, valor)"
          />
          <label :for="`prof-${prof}`">{{ prof }}</label>
          <small v-if="franja.tipus === 'reforc'" class="reforc-estat">
            {{ reforcAmbAlumnes(franja.nom, franja.hora, prof) ? $t('groups.reforcBusy') : $t('groups.reforcFreeNoStudents') }}
          </small>
        </div>
        <p v-if="franja.tipus === 'reforc'" class="teachers-panel-hint" style="margin-top: 0.5rem;">
          {{ $t('groups.reforcTodayHint') }}
        </p>
      </div>
    </OverlayPanel>

    <!-- Reforços (activitats alliberades fins que tenen alumnes): franges amb alumnes -->
    <Dialog
      v-model:visible="reforc.visible"
      :header="$t('groups.reforcTitle', { activitat: reforc.activitat })"
      modal
      :style="{ width: reforc.vista === 'setmana' ? '60rem' : '44rem', maxWidth: '96vw' }"
    >
      <p class="reforc-hint">{{ $t('groups.reforcHint') }}</p>
      <div class="reforc-toolbar">
        <div class="reforc-vista">
          <Button :label="$t('groups.reforcViewTeacher')" size="small"
                  :outlined="reforc.vista !== 'professor'" @click="reforc.vista = 'professor'" />
          <Button :label="$t('groups.reforcViewWeek')" size="small"
                  :outlined="reforc.vista !== 'setmana'" @click="reforc.vista = 'setmana'" />
        </div>
        <Dropdown
          v-if="reforc.vista === 'professor'"
          v-model="reforc.professor"
          :options="opcionsProfessorsReforc"
          optionLabel="nom"
          optionValue="nom"
          :placeholder="$t('groups.reforcPickTeacher')"
          :filter="true"
          filterBy="nom"
          class="reforc-teacher"
        >
          <template #option="{ option }">
            <span class="reforc-option">
              <span>{{ option.nom }}</span>
              <span class="reforc-count">{{ option.icona }} {{ option.amb }}/{{ option.total }}</span>
            </span>
          </template>
        </Dropdown>
        <label for="reforcData">{{ $t('groups.reforcFrom') }}</label>
        <InputText id="reforcData" v-model="reforc.data" type="date" />
      </div>
      <div class="reforc-toolbar reforc-toolbar-filtre">
        <div class="flex align-items-center gap-2">
          <Checkbox v-model="reforc.nomesPendents" inputId="reforcPendents" :binary="true" />
          <label for="reforcPendents">{{ $t('groups.reforcOnlyPending') }}</label>
        </div>
        <span class="reforc-summary">{{ $t('groups.reforcSummary', resumReforc) }}</span>
      </div>
      <div class="reforc-legend">
        <span><span class="reforc-swatch"></span>○ {{ $t('groups.reforcLegendFree') }}</span>
        <span><span class="reforc-swatch amb"></span>● {{ $t('groups.reforcLegendBusy') }}</span>
      </div>

      <!-- Vista «Setmana»: hores × dies, amb els professors de cada franja -->
      <div v-if="reforc.vista === 'setmana'" class="reforc-tots">
        <table class="grups-table reforc-setmana">
          <thead>
            <tr>
              <th></th>
              <th v-for="dia in diesSetmana" :key="`s-${dia}`">{{ dia }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="hora in horesSetmana" :key="`s-${hora}`">
              <td class="grup-name">{{ hora }}</td>
              <td v-for="dia in diesSetmana" :key="`s-${dia}-${hora}`" class="reforc-setmana-cell">
                <button
                  v-for="f in frangesSetmana(dia, hora)"
                  :key="`s-${f.professor}-${dia}-${hora}`"
                  type="button"
                  class="reforc-slot reforc-slot-petit"
                  :class="{ amb: f.amb_alumnes }"
                  :disabled="reforc.desant"
                  :title="titolFranja(f)"
                  @click="canviaFranjaReforc(dia, hora, f.professor)"
                >
                  {{ f.amb_alumnes ? '●' : '○' }} {{ f.professor }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <table v-if="reforc.vista === 'professor' && reforc.professor" class="grups-table reforc-grid">
        <thead>
          <tr>
            <th></th>
            <th v-for="dia in diesReforc" :key="dia">{{ dia }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="hora in horesReforc" :key="hora">
            <td class="grup-name">{{ hora }}</td>
            <td v-for="dia in diesReforc" :key="`${dia}-${hora}`" class="checkbox-cell">
              <button
                v-if="frangaReforc(dia, hora)"
                type="button"
                class="reforc-slot"
                :class="{ amb: frangaReforc(dia, hora).amb_alumnes }"
                :disabled="reforc.desant"
                :title="titolFranja(frangaReforc(dia, hora))"
                @click="canviaFranjaReforc(dia, hora)"
              >
                <template v-if="frangaReforc(dia, hora).amb_alumnes">
                  ● {{ $t('groups.reforcBusy') }}<br /><small>{{ $t('groups.reforcSince', { data: dataCurta(frangaReforc(dia, hora).des_de) }) }}</small>
                </template>
                <template v-else>○ {{ $t('groups.reforcFree') }}</template>
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <template #footer>
        <Button :label="$t('common.close')" text severity="secondary" @click="reforc.visible = false" />
      </template>
    </Dialog>

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
import { avisaSubstitutsTrets } from '../substitutsTrets'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Chip from 'primevue/chip'
import OverlayPanel from 'primevue/overlaypanel'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'

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
// Reforços sense alumnes que un dia concret sí que en tenen: {hora: [professors]}
const professorsOcupats = reactive({})
const professorsOcupatsOriginals = ref({})
const panellProfessors = ref(null)
const franja = ref(null)
// Activitats alliberables: {activitat: {hora: [professors]}} i les marcades aquell dia
const activitatsPerHora = ref({})
const activitatsMarcades = reactive({})
const activitatsMarcadesOriginals = ref({})
// Activitats alliberades fins que tenen alumnes (p.ex. Reforç)
const activitatsPerDefecte = ref([])
// ...i qui les fa aquell dia, amb l'estat: {activitat: {hora: [{professor, amb_alumnes}]}}
const reforcsDelDia = ref({})
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

const professorsOcupatsNets = () => {
  const nets = {}
  hores.value.forEach(hora => {
    const profs = [...(professorsOcupats[hora] || [])].sort()
    if (profs.length) nets[hora] = profs
  })
  return nets
}

const estaOcupat = (prof, hora) => (professorsOcupats[hora] || []).includes(prof)

const marcaOcupat = (prof, hora, valor) => {
  const actuals = (professorsOcupats[hora] || []).filter(p => p !== prof)
  professorsOcupats[hora] = valor ? [...actuals, prof] : actuals
}

const teCanvis = computed(() => {
  return JSON.stringify(professorsOcupatsNets()) !== JSON.stringify(professorsOcupatsOriginals.value) ||
    JSON.stringify(checkboxes) !== JSON.stringify(checkboxesOriginals.value) ||
    JSON.stringify(professorsAlliberatsNets()) !== JSON.stringify(professorsAlliberatsOriginals.value) ||
    JSON.stringify(activitatsMarcades) !== JSON.stringify(activitatsMarcadesOriginals.value)
})

const professorsDe = (grup, hora) => professorsPerGrupHora.value[hora]?.[grup] || []

const activitatsNoms = computed(() => Object.keys(activitatsPerHora.value))

const professorsActivitat = (act, hora) => activitatsPerHora.value[act]?.[hora] || []

const professorsReforcAvui = (act, hora) => (reforcsDelDia.value[act]?.[hora] || []).map(r => r.professor)

const reforcAmbAlumnes = (act, hora, prof) =>
  (reforcsDelDia.value[act]?.[hora] || []).some(r => r.professor === prof && r.amb_alumnes)

const professorsFranja = (f) => {
  if (f.tipus === 'activitat') return professorsActivitat(f.nom, f.hora)
  if (f.tipus === 'reforc') return professorsReforcAvui(f.nom, f.hora)
  return professorsDe(f.nom, f.hora)
}

const dataCurta = (iso) => {
  const [y, m, d] = (iso || '').split('-')
  return d ? `${d}/${m}/${y}` : ''
}

const estaAlliberat = (prof, hora) => (professorsAlliberats[hora] || []).includes(prof)

const alliberatsDe = (grup, hora) => professorsDe(grup, hora).filter(prof => estaAlliberat(prof, hora))

// Lliure aquell dia: amb alumnes i alliberat aquell dia, o sense alumnes i no ocupat aquell dia
const lliureReforcAvui = (act, hora, prof) =>
  reforcAmbAlumnes(act, hora, prof) ? estaAlliberat(prof, hora) : !estaOcupat(prof, hora)

// Els que aquell dia canvien respecte del seu estat (per destacar la icona)
const alliberatsReforcAvui = (act, hora) =>
  professorsReforcAvui(act, hora).filter(prof =>
    reforcAmbAlumnes(act, hora, prof) ? estaAlliberat(prof, hora) : estaOcupat(prof, hora))

const lliuresReforcAvui = (act, hora) =>
  professorsReforcAvui(act, hora).filter(prof => lliureReforcAvui(act, hora, prof)).length

const alliberatsActivitat = (act, hora) =>
  professorsActivitat(act, hora).filter(prof => estaAlliberat(prof, hora))

const marcaProfessor = (prof, hora, valor) => {
  const actuals = (professorsAlliberats[hora] || []).filter(p => p !== prof)
  professorsAlliberats[hora] = valor ? [...actuals, prof] : actuals
}

const treureProfessor = (prof) => {
  for (const hora in professorsAlliberats) {
    professorsAlliberats[hora] = professorsAlliberats[hora].filter(p => p !== prof)
  }
}

const obrirProfessors = (event, tipus, nom, hora) => {
  franja.value = { tipus, nom, hora }
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

// ===== Reforços: franges amb alumnes a partir d'un dia =====
const reforc = reactive({
  visible: false, activitat: '', professor: null, data: '',
  dies: [], hores: [], professors: {}, desant: false, nomesPendents: false,
  vista: 'professor'   // 'professor' (desplegable i graella) o 'setmana' (hores × dies)
})



const carregarReforc = async () => {
  const response = await axios.get(`/api/grups/reforcos/${encodeURIComponent(reforc.activitat)}`,
    { params: { data: reforc.data } })
  reforc.dies = response.data.dies || []
  reforc.hores = response.data.hores || []
  reforc.professors = response.data.professors || {}
}

const obrirReforc = async (activitat) => {
  // Marcar una franja recarrega el dia: primer cal desar (o descartar) el que s'hagi marcat
  if (!(await potSortir())) return
  Object.assign(reforc, { activitat, professor: null, data: isoDe(dataCarregada.value), visible: true })
  try {
    await carregarReforc()
  } catch (err) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: err.response?.data?.detail || '', life: 5000 })
  }
}

// Si canvia la data, l'estat de les franges és el d'aquella data
watch(() => reforc.data, (nova, vella) => {
  if (reforc.visible && nova && vella && nova !== vella) carregarReforc().catch(() => {})
})

const frangesProfessor = computed(() => reforc.professors[reforc.professor] || [])
const frangaReforc = (dia, hora) => frangesProfessor.value.find(f => f.dia === dia && f.hora === hora) || null
const diesReforc = computed(() => reforc.dies.filter(d => frangesProfessor.value.some(f => f.dia === d)))
const horesReforc = computed(() => reforc.hores.filter(h => frangesProfessor.value.some(f => f.hora === h)))

// Opcions del desplegable: cada professor amb quantes franges tenen alumnes
const opcionsProfessorsReforc = computed(() =>
  Object.entries(reforc.professors)
    .map(([nom, franges]) => {
      const amb = franges.filter(f => f.amb_alumnes).length
      const total = franges.length
      return { nom, amb, total, icona: amb === total ? '●' : (amb ? '◐' : '○') }
    })
    .filter(o => !reforc.nomesPendents || o.amb < o.total || o.nom === reforc.professor))

// Vista «Setmana»: franges de tots els professors visibles (amb el filtre), per dia i hora
const frangesVisiblesSetmana = computed(() => {
  const visibles = new Set(opcionsProfessorsReforc.value.map(o => o.nom))
  return Object.entries(reforc.professors)
    .filter(([nom]) => visibles.has(nom))
    .flatMap(([professor, franges]) => franges.map(f => ({ professor, ...f })))
})
const diesSetmana = computed(() => reforc.dies.filter(d => frangesVisiblesSetmana.value.some(f => f.dia === d)))
const horesSetmana = computed(() => reforc.hores.filter(h => frangesVisiblesSetmana.value.some(f => f.hora === h)))
const frangesSetmana = (dia, hora) =>
  frangesVisiblesSetmana.value.filter(f => f.dia === dia && f.hora === hora)

// Text en passar el ratolí per sobre: estat actual, historial i què fa el clic
const titolFranja = (f) => {
  if (!f) return ''
  const estat = f.amb_alumnes
    ? `${t('groups.reforcBusy')} ${t('groups.reforcSince', { data: dataCurta(f.des_de) })}`
    : t('groups.reforcFree')
  const linies = [estat]
  if (f.historial?.length) {
    linies.push(`${t('groups.reforcHistory')}:`)
    f.historial.forEach(h => {
      linies.push(`  ${dataCurta(h.des_de)} → ${h.amb_alumnes ? t('groups.reforcBusy') : t('groups.reforcFree')}`)
    })
  }
  linies.push(f.amb_alumnes ? t('groups.reforcMakeFree') : t('groups.reforcMakeBusy'))
  return linies.join('\n')
}

const resumReforc = computed(() => {
  const totes = Object.values(reforc.professors).flat()
  return { amb: totes.filter(f => f.amb_alumnes).length, total: totes.length }
})

const canviaFranjaReforc = async (dia, hora, professor = reforc.professor) => {
  const franja = (reforc.professors[professor] || []).find(f => f.dia === dia && f.hora === hora)
  if (!franja || !reforc.data) return
  reforc.desant = true
  try {
    const resposta = await axios.post('/api/grups/periode', {
      tipus: 'professor', clau: professor, hores: [hora], data: reforc.data,
      dia_setmana: dia, alliberat: franja.amb_alumnes   // amb alumnes → torna a estar alliberat
    })
    avisaSubstitutsTrets(toast, t, resposta.data?.substituts_trets)
    await carregarReforc()
    await recarregarDiaCarregat()
  } catch (err) {
    toast.add({ severity: 'error', summary: t('common.error'), detail: err.response?.data?.detail || '', life: 5000 })
  } finally {
    reforc.desant = false
  }
}

const inicialitzarActivitats = (perHora = {}, seleccionades = {}) => {
  activitatsPerHora.value = perHora
  for (const key in activitatsMarcades) {
    delete activitatsMarcades[key]
  }
  Object.keys(perHora).forEach(act => {
    activitatsMarcades[act] = {}
    Object.keys(perHora[act]).forEach(hora => {
      activitatsMarcades[act][hora] = (seleccionades[hora] || []).includes(act)
    })
  })
  activitatsMarcadesOriginals.value = JSON.parse(JSON.stringify(activitatsMarcades))
}

const inicialitzarOcupats = (seleccionats = {}) => {
  for (const key in professorsOcupats) {
    delete professorsOcupats[key]
  }
  Object.entries(seleccionats).forEach(([hora, profs]) => {
    professorsOcupats[hora] = [...profs]
  })
  professorsOcupatsOriginals.value = professorsOcupatsNets()
}

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

const carregarConfiguracio = async (data = props.dataGlobal) => {
  loading.value = true
  error.value = null

  try {
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
    inicialitzarActivitats(response.data.activitats_per_hora || {}, response.data.activitats_seleccionades_per_hora || {})
    activitatsPerDefecte.value = response.data.activitats_per_defecte || []
    reforcsDelDia.value = response.data.reforcs_per_hora || {}
    inicialitzarOcupats(response.data.ocupats_per_hora || {})
  } catch (err) {
    console.error('Error carregant configuració:', err)
    error.value = t('groups.errors.load')
  } finally {
    loading.value = false
  }
}

// Torna a carregar el dia que es mostra (després d'un canvi d'estat)
const recarregarDiaCarregat = () => carregarConfiguracio(dataCarregada.value)

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
    const activitatsPerHoraMarcades = {}
    Object.entries(activitatsMarcades).forEach(([act, perHora]) => {
      Object.entries(perHora).forEach(([hora, marcada]) => {
        if (marcada) (activitatsPerHoraMarcades[hora] ||= []).push(act)
      })
    })
    const response = await axios.put(`/api/grups/${isoDe(dataCarregada.value)}`, {
      grups: grupsPerHora,
      professors: professorsPerHora,
      activitats: activitatsPerHoraMarcades,
      ocupats: professorsOcupatsNets()
    })

    // Actualitzar originals
    checkboxesOriginals.value = JSON.parse(JSON.stringify(checkboxes))
    inicialitzarProfessors(professorsPerHora)
    activitatsMarcadesOriginals.value = JSON.parse(JSON.stringify(activitatsMarcades))
    professorsOcupatsOriginals.value = professorsOcupatsNets()

    toast.add({
      severity: 'success',
      summary: t('common.saved'),
      detail: response.data.message,
      life: 3000
    })
    avisaSubstitutsTrets(toast, t, response.data.substituts_trets)
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
  overflow: auto;
  max-height: calc(100vh - 16rem);
  min-height: 12rem;
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

.reforc-estat {
  color: #6b7280;
  margin-left: auto;
  padding-left: 0.75rem;
}

.reforc-avui-nom {
  font-weight: 400 !important;
  color: #4b5563;
  font-size: 0.85rem;
  padding-left: 1.75rem !important;
}

.perdef-cell {
  text-align: left !important;
  color: #4b5563;
  font-size: 0.85rem;
}

.perdef-cell .p-button {
  margin-left: 0.75rem;
}

.reforc-hint {
  color: #6b7280;
  font-size: 0.9rem;
  margin: 0 0 1rem;
  line-height: 1.4;
}

.reforc-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.reforc-toolbar-filtre {
  justify-content: space-between;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #e5e7eb;
}

.reforc-vista {
  display: inline-flex;
  gap: 0.25rem;
}

.reforc-tots {
  max-height: 55vh;
  overflow-y: auto;
}

.reforc-legend {
  display: flex;
  gap: 1.5rem;
  font-size: 0.85rem;
  color: #4b5563;
  margin-bottom: 0.75rem;
}

.reforc-legend > span {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.reforc-swatch {
  display: inline-block;
  width: 0.9rem;
  height: 0.9rem;
  border-radius: 3px;
  border: 1px solid #16a34a;
  background: #dcfce7;
}

.reforc-swatch.amb {
  border-color: #2563eb;
  background: #dbeafe;
}

.reforc-setmana-cell {
  vertical-align: top;
  min-width: 7rem;
}

.reforc-setmana-cell .reforc-slot {
  display: block;
  width: 100%;
  margin-bottom: 0.2rem;
  text-align: left;
}

.reforc-slot.reforc-slot-petit {
  width: auto;
  min-width: 0;
  padding: 0.15rem 0.45rem;
}

.reforc-teacher {
  min-width: 16rem;
}

.reforc-option {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  width: 100%;
}

.reforc-count {
  color: #6b7280;
  white-space: nowrap;
}

.reforc-summary {
  color: #4b5563;
  font-size: 0.9rem;
}

.reforc-grid td.grup-name {
  font-weight: 600;
}

.reforc-slot {
  width: 100%;
  min-width: 6.5rem;
  border: 1px solid #16a34a;
  background: #dcfce7;
  color: #14532d;
  border-radius: 6px;
  padding: 0.3rem 0.4rem;
  cursor: pointer;
  font-size: 0.8rem;
  line-height: 1.2;
}

.reforc-slot.amb {
  border-color: #2563eb;
  background: #dbeafe;
  color: #1e3a8a;
}

.reforc-slot:disabled {
  opacity: 0.6;
  cursor: wait;
}

.section-row.section-hours td {
  text-align: center;
}

.section-row.section-hours td:first-child {
  text-align: left;
}

.section-row td {
  background: #f3f4f6;
  font-weight: 600;
  color: #374151;
  text-align: left;
  padding: 0.4rem 1rem;
}

.period-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.period-field > label {
  font-weight: 600;
  color: #374151;
}

.period-history {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.9rem;
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
