import { onMounted, onBeforeUnmount } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useI18n } from 'vue-i18n'

// Grup propi de ConfirmDialog: App.vue el té a totes les pantalles (els
// ConfirmDialog sense grup són dins de cada pantalla, i Grups no en té).
export const GRUP_SORTIDA = 'sortida'

// Canvis sense desar en tancar un diàleg (també amb «Enrere»): es pregunta i
// la promesa diu si es pot tancar.
export function useConfirmaSortida() {
  const confirm = useConfirm()
  const { t } = useI18n()
  return (teCanvis) => {
    if (!teCanvis) return Promise.resolve(true)
    return new Promise(resolve => confirm.require({
      group: GRUP_SORTIDA,
      message: t('common.unsavedChangesPrompt'),
      header: t('common.unsavedChangesTitle'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.closeAnyway'),
      rejectLabel: t('common.cancel'),
      accept: () => resolve(true),
      reject: () => resolve(false),
      onHide: () => resolve(false)
    }))
  }
}

// Tancar o recarregar la pestanya amb canvis sense desar: avís del navegador
// (l'únic que es pot mostrar en aquest moment)
export function useAvisTancarPestanya(teCanvis) {
  const avisa = (event) => {
    if (!teCanvis()) return
    event.preventDefault()
    event.returnValue = ''
  }
  onMounted(() => window.addEventListener('beforeunload', avisa))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', avisa))
}
