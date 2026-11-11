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
        <div v-if="cursos && cursos.length" class="field">
          <label :for="prefixEtiquetes + '-camp-1'">{{ $t('stats.period.course') }}</label>
          <Dropdown :aria-label="$t('stats.period.course')" :inputId="prefixEtiquetes + '-camp-1'"
            v-model="cursTriatId"
            :options="cursos"
            optionLabel="nom"
            optionValue="id"
            :placeholder="$t('stats.period.customRange')"
            :showClear="true"
            @change="onCursTriat"
          />
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-2'">{{ $t('stats.period.start') }}</label>
          <Calendar :inputId="prefixEtiquetes + '-camp-2'"
            v-model="dataInici"
            dateFormat="yy-mm-dd"
            :maxDate="dataFinal"
            :showIcon="true"
            :placeholder="$t('stats.period.datePlaceholder')"
          />
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-3'">{{ $t('stats.period.end') }}</label>
          <Calendar :inputId="prefixEtiquetes + '-camp-3'"
            v-model="dataFinal"
            dateFormat="yy-mm-dd"
            :minDate="dataInici"
            :showIcon="true"
            :placeholder="$t('stats.period.datePlaceholder')"
          />
        </div>
        <div class="field">
          <label for="estadistiques-hores">{{ $t('stats.period.hours') }}</label>
          <MultiSelect :aria-label="$t('stats.period.hours')"
            v-model="horesTriades"
            inputId="estadistiques-hores"
            :options="frangesHorari"
            :placeholder="$t('stats.period.allHours')"
            :maxSelectedLabels="3"
            :selectedItemsLabel="$t('stats.period.hoursSelected', { n: '{0}' })"
            @hide="recarregaSiCanviaElFiltre"
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
                  <div class="stat-value">{{ resum.cobertura.a_cobrir }}</div>
                  <div class="stat-label">{{ $t('stats.summary.toCover') }}</div>
                  <div class="stat-detail">
                    {{ $t('stats.summary.toCoverBreakdown', { absences: resum.cobertura.absencies, services: resum.cobertura.serveis }) }}
                  </div>
                  <div class="stat-detail">
                    {{ $t('stats.summary.coveredDetail', { count: resum.cobertura.cobertes, percent: resum.cobertura.percentatge }, resum.cobertura.cobertes) }}
                  </div>
                </div>
              </div>

              <div class="stat-card success">
                <div class="stat-icon">👁️</div>
                <div class="stat-content">
                  <div class="stat-value">{{ resum.vigilancies.total }}</div>
                  <div class="stat-label">{{ $t('stats.summary.totalVigilancies') }}</div>
                  <div class="stat-detail">
                    {{ $t('stats.summary.vigilanciesCovered', { count: resum.vigilancies.cobertes, percent: resum.vigilancies.percentatge }, resum.vigilancies.cobertes) }}
                  </div>
                  <div class="stat-detail">
                    {{ $t('stats.summary.vigilanciesBreakdown', { vigilant: resum.vigilancies.vigilant, substitute: resum.vigilancies.substitut, uncovered: resum.vigilancies.descobertes }) }}
                  </div>
                </div>
              </div>

              <div class="stat-card info">
                <div class="stat-icon">📅</div>
                <div class="stat-content">
                  <div class="stat-value">{{ resum.activitat.dies_amb_absencies }}</div>
                  <div class="stat-label">{{ $t('stats.summary.daysWithAbsences') }}</div>
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
                <div class="section-header__hints">
                  <small>{{ $t('stats.summary.perTeacherHint') }}</small>
                  <small>{{ $t('stats.summary.balanceHint') }}</small>
                </div>
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
                <Column field="absencies" :header="$t('stats.columns.absences')" :sortable="true" />
                <Column field="serveis" :header="$t('stats.columns.services')" :sortable="true" />
                <Column field="total_absencies" :header="$t('stats.columns.absTotal')" :sortable="true" />
                <Column field="substitucions_fetes" :header="$t('stats.columns.subsDone')" :sortable="true" />
                <Column field="vigilancies_fetes" :header="$t('stats.columns.vigsDone')" :sortable="true" />
                <Column field="balanc" :header="$t('stats.columns.balance')" :sortable="true" />
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
                <small class="top-list__hint">{{ $t('stats.summary.doneHint') }}</small>
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
                  <span class="legend-to-cover">{{ $t('stats.temporal.legendToCover') }}</span>
                  <span class="legend-subs">{{ $t('stats.temporal.legendCovered') }}</span>
                  <span class="legend-vigs">{{ $t('stats.temporal.legendVigs') }}</span>
                </div>
                <div v-if="temporalStats.dies.length > 0" class="temporal-list">
                  <div v-for="dia in temporalStats.dies" :key="dia.dia" class="temporal-row">
                    <div class="temporal-label">{{ localizeBackendDayName(dia.dia, t) }}</div>
                    <div class="temporal-bar">
                      <div
                        class="temporal-bar-fill"
                        :style="{ width: formatPercent(dia.a_cobrir, temporalStats.totals.a_cobrir) }"
                      ></div>
                    </div>
                    <div class="temporal-values">
                      <span class="to-cover">{{ dia.a_cobrir }}</span>
                      <span class="subs">{{ dia.cobertes }}</span>
                      <span class="vigs">{{ dia.vigilancies }}</span>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-list">{{ $t('common.noData') }}</div>
              </div>

              <div class="temporal-card">
                <h3>🕐 {{ $t('stats.temporal.byHour') }}</h3>
                <div class="temporal-legend">
                  <span class="legend-to-cover">{{ $t('stats.temporal.legendToCover') }}</span>
                  <span class="legend-subs">{{ $t('stats.temporal.legendCovered') }}</span>
                  <span class="legend-vigs">{{ $t('stats.temporal.legendVigs') }}</span>
                </div>
                <div v-if="temporalStats.hores.length > 0" class="temporal-list">
                  <div v-for="hora in temporalStats.hores" :key="hora.hora" class="temporal-row">
                    <div class="temporal-label">{{ hora.hora }}</div>
                    <div class="temporal-bar">
                      <div
                        class="temporal-bar-fill"
                        :style="{ width: formatPercent(hora.a_cobrir, temporalStats.totals.a_cobrir) }"
                      ></div>
                    </div>
                    <div class="temporal-values">
                      <span class="to-cover">{{ hora.a_cobrir }}</span>
                      <span class="subs">{{ hora.cobertes }}</span>
                      <span class="vigs">{{ hora.vigilancies }}</span>
                    </div>
                  </div>
                </div>
                <div v-else class="empty-list">{{ $t('common.noData') }}</div>
              </div>
            </div>
            <div class="temporal-actions">
              <Button
                :label="$t('stats.temporal.summaryBySlot')"
                icon="pi pi-clock"
                class="p-button-secondary"
                @click="obrirResumFranges"
              />
            </div>
          </TabPanel>

          <TabPanel :header="`📚 ${$t('stats.tabs.classes')}`">
            <div class="classes-actions">
              <Button
                :label="$t('stats.classes.detailButton')"
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
              <Column field="a_cobrir" :header="$t('stats.classes.columns.toCover')" :sortable="true" />
              <Column field="cobertes" :header="$t('stats.classes.columns.covered')" :sortable="true" />
              <Column field="percentatge" :header="$t('stats.classes.columns.coverage')" :sortable="true">
                <template #body="{ data }">{{ data.percentatge }}%</template>
              </Column>
              <Column field="assignatura_top" :header="$t('stats.classes.columns.topSubject')" />
              <Column field="professor_top" :header="$t('stats.classes.columns.topTeacher')" />
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
                  <Dropdown :aria-label="$t('stats.informes.professor.tots')"
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
          <Column field="tipus_absencia" :header="$t('stats.detail.columns.absenceType')">
            <template #body="{ data }">{{ nomTipusFila(data.tipus_absencia) }}</template>
          </Column>
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
          <Column field="tipus_absencia" :header="$t('stats.detail.columns.rowType')">
            <template #body="{ data }">{{ nomTipusFila(data.tipus_absencia) }}</template>
          </Column>
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
          <label :for="prefixEtiquetes + '-camp-4'">{{ $t('stats.slots.day') }}</label>
          <Dropdown :aria-label="$t('stats.slots.day')" :inputId="prefixEtiquetes + '-camp-4'"
            v-model="frangesDia"
            :options="diesOpcions"
            optionLabel="label"
            optionValue="value"
            :placeholder="$t('stats.slots.selectDay')"

          />
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-5'">{{ $t('stats.slots.hour') }}</label>
          <Dropdown :aria-label="$t('stats.slots.hour')" :inputId="prefixEtiquetes + '-camp-5'"
            v-model="frangesHora"
            :options="horesDisponibles"
            :placeholder="$t('stats.slots.selectHour')"

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
          <label :for="prefixEtiquetes + '-camp-6'">{{ $t('stats.classes.detailClasses') }}</label>
          <MultiSelect :aria-label="$t('stats.classes.detailClasses')" :inputId="prefixEtiquetes + '-camp-6'"
            v-model="classesSeleccionades"
            :options="classesDisponibles"
            optionLabel="label"
            optionValue="value"
            :placeholder="$t('stats.classes.detailPlaceholder')"

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
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { localizeBackendDayName } from '../views/scheduler/textUtils'
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
import { useEstadistiques } from '../composables/useEstadistiques'

