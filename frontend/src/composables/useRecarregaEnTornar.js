import { onMounted, onBeforeUnmount } from 'vue'
import { hiHaDesatsEnCurs } from '../api/desats.js'

// Quan la pestanya torna a ser visible (també en desbloquejar el mòbil) després
// d'haver estat oculta més d'aquest temps, es tornen a llegir les dades del dia.
const LLINDAR_RECARREGA_MS = 2 * 60 * 1000
// Si hi ha un canvi a mig fer, es torna a mirar cada tant fins que s'acaba
const TORNA_A_MIRAR_MS = 2000

// Un canvi a mig fer: un desplegable o un diàleg obert (també el full d'absències),
// un camp de text amb el focus (observacions sense desar) o un desat en curs.
const OBERTS = '.p-dropdown-panel, .p-multiselect-panel, .p-datepicker:not(.p-datepicker-inline), .p-dialog-mask, .bs-overlay'
const EDITANT = 'input:not([type="checkbox"]):not([type="radio"]):not([type="button"]), textarea, [contenteditable="true"]'
const hiHaUnCanviAMigFer = () =>
  hiHaDesatsEnCurs() || Boolean(document.querySelector(OBERTS)) || Boolean(document.activeElement?.matches?.(EDITANT))

// `recarrega()`: la càrrega del dia en silenci; `ocupada()`: si la pantalla té
// alguna cosa pròpia a mig fer (una càrrega, una selecció...).
export function useRecarregaEnTornar({ recarrega, ocupada }) {
  let amagadaDes = null
  let espera = null

  const intenta = () => {
    if (ocupada() || hiHaUnCanviAMigFer()) return false
    clearInterval(espera)
    espera = null
    recarrega()
    return true
  }

  const enCanviarVisibilitat = () => {
    if (document.visibilityState === 'hidden') {
      amagadaDes = Date.now()
      return
    }
    const haEstatOculta = amagadaDes !== null && Date.now() - amagadaDes > LLINDAR_RECARREGA_MS
    amagadaDes = null
    if (haEstatOculta && espera === null && !intenta()) espera = setInterval(intenta, TORNA_A_MIRAR_MS)
  }

  onMounted(() => document.addEventListener('visibilitychange', enCanviarVisibilitat))
  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', enCanviarVisibilitat)
    clearInterval(espera)
  })
}
