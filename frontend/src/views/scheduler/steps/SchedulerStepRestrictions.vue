<template>
  <div class="step-panel animate-fade-in">
    <TabView class="restriccions-tabs app-tabview">

      <!-- TAB 0: DURADES DEL TITULAR -->
      <TabPanel :header="`⏱ ${t('scheduler.steps.restrictions.tabs.durades')}`">
        <div class="subtab-content">
          <p class="restriccio-title">{{ t('scheduler.steps.restrictions.durades.title') }}</p>

          <div class="durada-global-row">
            <label :for="prefixEtiquetes + '-camp-1'">{{ t('scheduler.steps.restrictions.durades.globalLabel') }}</label>
            <div class="durada-global-control">
              <InputNumber :inputId="prefixEtiquetes + '-camp-1'"
                :modelValue="duradaTitular"
                :min="1"
                :max="8"
                showButtons
                buttonLayout="horizontal"
                incrementButtonIcon="pi pi-plus"
                decrementButtonIcon="pi pi-minus"
                class="scheduler-inputnumber"
                @update:modelValue="emit('update:duradaTitular', $event)"
              />
              <span >{{ t('scheduler.steps.restrictions.durades.globalSuffix') }}</span>
            </div>
          </div>
          <div class="durada-global-row">
            <label :for="prefixEtiquetes + '-camp-2'">{{ t('scheduler.steps.restrictions.durades.examGlobalLabel') }}</label>
            <div class="durada-global-control">
              <InputNumber :inputId="prefixEtiquetes + '-camp-2'"
                :modelValue="duradaExamen"
                :min="1"
                :max="8"
                showButtons
                buttonLayout="horizontal"
                incrementButtonIcon="pi pi-plus"
                decrementButtonIcon="pi pi-minus"
                class="scheduler-inputnumber"
                @update:modelValue="emit('update:duradaExamen', $event)"
              />
              <span >{{ t('scheduler.steps.restrictions.durades.examGlobalSuffix') }}</span>
            </div>
          </div>

          <div class="restriccions-header">
            <div>
              <p >{{ t('scheduler.steps.restrictions.durades.exceptionsTitle') }}</p>
              <p >{{ t('scheduler.steps.restrictions.durades.exceptionsDesc') }}</p>
            </div>
            <Button :label="t('common.add')" icon="pi pi-plus" size="small" outlined @click="obrirDialogDurada()" />
          </div>

          <DataTable :value="duradesGrups" class="p-datatable-sm restriccions-professors-table" stripedRows :emptyMessage="t('scheduler.steps.restrictions.durades.emptyMessage')">
            <Column field="nom" :header="t('scheduler.steps.restrictions.durades.columns.name')" style="width: 140px">
              <template #body="s">
                <span >{{ s.data.nom || t('common.noneDash') }}</span>
              </template>
            </Column>
            <Column field="assignatures" :header="t('scheduler.steps.restrictions.durades.columns.session')">
              <template #body="s">
                <div >
                  <Tag v-for="a in s.data.assignatures" :key="a" :value="a" severity="info" class="scheduler-tag" />
                </div>
              </template>
            </Column>
            <Column field="durada" :header="t('scheduler.steps.restrictions.durades.columns.duration')" style="width: 90px">
              <template #body="s">
                <div >
                  <Tag :value="`${s.data.durada}h`" severity="warning" class="tiny-tag" />
                </div>
              </template>
            </Column>
            <Column field="durada_examen" :header="t('scheduler.steps.restrictions.durades.columns.examDuration')" style="width: 90px">
              <template #body="s">
                <div >
                  <Tag :value="`${s.data.durada_examen ?? s.data.durada}h`" severity="info" class="tiny-tag" />
                </div>
              </template>
            </Column>
            <Column style="width: 100px">
              <template #body="s">
                <div >
                  <Button icon="pi pi-pencil" text severity="secondary" size="small" @click="obrirEditarDuradaGrup(s.data)" />
                  <Button icon="pi pi-trash" text severity="danger" size="small" @click="eliminarDuradaGrup(s.data.id)" />
                </div>
              </template>
            </Column>
          </DataTable>
        </div>
      </TabPanel>

      <TabPanel :header="`👤 ${t('scheduler.steps.restrictions.tabs.teachers')}`">
        <div class="subtab-content">
          <div class="restriccions-header">
            <div>
              <p class="restriccio-title">{{ t('scheduler.steps.restrictions.teachers.title') }}</p>
              <p >{{ t('scheduler.steps.restrictions.teachers.description') }}</p>
              <p >{{ t('scheduler.steps.restrictions.teachers.example') }}</p>
            </div>
            <Button :label="t('common.add')" icon="pi pi-plus" size="small" outlined @click="obrirDialogProfessor" />
          </div>
          <DataTable :value="restriccionsProfessors" class="p-datatable-sm restriccions-professors-table" stripedRows :emptyMessage="t('scheduler.steps.restrictions.teachers.emptyMessage')">
            <Column field="professor" :header="t('scheduler.steps.restrictions.teachers.columns.professor')" style="width: 15%"></Column>
            <Column field="assignatures" :header="t('scheduler.steps.restrictions.teachers.columns.subjects')">
              <template #body="s"><div ><Tag v-for="a in s.data.assignatures" :key="a" :value="a" severity="info" class="scheduler-tag" /></div></template>
            </Column>
            <Column field="dies" :header="t('scheduler.steps.restrictions.teachers.columns.restrictedDays')" style="width: 20%">
              <template #body="s"><span >{{ formatRestrictedDays(s.data.dies) }}</span></template>
            </Column>
            <Column field="max_examens" :header="t('scheduler.steps.restrictions.teachers.columns.max')" style="width: 60px; text-align: center">
              <template #body="s"><Tag :value="String(s.data.max_examens ?? 0)" severity="warning" class="tiny-tag" /></template>
            </Column>
            <Column field="pes" :header="t('scheduler.steps.restrictions.teachers.columns.weight')" style="width: 60px; text-align: center">
              <template #body="s"><Tag :value="String(s.data.pes ?? 0)" class="tiny-tag" /></template>
            </Column>
            <Column style="width: 120px">
              <template #body="s">
                <div >
                  <Button icon="pi pi-pencil" text severity="secondary" size="small" @click="obrirDialogProfessor(s.data)" />
                  <Button icon="pi pi-trash" text severity="danger" size="small" @click="eliminarRestriccio('professors', s.data.id)" />
                </div>
              </template>
            </Column>
          </DataTable>
        </div>
      </TabPanel>

      <TabPanel :header="`📌 ${t('scheduler.steps.restrictions.tabs.daysHours')}`">
        <div class="subtab-content">
          <div class="restriccions-header">
            <div>
              <p class="restriccio-title">{{ t('scheduler.steps.restrictions.daysHours.title') }}</p>
              <p >{{ t('scheduler.steps.restrictions.daysHours.description') }}</p>
            </div>
            <Button :label="t('common.add')" icon="pi pi-plus" size="small" outlined @click="obrirDialogDiaHora" />
          </div>
          <DataTable :value="restriccionsDiesHores" class="p-datatable-sm restriccions-professors-table" stripedRows :emptyMessage="t('scheduler.steps.restrictions.daysHours.emptyMessage')">
            <Column :header="t('scheduler.steps.restrictions.daysHours.columns.type')" style="width: 90px">
              <template #body="s">
                <Tag
                  :value="s.data.tipus === 'prohibir' ? t('scheduler.dialogs.daysHours.typeProhibit') : t('scheduler.dialogs.daysHours.typeFix')"
                  :severity="s.data.tipus === 'prohibir' ? 'danger' : 'success'"
                  class="tiny-tag"
                />
              </template>
            </Column>
            <Column :header="t('scheduler.steps.restrictions.daysHours.columns.subjects')">
              <template #body="s">
                <div >
                  <Tag v-for="a in s.data.assignatures" :key="a" :value="a" severity="info" class="scheduler-tag" />
                </div>
              </template>
            </Column>
            <Column field="dia" :header="t('scheduler.steps.restrictions.daysHours.columns.day')" style="width: 120px">
              <template #body="s"><Tag v-if="s.data.dia" :value="dayLabel(s.data.dia)" severity="info" class="tiny-tag" /><span v-else >{{ t('common.noneDash') }}</span></template>
            </Column>
            <Column field="hora" :header="t('scheduler.steps.restrictions.daysHours.columns.hour')" style="width: 100px">
              <template #body="s"><Tag v-if="s.data.hora" :value="s.data.hora" severity="warning" class="tiny-tag" /><span v-else >{{ t('common.noneDash') }}</span></template>
            </Column>
            <Column style="width: 120px">
              <template #body="s">
                <div >
                  <Button icon="pi pi-pencil" text severity="secondary" size="small" @click="obrirDialogDiaHora(s.data)" />
                  <Button icon="pi pi-trash" text severity="danger" size="small" @click="eliminarRestriccio('diesHores', s.data.id)" />
                </div>
              </template>
            </Column>
          </DataTable>
        </div>
      </TabPanel>

      <TabPanel :header="`⏰ ${t('scheduler.steps.restrictions.tabs.strictSchedule')}`">
        <div class="subtab-content">
          <p >{{ t('scheduler.steps.restrictions.strictSchedule.description') }}</p>
          <div class="professors-estrictes-grid">
            <div v-for="prof in llistaProfessors" :key="prof" class="prof-checkbox-item">
              <Checkbox
                :modelValue="professorsHorariEstricte"
                @update:modelValue="emit('update:professorsHorariEstricte', $event)"
                :inputId="'prof-' + toDomId(prof)"
                :value="prof"
              />
              <label :for="'prof-' + toDomId(prof)">{{ prof }}</label>
            </div>
          </div>
        </div>
      </TabPanel>

      <TabPanel :header="`📅 ${t('scheduler.steps.restrictions.tabs.dayPreferences')}`">
        <div class="subtab-content">
          <div class="restriccions-header">
            <div>
              <p class="restriccio-title">{{ t('scheduler.steps.restrictions.dayPreferences.title') }}</p>
              <p >{{ t('scheduler.steps.restrictions.dayPreferences.description') }}</p>
            </div>
            <Button :label="t('common.add')" icon="pi pi-plus" size="small" outlined @click="obrirDialogPreferenciaDia" />
          </div>
          <DataTable :value="restriccionsPreferencies" class="p-datatable-sm restriccions-professors-table" stripedRows :emptyMessage="t('scheduler.steps.restrictions.dayPreferences.emptyMessage')">
            <Column field="assignatures" :header="t('scheduler.steps.restrictions.dayPreferences.columns.subjects')">
              <template #body="s"><div ><Tag v-for="a in s.data.assignatures" :key="a" :value="a" severity="info" class="scheduler-tag" /></div></template>
            </Column>
            <Column field="tipus" :header="t('scheduler.steps.restrictions.dayPreferences.columns.type')" style="width: 160px">
              <template #body="s">
                <div >
                  <Tag
                    :value="preferenciaLabel(s.data.tipus)"
                    :severity="s.data.tipus === 'mateix_dia' ? 'success' : s.data.tipus === 'mateix_slot' ? 'info' : (s.data.tipus === 'no_mateix_dia' ? 'danger' : 'warning')"
                    class="tiny-tag"
                  />
                </div>
              </template>
            </Column>
            <Column field="pes" :header="t('scheduler.steps.restrictions.dayPreferences.columns.weightPercent')" style="width: 80px">
              <template #body="s"><Tag :value="`${String(s.data.pes ?? 0)}%`" :severity="s.data.pes >= 100 ? 'danger' : (s.data.pes >= 75 ? 'warning' : 'info')" class="tiny-tag" /></template>
            </Column>
            <Column style="width: 120px">
              <template #body="s">
                <div >
                  <Button icon="pi pi-pencil" text severity="secondary" size="small" @click="obrirDialogPreferenciaDia(s.data)" />
                  <Button icon="pi pi-trash" text severity="danger" size="small" @click="eliminarPreferencia(s.data.id)" />
                </div>
              </template>
            </Column>
          </DataTable>
        </div>
      </TabPanel>

      <TabPanel :header="`🚫 ${t('scheduler.steps.restrictions.tabs.incompatibilities')}`">
        <div class="subtab-content">
          <div class="restriccions-header">
            <div>
              <p class="restriccio-title">{{ t('scheduler.steps.restrictions.incompatibilities.title') }}</p>
              <p >{{ t('scheduler.steps.restrictions.incompatibilities.description') }}</p>
              <p >{{ t('scheduler.steps.restrictions.incompatibilities.example') }}</p>
            </div>
            <Button :label="t('common.add')" icon="pi pi-plus" size="small" outlined @click="obrirDialogIncompatibilitat" />
          </div>
          <DataTable :value="restriccionsIncompatibilitats" class="p-datatable-sm restriccions-professors-table" stripedRows :emptyMessage="t('scheduler.steps.restrictions.incompatibilities.emptyMessage')">
            <Column field="nom" :header="t('scheduler.steps.restrictions.incompatibilities.columns.groupName')" style="width: 150px"></Column>
            <Column field="assignatures" :header="t('scheduler.steps.restrictions.incompatibilities.columns.subjects')">
              <template #body="s"><div ><Tag v-for="a in s.data.assignatures" :key="a" :value="a" severity="danger" class="scheduler-tag" /></div></template>
            </Column>
            <Column field="pes" :header="t('scheduler.steps.restrictions.incompatibilities.columns.weight')" style="width: 80px">
              <template #body="s"><div ><Tag :value="String(s.data.pes ?? 100)" class="tiny-tag" /></div></template>
            </Column>
            <Column style="width: 120px">
              <template #body="s">
                <div >
                  <Button icon="pi pi-pencil" text severity="secondary" size="small" @click="obrirDialogIncompatibilitat(s.data)" />
                  <Button icon="pi pi-trash" text severity="danger" size="small" @click="eliminarRestriccio('incompatibilitats', s.data.id)" />
                </div>
              </template>
            </Column>
          </DataTable>
        </div>
      </TabPanel>

      <TabPanel :header="`⚖️ ${t('scheduler.steps.restrictions.tabs.weights')}`">
        <div class="subtab-content">
          <section class="restriccions-section-card">
            <h3 >⚖️ {{ t('scheduler.steps.restrictions.weights.title') }}</h3>
            <div class="pesos-grid">
              <div v-for="(val, clau) in pesos" :key="clau" class="peso-item">
                <div class="peso-meta">
                  <label >{{ (pesosInfo[clau]?.label || clau.replace(/_/g, ' ')) }}</label>
                  <p >{{ pesosInfo[clau]?.desc || '' }}</p>
                </div>
                <div class="peso-control">
                  <InputNumber
                    :aria-label="pesosInfo[clau]?.label || clau" :modelValue="pesos[clau]"
                    @update:modelValue="emit('update:peso', { key: clau, value: $event })"
                    showButtons
                    buttonLayout="horizontal"
                    incrementButtonIcon="pi pi-plus"
                    decrementButtonIcon="pi pi-minus"
                    :min="clau.includes('preferencia') ? -1000 : 0"
                    :max="clau.includes('dura') ? 5000 : 500"
                    class="scheduler-inputnumber"
                  />
                </div>
              </div>
            </div>
          </section>

          <section class="restriccions-section-card restriccions-section-card-muted">
            <div class="restriccions-header">
              <div>
                <h4 >💰 {{ t('scheduler.steps.restrictions.costs.title') }}</h4>
                <p >{{ t('scheduler.steps.restrictions.costs.description') }}</p>
              </div>
              <Button :label="t('scheduler.steps.restrictions.costs.addIndividual')" icon="pi pi-plus" size="small" outlined @click="obrirDialogCostProfessor()" />
            </div>

            <div class="pesos-grid">
              <div v-for="(val, clau) in costosProfessors.globals" :key="`global-${clau}`" class="peso-item">
                <div class="peso-meta">
                  <label >{{ (costosInfo[clau]?.label || clau.replace(/_/g, ' ')) }}</label>
                  <p >{{ costosInfo[clau]?.desc || '' }}</p>
                </div>
                <div class="peso-control">
                  <InputNumber
                    :aria-label="costosInfo[clau]?.label || clau" :modelValue="costosProfessors.globals[clau]"
                    @update:modelValue="emit('update:costGlobal', { key: clau, value: $event })"
                    showButtons
                    buttonLayout="horizontal"
                    incrementButtonIcon="pi pi-plus"
                    decrementButtonIcon="pi pi-minus"
                    :min="0"
                    :max="500"
                    class="scheduler-inputnumber"
                  />
                </div>
              </div>
            </div>

            <DataTable :value="costosProfessorsIndividuals" class="p-datatable-sm restriccions-professors-table" stripedRows :emptyMessage="t('scheduler.steps.restrictions.costs.individualEmptyMessage')">
              <Column field="professor" :header="t('scheduler.steps.restrictions.costs.columns.professor')" style="width: 200px"></Column>
              <Column field="substitucio" :header="t('scheduler.steps.restrictions.costs.columns.subst')" style="width: 90px">
                <template #body="s"><div ><Tag :value="String(s.data.substitucio)" class="tiny-tag" /></div></template>
              </Column>
              <Column field="abans_jornada" :header="t('scheduler.steps.restrictions.costs.columns.before')" style="width: 90px">
                <template #body="s"><div ><Tag :value="String(s.data.abans_jornada)" class="tiny-tag" /></div></template>
              </Column>
              <Column field="despres_jornada" :header="t('scheduler.steps.restrictions.costs.columns.after')" style="width: 90px">
                <template #body="s"><div ><Tag :value="String(s.data.despres_jornada)" class="tiny-tag" /></div></template>
              </Column>
              <Column field="no_treballa_dia" :header="t('scheduler.steps.restrictions.costs.columns.noWork')" style="width: 90px">
                <template #body="s"><div ><Tag :value="String(s.data.no_treballa_dia)" class="tiny-tag" /></div></template>
              </Column>
              <Column style="width: 120px">
                <template #body="s">
                  <div >
                    <Button icon="pi pi-pencil" text severity="secondary" size="small" @click="obrirDialogCostProfessor(s.data)" />
                    <Button icon="pi pi-trash" text severity="danger" size="small" @click="eliminarCostProfessor(s.data.professor)" />
                  </div>
                </template>
              </Column>
            </DataTable>
          </section>
        </div>
      </TabPanel>
    </TabView>
  </div>
