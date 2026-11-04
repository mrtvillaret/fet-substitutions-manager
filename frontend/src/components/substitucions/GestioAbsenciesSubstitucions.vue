<template>
    <!-- Bottom Sheet per gestionar absències -->
    <Teleport to="body">
      <Transition name="bs-overlay">
        <div v-if="mostrarDialogGestio" class="bs-overlay" @click="emit('tancarDialogGestio', $event)"></div>
      </Transition>
      <div class="bs-sheet" :class="{ 'bs-sheet--visible': mostrarDialogGestio }" role="dialog" aria-modal="true">
        <div class="bs-drag-handle"></div>
        <div class="bs-header">
          <span class="p-dialog-title">{{ $t('substitutions.dialogs.absences.title') }}</span>
          <button ref="closeBtnRef" class="bs-close-btn" @click="emit('tancarDialogGestio', $event)" :aria-label="$t('common.close')">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="bs-content">
          <!-- Professor selector -->
          <div class="bs-field">
            <label :for="prefixEtiquetes + '-camp-1'" class="bs-label">{{ $t('substitutions.dialogs.absences.absentTeacherLabel') }}</label>
            <Dropdown :filterInputProps="{ 'aria-label': $t('common.filterOptions') }" :aria-label="$t('substitutions.dialogs.absences.absentTeacherLabel')" :inputId="prefixEtiquetes + '-camp-1'"
              v-model="dropdownProfValue"
              :options="professorsAmbInfo"
              optionLabel="nom"
              optionDisabled="coberta"
              :filter="true"
              :placeholder="$t('substitutions.dialogs.absences.selectTeacher')"
              @change="emit('seleccionarProfessorDropdown', $event)"

            >
              <template #value="{ value, placeholder }">
                {{ value ? value.nom : placeholder }}
              </template>
              <template #option="{ option }">
                <div class="bs-prof-option" :class="{ 'bs-prof-option--absencies': option.teAbsencies, 'bs-prof-option--coberta': option.coberta }">
                  <span>{{ option.nom }}<span v-if="option.coberta" class="bs-badge-coberta"> {{ option.finsA ? $t('substitutions.dialogs.absences.coveredUntil', { data: option.finsA }) : $t('substitutions.dialogs.absences.covered') }}</span></span>
                  <span v-if="option.teAbsencies" class="bs-badge-hores">{{ option.numHores }}h</span>
                </div>
              </template>
            </Dropdown>
          </div>

          <!-- Rang de dates -->
          <div class="bs-field bs-field--rang" v-if="gestioAbsencies.professor">
            <div class="bs-rang-toggle">
              <button type="button"
                :class="['bs-rang-opt', !modeRang && 'bs-rang-opt--active']"
                @click="modeRang = false; dataFinalRang = ''">
                {{ $t('substitutions.range.onlyToday') }}
              </button>
              <button type="button"
                :class="['bs-rang-opt', modeRang && 'bs-rang-opt--active']"
                @click="modeRang = true">
                {{ $t('substitutions.range.until') }}
              </button>
            </div>
            <div v-if="modeRang" class="bs-rang-dates">
              <span class="bs-rang-inici">{{ dataISOCurta }}</span>
              <span class="bs-rang-arrow">→</span>
              <input type="date" class="bs-input bs-rang-fi"
                :aria-label="$t('substitutions.range.until')" v-model="dataFinalRang" :min="dataISO" />
            </div>
            <div v-if="modeRang && datesDelRang.length > 1" class="bs-rang-resum">
              {{ $t('substitutions.range.summary', { count: datesDelRang.length }, datesDelRang.length) }}
            </div>
          </div>

          <!-- Hores d'absència Normal -->
          <div class="bs-field">
            <div class="bs-label-row">
              <label class="bs-label">{{ $t('substitutions.dialogs.absences.normalHoursLabel') }} <span class="bs-type-badge bs-type-badge--normal">{{ $t('substitutions.dialogs.absences.normalBadge') }}</span></label>
              <button type="button" class="bs-sel-all-btn" @click="emit('toggleTotesAbsencia', $event)">{{ totesTrnadesAbsencia ? $t('substitutions.dialogs.absences.selectNone') : $t('substitutions.dialogs.absences.selectAll') }}</button>
            </div>
            <div class="bs-hours-grid">
              <button
                v-for="hora in horesDisponibles"
                :key="`abs-${hora}`"
                type="button"
                class="bs-hour-btn"
                :class="{
                  'bs-hour-btn--selected': gestioAbsencies.horesAbsencia.includes(hora),
                  'bs-hour-btn--al-centre': horesCarregades && !horesAmbClasse.includes(hora) && horesAlCentre.includes(hora),
                  'bs-hour-btn--fora': horesCarregades && !horesAmbClasse.includes(hora) && !horesAlCentre.includes(hora)
                }"
                :disabled="gestioAbsencies.horesServei.includes(hora)"
                @click="emit('toggleHoraAbsencia', hora)"
              >{{ hora }}</button>
            </div>
          </div>

          <!-- Hores de Servei -->
          <div class="bs-field">
            <div class="bs-label-row">
              <label class="bs-label">{{ $t('substitutions.dialogs.absences.serviceHoursLabel') }} <span class="bs-type-badge bs-type-badge--servei">{{ $t('substitutions.dialogs.absences.serviceBadge') }}</span></label>
              <button type="button" class="bs-sel-all-btn bs-sel-all-btn--servei" @click="emit('toggleTotesServei', $event)">{{ totesTrnadesServei ? $t('substitutions.dialogs.absences.selectNone') : $t('substitutions.dialogs.absences.selectAll') }}</button>
            </div>
            <div class="bs-hours-grid">
              <button
                v-for="hora in horesDisponibles"
                :key="`serv-${hora}`"
                type="button"
                class="bs-hour-btn bs-hour-btn--servei-base"
                :class="{
                  'bs-hour-btn--servei-selected': gestioAbsencies.horesServei.includes(hora),
                  'bs-hour-btn--al-centre': horesCarregades && !horesAmbClasse.includes(hora) && horesAlCentre.includes(hora),
                  'bs-hour-btn--fora': horesCarregades && !horesAmbClasse.includes(hora) && !horesAlCentre.includes(hora)
                }"
                :disabled="gestioAbsencies.horesAbsencia.includes(hora)"
                @click="emit('toggleHoraServei', hora)"
              >{{ hora }}</button>
            </div>
          </div>

          <!-- Llista absències del dia -->
          <div v-if="absenciesDelDiaAgrupades.length > 0" class="bs-absencies-section">
            <p class="bs-section-title">{{ $t('substitutions.dialogs.absences.todayAbsences') }}</p>
            <div
              v-for="grup in absenciesDelDiaAgrupades"
              :key="grup.professor"
              class="bs-card bs-card--clickable"
              @click="emit('editarAbsenciesProfessor', { professor_absent: grup.professor })"
            >
              <span class="bs-card-prof">{{ grup.professor }}</span>
              <button class="bs-card-del" @click.stop="emit('confirmarEliminarAbsenciesProf', grup.professor)"
                :disabled="loading" :aria-label="$t('common.delete')"><i class="pi pi-trash" aria-hidden="true"></i></button>
            </div>
          </div>
        </div>

        <div class="bs-footer">
          <button
            type="button"
            class="bs-btn-primary"
            :disabled="!gestioAbsencies.professor || (gestioAbsencies.horesAbsencia.length === 0 && gestioAbsencies.horesServei.length === 0) || loading"
            @click="emit('afegirAbsenciaImmediata', $event)"
          >
            <span v-if="loading" class="bs-spinner"></span>
            <span v-else>{{ $t('substitutions.dialogs.absences.addAbsence') }}</span>
          </button>
        </div>
      </div>
    </Teleport>
