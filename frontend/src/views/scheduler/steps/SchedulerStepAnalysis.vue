<template>
  <div class="step-panel animate-fade-in analysis-print-area">
    <div class="card analysis-header">
      <div>
        <h3 class="analysis-title">📊 {{ t('scheduler.steps.analysis.title') }}</h3>
        <p class="analysis-desc">{{ t('scheduler.steps.analysis.subtitle') }}</p>
      </div>
      <div class="analysis-actions">
        <Button :label="t('scheduler.steps.analysis.actions.analyze')" icon="pi pi-search" class="p-button-lg" :loading="analisiLoading" @click="$emit('analitzar')" />
        <Button v-if="analisiResult" :label="t('scheduler.steps.analysis.actions.printPdf')" icon="pi pi-print" class="p-button-text" @click="$emit('imprimir')" />
      </div>
    </div>

    <Message v-if="avisos.length" severity="warn" :closable="false">
      <div v-for="(avis, idx) in avisos" :key="idx">{{ avis }}</div>
    </Message>

    <div v-if="analisiResult" class="card analysis-card">
      <div class="analysis-tab-hint">
        <span class="analysis-tab-title">{{ analysisTabInfo.title }}</span>
        <span class="analysis-tab-desc">{{ analysisTabInfo.desc }}</span>
      </div>
      <TabView :activeIndex="analysisActiveIndex" class="analysis-tabs app-tabview" @update:activeIndex="$emit('update:analysisActiveIndex', $event)">
        <TabPanel :header="t('scheduler.steps.analysis.tabs.byHourDay')">
          <div class="analysis-panel" :class="{ active: analysisActiveIndex === 0 }">
            <div v-if="perSlotsParsed.length" class="analysis-modern">
              <div v-for="dia in perSlotsParsed" :key="dia.dia" class="analysis-day">
                <h4 class="analysis-day-title">📅 {{ etiquetaDiaInforme(dia.dia, t).toUpperCase() }}</h4>
                <div v-for="slot in dia.slots" :key="`${dia.dia}-${slot.hora}`" class="analysis-slot">
                  <div class="analysis-slot-header">⏰ {{ slot.hora }}</div>
                  <div v-for="nivell in slot.nivells" :key="nivell.nivell" class="analysis-level">
                    <div class="analysis-level-title">{{ nivell.nivell }}</div>
                    <table class="analysis-level-table">
                      <thead>
                        <tr>
                          <th>{{ t('scheduler.steps.analysis.columns.category') }}</th>
                          <th>{{ t('scheduler.steps.analysis.columns.groupings') }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-if="nivell.optimes.length" class="analysis-row-lines">
                          <td><span class="analysis-pill ok">{{ t('scheduler.steps.analysis.pills.optimal') }}</span></td>
                          <td class="analysis-items">
                            <div v-for="(item, idx) in nivell.optimes" :key="`${item.label}-${idx}`" class="analysis-item-line">
                              <div class="analysis-item-label">{{ item.label }}</div>
                              <div v-if="item.details.length" class="analysis-item-details">
                                <div v-for="(det, dIdx) in item.details" :key="`${item.label}-${dIdx}`" class="analysis-item-detail">{{ textDetall(det, t, ' | ') }}</div>
                              </div>
                            </div>
                          </td>
                        </tr>
                        <tr v-if="nivell.bones.length" class="analysis-row-lines">
                          <td><span class="analysis-pill warn">{{ t('scheduler.steps.analysis.pills.good') }}</span></td>
                          <td class="analysis-items">
                            <div v-for="(item, idx) in nivell.bones" :key="`${item.label}-${idx}`" class="analysis-item-line">
                              <div class="analysis-item-label">{{ item.label }}</div>
                              <div v-if="item.details.length" class="analysis-item-details">
                                <div v-for="(det, dIdx) in item.details" :key="`${item.label}-${dIdx}`" class="analysis-item-detail">{{ textDetall(det, t, ' | ') }}</div>
                              </div>
                            </div>
                          </td>
                        </tr>
                        <tr v-if="nivell.acceptables.length" class="analysis-row-lines">
                          <td><span class="analysis-pill alert">{{ t('scheduler.steps.analysis.pills.acceptable') }}</span></td>
                          <td class="analysis-items">
                            <div v-for="(item, idx) in nivell.acceptables" :key="`${item.label}-${idx}`" class="analysis-item-line">
                              <div class="analysis-item-label">{{ item.label }}</div>
                              <div v-if="item.details.length" class="analysis-item-details">
                                <div v-for="(det, dIdx) in item.details" :key="`${item.label}-${dIdx}`" class="analysis-item-detail">{{ textDetall(det, t, ' | ') }}</div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </TabPanel>
        <TabPanel :header="t('scheduler.steps.analysis.tabs.byGrouping')">
          <div class="analysis-panel" :class="{ active: analysisActiveIndex === 1 }">
            <div v-if="perSessioParsed.length" class="analysis-modern">
              <div v-for="sessio in perSessioParsed" :key="sessio.titol" class="analysis-session">
                <div class="analysis-session-header">
                  <h4 class="analysis-session-title">📝 {{ sessio.titol }}</h4>
                  <p class="analysis-session-sub">👥 {{ t('scheduler.steps.analysis.teachersPrefix') }} {{ sessio.professors.join(', ') || t('common.noneDash') }}</p>
                </div>
                <table class="analysis-table">
                  <thead>
                    <tr>
                      <th></th>
                      <th>{{ t('scheduler.steps.analysis.columns.day') }}</th>
                      <th>{{ t('scheduler.steps.analysis.columns.hour') }}</th>
                      <th>{{ t('scheduler.steps.analysis.columns.subs') }}</th>
                      <th>{{ t('scheduler.steps.analysis.columns.before') }}</th>
                      <th>{{ t('scheduler.steps.analysis.columns.after') }}</th>
                      <th>{{ t('scheduler.steps.analysis.columns.noWork') }}</th>
                      <th>{{ t('scheduler.steps.analysis.columns.details') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(fila, idx) in sessio.files" :key="idx" :class="analysisFilaClass(fila, idx, sessio.files)">
                      <td class="emoji">{{ fila.emoji }}</td>
                      <td>{{ etiquetaDiaInforme(fila.dia, t) }}</td>
                      <td>{{ fila.hora }}</td>
                      <td>{{ fila.subs }}</td>
                      <td>{{ fila.abans }}</td>
                      <td>{{ fila.despres }}</td>
                      <td>{{ fila.no_treballa }}</td>
                      <td class="details">{{ textDetalls(fila.detalls, t) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </TabPanel>
        <TabPanel :header="t('scheduler.steps.analysis.tabs.teachersPerSlot')">
          <div class="analysis-panel" :class="{ active: analysisActiveIndex === 2 }">
            <div v-if="professorsSlotParsed.length" class="analysis-modern">
              <div v-for="dia in professorsSlotParsed" :key="dia.dia" class="analysis-day">
                <h4 class="analysis-day-title">📅 {{ etiquetaDiaInforme(dia.dia, t) }}</h4>
                <div v-for="horaBloc in dia.hores" :key="`${dia.dia}-${horaBloc.hora}`" class="analysis-slot">
                  <div class="analysis-slot-header">⏰ {{ horaBloc.hora }}</div>
                  <div class="analysis-hour">
                    <table class="analysis-prof-table">
                      <thead>
                        <tr>
                          <th>{{ t('scheduler.steps.analysis.columns.availableCount', { count: horaBloc.disponibles.length }) }}</th>
                          <th>{{ t('scheduler.steps.analysis.columns.releasedCount', { count: horaBloc.alliberats.length }) }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>
                            <ul v-if="horaBloc.disponibles.length" class="analysis-list">
                              <li v-for="p in horaBloc.disponibles" :key="textProfessor(p)">{{ textProfessor(p) }}</li>
                            </ul>
                            <div v-else class="analysis-muted">{{ t('scheduler.steps.analysis.noneShort') }}</div>
                          </td>
                          <td>
                            <ul v-if="horaBloc.alliberats.length" class="analysis-list">
                              <li v-for="p in horaBloc.alliberats" :key="textProfessor(p)">{{ textProfessor(p) }}</li>
                            </ul>
                            <div v-else class="analysis-muted">{{ t('scheduler.steps.analysis.noneShort') }}</div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    <div v-if="!horaBloc.disponibles.length && !horaBloc.alliberats.length" class="analysis-muted">
                      {{ t('scheduler.steps.analysis.noneReason') }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </TabPanel>
      </TabView>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { avisosDeGrupsSenseNivell } from '../missatges.js'
import { etiquetaDiaInforme, textDetall, textDetalls, textProfessor } from '../informesAnalisi.js'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'

const props = defineProps({
  analisiLoading: { type: Boolean, default: false },
  analisiResult: { type: Object, default: null },
  analysisActiveIndex: { type: Number, default: 0 },
  analysisTabInfo: { type: Object, default: () => ({ title: '', desc: '' }) },
  perSlotsParsed: { type: Array, default: () => [] },
  perSessioParsed: { type: Array, default: () => [] },
  professorsSlotParsed: { type: Array, default: () => [] },
  analysisFilaClass: { type: Function, required: true },
})

defineEmits(['analitzar', 'imprimir', 'update:analysisActiveIndex'])
const { t } = useI18n()
// Grups de les assignacions que no són a cap nivell: no es planifiquen
const avisos = computed(() => avisosDeGrupsSenseNivell(props.analisiResult?.avisos, t))
</script>
