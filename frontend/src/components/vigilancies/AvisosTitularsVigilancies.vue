<template>
    <!-- Titulars que no s'han posat perquè tenien l'hora lliure: ho decideix qui fa les vigilàncies -->
    <Message
      v-if="!loading && !error && titularsHoraLliure.length"
      severity="warn"
      :closable="true"
      class="titulars-hora-lliure"
      @close="titularsHoraLliure = []"
    >
      <div>{{ $t('vigilancies.freeHourOwners.title', { count: titularsHoraLliure.length }, titularsHoraLliure.length) }}</div>
      <ul>
        <li v-for="item in titularsHoraLliure" :key="item.vigilancia_id">
          {{ item.hora }} · {{ item.grups }} · {{ item.tipus }} — <strong>{{ item.titular }}</strong>
          <Button
            :label="$t('vigilancies.freeHourOwners.assign')"
            size="small"
            text
            :loading="posantTitular === item.vigilancia_id"
            @click="posaTitularHoraLliure(item)"
          />
        </li>
      </ul>
    </Message>

    <!-- Vigilàncies que la configuració d'exàmens no deixa definides -->
    <Message
      v-if="!loading && !error && vigilanciesSenseTitular.length"
      severity="info"
      :closable="true"
      class="titulars-hora-lliure"
      @close="vigilanciesSenseTitular = []"
    >
      <div>{{ $t('vigilancies.withoutOwner.title', { count: vigilanciesSenseTitular.length }, vigilanciesSenseTitular.length) }}</div>
      <ul>
        <li v-for="item in vigilanciesSenseTitular" :key="item.vigilancia_id">
          {{ item.hora }} · {{ item.grups }} · {{ item.tipus }} — {{ $t(`vigilancies.withoutOwner.${item.motiu}`) }}
        </li>
      </ul>
      <Button
        :label="$t('vigilancies.withoutOwner.openConfig')"
        icon="pi pi-cog"
        size="small"
        text
        @click="obreConfiguracioExamens"
      />
    </Message>

</template>

<script setup>
import Message from 'primevue/message'
import Button from 'primevue/button'

const titularsHoraLliure = defineModel('titularsHoraLliure', { required: true })
const vigilanciesSenseTitular = defineModel('vigilanciesSenseTitular', { required: true })
defineProps({ loading: Boolean, error: String, posantTitular: [String, Number], posaTitularHoraLliure: Function, obreConfiguracioExamens: Function })
</script>

<style scoped>
.titulars-hora-lliure ul {
  margin: 0.25rem 0 0;
  padding-left: 1.25rem;
}
</style>