const prefixEtiquetes = useId()

const toast = useToast()
const { t } = useI18n()

const props = defineProps({
  visible: {
    type: Boolean,
    required: true
  },
  // Curs de la data on s'està treballant. Marca el rang de dates per defecte.
  curs: {
    type: Object,
    default: null
  },
  // Tots els cursos, com a presets del selector de període.
  cursos: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:visible'])

const {
  loading,
  dataInici,
  dataFinal,
  resum,
  temporalStats,
  classesStats,
  professorsResum,
  professorDetailVisible,
  professorDetail,
  detailLoading,
  frangesVisible,
  frangesLoading,
  frangesData,
  frangesDia,
  frangesHora,
  classesDetailVisible,
  classesDetailLoading,
  classesDetailData,
  classesSeleccionades,
  generantDireccio,
  generantProfessor,
  informeProfessorSeleccionat,
  informeMostrarTaules,
  informeProfessorsOpcions,
  frangesHorari,
  horesTriades,
  diesOpcions,
  horesDisponibles,
  topAbsents,
  topSubstituts,
  topAbsentsMax,
  topSubstitutsMax,
  classesDisponibles,
  cursTriatId,
  onCursTriat,
  recarregaSiCanviaElFiltre,
  carregarEstadistiques,
  nomTipusFila,
  formatPercent,
  formatBarWidth,
  formatProfessors,
  obrirResumFranges,
  carregarFranges,
  onProfessorRowClick,
  obrirDetallClasses,
  onClasseRowClick,
  carregarDetallClasses,
  tancar,
  generarInformeDireccio,
  generarInformeProfessor,
} = useEstadistiques({ props, emit, t, toast })
</script>

<style scoped src="./estadistiquesDialog.css"></style>
