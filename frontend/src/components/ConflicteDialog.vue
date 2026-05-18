<template>
  <Dialog
    :visible="visible"
    modal
    :closable="false"
    :header="title"
    class="conflicte-dialog"
    @update:visible="onVisibleChange"
  >
    <p class="conflicte-message">{{ message }}</p>
    <template #footer>
      <Button
        :label="reloadLabel"
        class="p-button-text"
        @click="handleReload"
      />
      <Button
        :label="overwriteLabel"
        class="p-button-warning"
        @click="handleOverwrite"
      />
    </template>
  </Dialog>
</template>

<script setup>
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, required: true },
  message: { type: String, required: true },
  reloadLabel: { type: String, required: true },
  overwriteLabel: { type: String, required: true }
})

const emit = defineEmits(['update:visible', 'reload', 'overwrite'])

const onVisibleChange = (value) => {
  emit('update:visible', value)
}

const handleReload = () => {
  emit('reload')
  emit('update:visible', false)
}

const handleOverwrite = () => {
  emit('overwrite')
  emit('update:visible', false)
}
</script>

<style scoped>
.conflicte-message {
  margin: 0;
}
</style>
