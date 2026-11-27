import { avisaError, detallDError } from '../api/errors.js'
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import * as apiSubstitucions from '../api/substitucions.js'
import { dataIso } from '../dates.js'
import { avisaSubstitutsTrets } from '../substitutsTrets.js'

// Estat i operacions d'absències; els canvis del dia es recarreguen a la vista.
export function useAbsenciesSubstitucions({ dataISO, professors, absenciesCobertes, totesAbsencies, horesDisponibles, loading, toast, t, confirmaEsborrar, obreSiConflicte, carregarSubstitucions, carregarTotesAbsencies }) {
  const mostrarDialogGestio = ref(false)
  const dropdownProfValue = ref(null)
  const gestioAbsencies = ref({
    professor: null,
    professorSearch: '',
    horesAbsencia: [],
    horesServei: []
  })
  const horesAmbClasse = ref([])
  const horesAlCentre = ref([])
  const horesCarregades = ref(false)
  const modeRang = ref(false)
  const dataFinalRang = ref('')

  const ddmm = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

  const professorsAmbInfo = computed(() => {
    const absenciesReals = absenciesDelDia.value
    const professorsAmbAbsencies = new Set(absenciesReals.map(sub => sub.professor_absent))

    return [
      ...professors.value.map(prof => ({
        nom: prof,
        teAbsencies: professorsAmbAbsencies.has(prof),
        numHores: absenciesReals.filter(sub => sub.professor_absent === prof).length,
        coberta: false
      })),
      ...absenciesCobertes.value.map(a => ({
        nom: a.professor,
        teAbsencies: false,
        numHores: 0,
        coberta: true,
        finsA: a.data_final ? ddmm(a.data_final) : null
      }))
    ]
  })

  // La fila del vigilant absent (la seva vigilància queda sense vigilant)
  const esVigilanciaAbsent = (sub) => (sub.tipus_absencia || '').toUpperCase() === 'VIGILANCIA_ABSENT'

  // Les absències del professor (absència, servei o vigilant absent): ni la classe
  // que deixa un vigilant (VIGILANCIA) ni les encadenades
  const esAbsencia = (sub) => !['VIGILANCIA', 'VIGILÀNCIA', 'ENCADENADA'].includes((sub.tipus_absencia || '').toUpperCase())

  // Les hores d'absència (també les de vigilant absent) i de servei d'un professor
  const horesDe = (professor) => {
    const absProf = absenciesDelDia.value.filter(a => a.professor_absent === professor)
    return {
      horesAbsencia: absProf.filter(a => a.tipus_absencia === 'ABSENCIA' || esVigilanciaAbsent(a)).map(a => a.hora),
      horesServei: absProf.filter(a => a.tipus_absencia === 'SERVEI').map(a => a.hora)
    }
  }

  const absenciesDelDia = computed(() => {
    return totesAbsencies.value
      .filter(esAbsencia)
      .sort((a, b) => {
        const ia = horesDisponibles.value.indexOf(a.hora)
        const ib = horesDisponibles.value.indexOf(b.hora)
        if (ia !== ib) return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
        return (a.professor_absent || '').localeCompare(b.professor_absent || '')
      })
  })

  const absenciesDelDiaAgrupades = computed(() => {
    const grups = {}
    for (const abs of absenciesDelDia.value) {
      const prof = abs.professor_absent
      if (!grups[prof]) grups[prof] = { professor: prof, horesAbsencia: [], horesServei: [] }
      const tipus = (abs.tipus_absencia || '').toUpperCase()
      if (tipus === 'SERVEI') grups[prof].horesServei.push(abs.hora)
      else grups[prof].horesAbsencia.push(abs.hora)
    }
    return Object.values(grups).sort((a, b) => a.professor.localeCompare(b.professor))
  })

  const seleccionarProfessorDropdown = (event) => {
    if (event.value) {
      seleccionarProfessor(event.value)
    }
  }

  const datesDelRang = computed(() => {
    if (!modeRang.value || !dataFinalRang.value) return [dataISO.value]
    const dates = []
    const fi = new Date(dataFinalRang.value + 'T00:00:00')
    let actual = new Date(dataISO.value + 'T00:00:00')
    while (actual <= fi) {
      const dow = actual.getDay()
      if (dow !== 0 && dow !== 6) dates.push(dataIso(actual))
      actual.setDate(actual.getDate() + 1)
    }
    return dates.length > 0 ? dates : [dataISO.value]
  })


  const obrirDialogNou = () => {
    gestioAbsencies.value = {
      professor: null,
      professorSearch: '',
      horesAbsencia: [],
      horesServei: []
    }
    mostrarDialogGestio.value = true
    document.body.style.overflow = 'hidden'
  }

  const confirmarEliminarAbsenciesProf = (professorNom) => {
    confirmaEsborrar({
      message: t('substitutions.confirm.deleteAllAbsencesMessage', { teacher: professorNom }),
      header: t('substitutions.confirm.deleteAbsenceTitle'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: () => eliminarTotesAbsenciesProf(professorNom)
    })
  }

  const eliminarTotesAbsenciesProf = async (professorNom) => {
    loading.value = true
    try {
      const data = dataISO.value
      const updatedAtMap = {}
      absenciesDelDia.value
        .filter(a => a.professor_absent === professorNom && !esVigilanciaAbsent(a))
        .forEach(a => { if (a.updated_at) updatedAtMap[a.hora] = a.updated_at })

      await apiSubstitucions.desaAbsencies(data, professorNom, {
        hores_absencia: [],
        hores_servei: [],
        updated_at_map: updatedAtMap
      }, { silent: true })

      toast.add({
        severity: 'success',
        summary: t('common.deleted'),
        detail: t('substitutions.messages.allAbsencesDeleted', { teacher: professorNom }),
        life: 3000
      })

      await carregarSubstitucions()
    } catch (error) {
      console.error('Error eliminant absències:', error)
      if (obreSiConflicte(error, () => apiSubstitucions.desaAbsencies(dataISO.value, professorNom, {
        hores_absencia: [], hores_servei: [], force: true
      }))) return
      avisaError(error, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('substitutions.errors.deleteAbsence'),
        life: 3000
      }))
    } finally {
      loading.value = false
    }
  }

  const editarAbsenciesProfessor = async (substitucio) => {
    const professorNom = substitucio.professor_absent
    await carregarTotesAbsencies()

    gestioAbsencies.value = { professor: professorNom, professorSearch: '', ...horesDe(professorNom) }
    dropdownProfValue.value = professorsAmbInfo.value.find(p => p.nom === professorNom) || null

    carregarHoresAmbClasse(professorNom)
    mostrarDialogGestio.value = true
    document.body.style.overflow = 'hidden'
  }

  const tancarDialogGestio = () => {
    mostrarDialogGestio.value = false
    gestioAbsencies.value = {
      professor: null,
      professorSearch: '',
      horesAbsencia: [],
      horesServei: []
    }
    dropdownProfValue.value = null
    horesAmbClasse.value = []
    horesAlCentre.value = []
    horesCarregades.value = false
    modeRang.value = false
    dataFinalRang.value = ''
    document.body.style.overflow = ''
  }

  // Funcions del bottom sheet
  const carregarHoresAmbClasse = async (professorNom) => {
    horesCarregades.value = false
    try {
      const resposta = await apiSubstitucions.horesProfessor(dataISO.value, professorNom)
      horesAmbClasse.value = resposta.hores_amb_classe
      horesAlCentre.value = resposta.hores_al_centre || []
    } catch {
      horesAmbClasse.value = []
      horesAlCentre.value = []
    } finally {
      horesCarregades.value = true
    }
  }

  const seleccionarProfessor = (prof) => {
    Object.assign(gestioAbsencies.value, { professor: prof.nom, professorSearch: '', ...horesDe(prof.nom) })
    carregarHoresAmbClasse(prof.nom)
  }


  const toggleHoraAbsencia = (hora) => {
    const idx = gestioAbsencies.value.horesAbsencia.indexOf(hora)
    if (idx === -1) gestioAbsencies.value.horesAbsencia.push(hora)
    else gestioAbsencies.value.horesAbsencia.splice(idx, 1)
  }

  const toggleHoraServei = (hora) => {
    const idx = gestioAbsencies.value.horesServei.indexOf(hora)
    if (idx === -1) gestioAbsencies.value.horesServei.push(hora)
    else gestioAbsencies.value.horesServei.splice(idx, 1)
  }

  const disponiblesPerAbsencia = computed(() =>
    horesDisponibles.value.filter(h => !gestioAbsencies.value.horesServei.includes(h))
  )
  const disponiblesPerServei = computed(() =>
    horesDisponibles.value.filter(h => !gestioAbsencies.value.horesAbsencia.includes(h))
  )
  const totesTriadesAbsencia = computed(() =>
    disponiblesPerAbsencia.value.length > 0 &&
    disponiblesPerAbsencia.value.every(h => gestioAbsencies.value.horesAbsencia.includes(h))
  )
  const totesTriadesServei = computed(() =>
    disponiblesPerServei.value.length > 0 &&
    disponiblesPerServei.value.every(h => gestioAbsencies.value.horesServei.includes(h))
  )

  const toggleTotesAbsencia = () => {
    if (totesTriadesAbsencia.value) {
      gestioAbsencies.value.horesAbsencia = []
    } else {
      gestioAbsencies.value.horesAbsencia = [...disponiblesPerAbsencia.value]
    }
  }
  const toggleTotesServei = () => {
    if (totesTriadesServei.value) {
      gestioAbsencies.value.horesServei = []
    } else {
      gestioAbsencies.value.horesServei = [...disponiblesPerServei.value]
    }
  }

  const afegirAbsenciaImmediata = async () => {
    if (!gestioAbsencies.value.professor) {
      toast.add({ severity: 'error', summary: t('common.error'), detail: t('substitutions.errors.selectTeacher'), life: 3000 })
      return
    }
    if (gestioAbsencies.value.horesAbsencia.length === 0 && gestioAbsencies.value.horesServei.length === 0) {
      toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('substitutions.dialogs.absences.hoursHint'), life: 3000 })
      return
    }

    const profNom = gestioAbsencies.value.professor
    const horesAbsencia = [...gestioAbsencies.value.horesAbsencia]
    const horesServei = [...gestioAbsencies.value.horesServei]

    loading.value = true
    try {
      const dates = datesDelRang.value

      if (dates.length === 1) {
        const data = dates[0]
        const updatedAtMap = {}
        absenciesDelDia.value
          .filter(a => a.professor_absent === profNom && !esVigilanciaAbsent(a))
          .forEach(a => { if (a.updated_at) updatedAtMap[a.hora] = a.updated_at })

        // Únic PUT multi-tipus: el backend processa ABSENCIA i SERVEI de forma independent
        const resposta = await apiSubstitucions.desaAbsencies(data, profNom, {
          hores_absencia: horesAbsencia,
          hores_servei: horesServei,
          updated_at_map: updatedAtMap
        }, { silent: true })

        toast.add({
          severity: 'success',
          summary: t('common.saved'),
          detail: t('substitutions.messages.absencesSaved', { teacher: profNom }),
          life: 2500
        })
        avisaSubstitutsTrets(toast, t, resposta?.substituts_trets)
        if (resposta?.vigilancies_desassignades > 0) {
          toast.add({
            severity: 'info',
            summary: t('substitutions.messages.vigilanciesUnassignedTitle'),
            detail: t('substitutions.messages.vigilanciesUnassignedDetail', { count: resposta.vigilancies_desassignades }, resposta.vigilancies_desassignades),
            life: 6000
          })
        }
        await carregarSubstitucions()
      } else {
        // Cada dia es desa per separat: si un falla, els altres es queden desats
        const resultats = await Promise.allSettled(dates.map(d =>
          apiSubstitucions.desaAbsencies(d, profNom, {
            hores_absencia: horesAbsencia,
            hores_servei: horesServei,
            updated_at_map: {}
          }, { silent: true })
        ))
        const desats = dates.filter((_, i) => resultats[i].status === 'fulfilled')
        const fallats = dates.flatMap((d, i) => resultats[i].status === 'rejected' ? [[d, resultats[i].reason]] : [])
        if (fallats.length) {
          toast.add({
            severity: 'error',
            summary: t('common.error'),
            detail: t('substitutions.range.partial', {
              desats: desats.map(ddmm).join(', ') || '—',
              fallats: fallats.map(([d, error]) => `${ddmm(d)} (${detallDError(error) || t('substitutions.errors.saveAbsences')})`).join('; ')
            }),
            life: 10000
          })
        } else {
          toast.add({
            severity: 'success',
            summary: t('common.saved'),
            detail: `${dates.length} ${t('substitutions.range.daysRegistered', { teacher: profNom })}`,
            life: 4000
          })
          modeRang.value = false
          dataFinalRang.value = ''
        }
        avisaSubstitutsTrets(toast, t, resultats.flatMap(r => r.value?.substituts_trets || []))
        await carregarSubstitucions()
      }
    } catch (error) {
      console.error('Error afegint absència:', error)
      if (obreSiConflicte(error, () => apiSubstitucions.desaAbsencies(dataISO.value, profNom, {
        hores_absencia: horesAbsencia, hores_servei: horesServei, force: true
      }))) return
      avisaError(error, () => toast.add({ severity: 'error', summary: t('common.error'), detail: detallDError(error) || t('substitutions.errors.saveAbsences'), life: 8000 }))
    } finally {
      loading.value = false
    }
  }


  // Quan les dades canvien (desa/elimina), sincronitzar els dos grids si hi ha professor seleccionat
  watch(absenciesDelDia, () => {
    if (!mostrarDialogGestio.value || !gestioAbsencies.value.professor) return
    Object.assign(gestioAbsencies.value, horesDe(gestioAbsencies.value.professor))
  })


  onBeforeUnmount(() => {
    document.body.style.overflow = ''
  })

  return { mostrarDialogGestio, dropdownProfValue, gestioAbsencies, horesAmbClasse, horesAlCentre, horesCarregades, modeRang, dataFinalRang, professorsAmbInfo, absenciesDelDiaAgrupades, seleccionarProfessorDropdown, datesDelRang, obrirDialogNou, confirmarEliminarAbsenciesProf, editarAbsenciesProfessor, tancarDialogGestio, toggleHoraAbsencia, toggleHoraServei, totesTriadesAbsencia, totesTriadesServei, toggleTotesAbsencia, toggleTotesServei, afegirAbsenciaImmediata }
}
