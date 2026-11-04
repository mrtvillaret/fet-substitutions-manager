<template>
  <Message severity="error" :closable="false" class="error-carrega">
    <div class="error-carrega-contingut">
      <span>{{ missatge }}</span>
      <Button :label="$t('substitutions.actions.retry')" icon="pi pi-refresh" size="small" @click="$emit('reintenta')" />
    </div>
  </Message>
</template>
<script setup>
import Message from 'primevue/message'
import Button from 'primevue/button'
defineProps({ missatge: { type: String, required: true } })
defineEmits(['reintenta'])
</script>
<style scoped>
.error-carrega { margin-bottom: 1rem; }
.error-carrega-contingut { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; width: 100%; }
</style>
