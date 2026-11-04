<template>
  <!-- DIALOG DURADES PER GRUP -->
  <Dialog
    :visible="mostrarDialogDurada"
    @update:visible="emit('update:mostrarDialogDurada', $event)"
    :header="editantDuradaId ? t('scheduler.steps.restrictions.durades.dialog.titleEdit') : t('scheduler.steps.restrictions.durades.dialog.titleAdd')"
    :modal="true"
    :style="{ width: '480px' }"
  >
    <div class="p-fluid">
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-1'" class="font-bold">{{ t('scheduler.steps.restrictions.durades.dialog.nameLabel') }}</label>
        <InputText :id="prefixEtiquetes + '-camp-1'"
          :modelValue="formularisLocals.formulariDurada.nom" @update:modelValue="actualitzaCamp('formulariDurada', 'nom', $event)"
          :placeholder="t('scheduler.steps.restrictions.durades.dialog.namePlaceholder')"
        />
      </div>
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-2'" class="font-bold">{{ t('scheduler.steps.restrictions.durades.dialog.sessionsLabel') }}</label>
        <MultiSelect :filterInputProps="{ 'aria-label': t('common.filterOptions') }" :aria-label="t('scheduler.steps.restrictions.durades.dialog.sessionsLabel')" :inputId="prefixEtiquetes + '-camp-2'"
          :modelValue="formularisLocals.formulariDurada.sessions" @update:modelValue="actualitzaCamp('formulariDurada', 'sessions', $event)"
          :options="llistaSessions"
          filter
          :placeholder="t('scheduler.steps.restrictions.durades.dialog.sessionsPlaceholder')"
          class="scheduler-multiselect"
        />
      </div>
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-3'" class="font-bold">{{ t('scheduler.steps.restrictions.durades.dialog.durationLabel') }}</label>
        <div class="flex align-items-center gap-2">
          <InputNumber :inputId="prefixEtiquetes + '-camp-3'"
            :modelValue="formularisLocals.formulariDurada.durada" @update:modelValue="actualitzaCamp('formulariDurada', 'durada', $event)"
            showButtons
            buttonLayout="horizontal"
            incrementButtonIcon="pi pi-plus"
            decrementButtonIcon="pi pi-minus"
            :min="1"
            :max="8"
            class="scheduler-inputnumber"
          />
          <span class="text-sm text-color-secondary">{{ t('scheduler.steps.restrictions.durades.dialog.durationSuffix') }}</span>
        </div>
      </div>
      <div class="field mb-2">
        <label :for="prefixEtiquetes + '-camp-4'" class="font-bold">{{ t('scheduler.steps.restrictions.durades.dialog.examDurationLabel') }}</label>
        <div class="flex align-items-center gap-2">
          <InputNumber :inputId="prefixEtiquetes + '-camp-4'"
            :modelValue="formularisLocals.formulariDurada.durada_examen" @update:modelValue="actualitzaCamp('formulariDurada', 'durada_examen', $event)"
            showButtons
            buttonLayout="horizontal"
            incrementButtonIcon="pi pi-plus"
            decrementButtonIcon="pi pi-minus"
            :min="1"
            :max="8"
            class="scheduler-inputnumber"
          />
          <span class="text-sm text-color-secondary">{{ t('scheduler.steps.restrictions.durades.dialog.examDurationSuffix') }}</span>
        </div>
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" text @click="emit('update:mostrarDialogDurada', false)" />
      <Button :label="t('common.save')" @click="desarDialogDurada" />
    </template>
  </Dialog>

  <Dialog
    :visible="mostrarDialogProfessor"
    @update:visible="emit('update:mostrarDialogProfessor', $event)"
    :header="professorEditantId ? t('scheduler.dialogs.restriction.editTitle') : t('scheduler.dialogs.restriction.newTitle')"
    :modal="true"
    :style="{ width: '560px' }"
  >
    <div class="p-fluid">
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-5'" class="font-bold">{{ t('scheduler.dialogs.fields.teacher') }}</label>
        <Dropdown :filterInputProps="{ 'aria-label': t('common.filterOptions') }" :aria-label="t('scheduler.dialogs.fields.teacher')" :inputId="prefixEtiquetes + '-camp-5'" :modelValue="formularisLocals.formulariProfessor.professor" @update:modelValue="actualitzaCamp('formulariProfessor', 'professor', $event)" :options="llistaProfessors" filter class="scheduler-dropdown" />
      </div>
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-6'" class="font-bold">{{ t('scheduler.dialogs.fields.subjects') }}</label>
        <MultiSelect :filterInputProps="{ 'aria-label': t('common.filterOptions') }" :aria-label="t('scheduler.dialogs.fields.subjects')" :inputId="prefixEtiquetes + '-camp-6'" :modelValue="formularisLocals.formulariProfessor.assignatures" @update:modelValue="actualitzaCamp('formulariProfessor', 'assignatures', $event)" :options="llistaSessions" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
      <div class="field">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.restrictedDays') }}</label>
        <div class="flex flex-wrap gap-3">
          <div v-for="dia in diesSetmana" :key="dia" class="flex align-items-center gap-2">
            <Checkbox :inputId="`dia-${dia}`" :modelValue="formularisLocals.formulariProfessor.dies" @update:modelValue="actualitzaCamp('formulariProfessor', 'dies', $event)" :value="dia" />
            <label :for="`dia-${dia}`">{{ dayLabel(dia) }}</label>
          </div>
        </div>
      </div>
      <div class="grid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-7'" class="font-bold">{{ t('scheduler.dialogs.fields.maxExams') }}</label>
          <InputNumber :inputId="prefixEtiquetes + '-camp-7'" :modelValue="formularisLocals.formulariProfessor.max_examens" @update:modelValue="actualitzaCamp('formulariProfessor', 'max_examens', $event)" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="20" class="scheduler-inputnumber" />
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-8'" class="font-bold">{{ t('scheduler.dialogs.fields.weightPercent') }}</label>
          <InputNumber :inputId="prefixEtiquetes + '-camp-8'" :modelValue="formularisLocals.formulariProfessor.pes" @update:modelValue="actualitzaCamp('formulariProfessor', 'pes', $event)" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="100" suffix=" %" class="scheduler-inputnumber" />
        </div>
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" text @click="emit('update:mostrarDialogProfessor', false)" />
      <Button :label="t('common.save')" @click="desarDialogProfessor" />
    </template>
  </Dialog>

  <Dialog
    :visible="mostrarDialogDiaHora"
    @update:visible="emit('update:mostrarDialogDiaHora', $event)"
    :header="diaHoraEditantId ? t('scheduler.dialogs.restriction.editTitle') : t('scheduler.dialogs.restriction.newTitle')"
    :modal="true"
    :style="{ width: '520px' }"
  >
    <div class="p-fluid">
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-9'" class="font-bold">{{ t('scheduler.dialogs.daysHours.typeLabel') }}</label>
        <SelectButton :aria-label="t('scheduler.dialogs.daysHours.typeLabel')" :id="prefixEtiquetes + '-camp-9'"
          :modelValue="formularisLocals.formulariDiaHora.tipus" @update:modelValue="actualitzaCamp('formulariDiaHora', 'tipus', $event)"
          :options="tipusDiaHoraOptions"
          optionLabel="label"
          optionValue="value"
          class="w-full"
        />
      </div>
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-10'" class="font-bold">{{ t('scheduler.dialogs.fields.subjects') }}</label>
        <MultiSelect :filterInputProps="{ 'aria-label': t('common.filterOptions') }" :aria-label="t('scheduler.dialogs.fields.subjects')" :inputId="prefixEtiquetes + '-camp-10'" :modelValue="formularisLocals.formulariDiaHora.assignatures" @update:modelValue="actualitzaCamp('formulariDiaHora', 'assignatures', $event)" :options="llistaSessions" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
      <div class="grid">
        <div class="field">
          <div class="flex align-items-center gap-2 mb-2">
            <Checkbox :aria-label="t('scheduler.dialogs.fields.fixedDay')" inputId="te-dia" :modelValue="formularisLocals.formulariDiaHora.teDia" @update:modelValue="actualitzaCamp('formulariDiaHora', 'teDia', $event)" :binary="true" />
            <label>{{ t('scheduler.dialogs.fields.fixedDay') }}</label>
          </div>
          <Dropdown
            :aria-label="t('scheduler.dialogs.fields.fixedDay')" :modelValue="formularisLocals.formulariDiaHora.dia" @update:modelValue="actualitzaCamp('formulariDiaHora', 'dia', $event)"
            :options="diesSetmanaOptions"
            optionLabel="label"
            optionValue="value"
            :disabled="!formulariDiaHora.teDia"
            class="scheduler-dropdown"
          />
        </div>
        <div class="field">
          <div class="flex align-items-center gap-2 mb-2">
            <Checkbox :aria-label="t('scheduler.dialogs.fields.fixedHour')" inputId="te-hora" :modelValue="formularisLocals.formulariDiaHora.teHora" @update:modelValue="actualitzaCamp('formulariDiaHora', 'teHora', $event)" :binary="true" />
            <label>{{ t('scheduler.dialogs.fields.fixedHour') }}</label>
          </div>
          <Dropdown :aria-label="t('scheduler.dialogs.fields.fixedHour')" :modelValue="formularisLocals.formulariDiaHora.hora" @update:modelValue="actualitzaCamp('formulariDiaHora', 'hora', $event)" :options="llistaHoresDisponibles" :disabled="!formulariDiaHora.teHora" class="scheduler-dropdown" />
        </div>
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" text @click="emit('update:mostrarDialogDiaHora', false)" />
      <Button :label="t('common.save')" @click="desarDialogDiaHora" />
    </template>
  </Dialog>

  <Dialog
    :visible="mostrarDialogPreferenciaDia"
    @update:visible="emit('update:mostrarDialogPreferenciaDia', $event)"
    :header="preferenciaEditantId ? t('scheduler.dialogs.preference.editTitle') : t('scheduler.dialogs.preference.newTitle')"
    :modal="true"
    :style="{ width: '520px' }"
  >
    <div class="p-fluid">
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-11'" class="font-bold">{{ t('scheduler.dialogs.fields.subjects') }}</label>
        <MultiSelect :filterInputProps="{ 'aria-label': t('common.filterOptions') }" :aria-label="t('scheduler.dialogs.fields.subjects')" :inputId="prefixEtiquetes + '-camp-11'" :modelValue="formularisLocals.formulariPreferencia.assignatures" @update:modelValue="actualitzaCamp('formulariPreferencia', 'assignatures', $event)" :options="llistaSessions" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
      <div class="grid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-12'" class="font-bold">{{ t('scheduler.dialogs.fields.type') }}</label>
          <Dropdown :aria-label="t('scheduler.dialogs.fields.type')" :inputId="prefixEtiquetes + '-camp-12'" :modelValue="formularisLocals.formulariPreferencia.tipus" @update:modelValue="actualitzaCamp('formulariPreferencia', 'tipus', $event)" :options="tipusPreferenciaDia" optionLabel="label" optionValue="value" class="scheduler-dropdown" />
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-13'" class="font-bold">{{ t('scheduler.dialogs.fields.weightPercent') }}</label>
          <InputNumber :inputId="prefixEtiquetes + '-camp-13'" :modelValue="formularisLocals.formulariPreferencia.pes" @update:modelValue="actualitzaCamp('formulariPreferencia', 'pes', $event)" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="100" suffix=" %" class="scheduler-inputnumber" />
          <small class="text-color-secondary">{{ t('scheduler.dialogs.preference.weightHelp') }}</small>
        </div>
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" text @click="emit('update:mostrarDialogPreferenciaDia', false)" />
      <Button :label="t('common.save')" @click="desarDialogPreferenciaDia" />
    </template>
  </Dialog>

  <Dialog
    :visible="mostrarDialogIncompatibilitat"
    @update:visible="emit('update:mostrarDialogIncompatibilitat', $event)"
    :header="incompatEditantId ? t('scheduler.dialogs.incompatibility.editTitle') : t('scheduler.dialogs.incompatibility.newTitle')"
    :modal="true"
    :style="{ width: '520px' }"
  >
    <div class="p-fluid">
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-14'" class="font-bold">{{ t('scheduler.dialogs.fields.groupName') }}</label>
        <InputText :id="prefixEtiquetes + '-camp-14'" :modelValue="formularisLocals.formulariIncompat.nom" @update:modelValue="actualitzaCamp('formulariIncompat', 'nom', $event)" />
      </div>
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-15'" class="font-bold">{{ t('scheduler.dialogs.fields.incompatibleSubjects') }}</label>
        <MultiSelect :filterInputProps="{ 'aria-label': t('common.filterOptions') }" :aria-label="t('scheduler.dialogs.fields.incompatibleSubjects')" :inputId="prefixEtiquetes + '-camp-15'" :modelValue="formularisLocals.formulariIncompat.assignatures" @update:modelValue="actualitzaCamp('formulariIncompat', 'assignatures', $event)" :options="llistaSessions" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-16'" class="font-bold">{{ t('scheduler.dialogs.fields.weightPercent') }}</label>
        <InputNumber :inputId="prefixEtiquetes + '-camp-16'" :modelValue="formularisLocals.formulariIncompat.pes" @update:modelValue="actualitzaCamp('formulariIncompat', 'pes', $event)" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="100" suffix=" %" class="scheduler-inputnumber" />
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" text @click="emit('update:mostrarDialogIncompatibilitat', false)" />
      <Button :label="t('common.save')" @click="desarDialogIncompatibilitat" />
    </template>
  </Dialog>

  <Dialog
    :visible="mostrarDialogAgrupacio"
    @update:visible="emit('update:mostrarDialogAgrupacio', $event)"
    :header="agrupacioEditantId ? t('scheduler.dialogs.grouping.editTitle') : t('scheduler.dialogs.grouping.newTitle')"
    :modal="true"
    :style="{ width: '560px' }"
  >
    <div class="p-fluid">
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-17'" class="font-bold">{{ t('scheduler.dialogs.fields.optionalName') }}</label>
        <InputText :id="prefixEtiquetes + '-camp-17'" :modelValue="formularisLocals.formulariAgrupacio.nom" @update:modelValue="actualitzaCamp('formulariAgrupacio', 'nom', $event)" :placeholder="t('scheduler.dialogs.grouping.namePlaceholder')" />
      </div>
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-18'" class="font-bold">{{ t('scheduler.dialogs.fields.subjects') }}</label>
        <MultiSelect :filterInputProps="{ 'aria-label': t('common.filterOptions') }" :aria-label="t('scheduler.dialogs.fields.subjects')" :inputId="prefixEtiquetes + '-camp-18'" :modelValue="formularisLocals.formulariAgrupacio.assignatures" @update:modelValue="actualitzaCamp('formulariAgrupacio', 'assignatures', $event)" :options="sessionsFiltrades" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" text @click="emit('update:mostrarDialogAgrupacio', false)" />
      <Button :label="t('common.save')" @click="desarDialogAgrupacio" />
    </template>
  </Dialog>

  <Dialog
    :visible="mostrarDialogCostProfessor"
    @update:visible="emit('update:mostrarDialogCostProfessor', $event)"
    :header="costProfessorEditantId ? t('scheduler.dialogs.cost.editTitle') : t('scheduler.dialogs.cost.newTitle')"
    :modal="true"
    :style="{ width: '560px' }"
  >
    <div class="p-fluid">
      <div class="field">
        <label :for="prefixEtiquetes + '-camp-19'" class="font-bold">{{ t('scheduler.dialogs.fields.teacher') }}</label>
        <Dropdown :filterInputProps="{ 'aria-label': t('common.filterOptions') }" :aria-label="t('scheduler.dialogs.fields.teacher')" :inputId="prefixEtiquetes + '-camp-19'" :modelValue="formularisLocals.formulariCostProfessor.professor" @update:modelValue="actualitzaCamp('formulariCostProfessor', 'professor', $event)" :options="llistaProfessors" filter class="scheduler-dropdown" />
      </div>
      <div class="grid">
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-20'" class="font-bold">{{ t('scheduler.dialogs.cost.fields.substitution') }}</label>
          <InputNumber :inputId="prefixEtiquetes + '-camp-20'" :modelValue="formularisLocals.formulariCostProfessor.substitucio" @update:modelValue="actualitzaCamp('formulariCostProfessor', 'substitucio', $event)" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="500" class="scheduler-inputnumber" />
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-21'" class="font-bold">{{ t('scheduler.dialogs.cost.fields.beforeShift') }}</label>
          <InputNumber :inputId="prefixEtiquetes + '-camp-21'" :modelValue="formularisLocals.formulariCostProfessor.abans_jornada" @update:modelValue="actualitzaCamp('formulariCostProfessor', 'abans_jornada', $event)" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="500" class="scheduler-inputnumber" />
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-22'" class="font-bold">{{ t('scheduler.dialogs.cost.fields.afterShift') }}</label>
          <InputNumber :inputId="prefixEtiquetes + '-camp-22'" :modelValue="formularisLocals.formulariCostProfessor.despres_jornada" @update:modelValue="actualitzaCamp('formulariCostProfessor', 'despres_jornada', $event)" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="500" class="scheduler-inputnumber" />
        </div>
        <div class="field">
          <label :for="prefixEtiquetes + '-camp-23'" class="font-bold">{{ t('scheduler.dialogs.cost.fields.noWorkDay') }}</label>
          <InputNumber :inputId="prefixEtiquetes + '-camp-23'" :modelValue="formularisLocals.formulariCostProfessor.no_treballa_dia" @update:modelValue="actualitzaCamp('formulariCostProfessor', 'no_treballa_dia', $event)" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="500" class="scheduler-inputnumber" />
        </div>
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" text @click="emit('update:mostrarDialogCostProfessor', false)" />
      <Button :label="t('common.save')" @click="desarDialogCostProfessor" />
    </template>
  </Dialog>

  <Dialog
    :visible="mostrarDialogIntents"
    @update:visible="emit('update:mostrarDialogIntents', $event)"
    :header="t('scheduler.dialogs.attempts.title')"
    :modal="true"
    :style="{ width: '750px' }"
  >
    <div class="text-xs text-color-secondary mb-2" v-if="bestIntent">
      {{ t('scheduler.dialogs.attempts.shownBest', { intent: bestIntent.intent, cost: bestIntent.cost_total }) }}
    </div>
    <div class="text-xs text-color-secondary mb-2" v-else-if="intentsLog.length">
      {{ t('scheduler.dialogs.attempts.shownLast', { cost: intentsLog[intentsLog.length - 1].cost_total }) }}
    </div>
    <DataTable :value="intentsLog" class="p-datatable-sm" stripedRows :emptyMessage="t('scheduler.dialogs.attempts.emptyMessage')">
      <Column field="intent" header="#" style="width: 50px" />
      <Column field="cost_total" :header="t('scheduler.dialogs.attempts.columns.cost')" style="width: 80px" />
      <Column field="best_so_far" :header="t('scheduler.dialogs.attempts.columns.best')" style="width: 80px">
        <template #body="s">
          <span>{{ s.data.best_so_far ?? t('common.noneDash') }}</span>
        </template>
      </Column>
      <Column field="total_sessions" :header="t('scheduler.dialogs.attempts.columns.sessions')" style="width: 60px" />
      <Column field="total_substitucions" :header="t('scheduler.dialogs.attempts.columns.substitutions')" style="width: 60px" />
      <Column field="professors_abans" :header="t('scheduler.dialogs.attempts.columns.before')" style="width: 60px" />
      <Column field="professors_despres" :header="t('scheduler.dialogs.attempts.columns.after')" style="width: 70px" />
      <Column :header="t('scheduler.dialogs.attempts.columns.valid')" style="width: 60px">
        <template #body="s">
          <Tag :value="s.data.valid ? '✓' : '✗'" :severity="s.data.valid ? 'success' : 'warning'" class="text-xs" />
        </template>
      </Column>
      <Column header="★" style="width: 40px">
        <template #body="s">
          <span v-if="s.data.is_best">⭐</span>
        </template>
      </Column>
    </DataTable>
    <template #footer>
      <Button :label="t('common.close')" text @click="emit('update:mostrarDialogIntents', false)" />
    </template>
  </Dialog>

  <Dialog
    :visible="mostrarDialogIncompat"
    @update:visible="emit('update:mostrarDialogIncompat', $event)"
    :header="t('scheduler.dialogs.incompatibilities.title')"
    :modal="true"
    :style="{ width: '720px' }"
  >
    <div class="text-sm text-color-secondary mb-2">
      {{ incompatErrorMsg || t('scheduler.dialogs.incompatibilities.defaultMessage') }}
    </div>
    <Message v-if="explicacioNoDisponible" severity="warn" :closable="false" class="mb-2">
      {{ t('scheduler.dialogs.incompatibilities.explanationUnavailable', { ref: explicacioNoDisponible }) }}
    </Message>
    <ul v-if="incompatibilitats.length" class="pl-3">
      <li v-for="(msg, idx) in incompatibilitats" :key="idx" class="text-sm">{{ msg }}</li>
    </ul>
    <div v-else-if="!explicacioNoDisponible" class="text-sm">{{ t('scheduler.dialogs.incompatibilities.undetermined') }}</div>
    <template #footer>
      <Button :label="t('common.close')" text @click="emit('update:mostrarDialogIncompat', false)" />
    </template>
  </Dialog>
