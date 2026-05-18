import { ref, computed, watch } from 'vue'
import { useConfirm } from 'primevue/useconfirm'

export const useAlliberamentsPerNivell = ({
  t,
  locale,
  genConfig,
  config,
  selectedDates,
  configReady,
  scheduleConfigSave,
  llistaHoresDisponibles,
  formatDateLocal,
  parseIsoLocal,
  isSameDay,
}) => {
  const alliberamentsPerNivell = ref({})

  const resolveLocale = () => {
    const code = locale?.value || locale || 'ca'
    if (code === 'es') return 'es-ES'
    if (code === 'en') return 'en-GB'
    return 'ca-ES'
  }

  const datesPerNivellModel = computed(() => {
    const result = {}
    for (const nivell of (genConfig.value?.nivells_actius || [])) {
      const data = alliberamentsPerNivell.value[nivell]
      result[nivell] = data?.dates || []
    }
    return result
  })

  const datesSeleccionadesDesDeNivells = () => {
    const set = new Set()
    const nivellsActius = genConfig.value?.nivells_actius || []
    nivellsActius.forEach((nivell) => {
      const dates = alliberamentsPerNivell.value[nivell]?.dates || []
      dates.forEach((date) => {
        const iso = formatDateLocal(date)
        if (iso) set.add(iso)
      })
    })
    return Array.from(set).sort().map(parseIsoLocal).filter(Boolean)
  }

  const sincronitzarDatesGlobals = () => {
    const derivades = datesSeleccionadesDesDeNivells()
    if (!derivades.length) return
    const actual = (selectedDates.value || []).map(formatDateLocal).filter(Boolean).sort()
    const target = derivades.map(formatDateLocal).filter(Boolean).sort()
    if (actual.length === target.length && actual.every((d, i) => d === target[i])) return
    selectedDates.value = derivades
  }

  const formatDataCurta = (dataStr) => {
    const parts = dataStr.split('-')
    const date = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10))
    const weekdayShort = new Intl.DateTimeFormat(resolveLocale(), { weekday: 'short' })
      .format(date)
      .replace('.', '')
    return `${date.getDate()} ${weekdayShort}`
  }

  const cloneAlliberaments = (obj) => {
    const result = {}
    for (const [nivell, data] of Object.entries(obj || {})) {
      result[nivell] = {
        dates: [...(data.dates || [])],
        durada: data.durada || 1,
        config: JSON.parse(JSON.stringify(data.config || {}))
      }
    }
    return result
  }

  const aplicarCanvisDates = (nivell, newDates, esborrarConfigEliminades) => {
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]) updated[nivell] = { dates: [], durada: 1, config: {} }

    const oldDates = updated[nivell].dates || []
    if (esborrarConfigEliminades) {
      const removedDates = oldDates.filter((oldDate) => !newDates.some((newDate) => isSameDay(oldDate, newDate)))
      for (const removedDate of removedDates) {
        const dateStr = formatDateLocal(removedDate)
        if (dateStr && updated[nivell].config[dateStr]) {
          delete updated[nivell].config[dateStr]
        }
      }
    }

    const addedDates = newDates.filter((newDate) => !oldDates.some((oldDate) => isSameDay(oldDate, newDate)))
    for (const addedDate of addedDates) {
      const dateStr = formatDateLocal(addedDate)
      if (dateStr && !updated[nivell].config[dateStr]) {
        updated[nivell].config[dateStr] = {}
      }
    }

    updated[nivell].dates = newDates.map((date) => new Date(date.getTime()))
    alliberamentsPerNivell.value = updated
  }

  const confirm = useConfirm()
  const onDatesChange = (nivell, newDates) => {
    const oldDates = alliberamentsPerNivell.value[nivell]?.dates || []
    const removedDates = oldDates.filter((oldDate) => !newDates.some((newDate) => isSameDay(oldDate, newDate)))

    const datesAmbConfig = removedDates.filter((removedDate) => {
      const dateStr = formatDateLocal(removedDate)
      const cfg = alliberamentsPerNivell.value[nivell]?.config?.[dateStr]
      return cfg && Object.values(cfg).some((cell) => cell.a || cell.i)
    })

    if (datesAmbConfig.length > 0) {
      const dateStr = formatDateLocal(datesAmbConfig[0])
      confirm.require({
        message: t('scheduler.steps.config.confirm.deleteSavedConfigMessage', { day: formatDataCurta(dateStr) }),
        header: t('common.confirmation'),
        icon: 'pi pi-exclamation-triangle',
        acceptLabel: t('common.delete'),
        rejectLabel: t('common.cancel'),
        accept: () => aplicarCanvisDates(nivell, newDates, true),
        reject: () => {},
      })
    } else {
      aplicarCanvisDates(nivell, newDates, true)
    }
  }

  const getDatesPerNivellOrdenades = (nivell) => {
    const data = alliberamentsPerNivell.value[nivell]
    if (!data?.dates?.length) return []
    return [...data.dates]
      .map((date) => formatDateLocal(date))
      .filter((date) => date !== null)
      .sort()
  }

  const isAlliberat = (nivell, data, hora) => {
    const cfg = alliberamentsPerNivell.value[nivell]?.config?.[data]?.[hora]
    return cfg?.a === true
  }

  const isIniciExamen = (nivell, data, hora) => {
    const cfg = alliberamentsPerNivell.value[nivell]?.config?.[data]?.[hora]
    return cfg?.i === true
  }

  const toggleAlliberat = (nivell, data, hora) => {
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]) updated[nivell] = { dates: [], durada: 1, config: {} }
    if (!updated[nivell].config[data]) updated[nivell].config[data] = {}
    if (!updated[nivell].config[data][hora]) updated[nivell].config[data][hora] = { a: false, i: false }

    const cell = updated[nivell].config[data][hora]
    cell.a = !cell.a
    if (!cell.a) cell.i = false

    alliberamentsPerNivell.value = updated
  }

  const toggleIniciExamen = (nivell, data, hora) => {
    if (!isAlliberat(nivell, data, hora)) return

    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]?.config?.[data]?.[hora]) return

    const cell = updated[nivell].config[data][hora]
    cell.i = !cell.i
    if (cell.i) cell.a = true

    alliberamentsPerNivell.value = updated
  }

  const eliminarDataNivell = (nivell, eventOrStr, esborrarConfig) => {
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]) return

    const dateStr = eventOrStr instanceof Date ? formatDateLocal(eventOrStr) : eventOrStr
    if (eventOrStr instanceof Date) {
      updated[nivell].dates = updated[nivell].dates.filter((date) => !isSameDay(date, eventOrStr))
    } else {
      updated[nivell].dates = updated[nivell].dates.filter((date) => formatDateLocal(date) !== dateStr)
    }

    if (esborrarConfig && updated[nivell].config && dateStr) {
      delete updated[nivell].config[dateStr]
    }

    alliberamentsPerNivell.value = updated
  }

  const menuFila = ref()
  const menuColumna = ref()
  const menuContext = ref({ nivell: '', data: '', hora: '' })

  const accioFilaTotAlliberat = () => {
    const { nivell, data } = menuContext.value
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]) return
    if (!updated[nivell].config[data]) updated[nivell].config[data] = {}
    for (const hora of llistaHoresDisponibles.value) {
      updated[nivell].config[data][hora] = { a: true, i: false }
    }
    alliberamentsPerNivell.value = updated
  }

  const accioFilaTotAmbInici = () => {
    const { nivell, data } = menuContext.value
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]) return
    if (!updated[nivell].config[data]) updated[nivell].config[data] = {}
    for (const hora of llistaHoresDisponibles.value) {
      updated[nivell].config[data][hora] = { a: true, i: true }
    }
    alliberamentsPerNivell.value = updated
  }

  const accioFilaNetejar = () => {
    const { nivell, data } = menuContext.value
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]?.config?.[data]) return
    for (const hora of Object.keys(updated[nivell].config[data])) {
      updated[nivell].config[data][hora] = { a: false, i: false }
    }
    alliberamentsPerNivell.value = updated
  }

  const accioFilaEliminar = () => {
    const { nivell, data } = menuContext.value
    eliminarDataNivell(nivell, data, true)
  }

  const accioColumnaTotAlliberat = () => {
    const { nivell, hora } = menuContext.value
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]) return
    for (const data of getDatesPerNivellOrdenades(nivell)) {
      if (!updated[nivell].config[data]) updated[nivell].config[data] = {}
      updated[nivell].config[data][hora] = { a: true, i: false }
    }
    alliberamentsPerNivell.value = updated
  }

  const accioColumnaTotAmbInici = () => {
    const { nivell, hora } = menuContext.value
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]) return
    for (const data of getDatesPerNivellOrdenades(nivell)) {
      if (!updated[nivell].config[data]) updated[nivell].config[data] = {}
      updated[nivell].config[data][hora] = { a: true, i: true }
    }
    alliberamentsPerNivell.value = updated
  }

  const accioColumnaNetejar = () => {
    const { nivell, hora } = menuContext.value
    const updated = cloneAlliberaments(alliberamentsPerNivell.value)
    if (!updated[nivell]?.config) return
    for (const data of getDatesPerNivellOrdenades(nivell)) {
      if (updated[nivell].config[data]?.[hora]) {
        updated[nivell].config[data][hora] = { a: false, i: false }
      }
    }
    alliberamentsPerNivell.value = updated
  }

  const menuFilaItems = computed(() => ([
    { label: `🟩 ${t('scheduler.steps.config.menu.allReleased')}`, icon: 'pi pi-check-square', command: () => accioFilaTotAlliberat() },
    { label: `🟩🟦 ${t('scheduler.steps.config.menu.releasedAndStart')}`, icon: 'pi pi-check-square', command: () => accioFilaTotAmbInici() },
    { label: `✖ ${t('scheduler.steps.config.menu.clearRow')}`, icon: 'pi pi-times', command: () => accioFilaNetejar() },
    { separator: true },
    { label: `❌ ${t('scheduler.steps.config.menu.deleteDay')}`, icon: 'pi pi-trash', command: () => accioFilaEliminar() }
  ]))

  const menuColumnaItems = computed(() => ([
    { label: `🟩 ${t('scheduler.steps.config.menu.allReleased')}`, icon: 'pi pi-check-square', command: () => accioColumnaTotAlliberat() },
    { label: `🟩🟦 ${t('scheduler.steps.config.menu.releasedAndStart')}`, icon: 'pi pi-check-square', command: () => accioColumnaTotAmbInici() },
    { label: `✖ ${t('scheduler.steps.config.menu.clearColumn')}`, icon: 'pi pi-times', command: () => accioColumnaNetejar() }
  ]))

  const mostrarMenuFila = (event, nivell, data) => {
    menuContext.value = { nivell, data, hora: '' }
    menuFila.value.toggle(event)
  }

  const mostrarMenuColumna = (event, nivell, hora) => {
    menuContext.value = { nivell, data: '', hora }
    menuColumna.value.toggle(event)
  }

  watch([alliberamentsPerNivell, () => genConfig.value?.nivells_actius], () => {
    sincronitzarDatesGlobals()
    if (!configReady.value) return
    scheduleConfigSave()
  }, { deep: true })

  return {
    alliberamentsPerNivell,
    datesPerNivellModel,
    sincronitzarDatesGlobals,
    onDatesChange,
    getDatesPerNivellOrdenades,
    formatDataCurta,
    isAlliberat,
    isIniciExamen,
    toggleAlliberat,
    toggleIniciExamen,
    menuFila,
    menuColumna,
    menuFilaItems,
    menuColumnaItems,
    mostrarMenuFila,
    mostrarMenuColumna,
  }
}
