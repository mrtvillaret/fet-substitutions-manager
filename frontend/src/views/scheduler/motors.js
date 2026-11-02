// Els valors per defecte dels paràmetres d'un motor (GET /api/scheduler/motors)
// que la pantalla copia a la petició de generar: només els que s'hi poden
// canviar (els que tenen etiqueta, param_labels). La resta, el motor els pren
// dels seus valors per defecte.
export function parametresDelMotor (meta) {
  const etiquetes = meta?.param_labels || {}
  return Object.fromEntries(Object.entries(meta?.params || {}).filter(([clau]) => clau in etiquetes))
}