</template>

<script setup>
import { useId } from 'vue'
import { ref, watch, nextTick } from 'vue'
import Dropdown from 'primevue/dropdown'

const prefixEtiquetes = useId()

const dropdownProfValue = defineModel('dropdownProfValue', { required: true })
const modeRang = defineModel('modeRang', { required: true })
const dataFinalRang = defineModel('dataFinalRang', { required: true })
const props = defineProps({
  mostrarDialogGestio: { type: Boolean, required: true },
  gestioAbsencies: { type: Object, required: true },
  professorsAmbInfo: { type: Array, required: true },
  dataISOCurta: { type: String, required: true },
  dataISO: { type: String, required: true },
  datesDelRang: { type: Array, required: true },
  horesDisponibles: { type: Array, required: true },
  horesCarregades: { type: Boolean, required: true },
  horesAmbClasse: { type: Array, required: true },
  horesAlCentre: { type: Array, required: true },
  totesTrnadesAbsencia: { type: Boolean, required: true },
  totesTrnadesServei: { type: Boolean, required: true },
  absenciesDelDiaAgrupades: { type: Array, required: true },
  loading: { type: Boolean, required: true }
})
const emit = defineEmits(['tancarDialogGestio', 'seleccionarProfessorDropdown', 'toggleTotesAbsencia', 'toggleHoraAbsencia', 'toggleTotesServei', 'toggleHoraServei', 'editarAbsenciesProfessor', 'confirmarEliminarAbsenciesProf', 'afegirAbsenciaImmediata'])

