<template>
  <!-- Filtre per aula (Vigilàncies i Configuració d'exàmens). Amb «ENLLAÇ» es
       veu de seguida qui fa d'enllaç. Amb cerca: hi pot haver moltes aules. -->
  <Dropdown
    v-model="aula"
    :options="[etiquetaTotes, ...aules]"
    :placeholder="$t('vigilancies.filters.room')"
    :aria-label="$t('vigilancies.filters.room')"
    filter
    class="p-inputtext-sm filtre-aula"
  >
    <template v-if="ambNom" #value="{ value }">
      {{ !value || value === etiquetaTotes ? $t('vigilancies.filters.roomAll') : $t('vigilancies.filters.roomValue', { valor: value }) }}
    </template>
  </Dropdown>
</template>

<script setup>
import Dropdown from 'primevue/dropdown'

// El valor és l'aula triada, o `etiquetaTotes` (sense filtre)
const aula = defineModel({ type: String, default: '' })
defineProps({
  aules: { type: Array, default: () => [] },
  etiquetaTotes: { type: String, required: true },
  ambNom: { type: Boolean, default: false } // «Aula: totes», «Aula: ENLLAÇ» (sense etiqueta a fora)
})
</script>

<style scoped>
.filtre-aula {
  width: 150px;
}
</style>