</template>

<script setup>
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { localizeBackendDayName } from '../textUtils'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'

defineProps({
  duradaTitular: { type: Number, default: 1 },
  duradaExamen: { type: Number, default: 1 },
  duradesGrups: { type: Array, default: () => [] },
  obrirDialogDurada: { type: Function, required: true },
  obrirEditarDuradaGrup: { type: Function, required: true },
  eliminarDuradaGrup: { type: Function, required: true },
  restriccionsProfessors: { type: Array, default: () => [] },
  restriccionsDiesHores: { type: Array, default: () => [] },
  restriccionsPreferencies: { type: Array, default: () => [] },
  restriccionsIncompatibilitats: { type: Array, default: () => [] },
  llistaProfessors: { type: Array, default: () => [] },
  professorsHorariEstricte: { type: Array, default: () => [] },
  pesos: { type: Object, required: true },
  pesosInfo: { type: Object, required: true },
  costosProfessors: { type: Object, required: true },
  costosInfo: { type: Object, required: true },
  costosProfessorsIndividuals: { type: Array, default: () => [] },
  toDomId: { type: Function, required: true },
  obrirDialogProfessor: { type: Function, required: true },
  eliminarRestriccio: { type: Function, required: true },
  obrirDialogDiaHora: { type: Function, required: true },
  obrirDialogPreferenciaDia: { type: Function, required: true },
  eliminarPreferencia: { type: Function, required: true },
  obrirDialogIncompatibilitat: { type: Function, required: true },
  obrirDialogCostProfessor: { type: Function, required: true },
  eliminarCostProfessor: { type: Function, required: true }
})

const prefixEtiquetes = useId()

const emit = defineEmits(['update:professorsHorariEstricte', 'update:peso', 'update:costGlobal', 'update:duradaTitular', 'update:duradaExamen'])
const { t } = useI18n()
const dayLabel = (day) => localizeBackendDayName(day, t)

const preferenciaLabel = (tipus) => {
  if (tipus === 'mateix_dia') return t('scheduler.steps.restrictions.dayPreferences.type.sameDay')
  if (tipus === 'mateix_slot') return t('scheduler.steps.restrictions.dayPreferences.type.sameSlot')
  return t('scheduler.steps.restrictions.dayPreferences.type.differentDays')
}

const formatRestrictedDays = (days) => {
  if (!Array.isArray(days) || !days.length) return t('common.noneDash')
  return days.map((day) => dayLabel(day)).join(', ')
}
</script>
