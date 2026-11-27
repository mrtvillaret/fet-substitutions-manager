import { ref } from 'vue'

// El diàleg de conflicte (409 amb la versió actual: algú altre ha canviat les
// dades): «Recarrega» les torna a llegir; «Sobreescriu» repeteix el desat amb
// `force` i després recarrega.
export function useConflicte(recarrega) {
  const mostrarDialogConflicte = ref(false)
  let sobreescriu = null

  // Si l'error és un conflicte, obre el diàleg; sobreescriure crida
  // `reintenta(versioActual)`. Retorna si ho era.
  const obreSiConflicte = (error, reintenta) => {
    const actual = error?.response?.status === 409 && error.response.data?.detail?.current_data
    if (!actual) return false
    sobreescriu = async () => {
      await reintenta(actual)
      await recarrega()
    }
    mostrarDialogConflicte.value = true
    return true
  }

  const gestionarConflicte = () => recarrega()
  const executarOverwrite = async () => {
    if (sobreescriu) await sobreescriu()
  }

  return { mostrarDialogConflicte, obreSiConflicte, gestionarConflicte, executarOverwrite }
}
