<template>
  <div class="step-panel animate-fade-in">
    <div class="card bg-primary-light mb-4" v-if="!generating">
      <div class="scheduler-setup">
        <div class="motor-toolbar">
          <div class="motor-main-field">
            <div class="field-info">
              <label class="font-bold">{{ t('scheduler.steps.results.motorLabel') }}</label>
              <small class="field-help">{{ t('scheduler.steps.results.motorHelp') }}</small>
            </div>
            <div class="field-control">
              <Dropdown
                inputId="motor"
                :modelValue="genConfig?.motor"
                @update:modelValue="setGenConfigField('motor', $event)"
                :options="motors"
                optionLabel="label"
                optionValue="value"
                optionDisabled="disabled"
                class="scheduler-dropdown"
              />
            </div>
          </div>

          <template v-for="p in mainParams" :key="p.key">
            <div class="motor-main-field">
              <div class="field-info">
                <label :for="`mp-${p.key}`" class="font-bold">{{ p.label }}</label>
                <small class="field-help">{{ p.help }}</small>
              </div>
              <div class="field-control">
                <Dropdown
                  v-if="p.type === 'select'"
                  :inputId="`mp-${p.key}`"
                  :modelValue="genConfig?.[p.key]"
                  @update:modelValue="setGenConfigField(p.key, $event)"
                  :options="p.options"
                  optionLabel="label"
                  optionValue="value"
                  class="scheduler-dropdown"
                />
                <InputNumber
                  v-else
                  :inputId="`mp-${p.key}`"
                  :modelValue="genConfig?.[p.key]"
                  @update:modelValue="setGenConfigField(p.key, $event)"
                  showButtons
                  buttonLayout="horizontal"
                  incrementButtonIcon="pi pi-plus"
                  decrementButtonIcon="pi pi-minus"
                  :min="p.min"
                  :max="p.max"
                  :step="p.step"
                  class="scheduler-inputnumber"
                />
              </div>
            </div>
          </template>
        </div>

        <div class="motor-controls-row" :class="{ single: !(mostrarParametresAvancats && advancedParams.length) }">
          <div v-if="mostrarParametresAvancats && advancedParams.length" class="motor-advanced-column">
            <div class="motor-advanced-fields">
              <div v-for="p in advancedParams" :key="p.key" class="motor-adv-card">
                <label :for="`ap-${p.key}`" class="font-bold">{{ p.label }}</label>
                <small class="field-help">{{ p.help }}</small>
                <Dropdown
                  v-if="p.type === 'select'"
                  :inputId="`ap-${p.key}`"
                  :modelValue="genConfig?.[p.key]"
                  @update:modelValue="setGenConfigField(p.key, $event)"
                  :options="p.options"
                  optionLabel="label"
                  optionValue="value"
                  class="scheduler-dropdown"
                />
                <InputNumber
                  v-else
                  :inputId="`ap-${p.key}`"
                  :modelValue="genConfig?.[p.key]"
                  @update:modelValue="setGenConfigField(p.key, $event)"
                  buttonLayout="horizontal"
                  incrementButtonIcon="pi pi-plus"
                  decrementButtonIcon="pi pi-minus"
                  :min="p.min"
                  :max="p.max"
                  :step="p.step"
                  class="scheduler-inputnumber"
                />
              </div>
            </div>
          </div>
          <div class="motor-run-column">
            <div v-if="advancedParams.length" class="motor-advanced-toggle">
              <Checkbox
                :modelValue="mostrarParametresAvancats"
                @update:modelValue="emit('update:mostrarParametresAvancats', $event)"
                inputId="adv"
                :binary="true"
              />
              <label class="ml-2">{{ t('scheduler.steps.results.advancedParamsToggle') }}</label>
            </div>
            <div class="motor-actions">
              <Button :label="t('scheduler.steps.results.actions.generateSchedule')" icon="pi pi-bolt" class="p-button-lg motor-generate-button" :loading="generating" @click="emit('generar')" />
              <small class="motor-run-help">{{ t('scheduler.steps.results.runHelp') }}</small>
            </div>
            <div v-if="pinnedNoms?.size > 0" class="pin-toolbar">
              <span
                class="pin-badge"
                v-tooltip.top="{ value: pinnedNomsList, escape: false }"
              >
                <i class="pi pi-lock"></i>
                {{ t('scheduler.editable.pinCount', { count: pinnedNoms.size }) }}
              </span>
              <Button
                @click="onClearPins?.()"
                :label="t('scheduler.editable.unpinAll')"
                icon="pi pi-lock-open"
                severity="warning"
                size="small"
                outlined
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="generating" class="card text-center p-8"><ProgressSpinner /><h2 class="mt-4">{{ t('scheduler.steps.results.generatingTitle') }}</h2></div>

    <div v-if="result" class="result-view animate-slide-up horari-print-area">
      <div class="result-toolbar mb-3">
        <Button
          :label="modeEdicio ? t('scheduler.steps.results.actions.viewMode') : t('scheduler.steps.results.actions.editMode')"
          :icon="modeEdicio ? 'pi pi-eye' : 'pi pi-pencil'"
          :severity="modeEdicio ? 'secondary' : 'info'"
          outlined
          @click="emit('update:modeEdicio', !modeEdicio)"
        />
      </div>

      <div class="result-overview mb-4">
        <div class="card result-kpis-card">
          <h3>📈 {{ t('scheduler.steps.results.statsTitle') }}</h3>
          <div class="kpi-grid">
            <div class="kpi-item kpi-main">
              <span class="kpi-label">{{ t('scheduler.steps.results.kpis.totalCost') }}</span>
              <span class="kpi-value">{{ result.horari.metadata.cost_total }}</span>
            </div>
            <div class="kpi-item">
              <span v-tooltip.top="recompteTooltip">
                {{ t('scheduler.steps.results.kpis.placedExams') }}
                <i v-if="recompteTooltip" class="pi pi-info-circle ml-2 text-xs"></i>
              </span>
              <span class="kpi-value">{{ recompteTotalsText }}</span>
            </div>
            <div class="kpi-item">
              <span class="kpi-label">{{ t('scheduler.steps.results.kpis.substitutions') }}</span>
              <span class="kpi-value">{{ result.horari.metadata.total_substitucions }}</span>
            </div>
            <div class="kpi-item">
              <span class="kpi-label">{{ t('scheduler.steps.results.kpis.before') }}</span>
              <span class="kpi-value">{{ result.horari.metadata.professors_abans }}</span>
            </div>
            <div class="kpi-item">
              <span class="kpi-label">{{ t('scheduler.steps.results.kpis.after') }}</span>
              <span class="kpi-value">{{ result.horari.metadata.professors_despres || 0 }}</span>
            </div>
            <div v-if="result.horari.metadata.temps_generacio_ms != null" class="kpi-item kpi-time">
              <span class="kpi-label">{{ t('scheduler.steps.results.kpis.generationTime') }}</span>
              <span class="kpi-value kpi-value-small">{{ result.horari.metadata.temps_generacio_ms >= 1000 ? (result.horari.metadata.temps_generacio_ms / 1000).toFixed(1) + 's' : result.horari.metadata.temps_generacio_ms + 'ms' }}</span>
            </div>
          </div>
        </div>

        <div class="card bg-slate-50 incidencies-card result-incidencies screen-only">
          <h3>⚠️ {{ t('scheduler.steps.results.incidentsTitle', { count: incidenciesCount }) }}</h3>
          <div class="incidencies-scroll">
            <div class="incident-content">
              <template v-for="(grup, gIdx) in incidenciesAgrupades" :key="gIdx">
                <div class="incident-group">
                  <div class="incident-header" :class="`severity-${grup.severity}`">{{ grup.titol }} ({{ grup.items.length }})</div>
                  <div class="incident-item" v-for="(inc, idx) in grup.items" :key="`${gIdx}-${idx}`">
                    <span class="incident-text" :class="{ 'incident-with-cost': hasIncidentCost(inc) }" :title="formatIncidentFull(grup, inc)">{{ formatIncidentShort(grup, inc) }}</span>
                  </div>
                </div>
              </template>
              <div v-if="!logsIncidencies.length" class="incident-empty">{{ t('scheduler.steps.results.noIncidents') }}</div>
            </div>
          </div>
        </div>
      </div>

      <HorariEditable
        v-if="modeEdicio"
        :horari-inicial="result.horari"
        :data-referencia="dataReferenciaScheduler"
        :selected-dates="selectedDates.map(formatLocalDate)"
        :pinned-noms="pinnedNoms"
        @actualitzat="onHorariActualitzat"
        @cost-changed="onCostChanged"
        @pin-changed="onPinChanged?.()"
      />

      <template v-else>
        <div v-for="setmana in horarisPerSetmana" :key="setmana.id" class="horari-taula-container card shadow-sm mb-3 print-week">
          <div class="setmana-header" v-if="horarisPerSetmana.length > 1">{{ t('scheduler.steps.results.weekLabel', { num: setmana.numSetmana }) }}</div>
          <table class="horari-taula">
            <thead>
              <tr>
                <th class="hora-col"></th>
                <th v-for="dia in setmana.dies" :key="dia.dia" class="dia-col-header" :class="{ 'dia-buit': !dia.estaSeleccionat }">
                  <div class="dia-nom">{{ dia.diaLabel || dia.dia }}</div>
                  <div class="dia-data" v-if="dia.data">{{ dia.data }}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="hora in horesExamenConfig" :key="hora">
                <td class="hora-cell">{{ hora }}</td>
                <td v-for="dia in setmana.dies" :key="`${dia.dia}-${hora}`" class="slot-cell" :class="{ 'slot-buit': !dia.estaSeleccionat }">
                  <template v-if="dia.estaSeleccionat && getSlotPerHora(dia, hora)">
                    <div v-for="nivellInfo in getSessionsPerNivell(getSlotPerHora(dia, hora))" :key="nivellInfo.nivell" class="nivell-card" :class="getNivellClass(nivellInfo, dia.dia, hora)">
                      <div class="nivell-header">{{ nivellInfo.nivell }}</div>
                      <div class="nivell-examens">
                        <div v-for="ex in getExamsUnics(nivellInfo.examens)" :key="`${ex.assignatura}-${ex.titular}`" class="examen-item">
                          <span v-if="isSessioFixada(ex.sessioNom)" class="ex-pin" :title="t('scheduler.editable.pin')">📌</span>
                          <span class="ex-nom">{{ ex.sessioNom || ex.assignatura }}</span>
                          <span class="ex-prof">{{ ex.titular }}</span>
                          <span v-if="getAvisosIconsExamen(ex, dia.dia, hora).length" class="ex-icons" :title="getAvisosTitleExamen(ex, dia.dia, hora)">
                            <span v-for="(icon, idx) in getAvisosIconsExamen(ex, dia.dia, hora)" :key="idx">{{ icon }}</span>
                          </span>
                        </div>
                      </div>
                    </div>
                  </template>
                  <div v-else-if="dia.estaSeleccionat" class="slot-lliure">{{ t('common.noneDash') }}</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <div class="card bg-slate-50 incidencies-card print-only print-incidencies">
        <h3>⚠️ {{ t('scheduler.steps.results.incidentsTitle', { count: incidenciesCount }) }}</h3>
        <div class="incidencies-scroll">
          <div class="incident-content">
            <template v-for="(grup, gIdx) in incidenciesAgrupades" :key="`print-${gIdx}`">
              <div class="incident-group">
                <div class="incident-header" :class="`severity-${grup.severity}`">{{ grup.titol }} ({{ grup.items.length }})</div>
                <div class="incident-item" v-for="(inc, idx) in grup.items" :key="`print-${gIdx}-${idx}`">
                  <span class="incident-text" :class="{ 'incident-with-cost': hasIncidentCost(inc) }" :title="formatIncidentFull(grup, inc)">{{ formatIncidentShort(grup, inc) }}</span>
                </div>
              </div>
            </template>
            <div v-if="!logsIncidencies.length" class="incident-empty">{{ t('scheduler.steps.results.noIncidents') }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { extractIncidentScore } from '../textUtils'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import ProgressSpinner from 'primevue/progressspinner'
import HorariEditable from '../../../components/HorariEditable.vue'

const props = defineProps({
  generating: { type: Boolean, default: false },
  result: { type: Object, default: null },
  modeEdicio: { type: Boolean, default: false },
  mostrarParametresAvancats: { type: Boolean, default: false },
  genConfig: { type: Object, required: true },
  motors: { type: Array, default: () => [] },
  mainParams: { type: Array, default: () => [] },
  advancedParams: { type: Array, default: () => [] },
  recompteTooltip: { type: String, default: '' },
  recompteTotalsText: { type: String, default: '—' },
  incidenciesCount: { type: Number, default: 0 },
  incidenciesAgrupades: { type: Array, default: () => [] },
  logsIncidencies: { type: Array, default: () => [] },
  horesExamenConfig: { type: Array, default: () => [] },
  horarisPerSetmana: { type: Array, default: () => [] },
  dataReferenciaScheduler: { type: String, default: '' },
  selectedDates: { type: Array, default: () => [] },
  formatLocalDate: { type: Function, required: true },
  getSlotPerHora: { type: Function, required: true },
  getSessionsPerNivell: { type: Function, required: true },
  getNivellClass: { type: Function, required: true },
  getExamsUnics: { type: Function, required: true },
  getAvisosIconsExamen: { type: Function, required: true },
  getAvisosTitleExamen: { type: Function, required: true },
  formatIncidentFull: { type: Function, required: true },
  formatIncidentShort: { type: Function, required: true },
  onHorariActualitzat: { type: Function, required: true },
  onCostChanged: { type: Function, required: true },
  pinnedNoms: { type: Set, default: () => new Set() },
  onPinChanged: { type: Function, default: null },
  onClearPins: { type: Function, default: null }
})

const emit = defineEmits(['generar', 'update:modeEdicio', 'update:mostrarParametresAvancats', 'update:genConfigField'])
const { t } = useI18n()

const setGenConfigField = (key, value) => {
  emit('update:genConfigField', { key, value })
}

const pinnedNomsList = computed(() => {
  if (!props.pinnedNoms?.size) return ''
  return Array.from(props.pinnedNoms).join('<br>')
})

const isSessioFixada = (sessioNom) => props.pinnedNoms?.has(sessioNom)

const hasIncidentCost = (inc) => {
  const val = extractIncidentScore(inc).match(/(\d+)/)?.[1]
  return val !== undefined && Number(val) > 0
}
</script>
