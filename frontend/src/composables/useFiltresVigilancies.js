import { ref, computed, watch } from 'vue'

// Extret de la vista: es preserven estat, efectes i ordre de les operacions.
export function useFiltresVigilancies({ vigilancies, aules, collator, t }) {
  const allLabel = computed(() => t('common.all'))

  const statusAssignedLabel = computed(() => t('vigilancies.stats.assigned'))

  const statusPendingLabel = computed(() => t('vigilancies.stats.pending'))

  const statusOptions = computed(() => [
    allLabel.value,
    statusAssignedLabel.value,
    statusPendingLabel.value
  ])

  const filtreLevell = ref(allLabel.value)

  const filtreHora = ref(allLabel.value)

  const filtreEstat = ref(allLabel.value)

  const filtreAula = ref(allLabel.value)

  const etiquetaFiltre = (clau, valor) =>
    !valor || valor === allLabel.value
      ? t(`vigilancies.filters.${clau}All`)
      : t(`vigilancies.filters.${clau}Value`, { valor })

  const filtresActius = computed(() =>
    [filtreLevell.value, filtreHora.value, filtreEstat.value, filtreAula.value].some(f => f && f !== allLabel.value)
  )

  watch(allLabel, (newVal, oldVal) => {
    if (filtreLevell.value === oldVal) {
      filtreLevell.value = newVal
    }
    if (filtreHora.value === oldVal) {
      filtreHora.value = newVal
    }
    if (filtreEstat.value === oldVal) {
      filtreEstat.value = newVal
    }
    if (filtreAula.value === oldVal) {
      filtreAula.value = newVal
    }
  })

  const vigilanciesAssignades = computed(() =>
    vigilanciesFiltrades.value.filter(v => v.vigilant && v.vigilant.trim()).length
  )

  const vigilanciesPendents = computed(() =>
    vigilanciesFiltrades.value.filter(v => !v.vigilant || !v.vigilant.trim()).length
  )

  const vigilanciesFiltrades = computed(() => {
    let result = vigilancies.value

    if (filtreLevell.value && filtreLevell.value !== allLabel.value) {
      result = result.filter(v => v.nivell === filtreLevell.value)
    }
    if (filtreHora.value && filtreHora.value !== allLabel.value) {
      result = result.filter(v => v.hora === filtreHora.value)
    }
    if (filtreEstat.value === statusAssignedLabel.value) {
      result = result.filter(v => v.vigilant && v.vigilant.trim())
    } else if (filtreEstat.value === statusPendingLabel.value) {
      result = result.filter(v => !v.vigilant || !v.vigilant.trim())
    }
    if (filtreAula.value && filtreAula.value !== allLabel.value) {
      result = result.filter(v => v.aula === filtreAula.value)
    }
    return result
  })

  const aulesDelFiltre = computed(() =>
    [...new Set([...aules.value, ...vigilancies.value.map(v => v.aula)].filter(Boolean))]
      .sort((a, b) => collator.value.compare(a, b))
  )

  return { allLabel, statusOptions, filtreLevell, filtreHora, filtreEstat, filtreAula, etiquetaFiltre, filtresActius, vigilanciesAssignades, vigilanciesPendents, vigilanciesFiltrades, aulesDelFiltre }
}