const closeBtnRef = ref(null)
watch(() => props.mostrarDialogGestio, (val) => {
  if (val) nextTick(() => closeBtnRef.value?.focus())
})
</script>

<style scoped>
/* Els desplegables de la vista (la taula, a TaulaSubstitucions i taules.css) */
:deep(.p-dropdown) {
  width: 100%;
  font-size: 0.925rem;
}

:deep(.p-dropdown .p-dropdown-label) {
  padding: 0.65rem 0.75rem;
  font-weight: 500;
}

:deep(.p-dropdown-panel .p-dropdown-items .p-dropdown-item) {
  padding: 0.65rem 1rem;
  font-size: 0.925rem;
}


/* ================================================================
   BOTTOM SHEET — Gestionar absències
   Mobile: slide up from bottom. Desktop: centered modal.
   ================================================================ */

.bs-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.48);
  z-index: 1050;
}

.bs-overlay-enter-active,
.bs-overlay-leave-active {
  transition: opacity 0.25s ease;
}
.bs-overlay-enter-from,
.bs-overlay-leave-to {
  opacity: 0;
}

.bs-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  border-radius: 12px 12px 0 0;
  z-index: 1051;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  transform: translateY(100%);
  transition: transform 0.32s cubic-bezier(0.32, 0.72, 0, 1);
  box-shadow: 0 -4px 32px rgba(0, 0, 0, 0.18);
  pointer-events: none;
  overflow: hidden;
  padding: 0;
}

.bs-sheet--visible {
  transform: translateY(0);
  pointer-events: auto;
}

/* Desktop: centered modal — mateix breakpoint que PrimeVue (720px) */
@media (min-width: 720px) {
  .bs-sheet {
    bottom: auto;
    left: 50%;
    right: auto;
    top: 50%;
    width: 480px;
    height: min(82vh, 640px);
    border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    transform: translate(-50%, -44%) scale(0.97);
    opacity: 0;
    transition: transform 0.22s ease, opacity 0.22s ease;
    pointer-events: none;
  }
  .bs-sheet--visible {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
    pointer-events: auto;
  }
}

.bs-drag-handle {
  display: none;
}

/* Header — mateix estil que p-dialog-header de PrimeVue (lara-light-blue) */
.bs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 0 none;
  background: #ffffff;
  color: #374151;
  flex-shrink: 0;
}

/* Títol — rèplica de p-dialog-title */
.bs-header .p-dialog-title {
  font-weight: 700;
  font-size: 1.25rem;
  color: #374151;
}

/* Botó tancar — rèplica de p-dialog-header-icon */
.bs-close-btn {
  width: 2rem;
  height: 2rem;
  color: #6b7280;
  border: 0 none;
  background: transparent;
  border-radius: 50%;
  transition: background-color 0.2s, color 0.2s, box-shadow 0.2s;
  outline-color: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  padding: 0;
  flex-shrink: 0;
}
.bs-close-btn:hover {
  color: #374151;
  background: #f3f4f6;
}
.bs-close-btn:focus,
.bs-close-btn:focus-visible {
  outline: 0 none;
  box-shadow: 0 0 0 0.2rem #BFDBFE;
}

