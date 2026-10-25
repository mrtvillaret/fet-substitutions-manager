<template>
  <!-- El vigilant: el desplegable amb cerca i les opcions acolorides segons el
       que fa cada professor a l'hora (titular, alliberat, guàrdia, classe...).
       El mateix a la taula i al formulari de «Nova vigilància». -->
  <CampDesplegable
    :modelValue="modelValue"
    :options="opcions"
    optionLabel="label"
    optionValue="value"
    filter
    :placeholder="$t('vigilancies.placeholders.supervisor')"
    :etiqueta="$t('vigilancies.columns.supervisor')"
    :aspecte="aspecte"
    :text="etiquetaValor"
    sense-titol
    @update:modelValue="emit('update:modelValue', $event)"
    @change="emit('change', $event)"
  >
    <template #valor>
      <span v-if="modelValue" class="selector-vigilant__nom">{{ etiquetaValor || modelValue }}</span>
      <span v-else class="selector-vigilant__buit">{{ $t('vigilancies.placeholders.supervisor') }}</span>
    </template>
    <template #option="{ option }">
      <div
        class="selector-vigilant__opcio opcio-acolorida"
        :class="{ 'selector-vigilant__opcio--assignat': option.ja_assignat }"
        :style="{ backgroundColor: option.color }"
      >
        {{ option.label }}
      </div>
    </template>
  </CampDesplegable>
</template>

<script setup>
import CampDesplegable from './CampDesplegable.vue'

defineProps({
  modelValue: { type: String, default: '' },
  opcions: { type: Array, default: () => [] }, // els disponibles de l'hora (amb l'opció buida)
  etiquetaValor: { type: String, default: '' }, // el text del vigilant triat
  aspecte: { type: String, default: 'cella' }
})
const emit = defineEmits(['update:modelValue', 'change'])
</script>

<style scoped>
.selector-vigilant__buit {
  color: var(--text-color-secondary, #9ca3af);
}

.selector-vigilant__opcio {
  padding: 0.5rem;
  border-radius: 4px;
  font-weight: 500;
}

.selector-vigilant__opcio--assignat {
  font-weight: normal;
  opacity: 0.7;
}
</style>
