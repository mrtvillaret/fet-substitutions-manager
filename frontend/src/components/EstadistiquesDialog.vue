<template>
  <Dialog
    class="dialog-stable-height"
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="`📊 ${$t('stats.title')}`"
    :modal="true"
    :style="{ width: '1000px', maxHeight: '90vh' }"
    :closable="true"
  >
    <div class="estadistiques-container">
      <!-- Selector de període -->
      <div class="periode-selector">
        <div class="field">
          <label>{{ $t('stats.period.start') }}</label>
          <Calendar
            v-model="dataInici"
            dateFormat="yy-mm-dd"
            :showIcon="true"
            :placeholder="$t('stats.period.datePlaceholder')"
          />
        </div>
        <div class="field">
          <label>{{ $t('stats.period.end') }}</label>
          <Calendar
            v-model="dataFinal"
            dateFormat="yy-mm-dd"
            :showIcon="true"
            :placeholder="$t('stats.period.datePlaceholder')"
          />
        </div>
        <Button
          :label="`🔍 ${$t('stats.period.refresh')}`"
          @click="carregarEstadistiques"
          :loading="loading"
          class="p-button-primary"
        />
      </div>

      <Divider />

      <!-- Carregant -->
      <div v-if="loading" class="loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
        <p>{{ $t('stats.loading') }}</p>
      </div>

      <!-- Contingut -->
      <div v-else-if="resum" class="stats-content">
        <TabView class="app-tabview app-tabview--dialog">
          <TabPanel :header="`📊 ${$t('stats.tabs.summary')}`">
            <!-- Cards principals -->
            <div class="stats-cards">
              <div class="stat-card primary">
                <div class="stat-icon">📋</div>
                <div class="stat-content">
                  <div class="stat-value">{{ resum.substitucions.total }}</div>
                  <div class="stat-label">{{ $t('stats.summary.totalAbsences') }}</div>
                  <div class="stat-detail">
                    {{ $t('stats.summary.substitutionsDetail', { count: resum.substitucions.assignades, percent: resum.substitucions.percentatge_assignat }) }}
                  </div>
                </div>
              </div>

              <div class="stat-card success">
                <div class="stat-icon">👁️</div>
                <div class="stat-content">
                  <div class="stat-value">{{ resum.vigilancies.total }}</div>
                  <div class="stat-label">{{ $t('stats.summary.totalVigilancies') }}</div>
                  <div class="stat-detail">
                    {{ $t('stats.summary.vigilanciesDetail', { count: resum.vigilancies.assignades, percent: resum.vigilancies.percentatge_assignat }) }}
                  </div>
                </div>
              </div>

              <div class="stat-card info">
                <div class="stat-icon">📅</div>
                <div class="stat-content">
                  <div class="stat-value">{{ resum.activitat.dies_amb_substitucions }}</div>
                  <div class="stat-label">{{ $t('stats.summary.daysWithSubs') }}</div>
                </div>
              </div>

              <div class="stat-card warning">
                <div class="stat-icon">🗓️</div>
                <div class="stat-content">
                  <div class="stat-value">{{ resum.activitat.dies_amb_vigilancies }}</div>
                  <div class="stat-label">{{ $t('stats.summary.daysWithVigs') }}</div>
                </div>
              </div>
            </div>

            <div class="professors-section">
              <div class="section-header">
                <h3>👥 {{ $t('stats.summary.perTeacher') }}</h3>
                <small>{{ $t('stats.summary.perTeacherHint') }}</small>
              </div>
              <DataTable
                :value="professorsResum.professors"
                stripedRows
                :paginator="true"
                :rows="12"
                :rowsPerPageOptions="[12, 24, 48]"
                responsiveLayout="scroll"
                class="professors-table"
                @row-click="onProfessorRowClick"
              >
                <Column field="professor" :header="$t('stats.columns.teacher')" :sortable="true" />
                <Column field="abs_normals" :header="$t('stats.columns.absNormal')" :sortable="true" />
                <Column field="abs_pati" :header="$t('stats.columns.absBreak')" :sortable="true" />
                <Column field="abs_altres" :header="$t('stats.columns.absOther')" :sortable="true" />
                <Column field="total_abs" :header="$t('stats.columns.absTotal')" :sortable="true" />
                <Column field="subs_normals" :header="$t('stats.columns.subsNormal')" :sortable="true" />
                <Column field="subs_pati" :header="$t('stats.columns.subsBreak')" :sortable="true" />
                <Column field="total_subs" :header="$t('stats.columns.subsTotal')" :sortable="true" />
                <Column field="ratio_text" :header="$t('stats.columns.ratio')" :sortable="true" />
                <Column field="puntuacio" :header="$t('stats.columns.score')" :sortable="true" />
                <template #empty>
                  <div class="empty-list">{{ $t('common.noData') }}</div>
                </template>
              </DataTable>
            </div>

            <Divider />

            <!-- Top lists (Top 5) -->
            <div class="top-lists">
              <div class="top-list">
                <h3>👤 {{ $t('stats.summary.topAbsences') }}</h3>
                <div v-if="topAbsents.length > 0" class="bar-list">
                  <div v-for="(prof, idx) in topAbsents" :key="prof.professor" class="bar-row">
                    <span class="rank">{{ idx + 1 }}</span>
                    <span class="name">{{ prof.professor }}</span>
                    <div class="bar-track">
                      <div class="bar-fill warning" :style="{ width: formatBarWidth(prof.total, topAbsentsMax) }"></div>
                    </div>
                    <span class="bar-value">{{ prof.total }}</span>
                  </div>
                </div>
                <div v-else class="empty-list">{{ $t('common.noData') }}</div>
              </div>

              <div class="top-list">
                <h3>🔄 {{ $t('stats.summary.topSubstitutions') }}</h3>
                <div v-if="topSubstituts.length > 0" class="bar-list">
                  <div v-for="(prof, idx) in topSubstituts" :key="prof.professor" class="bar-row">
                    <span class="rank">{{ idx + 1 }}</span>
                    <span class="name">{{ prof.professor }}</span>
                    <div class="bar-track">
                      <div class="bar-fill success" :style="{ width: formatBarWidth(prof.total, topSubstitutsMax) }"></div>
                    </div>
                    <span class="bar-value">{{ prof.total }}</span>
                  </div>
                </div>
                <div v-else class="empty-list">{{ $t('common.noData') }}</div>
              </div>
            </div>
          </TabPanel>

          <TabPanel :header="`📈 ${$t('stats.tabs.temporal')}`">
            <div class="temporal-grid" v-if="temporalStats">
              <div class="temporal-card">
                <h3>📅 {{ $t('stats.temporal.byDay') }}</h3>
                <div class="temporal-legend">
                  <span class="legend-subs">{{ $t('stats.temporal.legendSubs') }}</span>
                  <span class="legend-vigs">{{ $t('stats.temporal.legendVigs') }}</span>
                </div>
                <div v-if="temporalStats.dies.length > 0" class="temporal-list">
                  <div v-for="dia in temporalStats.dies" :key="dia.dia" class="temporal-row">
                    <div class="temporal-label">{{ dia.dia }}</div>
                    <div class="temporal-bar">
                      <div
                        class="temporal-bar-fill"
                        :style="{ width: formatPercent(dia.substitucions, temporalStats.totals.substitucions) }"
                      ></div>
                    </div>
                    <div class="temporal-values">
                      <span class="subs">{{ dia.substitucions }}</span>
                      <span class="vigs">{{ dia.vigilancies }}</span>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-list">{{ $t('common.noData') }}</div>
              </div>

              <div class="temporal-card">
                <h3>🕐 {{ $t('stats.temporal.byHour') }}</h3>
                <div class="temporal-legend">
                  <span class="legend-subs">{{ $t('stats.temporal.legendSubs') }}</span>
                  <span class="legend-vigs">{{ $t('stats.temporal.legendVigs') }}</span>
                </div>
                <div v-if="temporalStats.hores.length > 0" class="temporal-list">
                  <div v-for="hora in temporalStats.hores" :key="hora.hora" class="temporal-row">
                    <div class="temporal-label">{{ hora.hora }}</div>
                    <div class="temporal-bar">
                      <div
                        class="temporal-bar-fill"
                        :style="{ width: formatPercent(hora.substitucions, temporalStats.totals.substitucions) }"
                      ></div>
                    </div>
                    <div class="temporal-values">
                      <span class="subs">{{ hora.substitucions }}</span>
                      <span class="vigs">{{ hora.vigilancies }}</span>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-list">{{ $t('common.noData') }}</div>
              </div>
            </div>
            <div class="temporal-actions">
              <Button
                :label="`⏰ ${$t('stats.temporal.summaryBySlot')}`"
                icon="pi pi-clock"
                class="p-button-secondary"
                @click="obrirResumFranges"
              />
            </div>
          </TabPanel>

          <TabPanel :header="`📚 ${$t('stats.tabs.classes')}`">
            <div class="classes-actions">
              <Button
                :label="`🔎 ${$t('stats.classes.detailButton')}`"
                icon="pi pi-search"
                class="p-button-secondary"
                @click="obrirDetallClasses()"
              />
            </div>
            <DataTable
              :value="classesStats.classes"
              stripedRows
              :paginator="true"
              :rows="10"
              :rowsPerPageOptions="[10, 20, 50]"
              responsiveLayout="scroll"
              class="classes-table"
              @row-click="onClasseRowClick"
            >
              <Column field="grup" :header="$t('stats.classes.columns.class')" :sortable="true" />
              <Column field="total_subs" :header="$t('stats.classes.columns.totalSubs')" :sortable="true" />
              <Column field="assignatura_top" :header="$t('stats.classes.columns.topSubject')" />
              <Column field="professor_top" :header="$t('stats.classes.columns.topTeacher')" />
              <Column field="hores" :header="$t('stats.classes.columns.hours')" :sortable="true" />
              <template #empty>
                <div class="empty-list">{{ $t('common.noData') }}</div>
              </template>
            </DataTable>
          </TabPanel>

          <TabPanel :header="`📄 ${$t('stats.tabs.informes')}`">
            <div class="informes-container">

              <!-- Informe de direcció -->
              <div class="informe-bloc">
                <div class="informe-bloc__titol">
                  <i class="pi pi-chart-bar" style="color: var(--navy)"></i>
                  {{ $t('stats.informes.direccio.titol') }}
                </div>
                <p class="informe-bloc__desc">{{ $t('stats.informes.direccio.desc') }}</p>
                <Button
                  :label="$t('stats.informes.direccio.btn')"
                  icon="pi pi-download"
                  class="p-button-primary"
                  :loading="generantDireccio"
                  @click="generarInformeDireccio"
                />
              </div>

              <Divider />

              <!-- Informe per professor -->
              <div class="informe-bloc">
                <div class="informe-bloc__titol">
                  <i class="pi pi-user" style="color: var(--teal)"></i>
                  {{ $t('stats.informes.professor.titol') }}
                </div>
                <p class="informe-bloc__desc">{{ $t('stats.informes.professor.desc') }}</p>
                <div class="informe-prof-controls">
                  <Dropdown
                    v-model="informeProfessorSeleccionat"
                    :options="informeProfessorsOpcions"
                    :placeholder="$t('stats.informes.professor.tots')"
                    :showClear="true"
                    style="min-width: 220px"
                  />
                  <div class="informe-check">
                    <input type="checkbox" id="mostrarTaules" v-model="informeMostrarTaules" />
                    <label for="mostrarTaules">{{ $t('stats.informes.professor.taules') }}</label>
                  </div>
                  <Button
                    :label="$t('stats.informes.professor.btn')"
                    icon="pi pi-download"
                    class="p-button-success"
                    :loading="generantProfessor"
                    @click="generarInformeProfessor"
                  />
                </div>
              </div>

            </div>
          </TabPanel>
        </TabView>
      </div>
    </div>

    <template #footer>
      <Button
        :label="$t('common.close')"
        icon="pi pi-times"
        @click="tancar"
        class="p-button-text"
      />
    </template>
  </Dialog>

  <Dialog
    v-model:visible="professorDetailVisible"
    :header="`📌 ${$t('stats.detail.title', { name: professorDetail?.professor || '' })}`"
    :modal="true"
    :style="{ width: '920px', maxHeight: '90vh' }"
    :closable="true"
  >
    <div v-if="detailLoading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('stats.detail.loading') }}</p>
    </div>
    <div v-else-if="professorDetail" class="detail-content">
      <div class="detail-section">
        <h3>🏥 {{ $t('stats.detail.absencesTitle') }}</h3>
        <DataTable
          :value="professorDetail.absencies"
          stripedRows
          :paginator="true"
          :rows="8"
          :rowsPerPageOptions="[8, 16, 32]"
          responsiveLayout="scroll"
          class="detail-table"
        >
          <Column field="dia_setmana" :header="$t('stats.detail.columns.day')" />
          <Column field="data" :header="$t('stats.detail.columns.date')" />
          <Column field="hora" :header="$t('stats.detail.columns.hour')" />
          <Column field="grup" :header="$t('stats.detail.columns.group')" />
          <Column field="assignatura" :header="$t('stats.detail.columns.subject')" />
          <Column field="substitut" :header="$t('stats.detail.columns.substitute')" />
          <Column field="tipus_absencia" :header="$t('stats.detail.columns.absenceType')" />
          <template #empty>
            <div class="empty-list">{{ $t('stats.detail.emptyAbsences') }}</div>
          </template>
        </DataTable>
      </div>

      <Divider />

      <div class="detail-section">
        <h3>🔄 {{ $t('stats.detail.substitutionsTitle') }}</h3>
        <DataTable
          :value="professorDetail.substitucions"
          stripedRows
          :paginator="true"
          :rows="8"
          :rowsPerPageOptions="[8, 16, 32]"
          responsiveLayout="scroll"
          class="detail-table"
        >
          <Column field="dia_setmana" :header="$t('stats.detail.columns.day')" />
          <Column field="data" :header="$t('stats.detail.columns.date')" />
          <Column field="hora" :header="$t('stats.detail.columns.hour')" />
          <Column field="professor_absent" :header="$t('stats.detail.columns.absentTeacher')" />
          <Column field="grup" :header="$t('stats.detail.columns.group')" />
          <Column field="assignatura" :header="$t('stats.detail.columns.subject')" />
          <Column field="tipus_substitut" :header="$t('stats.detail.columns.substituteType')" />
          <template #empty>
            <div class="empty-list">{{ $t('stats.detail.emptySubs') }}</div>
          </template>
        </DataTable>
      </div>
    </div>
  </Dialog>

  <Dialog
    v-model:visible="frangesVisible"
    :header="`⏰ ${$t('stats.slots.title')}`"
    :modal="true"
    :style="{ width: '720px', maxHeight: '90vh' }"
    :closable="true"
    class="franges-dialog"
  >
    <div class="franges-body">
      <div class="franges-controls">
        <div class="field">
          <label>{{ $t('stats.slots.day') }}</label>
          <Dropdown
            v-model="frangesDia"
            :options="diesDisponibles"
            :placeholder="$t('stats.slots.selectDay')"
            class="w-full"
          />
        </div>
        <div class="field">
          <label>{{ $t('stats.slots.hour') }}</label>
          <Dropdown
            v-model="frangesHora"
            :options="horesDisponibles"
            :placeholder="$t('stats.slots.selectHour')"
            class="w-full"
          />
        </div>
        <Button
          :label="$t('common.load')"
          class="p-button-primary"
          :loading="frangesLoading"
          @click="carregarFranges"
        />
      </div>

      <div v-if="frangesLoading" class="loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
        <p>{{ $t('stats.slots.loading') }}</p>
      </div>

      <div v-else-if="frangesData" class="franges-content">
        <div class="franges-summary">
          <Tag :value="$t('stats.slots.summarySlots', { count: frangesData.total_slots })" />
          <Tag :value="$t('stats.slots.summarySubs', { count: frangesData.total_substitucions })" />
        </div>
        <DataTable
          :value="frangesData.franges"
          stripedRows
          responsiveLayout="scroll"
          class="franges-table"
        >
          <Column field="num_substitucions" :header="$t('stats.slots.columns.concurrentSubs')" />
          <Column :header="$t('stats.slots.columns.teachers')">
            <template #body="slotProps">
              <span class="franges-professors">{{ formatProfessors(slotProps.data.professors) }}</span>
            </template>
          </Column>
          <template #empty>
            <div class="empty-list">{{ $t('common.noData') }}</div>
          </template>
        </DataTable>
      </div>
    </div>
  </Dialog>

  <Dialog
    v-model:visible="classesDetailVisible"
    :header="`📚 ${$t('stats.classes.detailTitle')}`"
    :modal="true"
    :style="{ width: '920px', maxHeight: '90vh' }"
    :closable="true"
    class="classes-detail-dialog"
  >
    <div class="classes-detail-body">
      <div class="classes-detail-controls">
        <div class="field">
          <label>{{ $t('stats.classes.detailClasses') }}</label>
          <MultiSelect
            v-model="classesSeleccionades"
            :options="classesDisponibles"
            optionLabel="label"
            optionValue="value"
            :placeholder="$t('stats.classes.detailPlaceholder')"
            class="w-full"
            display="chip"
          />
        </div>
        <Button
          :label="$t('common.load')"
          class="p-button-primary"
          :loading="classesDetailLoading"
          @click="carregarDetallClasses"
        />
      </div>

      <div v-if="classesDetailLoading" class="loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
        <p>{{ $t('stats.classes.detailLoading') }}</p>
      </div>

      <div v-else-if="classesDetailData" class="classes-detail-content">
        <div class="classes-detail-summary">
          <Tag :value="$t('stats.classes.summary.totalHours', { count: classesDetailData.resum.total })" />
          <Tag
            v-if="classesDetailData.resum.top_assignatura"
            :value="$t('stats.classes.summary.topSubject', { name: classesDetailData.resum.top_assignatura.nom, total: classesDetailData.resum.top_assignatura.total })"
          />
          <Tag
            v-if="classesDetailData.resum.top_professor"
            :value="$t('stats.classes.summary.topTeacher', { name: classesDetailData.resum.top_professor.nom, total: classesDetailData.resum.top_professor.total })"
          />
          <Tag
            v-if="classesDetailData.resum.top_substitut"
            :value="$t('stats.classes.summary.topSubstitute', { name: classesDetailData.resum.top_substitut.nom, total: classesDetailData.resum.top_substitut.total })"
          />
        </div>
        <div v-if="classesDetailData.resum.per_grup?.length" class="classes-detail-groups">
          <span v-for="g in classesDetailData.resum.per_grup" :key="g.grup" class="group-chip">
            {{ $t('stats.classes.summary.groupTotal', { group: g.grup, total: g.total }) }}
          </span>
        </div>
        <DataTable
          :value="classesDetailData.resultats"
          stripedRows
          :paginator="true"
          :rows="12"
          :rowsPerPageOptions="[12, 24, 48]"
          responsiveLayout="scroll"
          class="classes-detail-table"
        >
          <Column field="data" :header="$t('stats.detail.columns.date')" />
          <Column field="hora" :header="$t('stats.detail.columns.hour')" />
          <Column field="grup" :header="$t('stats.detail.columns.group')" />
          <Column field="assignatura" :header="$t('stats.detail.columns.subject')" />
          <Column field="professor_absent" :header="$t('stats.detail.columns.absentTeacher')" />
          <Column field="substitut" :header="$t('stats.detail.columns.substitute')" />
          <Column field="tipus_substitut" :header="$t('stats.detail.columns.substituteType')" />
          <template #empty>
            <div class="empty-list">{{ $t('common.noData') }}</div>
          </template>
        </DataTable>
      </div>
    </div>
  </Dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useToast } from 'primevue/usetoast'
