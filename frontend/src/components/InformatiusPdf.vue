<template>
  <details v-if="missatges.length" ref="detall" class="informatius-pdf">
    <summary>{{ $t('substitutions.dialogs.pdfValidation.showInformational', { count: missatges.length }, missatges.length) }}</summary>
    <ul>
      <li v-for="(missatge, idx) in missatges" :key="idx">{{ missatge }}</li>
    </ul>
  </details>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ missatges: { type: Array, required: true } })
const detall = ref(null)
watch(() => props.missatges, () => {
  if (detall.value) detall.value.open = false
})
</script>

<style scoped>
.informatius-pdf { margin: 1rem 0; }
summary { cursor: pointer; }
li { margin-bottom: 0.25rem; }
</style>
