// Desar les restriccions sense perdre el que la pantalla no coneix: les claus que no
// edita (de les restriccions dures, les preferències i els pesos) es tornen a enviar tal com
// es van carregar, i també el pes (`_pes_<assignatura>`) dels exàmens que continuen fixats.
const CLAUS_FIXES = ['assignatures_dia_fix', 'assignatures_hora_fix']

export function ambElQueNoConeix(carregades, noves) {
  const abans = carregades || {}
  const duresAbans = abans.restriccions_dures || {}
  const dures = { ...duresAbans, ...noves.restriccions_dures }
  for (const clau of CLAUS_FIXES) {
    const fixades = { ...(noves.restriccions_dures?.[clau] || {}) }
    for (const [k, v] of Object.entries(duresAbans[clau] || {})) {
      if (k.startsWith('_pes_') && k.slice(5) in fixades) fixades[k] = v
    }
    dures[clau] = fixades
  }
  return {
    ...abans,
    ...noves,
    restriccions_dures: dures,
    preferencies: { ...(abans.preferencies || {}), ...noves.preferencies },
    pesos_optimitzacio: { ...(abans.pesos_optimitzacio || {}), ...noves.pesos_optimitzacio }
  }
}
