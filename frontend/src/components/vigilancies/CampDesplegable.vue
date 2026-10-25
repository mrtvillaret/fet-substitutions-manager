<template>
  <!-- Un camp que es mostra com a text i només crea el desplegable quan s'hi
       fa clic (o s'hi prem Retorn). Una taula amb molts camps així és lleugera:
       crear-hi tots els desplegables de cop era el que la feia lenta. -->
  <div class="camp-desplegable" :class="`camp-desplegable--${aspecte}`">
    <Dropdown
      v-if="actiu"
      ref="desplegable"
      :modelValue="modelValue"
      :options="options"
      :optionLabel="optionLabel"
      :optionValue="optionValue"
      :filter="filter"
      :placeholder="placeholder"
      :aria-label="etiqueta"
      class="camp-desplegable__dropdown"
      @update:modelValue="tria"
      @hide="actiu = false"
    >
      <template v-if="$slots.option" #option="props">
        <slot name="option" v-bind="props" />
      </template>
    </Dropdown>
    <button
      v-else
      type="button"
      class="camp-desplegable__text"
      :class="{ 'camp-desplegable__text--buit': buit }"
      :aria-label="etiqueta"
      :title="senseTitol ? null : titol"
      @click="obre"
    >
      <span class="camp-desplegable__valor"><slot name="valor">{{ buit ? placeholder : modelValue }}</slot></span>
      <i class="pi pi-chevron-down camp-desplegable__fletxa" aria-hidden="true"></i>
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import Dropdown from 'primevue/dropdown'

const props = defineProps({
  modelValue: { type: [String, Number, null], default: null },
  options: { type: Array, default: () => [] },
  optionLabel: { type: String, default: undefined },
  optionValue: { type: String, default: undefined },
  filter: { type: Boolean, default: false },
  placeholder: { type: String, default: '' },
  etiqueta: { type: String, default: '' }, // per als lectors de pantalla
  text: { type: String, default: '' }, // el text que es mostra, si no és el valor (per al title)
  senseTitol: { type: Boolean, default: false }, // quan ja hi ha una altra ajuda (el vigilant)
  // 'cella': discret, per a la taula; 'camp': amb vora, per als formularis
  aspecte: { type: String, default: 'cella' }
})
const emit = defineEmits(['update:modelValue', 'change'])

const actiu = ref(false)
const desplegable = ref(null)
// El text sencer en passar-hi per damunt (a la cel·la es pot tallar amb «…»)
const titol = computed(() => (props.text || (buit.value ? '' : String(props.modelValue))) || props.etiqueta)
const buit = computed(() => props.modelValue === null || props.modelValue === undefined || props.modelValue === '')

const obre = async () => {
  actiu.value = true
  await nextTick()
  desplegable.value?.show(true)
}

// Les opcions «-- Nivell --», «-- Tipus --»... volen dir «cap»: el valor és buit
const tria = (valor) => {
  const net = typeof valor === 'string' && valor.startsWith('--') ? '' : valor
  emit('update:modelValue', net)
  emit('change', net)
}
</script>

<style scoped>
.camp-desplegable {
  min-width: 0;
}

.camp-desplegable__dropdown {
  width: 100%;
}

.camp-desplegable__text {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  width: 100%;
  min-height: 2rem;
  padding: 0.3rem 0.4rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

/* Una sola línia: el text sencer surt en passar-hi per damunt (title) */
.camp-desplegable__valor {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.camp-desplegable--camp .camp-desplegable__text {
  min-height: 2.5rem;
  border-color: var(--surface-border, #d1d5db);
  background: var(--surface-card, #fff);
}

.camp-desplegable__text:hover,
.camp-desplegable__text:focus-visible {
  border-color: var(--primary-color, #6366f1);
  background: var(--surface-card, #fff);
  outline: none;
}

.camp-desplegable__text--buit {
  color: var(--text-color-secondary, #9ca3af);
}

.camp-desplegable__fletxa {
  margin-left: auto;
  font-size: 0.7rem;
  opacity: 0.6;
  flex: 0 0 auto;
}

/* A la cel·la, la fletxa només en passar-hi per damunt: amagada no ocupa lloc */
.camp-desplegable--cella .camp-desplegable__fletxa {
  display: none;
}

.camp-desplegable--cella .camp-desplegable__text:hover .camp-desplegable__fletxa,
.camp-desplegable--cella .camp-desplegable__text:focus-visible .camp-desplegable__fletxa {
  display: inline;
}
</style>
