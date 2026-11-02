// Els costos desats dels professors (GET /api/scheduler/costos-professors:
// {costos_professors: {globals, individuals}}) damunt dels que mostra la
// pantalla. Sense resposta, els de la pantalla.
export function costosDesats (data, actuals) {
  const desats = data?.costos_professors || {}
  return {
    globals: { ...actuals.globals, ...(desats.globals || {}) },
    individuals: { ...(desats.individuals || actuals.individuals || {}) }
  }
}