import Dialog from 'primevue/dialog'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'

const toast = useToast()
const { t, locale } = useI18n()

const props = defineProps({
  visible: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)
const dataInici = ref(null)
const dataFinal = ref(null)
const resum = ref(null)
const professorsStats = ref({
  professors_absents: [],
  top_substituts: [],
  top_vigilants: []
})
const temporalStats = ref(null)
const classesStats = ref({ classes: [] })
const professorsResum = ref({ professors: [] })
const professorDetailVisible = ref(false)
const professorDetail = ref(null)
const detailLoading = ref(false)
const frangesVisible = ref(false)
const frangesLoading = ref(false)
const frangesData = ref(null)
const frangesDia = ref('')
const frangesHora = ref('')
const classesDetailVisible = ref(false)
const classesDetailLoading = ref(false)
const classesDetailData = ref(null)
const classesSeleccionades = ref([])

// Informes PDF
const generantDireccio = ref(false)
const generantProfessor = ref(false)
const informeProfessorSeleccionat = ref(null)
const informeMostrarTaules = ref(false)
const informeProfessorsOpcions = ref([])

const diesDisponibles = computed(() => (temporalStats.value?.dies || []).map((d) => d.dia))
const horesDisponibles = computed(() => (temporalStats.value?.hores || []).map((h) => h.hora))

const topAbsents = computed(() => (professorsStats.value.professors_absents || []).slice(0, 5))
const topSubstituts = computed(() => (professorsStats.value.top_substituts || []).slice(0, 5))
const topAbsentsMax = computed(() => Math.max(0, ...topAbsents.value.map(p => p.total || 0)))
const topSubstitutsMax = computed(() => Math.max(0, ...topSubstituts.value.map(p => p.total || 0)))
const classesDisponibles = computed(() => {
  const options = (classesStats.value?.classes || []).map((c) => ({
    label: c.grup,
    value: c.grup
  }))
  return options.sort((a, b) => a.label.localeCompare(b.label, locale.value || 'ca'))
})

// Inicialitzar dates (recuperar de la BD o últims 30 dies)
const inicialitzarDates = async () => {
  try {
    const response = await axios.get('/api/settings')
    const cfg = response.data || {}
    const dataIniciCfg = cfg.data_inici_estadistiques
    const dataFinalCfg = cfg.data_final_estadistiques

    if (dataIniciCfg && dataFinalCfg) {
      dataInici.value = new Date(dataIniciCfg)
      dataFinal.value = new Date(dataFinalCfg)
      return
    }
  } catch (error) {
    console.error('Error carregant configuració estadístiques:', error)
  }

  // Dates per defecte: últims 30 dies
  const avui = new Date()
  dataFinal.value = avui

  const fa30Dies = new Date()
  fa30Dies.setDate(avui.getDate() - 30)
  dataInici.value = fa30Dies
}

const formatDate = (date) => {
  if (!date) return null
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const carregarEstadistiques = async () => {
  loading.value = true
  try {
    const params = {
      data_inici: formatDate(dataInici.value),
      data_final: formatDate(dataFinal.value)
    }

    // Guardar dates a la BD per institució
    await axios.put('/api/settings', {
      data_inici_estadistiques: params.data_inici,
      data_final_estadistiques: params.data_final
    })

    const [resumResp, professorsResp, temporalResp, classesResp, taulaResp] = await Promise.all([
      axios.get('/api/estadistiques/resum', { params }),
      axios.get('/api/estadistiques/professors', { params }),
      axios.get('/api/estadistiques/temporal', { params }),
      axios.get('/api/estadistiques/classes', { params }),
      axios.get('/api/estadistiques/taula', { params })
    ])

    resum.value = resumResp.data
    professorsStats.value = professorsResp.data
    temporalStats.value = temporalResp.data
    classesStats.value = classesResp.data
    professorsResum.value = taulaResp.data
  } catch (error) {
    console.error('Error carregant estadístiques:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('stats.errors.load'),
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const formatPercent = (value, total) => {
  if (!total || total <= 0) return '0%'
  const percent = Math.min(100, Math.round((value / total) * 100))
  return `${percent}%`
}

const formatBarWidth = (value, maxValue) => {
  if (!maxValue || maxValue <= 0) return '0%'
  const percent = Math.min(100, Math.round((value / maxValue) * 100))
  return `${percent}%`
}

const formatProfessors = (professors) => {
  if (!professors || professors.length === 0) return '-'
  return professors.map((p) => `${p.professor} (${p.total})`).join(', ')
}

const obrirResumFranges = () => {
  if (!frangesDia.value) {
    frangesDia.value = diesDisponibles.value[0] || ''
  }
  if (!frangesHora.value) {
    frangesHora.value = horesDisponibles.value[0] || ''
  }
  frangesVisible.value = true
  if (frangesDia.value && frangesHora.value) {
    carregarFranges()
  }
}

const carregarFranges = async () => {
  if (!frangesDia.value || !frangesHora.value) return
  frangesLoading.value = true
  try {
    const params = {
      data_inici: formatDate(dataInici.value),
      data_final: formatDate(dataFinal.value),
      dia: frangesDia.value,
      hora: frangesHora.value
    }
    const resp = await axios.get('/api/estadistiques/franges', { params })
    frangesData.value = resp.data
  } catch (error) {
    console.error('Error carregant franges:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('stats.errors.slots'),
      life: 3000
    })
  } finally {
    frangesLoading.value = false
  }
}

const onProfessorRowClick = async (event) => {
  const prof = event?.data?.professor
  if (!prof) return
  detailLoading.value = true
  professorDetailVisible.value = true
  try {
    const params = {
      data_inici: formatDate(dataInici.value),
      data_final: formatDate(dataFinal.value)
    }
    const resp = await axios.get(`/api/estadistiques/professor/${encodeURIComponent(prof)}`, { params })
    professorDetail.value = resp.data
  } catch (error) {
    console.error('Error carregant detall professor:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('stats.errors.teacherDetail'),
      life: 3000
    })
  } finally {
    detailLoading.value = false
  }
}

const obrirDetallClasses = (grup = null) => {
  if (grup) {
    classesSeleccionades.value = [grup]
  } else if (!classesSeleccionades.value.length && classesDisponibles.value.length) {
    classesSeleccionades.value = [classesDisponibles.value[0].value]
  }
  classesDetailVisible.value = true
}

const onClasseRowClick = (event) => {
  const grup = event?.data?.grup
  if (!grup) return
  obrirDetallClasses(grup)
  carregarDetallClasses()
}

const carregarDetallClasses = async () => {
  if (!classesSeleccionades.value.length) {
    toast.add({
      severity: 'warn',
      summary: t('stats.classes.selectionRequired'),
      detail: t('stats.classes.selectAtLeastOne'),
      life: 2500
    })
    return
  }

  classesDetailLoading.value = true
  try {
    const params = {
      data_inici: formatDate(dataInici.value),
      data_final: formatDate(dataFinal.value),
      grups: classesSeleccionades.value
    }
    const resp = await axios.get('/api/estadistiques/classes/detall', { params })
    classesDetailData.value = resp.data
  } catch (error) {
    console.error('Error carregant detall classes:', error)
    toast.add({
      severity: 'error',
      summary: t('common.error'),
      detail: t('stats.errors.classesDetail'),
      life: 3000
    })
  } finally {
    classesDetailLoading.value = false
  }
}

const tancar = () => {
  emit('update:visible', false)
}

const _descarregarPdf = async (url, params, nomFitxer, refLoading) => {
  refLoading.value = true
  try {
    const resp = await axios.get(url, { params, responseType: 'blob' })
    const blob = new Blob([resp.data], { type: 'application/pdf' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = nomFitxer
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (error) {
    console.error('Error generant informe:', error)
    toast.add({ severity: 'error', summary: t('common.error'),
                detail: t('stats.informes.error'), life: 3000 })
  } finally {
    refLoading.value = false
  }
}

const generarInformeDireccio = async () => {
  const params = {
    data_inici: formatDate(dataInici.value),
    data_final: formatDate(dataFinal.value),
  }
  const nom = `informe_direccio_${params.data_inici}_${params.data_final}.pdf`
  await _descarregarPdf('/api/informes/direccio', params, nom, generantDireccio)
}

const generarInformeProfessor = async () => {
  const params = {
    data_inici: formatDate(dataInici.value),
    data_final: formatDate(dataFinal.value),
    mostrar_taules: informeMostrarTaules.value,
  }
  if (informeProfessorSeleccionat.value) {
    params.professor = informeProfessorSeleccionat.value
  }
  const nom = informeProfessorSeleccionat.value
    ? `informe_${informeProfessorSeleccionat.value}_${params.data_inici}_${params.data_final}.pdf`
    : `informe_professors_${params.data_inici}_${params.data_final}.pdf`
  await _descarregarPdf('/api/informes/professor', params, nom, generantProfessor)
}

const carregarInformeProfessors = async () => {
  try {
    const params = {
      data_inici: formatDate(dataInici.value),
      data_final: formatDate(dataFinal.value),
    }
    const resp = await axios.get('/api/informes/professors-llista', { params })
    informeProfessorsOpcions.value = resp.data.professors || []
  } catch (error) {
    console.error('Error carregant llista professors:', error)
  }
}

// Carregar quan s'obre el diàleg
watch(() => props.visible, (newVal) => {
  if (newVal) {
    inicialitzarDates().then(() => {
      carregarEstadistiques()
      carregarInformeProfessors()
    })
  }
})
</script>

<style scoped>
.estadistiques-container {
  padding: 0.75rem 0.75rem 0.5rem;
}

.informes-container {
  padding: 0.5rem 0;
}

.informe-bloc {
  padding: 1rem 0;
}

.informe-bloc__titol {
  font-size: 1rem;
  font-weight: 600;
  color: #1e3a5f;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.informe-bloc__desc {
  font-size: 0.875rem;
  color: #6b7280;
  margin-bottom: 0.75rem;
}

.informe-prof-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.informe-check {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  color: #374151;
}

.periode-selector {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 1.25rem;
}

.periode-selector .field {
  flex: 1;
}

.periode-selector .field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
  font-size: 0.9rem;
}

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

.stats-content {
  padding: 0.5rem 0;
}


.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.14rem;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.stat-card.primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-card.success {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  color: white;
}

.stat-card.info {
  background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
  color: white;
}

.stat-card.warning {
  background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
  color: white;
}

.stat-icon {
  font-size: 2rem;
  opacity: 0.9;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 1.6rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.85rem;
  opacity: 0.9;
  font-weight: 500;
}

.stat-detail {
  font-size: 0.75rem;
  opacity: 0.85;
  margin-top: 0.25rem;
}

.top-lists {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
}

.top-list h3 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #e5e7eb;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 6px;
  margin-bottom: 0.5rem;
  transition: all 0.2s;
}

.list-item:hover {
  background: #f3f4f6;
  transform: translateX(4px);
}

.rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: #667eea;
  color: white;
  border-radius: 50%;
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.name {
  flex: 1;
  font-weight: 500;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-list {
  text-align: center;
  padding: 2rem 1rem;
  color: #9ca3af;
  font-style: italic;
}

.bar-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.bar-row {
  display: grid;
  grid-template-columns: 32px 1fr 140px 36px;
  gap: 0.6rem;
  align-items: center;
  padding: 0.35rem 0.5rem;
  background: #f8fafc;
  border-radius: 8px;
}

.bar-track {
  height: 8px;
  background: #e5e7eb;
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.2s ease;
}

.bar-fill.warning {
  background: linear-gradient(90deg, #f59e0b, #f97316);
}

.bar-fill.success {
  background: linear-gradient(90deg, #10b981, #22c55e);
}

.bar-fill.info {
  background: linear-gradient(90deg, #3b82f6, #6366f1);
}

.bar-value {
  text-align: right;
  font-weight: 600;
  color: #374151;
}

.temporal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.5rem;
}

.temporal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}

.classes-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.75rem;
}

.temporal-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1rem 1.25rem;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.temporal-card h3 {
  margin: 0 0 1rem;
  font-size: 1.05rem;
  color: #1f2937;
}

.temporal-legend {
  display: flex;
  gap: 0.75rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: #6b7280;
  margin: -0.35rem 0 0.75rem;
}

.temporal-legend .legend-subs {
  color: #4f46e5;
}

.temporal-legend .legend-vigs {
  color: #6b7280;
}

.temporal-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.temporal-row {
  display: grid;
  grid-template-columns: 90px 1fr 70px;
  gap: 0.6rem;
  align-items: center;
}

.temporal-label {
  font-weight: 600;
  color: #374151;
  font-size: 0.9rem;
}

.temporal-bar {
  height: 8px;
  background: #e5e7eb;
  border-radius: 999px;
  overflow: hidden;
}

.temporal-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea 0%, #4f46e5 100%);
  border-radius: 999px;
}

.temporal-values {
  display: flex;
  justify-content: flex-end;
  gap: 0.4rem;
  font-size: 0.85rem;
}

.temporal-values .subs {
  font-weight: 600;
  color: #4f46e5;
}

.temporal-values .vigs {
  color: #6b7280;
}

.classes-table {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

:deep(.classes-table .p-datatable-tbody > tr) {
  cursor: pointer;
  transition: background-color 0.2s ease;
}

:deep(.classes-table .p-datatable-tbody > tr:hover) {
  background: #eef2ff;
}

.professors-section {
  margin-top: 1.5rem;
}

.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.section-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #1f2937;
}

.section-header small {
  color: #6b7280;
}

.professors-table {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

:deep(.professors-table .p-datatable-tbody > tr) {
  cursor: pointer;
  transition: background-color 0.2s ease;
}

:deep(.professors-table .p-datatable-tbody > tr:hover) {
  background: #eef2ff;
}

:deep(.professors-table .p-datatable-thead > tr > th) {
  background: #f8f9fa;
  color: #1f2937;
  font-weight: 700;
  text-align: center;
  padding: 0.75rem 0.6rem;
}

:deep(.professors-table .p-datatable-tbody > tr > td) {
  padding: 0.7rem 0.6rem;
  text-align: center;
  font-weight: 500;
  color: #374151;
}

:deep(.professors-table .p-datatable-tbody > tr > td:first-child),
:deep(.professors-table .p-datatable-thead > tr > th:first-child) {
  text-align: left;
  font-weight: 600;
}

:deep(.professors-table .p-datatable-tbody > tr > td:nth-child(5)),
:deep(.professors-table .p-datatable-tbody > tr > td:nth-child(8)),
:deep(.professors-table .p-datatable-tbody > tr > td:nth-child(10)) {
  font-weight: 700;
  color: #111827;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.detail-section h3 {
  margin: 0 0 0.75rem;
  font-size: 1.05rem;
  color: #1f2937;
}

.detail-table {
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

.franges-controls {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 1rem;
  align-items: end;
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.franges-controls :deep(.p-dropdown) {
  min-height: 2.6rem;
}

.franges-controls :deep(.p-dropdown-label) {
  padding: 0.6rem 0.85rem;
  font-size: 0.95rem;
}

.franges-controls :deep(.p-dropdown-trigger) {
  width: 2.2rem;
}

.franges-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.franges-body {
  padding: 1.25rem 1.25rem 1rem;
}

.franges-summary {
  display: flex;
  gap: 0.5rem;
}

.franges-summary :deep(.p-tag) {
  padding: 0.4rem 0.75rem;
  font-size: 0.9rem;
}

.franges-dialog :deep(.p-dialog-header) {
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

.franges-dialog :deep(.p-dialog-content) {
  background: #ffffff;
  padding: 0;
}

.classes-detail-body {
  padding: 1.25rem 1.25rem 1rem;
}

.classes-detail-controls {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 1rem;
  align-items: end;
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.classes-detail-controls :deep(.p-multiselect) {
  min-height: 2.6rem;
}

.classes-detail-controls :deep(.p-multiselect-label) {
  padding: 0.6rem 0.85rem;
  font-size: 0.95rem;
}

.classes-detail-controls :deep(.p-multiselect-trigger) {
  width: 2.2rem;
}

.classes-detail-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.classes-detail-summary :deep(.p-tag) {
  padding: 0.4rem 0.75rem;
  font-size: 0.9rem;
}

.classes-detail-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  color: #4b5563;
}

.classes-detail-groups .group-chip {
  background: #f1f5f9;
  border: 1px solid #e5e7eb;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
}

.classes-detail-table {
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

.classes-detail-table :deep(.p-datatable-thead > tr > th),
.classes-detail-table :deep(.p-datatable-tbody > tr > td) {
  padding: 0.75rem 0.7rem;
}

.classes-detail-dialog :deep(.p-dialog-content) {
  background: #ffffff;
  padding: 0;
}

.franges-dialog :deep(.p-tag) {
  font-weight: 600;
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
}

.franges-dialog :deep(.p-tag + .p-tag) {
  background: #ecfdf3;
  color: #166534;
}

.franges-professors {
  color: #374151;
  font-size: 0.9rem;
}

.franges-table {
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

.franges-table :deep(.p-datatable-thead > tr > th) {
  padding: 0.8rem 0.8rem;
}

.franges-table :deep(.p-datatable-tbody > tr > td) {
  padding: 0.8rem 0.8rem;
}

</style>
