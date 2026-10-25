<template>
  <!-- «Nova vigilància»: el formulari complet. Les opcions de tipus i de grups
       depenen del nivell, com a la taula, i el vigilant té el mateix selector
       (cerca, colors i ajuda). Qui el fa servir crea la fila amb `desa`. -->
  <Dialog
    v-model:visible="visible"
    :header="$t('vigilancies.form.title')"
    :modal="true"
    :style="{ width: '40rem' }"
    :breakpoints="{ '720px': '95vw' }"
  >
    <form class="formulari-vigilancia" @submit.prevent="desa">
      <div class="formulari-vigilancia__camp">
        <label>{{ $t('common.hour') }} *</label>
        <CampDesplegable v-model="fila.hora" :options="opcions.hores" :etiqueta="$t('common.hour')" aspecte="camp" />
      </div>
      <div class="formulari-vigilancia__camp">
        <label>{{ $t('vigilancies.columns.level') }}</label>
        <CampDesplegable
          v-model="fila.nivell"
          :options="[$t('vigilancies.placeholders.level'), ...opcions.nivells]"
          :placeholder="$t('vigilancies.placeholders.level')"
          :etiqueta="$t('vigilancies.columns.level')"
          aspecte="camp"
          @change="nivellCanviat"
        />
      </div>
      <div class="formulari-vigilancia__camp">
        <label>{{ $t('vigilancies.columns.type') }}</label>
        <CampDesplegable
          v-model="fila.tipus"
          :options="opcions.tipusDe(fila.nivell)"
          :placeholder="$t('vigilancies.placeholders.type')"
          :etiqueta="$t('vigilancies.columns.type')"
          aspecte="camp"
        />
      </div>
      <div class="formulari-vigilancia__camp">
        <label>{{ $t('common.group') }}</label>
        <CampDesplegable
          v-model="fila.grups"
          :options="[$t('vigilancies.placeholders.groups'), ...opcions.grupsDe(fila.nivell)]"
          :placeholder="$t('vigilancies.placeholders.groups')"
          :etiqueta="$t('common.group')"
          aspecte="camp"
        />
      </div>
      <div class="formulari-vigilancia__camp">
        <label>{{ $t('common.room') }}</label>
        <CampDesplegable
          v-model="fila.aula"
          :options="[$t('vigilancies.placeholders.room'), ...opcions.aules]"
          :placeholder="$t('vigilancies.placeholders.room')"
          :etiqueta="$t('common.room')"
          aspecte="camp"
        />
      </div>
      <div class="formulari-vigilancia__camp">
        <label>{{ $t('vigilancies.columns.supervisor') }} ({{ $t('vigilancies.form.optional') }})</label>
        <AjudaVigilant :data="data" :hora="fila.hora" :nom="fila.vigilant" :text="etiquetaVigilant" :color="colorVigilant">
          <SelectorVigilant
            v-model="fila.vigilant"
            :opcions="disponibles"
            :etiqueta-valor="etiquetaVigilant"
            aspecte="camp"
          />
        </AjudaVigilant>
      </div>
      <div class="formulari-vigilancia__camp formulari-vigilancia__camp--ample">
        <label :for="`${prefix}-observacions`">{{ $t('common.comments') }}</label>
        <input
          :id="`${prefix}-observacions`"
          v-model="fila.comentaris"
          class="formulari-vigilancia__text"
          type="text"
          :placeholder="$t('common.commentsPlaceholder')"
        />
      </div>
    </form>

    <template #footer>
      <Button :label="$t('common.cancel')" class="p-button-text" @click="visible = false" />
      <Button :label="$t('common.save')" icon="pi pi-check" :loading="desant" :disabled="!fila.hora" @click="desa" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import AjudaVigilant from './AjudaVigilant.vue'
import CampDesplegable from './CampDesplegable.vue'
import SelectorVigilant from './SelectorVigilant.vue'

const visible = defineModel('visible', { type: Boolean, default: false })
const props = defineProps({
  data: { type: String, required: true },
  opcions: { type: Object, required: true }, // { hores, nivells, aules, tipusDe, grupsDe }
  // La proposta en obrir-lo: { hora, nivell, tipus } (de la darrera fila)
  proposta: { type: Object, default: () => ({}) },
  // (consulta {hora, tipus, grups, aula}) -> Promise<opcions del vigilant>
  carregaDisponibles: { type: Function, required: true },
  desant: { type: Boolean, default: false }
})
const emit = defineEmits(['desa'])

const prefix = 'nova-vigilancia'
const buida = () => ({ hora: '', nivell: '', tipus: '', grups: '', aula: '', vigilant: '', comentaris: '' })
const fila = ref(buida())
const disponibles = ref([])

watch(visible, (obert) => {
  if (!obert) return
  fila.value = { ...buida(), ...props.proposta }
})

// Si el nivell canvia, el grup d'abans pot no ser-ne
const nivellCanviat = () => {
  if (fila.value.grups && !props.opcions.grupsDe(fila.value.nivell).includes(fila.value.grups)) fila.value.grups = ''
}

// Els disponibles depenen de l'hora i, per marcar el titular, de l'examen
watch(
  () => visible.value && [fila.value.hora, fila.value.tipus, fila.value.grups, fila.value.aula],
  async (clau) => {
    if (!clau || !fila.value.hora) {
      disponibles.value = []
      return
    }
    const { hora, tipus, grups, aula } = fila.value
    disponibles.value = await props.carregaDisponibles({ hora, tipus, grups, aula })
  },
  { deep: true }
)

const opcioVigilant = computed(() => disponibles.value.find((d) => d.value === fila.value.vigilant))
const etiquetaVigilant = computed(() => opcioVigilant.value?.label || '')
const colorVigilant = computed(() => opcioVigilant.value?.color || '')

const desa = () => {
  if (!fila.value.hora || props.desant) return
  emit('desa', { ...fila.value })
}
</script>

<style scoped>
/* Estils propis, com PdfOpcionsComunes: l'aplicació no carrega PrimeFlex */
.formulari-vigilancia {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem 1.25rem;
}

.formulari-vigilancia__camp {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}

.formulari-vigilancia__camp--ample {
  grid-column: 1 / -1;
}

.formulari-vigilancia__camp label {
  font-weight: 600;
  color: #374151;
}

.formulari-vigilancia__text {
  min-height: 2.5rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--surface-border, #d1d5db);
  border-radius: 6px;
  font: inherit;
}

.formulari-vigilancia__text:focus {
  border-color: var(--primary-color, #6366f1);
  outline: none;
}

@media (max-width: 720px) {
  .formulari-vigilancia {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