/* Scrollable content */
.bs-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Field */
.bs-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.bs-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}
.bs-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.bs-sel-all-btn {
  font-size: 0.75rem;
  font-weight: 500;
  color: #0369a1;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.bs-sel-all-btn--servei { color: #7c3aed; }
.bs-sel-all-btn:hover { opacity: 0.7; }

/* date input per al rang */
.bs-input {
  width: 100%;
  height: 48px;
  padding: 0 1rem;
  border: 1.5px solid #d1d5db;
  border-radius: 10px;
  font-size: 1rem;
  color: #1f2937;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}
.bs-input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.12);
}

/* Opció professor al Dropdown */
.bs-prof-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 0.5rem;
}
.bs-prof-option--absencies {
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  margin-left: -0.75rem;
  padding-left: calc(0.75rem - 3px);
  margin-right: -0.75rem;
  padding-right: 0.75rem;
}

.bs-prof-option--coberta {
  opacity: 0.6;
}

.bs-badge-coberta {
  font-size: 0.78rem;
  font-weight: 600;
  color: #6b7280;
}

.bs-badge-hores {
  font-size: 0.78rem;
  font-weight: 600;
  color: #92400e;
  background: #fef3c7;
  padding: 0.15rem 0.5rem;
  border-radius: 99px;
  flex-shrink: 0;
}


/* Badges de tipus al label */
.bs-type-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.5rem;
  border-radius: 99px;
  vertical-align: middle;
  margin-left: 0.3rem;
}
.bs-type-badge--normal {
  background: #e0e3f8;
  color: var(--primary-color-dark);
}
.bs-type-badge--servei {
  background: #ede9fe;
  color: #6d28d9;
}

/* Hours grid */
.bs-hours-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.bs-hour-btn {
  min-height: 36px;
  min-width: 68px;
  padding: 0 0.9rem;
  border: 1.5px solid #d1d5db;
  border-radius: 8px;
  background: #f9fafb;
  color: #374151;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.12s;
  white-space: nowrap;
}
.bs-hour-btn:disabled {
  opacity: 0.28;
  cursor: not-allowed;
}
.bs-hour-btn:not(:disabled):hover {
  border-color: var(--primary-color);
  background: #eef0fd;
  color: var(--primary-color-dark);
}

/* Botons Servei */
.bs-hour-btn--servei-base {
  border-color: #ddd6fe;
  background: #faf5ff;
  color: #4c1d95;
}
.bs-hour-btn--servei-base:not(:disabled):hover {
  border-color: #7c3aed;
  background: #ede9fe;
  color: #5b21b6;
}

/* Colors d'horari (al centre / fora) — després de servei-base per sobreescriure'l */
.bs-hour-btn--al-centre {
  background: #ffffff;
  border-color: #fed7aa;
  color: #c2410c;
}
.bs-hour-btn--al-centre:not(:disabled):hover {
  border-color: var(--primary-color);
  background: #eef0fd;
  color: var(--primary-color-dark);
}
.bs-hour-btn--fora {
  background: #f3f4f6;
  border-color: #e5e7eb;
  color: #9ca3af;
}
.bs-hour-btn--fora:not(:disabled):hover {
  border-color: var(--primary-color);
  background: #eef0fd;
  color: var(--primary-color-dark);
}

/* Seleccionats — han d'anar AL FINAL per guanyar sempre */
.bs-hour-btn--selected {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
  font-weight: 600;
}
.bs-hour-btn--selected:not(:disabled):hover {
  background: var(--primary-color-dark);
  border-color: var(--primary-color-dark);
}
.bs-hour-btn--servei-selected {
  background: #7c3aed;
  border-color: #7c3aed;
  color: white;
  font-weight: 600;
}
.bs-hour-btn--servei-selected:not(:disabled):hover {
  background: #6d28d9;
  border-color: #6d28d9;
}

