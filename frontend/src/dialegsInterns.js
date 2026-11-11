// Diàlegs de dins de les pantalles (PDF, fitxa d'absències, formularis...).
// No s'escriuen a l'adreça (sense el seu context no es podrien tornar a obrir),
// però fan servir el mateix historial que els diàlegs de l'adreça
// (useAplicacio.js): obrir-ne un afegeix una entrada amb `history.state.intern`
// i «Enrere» el tanca com si es premés la creu. Cada pantalla registra els seus
// mentre és muntada.
import { shallowReactive, isRef, onBeforeUnmount } from 'vue'

// nom → { obert: () => bool, tanca: () => void }
export const dialegsInterns = shallowReactive(new Map())

// Registra un diàleg; retorna la funció que el treu (només si encara és el seu)
export function registraDialegIntern(nom, { obert, tanca }) {
  const dialeg = { obert, tanca }
  dialegsInterns.set(nom, dialeg)
  return () => {
    if (dialegsInterns.get(nom) === dialeg) dialegsInterns.delete(nom)
  }
}

// El nom del diàleg intern obert (o null)
export function dialegInternObert() {
  for (const [nom, dialeg] of dialegsInterns) if (dialeg.obert()) return nom
  return null
}

// Tanca el diàleg intern `nom`, si és obert (com la creu)
export function tancaDialegIntern(nom) {
  const dialeg = dialegsInterns.get(nom)
  if (dialeg?.obert()) dialeg.tanca()
}

// Des d'un component: { nom: refBooleà | { obert, tanca } }. Un ref es tanca
// posant-lo a false (el mateix que fa la creu amb v-model:visible).
export function useDialegsInterns(dialegs) {
  const treu = Object.entries(dialegs).map(([nom, dialeg]) => registraDialegIntern(nom, isRef(dialeg)
    ? { obert: () => dialeg.value, tanca: () => { dialeg.value = false } }
    : dialeg))
  onBeforeUnmount(() => treu.forEach(f => f()))
}
