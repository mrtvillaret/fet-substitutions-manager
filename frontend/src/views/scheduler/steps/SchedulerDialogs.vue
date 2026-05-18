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
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.steps.restrictions.durades.dialog.nameLabel') }}</label>
        <InputText
          v-model="formulariDurada.nom"
          :placeholder="t('scheduler.steps.restrictions.durades.dialog.namePlaceholder')"
        />
      </div>
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.steps.restrictions.durades.dialog.sessionsLabel') }}</label>
        <MultiSelect
          v-model="formulariDurada.sessions"
          :options="llistaSessions"
          filter
          :placeholder="t('scheduler.steps.restrictions.durades.dialog.sessionsPlaceholder')"
          class="scheduler-multiselect"
        />
      </div>
      <div class="field mb-3">
        <label class="font-bold">{{ t('scheduler.steps.restrictions.durades.dialog.durationLabel') }}</label>
        <div class="flex align-items-center gap-2">
          <InputNumber
            v-model="formulariDurada.durada"
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
        <label class="font-bold">{{ t('scheduler.steps.restrictions.durades.dialog.examDurationLabel') }}</label>
        <div class="flex align-items-center gap-2">
          <InputNumber
            v-model="formulariDurada.durada_examen"
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
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.teacher') }}</label>
        <Dropdown v-model="formulariProfessor.professor" :options="llistaProfessors" filter class="scheduler-dropdown" />
      </div>
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.subjects') }}</label>
        <MultiSelect v-model="formulariProfessor.assignatures" :options="llistaSessions" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.restrictedDays') }}</label>
        <div class="flex flex-wrap gap-3">
          <div v-for="dia in diesSetmana" :key="dia" class="flex align-items-center gap-2">
            <Checkbox :inputId="`dia-${dia}`" v-model="formulariProfessor.dies" :value="dia" />
            <label :for="`dia-${dia}`">{{ dayLabel(dia) }}</label>
          </div>
        </div>
      </div>
      <div class="grid">
        <div class="field col-6">
          <label class="font-bold">{{ t('scheduler.dialogs.fields.maxExams') }}</label>
          <InputNumber v-model="formulariProfessor.max_examens" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="20" class="scheduler-inputnumber" />
        </div>
        <div class="field col-6">
          <label class="font-bold">{{ t('scheduler.dialogs.fields.weightPercent') }}</label>
          <InputNumber v-model="formulariProfessor.pes" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="100" suffix=" %" class="scheduler-inputnumber" />
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
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.daysHours.typeLabel') }}</label>
        <SelectButton
          v-model="formulariDiaHora.tipus"
          :options="tipusDiaHoraOptions"
          optionLabel="label"
          optionValue="value"
          class="w-full"
        />
      </div>
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.subjects') }}</label>
        <MultiSelect v-model="formulariDiaHora.assignatures" :options="llistaSessions" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
      <div class="grid">
        <div class="field col-6">
          <div class="flex align-items-center gap-2 mb-2">
            <Checkbox inputId="te-dia" v-model="formulariDiaHora.teDia" :binary="true" />
            <label>{{ t('scheduler.dialogs.fields.fixedDay') }}</label>
          </div>
          <Dropdown
            v-model="formulariDiaHora.dia"
            :options="diesSetmanaOptions"
            optionLabel="label"
            optionValue="value"
            :disabled="!formulariDiaHora.teDia"
            class="scheduler-dropdown"
          />
        </div>
        <div class="field col-6">
          <div class="flex align-items-center gap-2 mb-2">
            <Checkbox inputId="te-hora" v-model="formulariDiaHora.teHora" :binary="true" />
            <label>{{ t('scheduler.dialogs.fields.fixedHour') }}</label>
          </div>
          <Dropdown v-model="formulariDiaHora.hora" :options="llistaHoresDisponibles" :disabled="!formulariDiaHora.teHora" class="scheduler-dropdown" />
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
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.subjects') }}</label>
        <MultiSelect v-model="formulariPreferencia.assignatures" :options="llistaSessions" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
      <div class="grid">
        <div class="field col-6">
          <label class="font-bold">{{ t('scheduler.dialogs.fields.type') }}</label>
          <Dropdown v-model="formulariPreferencia.tipus" :options="tipusPreferenciaDia" optionLabel="label" optionValue="value" class="scheduler-dropdown" />
        </div>
        <div class="field col-6">
          <label class="font-bold">{{ t('scheduler.dialogs.fields.weightPercent') }}</label>
          <InputNumber v-model="formulariPreferencia.pes" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="100" suffix=" %" class="scheduler-inputnumber" />
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
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.groupName') }}</label>
        <InputText v-model="formulariIncompat.nom" />
      </div>
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.incompatibleSubjects') }}</label>
        <MultiSelect v-model="formulariIncompat.assignatures" :options="llistaSessions" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
      </div>
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.weightPercent') }}</label>
        <InputNumber v-model="formulariIncompat.pes" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="100" suffix=" %" class="scheduler-inputnumber" />
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
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.optionalName') }}</label>
        <InputText v-model="formulariAgrupacio.nom" :placeholder="t('scheduler.dialogs.grouping.namePlaceholder')" />
      </div>
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.subjects') }}</label>
        <MultiSelect v-model="formulariAgrupacio.assignatures" :options="sessionsFiltrades" filter :placeholder="t('scheduler.dialogs.fields.sessionsPlaceholder')" class="scheduler-multiselect" />
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
      <div class="field mb-4">
        <label class="font-bold">{{ t('scheduler.dialogs.fields.teacher') }}</label>
        <Dropdown v-model="formulariCostProfessor.professor" :options="llistaProfessors" filter class="scheduler-dropdown" />
      </div>
      <div class="grid">
        <div class="field col-6">
          <label class="font-bold">{{ t('scheduler.dialogs.cost.fields.substitution') }}</label>
          <InputNumber v-model="formulariCostProfessor.substitucio" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="500" class="scheduler-inputnumber" />
        </div>
        <div class="field col-6">
          <label class="font-bold">{{ t('scheduler.dialogs.cost.fields.beforeShift') }}</label>
          <InputNumber v-model="formulariCostProfessor.abans_jornada" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="500" class="scheduler-inputnumber" />
        </div>
        <div class="field col-6">
          <label class="font-bold">{{ t('scheduler.dialogs.cost.fields.afterShift') }}</label>
          <InputNumber v-model="formulariCostProfessor.despres_jornada" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="500" class="scheduler-inputnumber" />
        </div>
        <div class="field col-6">
          <label class="font-bold">{{ t('scheduler.dialogs.cost.fields.noWorkDay') }}</label>
          <InputNumber v-model="formulariCostProfessor.no_treballa_dia" showButtons buttonLayout="horizontal" incrementButtonIcon="pi pi-plus" decrementButtonIcon="pi pi-minus" :min="0" :max="500" class="scheduler-inputnumber" />
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
    <ul v-if="incompatibilitats.length" class="pl-3 m-0">
      <li v-for="(msg, idx) in incompatibilitats" :key="idx" class="text-sm mb-1">{{ msg }}</li>
    </ul>
    <div v-else class="text-sm">{{ t('scheduler.dialogs.incompatibilities.undetermined') }}</div>
    <template #footer>
      <Button :label="t('common.close')" text @click="emit('update:mostrarDialogIncompat', false)" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed } from 'vue'
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
  'update:mostrarDialogIncompat'
])

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
