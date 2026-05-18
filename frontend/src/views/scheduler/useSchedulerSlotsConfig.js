export function useSchedulerSlotsConfig({
  horesPerNivell,
  horesPerNivellModel,
  slotsValidsPerNivell,
  horesGraella,
  llistaHoresDisponibles,
  diesSetmana,
}) {
  // Hores per la graella d'un nivell específic
  const getHoresGraellaPerNivell = (nivell) => {
    const horesNivell = horesPerNivell.value[nivell]
    if (horesNivell && horesNivell.length > 0) {
      return llistaHoresDisponibles.value.filter((h) => horesNivell.includes(h))
    }
    // Si no té hores específiques, usa les globals
    return horesGraella.value
  }

  // Gestió d'hores per nivell
  const onHoresNivellChange = (nivell) => {
    const hores = horesPerNivellModel.value[nivell]
    const updated = { ...horesPerNivell.value }
    if (!hores || hores.length === 0) {
      delete updated[nivell]
    } else {
      updated[nivell] = [...hores]
    }
    horesPerNivell.value = updated
  }

  const resetHoresNivell = (nivell) => {
    const updated = { ...horesPerNivell.value }
    delete updated[nivell]
    horesPerNivell.value = updated
  }

  const isSlotEnabled = (dia, hora) => true

  const isSameSet = (a, b) => {
    if (a.size !== b.size) return false
    for (const v of a) {
      if (!b.has(v)) return false
    }
    return true
  }

  const getNivellSlotsSet = (nivell) => {
    const map = slotsValidsPerNivell.value || {}
    const set = map?.[nivell]
    return set instanceof Set ? set : null
  }

  const isSlotEnabledPerNivell = (nivell, dia, hora) => {
    if (!isSlotEnabled(dia, hora)) return false
    if (!nivell) return false
    const set = getNivellSlotsSet(nivell)
    if (!set) return true // Si no té config específica, tots els slots globals estan habilitats
    return set.has(`${dia}-${hora}`)
  }

  // Construeix el set de slots base per un nivell (segons les seves hores)
  const buildNivellSlotsSet = (nivell) => {
    const set = new Set()
    const hores = getHoresGraellaPerNivell(nivell)
    hores.forEach((hora) => {
      diesSetmana.forEach((dia) => {
        if (isSlotEnabled(dia, hora)) {
          set.add(`${dia}-${hora}`)
        }
      })
    })
    return set
  }

  const toggleNivellSlot = (nivell, dia, hora) => {
    if (!nivell) return
    if (!isSlotEnabled(dia, hora)) return // No es pot activar un slot bloquejat globalment

    const map = slotsValidsPerNivell.value || {}
    let set = map[nivell]
    if (!(set instanceof Set)) {
      // Inicialitza amb tots els slots globals habilitats per les hores d'aquest nivell
      set = buildNivellSlotsSet(nivell)
    }
    const key = `${dia}-${hora}`
    if (set.has(key)) set.delete(key)
    else set.add(key)

    const updated = { ...map }
    const baseSet = buildNivellSlotsSet(nivell)
    if (isSameSet(set, baseSet)) {
      delete updated[nivell] // Si és igual al base, no cal guardar-ho
    } else {
      updated[nivell] = set
    }
    slotsValidsPerNivell.value = updated
  }

  const resetNivellSlots = (nivell) => {
    if (!nivell) return
    const updated = { ...(slotsValidsPerNivell.value || {}) }
    delete updated[nivell]
    slotsValidsPerNivell.value = updated
  }

  const serialitzarSlotsValidsPerNivell = () => {
    const payload = {}
    const map = slotsValidsPerNivell.value || {}
    Object.entries(map).forEach(([nivell, set]) => {
      if (!(set instanceof Set)) return
      const perDia = {}
      set.forEach((key) => {
        const [dia, hora] = key.split('-')
        if (!perDia[dia]) perDia[dia] = []
        perDia[dia].push(hora)
      })
      Object.keys(perDia).forEach((dia) => {
        perDia[dia] = Array.from(new Set(perDia[dia]))
      })
      payload[nivell] = perDia
    })
    return payload
  }

  return {
    getHoresGraellaPerNivell,
    onHoresNivellChange,
    resetHoresNivell,
    isSlotEnabledPerNivell,
    toggleNivellSlot,
    resetNivellSlots,
    serialitzarSlotsValidsPerNivell,
  }
}
