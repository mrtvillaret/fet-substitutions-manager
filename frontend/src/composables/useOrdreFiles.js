// L'ordre de les files de Vigilàncies: moure una fila dins del bloc de la seva
// hora (arrossegant-la o amb ↑/↓) i ressaltar les files noves o mogudes.
// Res no es reordena sol: l'ordre és el desat, i el canvien «Ordena» i això.
import { nextTick, ref } from 'vue'

const DURADA_RESSALTAT_MS = 4000

// Els ids d'un bloc amb `id` mogut a la posició `desti` (0 = la primera)
export const ambFilaMoguda = (ids, id, desti) => {
  const resta = ids.filter((x) => String(x) !== String(id))
  const posicio = Math.max(0, Math.min(desti, resta.length))
  return [...resta.slice(0, posicio), id, ...resta.slice(posicio)]
}

export const useOrdreFiles = () => {
  // Ids de les files ressaltades (acabades de crear o de canviar d'hora)
  const ressaltades = ref(new Set())

  // Ressalta la fila uns segons i hi desplaça la pantalla
  const ressalta = async (id) => {
    const clau = String(id)
    ressaltades.value = new Set([...ressaltades.value, clau])
    await nextTick()
    document.querySelector(`[data-fila-id="${CSS.escape(clau)}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    setTimeout(() => {
      const resta = new Set(ressaltades.value)
      resta.delete(clau)
      ressaltades.value = resta
    }, DURADA_RESSALTAT_MS)
  }

  return { ressaltades, ressalta }
}
