import { avisaError, detallDError } from '../errorsApi.js'
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import * as apiSubstitucions from '../api/substitucions.js'
import { dataIso } from '../dates.js'
import { avisaSubstitutsTrets } from '../substitutsTrets.js'

// Estat i operacions d'absències; els canvis del dia es recarreguen a la vista.
export function useAbsenciesSubstitucions({ dataISO, professors, absenciesCobertes, totesAbsencies, horesDisponibles, loading, toast, t, confirmaEsborrar, obrirDialogConflicte, carregarSubstitucions, carregarTotesAbsencies }) {
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

  const professorsAmbInfo = computed(() => {
    // Detectar quins professors tenen absències REALS (excloent vigilàncies tècniques i forats)
    const absenciesReals = totesAbsencies.value.filter(sub => {
      const tipus = (sub.tipus_absencia || "").toUpperCase();
      return !["VIGILANCIA", "VIGILÀNCIA", "ENCADENADA"].includes(tipus);
    });

    const professorsAmbAbsencies = new Set(
      absenciesReals.map(sub => sub.professor_absent)
    );

    const finsA = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : null)  // dd/mm
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
        finsA: finsA(a.data_final)
      }))
    ]
  })

  // Detecta si una sub és Tipus A VIGILANCIA_ABSENT (vigilant absent → slot descobert)
  const esVigilanciaAbsent = (sub) => (sub.tipus_absencia || '').toUpperCase() === 'VIGILANCIA_ABSENT'

  const absenciesDelDia = computed(() => {
    return totesAbsencies.value
      .filter(a => {
        const tipus = (a.tipus_absencia || '').toUpperCase()
        if (tipus === 'ENCADENADA') return false
        if (tipus === 'VIGILANCIA') return esVigilanciaAbsent(a) // Inclou Tipus A, exclou Tipus B
        return true
      })
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
      const isoLocal = dataIso
    const dates = []
    const fi = new Date(dataFinalRang.value + 'T00:00:00')
    let actual = new Date(dataISO.value + 'T00:00:00')
    while (actual <= fi) {
      const dow = actual.getDay()
      if (dow !== 0 && dow !== 6) dates.push(isoLocal(actual))
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
      if (error.response?.status === 409) {
        obrirDialogConflicte(async () => {
          await apiSubstitucions.desaAbsencies(dataISO.value, professorNom, {
            hores_absencia: [],
            hores_servei: [],
            force: true
          })
          await carregarSubstitucions()
        })
        return
      }
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

    const absProf = totesAbsencies.value.filter(a => {
      const tipus = (a.tipus_absencia || '').toUpperCase()
      if (a.professor_absent !== professorNom) return false
      if (tipus === 'ENCADENADA') return false
      if (tipus === 'VIGILANCIA') return esVigilanciaAbsent(a) // Inclou Tipus A, exclou Tipus B
      return true
    })
    // Hores ABSENCIA + hores on el vigilant és absent (Tipus A VIGILANCIA)
    const horesAbsencia = absProf
      .filter(a => a.tipus_absencia === 'ABSENCIA' || esVigilanciaAbsent(a))
      .map(a => a.hora)
    gestioAbsencies.value = {
      professor: professorNom,
      professorSearch: '',
      horesAbsencia,
      horesServei: absProf.filter(a => a.tipus_absencia === 'SERVEI').map(a => a.hora)
    }
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
    const absProf = absenciesDelDia.value.filter(a => a.professor_absent === prof.nom)
    gestioAbsencies.value.professor = prof.nom
    gestioAbsencies.value.professorSearch = ''
    gestioAbsencies.value.horesAbsencia = absProf.filter(a => a.tipus_absencia === 'ABSENCIA' || esVigilanciaAbsent(a)).map(a => a.hora)
    gestioAbsencies.value.horesServei = absProf.filter(a => a.tipus_absencia === 'SERVEI').map(a => a.hora)
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
  const totesTrnadesAbsencia = computed(() =>
    disponiblesPerAbsencia.value.length > 0 &&
    disponiblesPerAbsencia.value.every(h => gestioAbsencies.value.horesAbsencia.includes(h))
  )
  const totesTrnadesServei = computed(() =>
    disponiblesPerServei.value.length > 0 &&
    disponiblesPerServei.value.every(h => gestioAbsencies.value.horesServei.includes(h))
  )

  const toggleTotesAbsencia = () => {
    if (totesTrnadesAbsencia.value) {
      gestioAbsencies.value.horesAbsencia = []
    } else {
      gestioAbsencies.value.horesAbsencia = [...disponiblesPerAbsencia.value]
    }
  }
  const toggleTotesServei = () => {
    if (totesTrnadesServei.value) {
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
        const respostes = await Promise.all(dates.map(d =>
          apiSubstitucions.desaAbsencies(d, profNom, {
            hores_absencia: horesAbsencia,
            hores_servei: horesServei,
            updated_at_map: {}
          })
        ))
        toast.add({
          severity: 'success',
          summary: t('common.saved'),
          detail: `${dates.length} ${t('substitutions.range.daysRegistered', { teacher: profNom })}`,
          life: 4000
        })
        avisaSubstitutsTrets(toast, t, respostes.flatMap(r => r?.substituts_trets || []))
        modeRang.value = false
        dataFinalRang.value = ''
        await carregarSubstitucions()
      }
    } catch (error) {
      console.error('Error afegint absència:', error)
      if (error.response?.status === 409) {
        obrirDialogConflicte(async () => {
          const d = dataISO.value
          await apiSubstitucions.desaAbsencies(d, profNom, {
            hores_absencia: horesAbsencia,
            hores_servei: horesServei,
            force: true
          })
          await carregarSubstitucions()
        })
        return
      }
      avisaError(error, () => toast.add({ severity: 'error', summary: t('common.error'), detail: (typeof detallDError(error) === 'string' && detallDError(error)) || t('substitutions.errors.saveAbsences'), life: 8000 }))
    } finally {
      loading.value = false
    }
  }


  // Quan les dades canvien (desa/elimina), sincronitzar els dos grids si hi ha professor seleccionat
  watch(absenciesDelDia, () => {
    if (!mostrarDialogGestio.value || !gestioAbsencies.value.professor) return
    const prof = gestioAbsencies.value.professor
    const absProf = absenciesDelDia.value.filter(a => a.professor_absent === prof)
    gestioAbsencies.value.horesAbsencia = absProf.filter(a => a.tipus_absencia === 'ABSENCIA' || esVigilanciaAbsent(a)).map(a => a.hora)
    gestioAbsencies.value.horesServei = absProf.filter(a => a.tipus_absencia === 'SERVEI').map(a => a.hora)
  })


  onBeforeUnmount(() => {
    document.body.style.overflow = ''
  })

  return { mostrarDialogGestio, dropdownProfValue, gestioAbsencies, horesAmbClasse, horesAlCentre, horesCarregades, modeRang, dataFinalRang, professorsAmbInfo, esVigilanciaAbsent, absenciesDelDia, absenciesDelDiaAgrupades, seleccionarProfessorDropdown, datesDelRang, obrirDialogNou, confirmarEliminarAbsenciesProf, eliminarTotesAbsenciesProf, editarAbsenciesProfessor, tancarDialogGestio, carregarHoresAmbClasse, seleccionarProfessor, toggleHoraAbsencia, toggleHoraServei, disponiblesPerAbsencia, disponiblesPerServei, totesTrnadesAbsencia, totesTrnadesServei, toggleTotesAbsencia, toggleTotesServei, afegirAbsenciaImmediata }
}
