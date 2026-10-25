import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'

// En pantalles tàctils (sense ratolí per passar per damunt de la fila), les
// accions d'una fila surten en tocar-la (AccionsFila.vue): només les d'aquella
// fila, i en tocar-ne una altra canvien. Tocar un camp editable l'edita i no
// mostra les accions. A l'ordinador no fa res: les accions surten en passar-hi
// el ratolí (taules.css).

// El que es toca per editar, no per triar la fila
const CAMPS = 'input, textarea, select, button, a, label, .p-dropdown, .p-checkbox, .camp-desplegable, [contenteditable]'

export function useFilaTactil() {
  const tactil = ref(false)
  // { clau, element, x }: la clau identifica la fila; l'element (el <tr>) i la x
  // del toc situen les accions
  const activa = shallowRef(null)
  let consulta = null

  const actualitza = () => {
    tactil.value = consulta.matches
    if (!tactil.value) activa.value = null
  }

  onMounted(() => {
    consulta = window.matchMedia('(hover: none)')
    actualitza()
    consulta.addEventListener('change', actualitza)
  })
  onBeforeUnmount(() => consulta?.removeEventListener('change', actualitza))

  // event: el clic (o toc) dins de la fila; clau: la de la fila tocada
  const tocaFila = (event, clau) => {
    if (!tactil.value) return
    if (event.target.closest(CAMPS)) {
      activa.value = null
      return
    }
    const element = event.target.closest('tr')
    activa.value = activa.value?.clau === clau ? null : { clau, element, x: event.clientX }
  }

  const tanca = () => {
    activa.value = null
  }

  const esActiva = (clau) => activa.value?.clau === clau

  return { tactil, activa, tocaFila, tanca, esActiva }
}
