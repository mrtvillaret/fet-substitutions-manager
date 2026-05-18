<template>
  <div class="step-panel animate-fade-in">
    <div class="card shadow-sm">
      <h3>📅 {{ t('scheduler.steps.config.title') }}</h3>

      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.steps.config.levelsLabel') }}</label>
        <MultiSelect
          inputId="nivells-select"
          :modelValue="nivellsActius"
          @update:modelValue="emit('update:nivellsActius', $event)"
          :options="config?.nivells || []"
          :placeholder="t('scheduler.steps.config.levelsPlaceholder')"
          class="w-full"
          style="max-width: 400px"
        />
      </div>

      <TabView v-if="nivellsActius?.length" class="nivell-alliberaments-tabs app-tabview">
        <TabPanel v-for="nivell in nivellsActius" :key="nivell" :header="nivell">
          <div class="nivell-config-layout">
            <div class="calendari-section">
              <h4>📅 {{ t('scheduler.steps.config.examDaysTitle') }}</h4>
              <Calendar
                :modelValue="datesPerNivellModel[nivell]"
                @update:modelValue="onDatesChange(nivell, $event)"
                selectionMode="multiple"
                inline
                :showWeek="true"
              />
            </div>

            <div class="alliberaments-section">
              <div class="alliberaments-header">
                <h4>🟩 {{ t('scheduler.steps.config.freeAndStartTitle') }}</h4>
                <div class="llegenda">
                  <span class="llegenda-item"><span class="cb-demo cb-alliberat-demo"></span> {{ t('scheduler.steps.config.legend.free') }}</span>
                  <span class="llegenda-item"><span class="cb-demo cb-inici-demo"></span> {{ t('scheduler.steps.config.legend.start') }}</span>
                </div>
              </div>

              <div class="alliberaments-grid-container" v-if="getDatesPerNivellOrdenades(nivell).length">
                <table class="alliberaments-grid">
                  <thead>
                    <tr>
                      <th class="dia-header"></th>
                      <th
                        v-for="hora in llistaHoresDisponibles"
                        :key="`h-${nivell}-${hora}`"
                        class="hora-header"
                        @click="mostrarMenuColumna($event, nivell, hora)"
                      >
                        {{ hora }}
                        <i class="pi pi-chevron-down text-xs ml-1"></i>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="data in getDatesPerNivellOrdenades(nivell)" :key="`d-${nivell}-${data}`">
                      <td class="dia-label" @click="mostrarMenuFila($event, nivell, data)">
                        {{ formatDataCurta(data) }}
                        <i class="pi pi-chevron-right text-xs ml-1"></i>
                      </td>
                      <td
                        v-for="hora in llistaHoresDisponibles"
                        :key="`c-${nivell}-${data}-${hora}`"
                        class="alliberament-cell"
                      >
                        <div class="cell-checkboxes">
                          <input
                            type="checkbox"
                            :checked="isAlliberat(nivell, data, hora)"
                            @change="toggleAlliberat(nivell, data, hora)"
                            class="cb-alliberat"
                            :title="t('scheduler.steps.config.legend.free')"
                          />
                          <input
                            type="checkbox"
                            :checked="isIniciExamen(nivell, data, hora)"
                            @change="toggleIniciExamen(nivell, data, hora)"
                            class="cb-inici"
                            :disabled="!isAlliberat(nivell, data, hora)"
                            :title="t('scheduler.steps.config.legend.start')"
                          />
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="no-dates-message">
                <i class="pi pi-info-circle mr-2"></i>
                {{ t('scheduler.steps.config.noDatesMessage') }}
              </div>
            </div>
          </div>
        </TabPanel>
      </TabView>

      <div v-else class="no-nivells-message">
        <i class="pi pi-info-circle mr-2"></i>
        {{ t('scheduler.steps.config.noLevelsMessage') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import MultiSelect from 'primevue/multiselect'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Calendar from 'primevue/calendar'
defineProps({
  config: { type: Object, default: null },
  nivellsActius: { type: Array, default: () => [] },
  datesPerNivellModel: { type: Object, required: true },
  llistaHoresDisponibles: { type: Array, default: () => [] },
  onDatesChange: { type: Function, required: true },
  getDatesPerNivellOrdenades: { type: Function, required: true },
  formatDataCurta: { type: Function, required: true },
  isAlliberat: { type: Function, required: true },
  toggleAlliberat: { type: Function, required: true },
  isIniciExamen: { type: Function, required: true },
  toggleIniciExamen: { type: Function, required: true },
  mostrarMenuColumna: { type: Function, required: true },
  mostrarMenuFila: { type: Function, required: true }
})

const emit = defineEmits(['update:nivellsActius'])
const { t } = useI18n()
</script>