/* Segmented toggle */
.bs-toggle-segment {
  display: inline-flex;
  background: #f3f4f6;
  border-radius: 10px;
  padding: 3px;
  gap: 3px;
}
.bs-toggle-opt {
  min-height: 40px;
  padding: 0 1.5rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #6b7280;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.bs-toggle-opt--active {
  background: white;
  color: #1f2937;
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
}

/* Absències del dia */
.bs-absencies-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.bs-section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin: 0;
}
.bs-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 0.65rem 0.9rem;
  gap: 0.75rem;
}
.bs-card--clickable {
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s;
}
.bs-card--clickable:hover { background: #f0f9ff; border-color: #bae6fd; }
.bs-card-info {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}
.bs-card-prof {
  font-weight: 600;
  font-size: 0.875rem;
  color: #1f2937;
}
.bs-card-hora {
  font-size: 0.8rem;
  color: #6b7280;
  background: #e5e7eb;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  white-space: nowrap;
}
.bs-card-tipus {
  font-size: 0.78rem;
  font-weight: 500;
  background: #e0f2fe;
  color: #0369a1;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
}
.bs-card-tipus--servei {
  background: #f3e8ff;
  color: #7c3aed;
}
.bs-card-del {
  width: 34px;
  height: 34px;
  border: 1px solid #fee2e2;
  background: #fff5f5;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  color: var(--color-perill);
  transition: all 0.12s;
  flex-shrink: 0;
}
.bs-card-del:hover { background: #fee2e2; border-color: #fca5a5; }
.bs-card-del:disabled { opacity: 0.45; cursor: not-allowed; }
.bs-card-hores-detall {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin-top: 0.1rem;
}
.bs-card-hores-normal {
  font-size: 0.8rem;
  color: #0369a1;
  background: #e0f2fe;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  white-space: nowrap;
}
.bs-card-hores-servei {
  font-size: 0.8rem;
  color: #7c3aed;
  background: #f3e8ff;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  white-space: nowrap;
}
.bs-card-actions {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}
.bs-card-edit {
  width: 34px;
  height: 34px;
  border: 1px solid #e0f2fe;
  background: #f0f9ff;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  transition: all 0.12s;
  flex-shrink: 0;
}
.bs-card-edit:hover { background: #bae6fd; border-color: #7dd3fc; }
.bs-card-edit:disabled { opacity: 0.45; cursor: not-allowed; }

/* Footer sticky */
.bs-footer {
  padding: 0.75rem 1rem;
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
  border-top: 1px solid #f1f5f9;
  flex-shrink: 0;
  background: white;
  border-radius: 0;
}
@media (min-width: 640px) {
  .bs-footer { border-radius: 0 0 16px 16px; }
}

.bs-btn-primary {
  width: 100%;
  height: 52px;
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}
.bs-btn-primary:hover:not(:disabled) { background: #15803d; }
.bs-btn-primary:disabled {
  background: #d1d5db;
  color: #9ca3af;
  cursor: not-allowed;
}

/* Spinner al botó */
.bs-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: white;
  border-radius: 50%;
  animation: bs-spin 0.6s linear infinite;
}
@keyframes bs-spin {
  to { transform: rotate(360deg); }
}

/* Rang de dates */
.bs-field--rang { gap: 0.5rem; }
.bs-rang-toggle {
  display: flex;
  gap: 3px;
  background: #f3f4f6;
  border-radius: 8px;
  padding: 3px;
}
.bs-rang-opt {
  flex: 1; padding: 0.4rem 0.75rem;
  border: none; border-radius: 6px;
  font-size: 0.875rem; cursor: pointer;
  background: transparent; color: #6b7280;
  transition: all 0.15s;
}
.bs-rang-opt--active {
  background: white; color: var(--primary-color);
  font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.bs-rang-dates {
  display: flex; align-items: center;
  gap: 0.5rem; margin-top: 0.25rem;
}
.bs-rang-inici { font-size: 0.875rem; color: #6b7280; font-weight: 500; }
.bs-rang-arrow { color: #9ca3af; }
.bs-rang-fi { flex: 1; height: 36px; font-size: 0.875rem; }
.bs-rang-resum {
  font-size: 0.8rem; color: var(--primary-color);
  font-weight: 600; text-align: center;
}
</style>