</template>

<script setup>
import { useId } from 'vue'
import { computed, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { localizeBackendDayName } from '../textUtils'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import SelectButton from 'primevue/selectbutton'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Message from 'primevue/message'

const prefixEtiquetes = useId()

const props = defineProps({
  mostrarDialogDurada: { type: Boolean, default: false },
  editantDuradaId: { type: [Number, String], default: null },
  formulariDurada: { type: Object, required: true },
  mostrarDialogProfessor: { type: Boolean, default: false },
  professorEditantId: { type: String, default: null },
  formulariProfessor: { type: Object, required: true },
  mostrarDialogDiaHora: { type: Boolean, default: false },
  diaHoraEditantId: { type: String, default: null },
  formulariDiaHora: { type: Object, required: true },
  mostrarDialogPreferenciaDia: { type: Boolean, default: false },
  preferenciaEditantId: { type: String, default: null },
  formulariPreferencia: { type: Object, required: true },
  mostrarDialogIncompatibilitat: { type: Boolean, default: false },
  incompatEditantId: { type: String, default: null },
  formulariIncompat: { type: Object, required: true },
  mostrarDialogAgrupacio: { type: Boolean, default: false },
  agrupacioEditantId: { type: String, default: null },
  formulariAgrupacio: { type: Object, required: true },
  mostrarDialogCostProfessor: { type: Boolean, default: false },
  costProfessorEditantId: { type: String, default: null },
  formulariCostProfessor: { type: Object, required: true },
  mostrarDialogIntents: { type: Boolean, default: false },
  mostrarDialogIncompat: { type: Boolean, default: false },
  llistaProfessors: { type: Array, default: () => [] },
  llistaSessions: { type: Array, default: () => [] },
  diesSetmana: { type: Array, default: () => [] },
  llistaHoresDisponibles: { type: Array, default: () => [] },
  tipusPreferenciaDia: { type: Array, default: () => [] },
  sessionsFiltrades: { type: Array, default: () => [] },
  intentsLog: { type: Array, default: () => [] },
  bestIntent: { type: Object, default: null },
  incompatibilitats: { type: Array, default: () => [] },
  incompatErrorMsg: { type: String, default: '' },
  explicacioNoDisponible: { type: String, default: null },
  desarDialogDurada: { type: Function, required: true },
  desarDialogProfessor: { type: Function, required: true },
  desarDialogDiaHora: { type: Function, required: true },
  desarDialogPreferenciaDia: { type: Function, required: true },
  desarDialogIncompatibilitat: { type: Function, required: true },
  desarDialogAgrupacio: { type: Function, required: true },
  desarDialogCostProfessor: { type: Function, required: true }
})

const emit = defineEmits([
  'update:mostrarDialogDurada',
  'update:mostrarDialogProfessor',
  'update:mostrarDialogDiaHora',
  'update:mostrarDialogPreferenciaDia',
  'update:mostrarDialogIncompatibilitat',
  'update:mostrarDialogAgrupacio',
  'update:mostrarDialogCostProfessor',
  'update:mostrarDialogIntents',
  'update:mostrarDialogIncompat',
  'update:formulariDurada',
  'update:formulariProfessor',
  'update:formulariDiaHora',
  'update:formulariPreferencia',
  'update:formulariIncompat',
  'update:formulariAgrupacio',
  'update:formulariCostProfessor',
])

// Cada camp continua arribant al pare en editar-lo (també si després es
// cancel·la). Les còpies eviten modificar les props o compartir-hi els arrays.
const copiaFormulari = (valor) => {
  if (Array.isArray(valor)) return valor.map(copiaFormulari)
  if (valor && typeof valor === 'object') {
    return Object.fromEntries(Object.entries(valor).map(([clau, camp]) => [clau, copiaFormulari(camp)]))
  }
  return valor
}

const formularisLocals = reactive({})
const nomsFormularis = [
  'formulariDurada',
  'formulariProfessor',
  'formulariDiaHora',
  'formulariPreferencia',
  'formulariIncompat',
  'formulariAgrupacio',
  'formulariCostProfessor',
]

for (const nom of nomsFormularis) {
  // El pare reinicia els formularis en obrir/editar i després de desar. La
  // sincronització immediata també preserva els canvis de camps fets pel pare.
  watch(() => props[nom], (valor) => {
    formularisLocals[nom] = copiaFormulari(valor)
  }, { immediate: true, deep: true, flush: 'sync' })
}

const actualitzaCamp = (nom, camp, valor) => {
  formularisLocals[nom][camp] = copiaFormulari(valor)
  emit(`update:${nom}`, copiaFormulari(formularisLocals[nom]))
}

const { t } = useI18n()
const dayLabel = (day) => localizeBackendDayName(day, t)

const diesSetmanaOptions = computed(() => props.diesSetmana.map((day) => ({
  label: dayLabel(day),
  value: day
})))

const tipusDiaHoraOptions = computed(() => [
  { label: t('scheduler.dialogs.daysHours.typeFix'), value: 'fixar' },
  { label: t('scheduler.dialogs.daysHours.typeProhibit'), value: 'prohibir' }
])
</script>

<style scoped>
/* L'aplicació no carrega PrimeFlex: les seves classes (field, grid, flex,
   gap-2...) no fan res i els camps dels formularis quedaven enganxats.
   Provisional, fins que es parteixi aquesta vista (fase 3): els espais dels
   diàlegs, aquí, només per a les classes que s'hi fan servir. */
.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.field:last-child {
  margin-bottom: 0;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 1rem;
}

.flex {
  display: flex;
}

.flex-wrap {
  flex-wrap: wrap;
}

.align-items-center {
  align-items: center;
}

.gap-2 {
  gap: 0.5rem;
}

.gap-3 {
  gap: 1rem;
}

.mb-2 {
  margin-bottom: 0.5rem;
}

.pl-3 {
  padding-left: 1.25rem;
}

.font-bold {
  font-weight: 600;
}

.text-sm {
  font-size: 0.875rem;
}

.text-xs {
  font-size: 0.75rem;
}

.text-color-secondary {
  color: var(--text-color-secondary, #6b7280);
}

.w-full {
  width: 100%;
}
</style>
