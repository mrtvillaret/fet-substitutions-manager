import { avisaError } from '../errorsApi.js'
import { ref, computed, watch, onMounted, onBeforeUnmount, reactive } from 'vue'
import * as apiGrups from '../api/grups'
import { dataTreball } from '../dataTreball'
import { dataIso } from '../dates'
import { avisaSubstitutsTrets } from '../substitutsTrets'

export function useGrups(dependents) {
  const { t, locale, toast } = dependents

  const hores = ref([])
  const grupsDisponibles = ref([])
  const checkboxes = reactive({})
  const checkboxesOriginals = ref({})
  // Professors alliberats sense el seu grup: {hora: [professors]}
  const professorsPerGrupHora = ref({})
  const professorsAlliberats = reactive({})
  const professorsAlliberatsOriginals = ref({})
  // Reforços sense alumnes que un dia concret sí que en tenen: {hora: [professors]}
  const professorsOcupats = reactive({})
  const professorsOcupatsOriginals = ref({})
  const panellProfessors = ref(null)
  const franja = ref(null)
  // Activitats alliberables: {activitat: {hora: [professors]}} i les marcades aquell dia
  const activitatsPerHora = ref({})
  const activitatsMarcades = reactive({})
  const activitatsMarcadesOriginals = ref({})
  // Activitats alliberades fins que tenen alumnes (p.ex. Reforç)
  const activitatsPerDefecte = ref([])
  // ...i qui les fa aquell dia, amb l'estat: {activitat: {hora: [{professor, amb_alumnes}]}}
  const reforcsDelDia = ref({})
  const loading = ref(false)
  const desant = ref(false)
  const error = ref(null)

  // Dia carregat a la pantalla: és on es desa, encara que el calendari ja
  // marqui un altre dia (p.ex. si en canviar de dia s'ha triat «Cancel·la»).
  const dataCarregada = ref(dataTreball.value)

  const isoDe = dataIso

  const dataFormatada = computed(() => {
    return dataCarregada.value.toLocaleDateString(locale.value || 'ca-ES', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  })


  const professorsAlliberatsNets = () => {
    const nets = {}
    hores.value.forEach(hora => {
      const profs = [...(professorsAlliberats[hora] || [])].sort()
      if (profs.length) nets[hora] = profs
    })
    return nets
  }

  const professorsOcupatsNets = () => {
    const nets = {}
    hores.value.forEach(hora => {
      const profs = [...(professorsOcupats[hora] || [])].sort()
      if (profs.length) nets[hora] = profs
    })
    return nets
  }

  const estaOcupat = (prof, hora) => (professorsOcupats[hora] || []).includes(prof)

  const marcaOcupat = (prof, hora, valor) => {
    const actuals = (professorsOcupats[hora] || []).filter(p => p !== prof)
    professorsOcupats[hora] = valor ? [...actuals, prof] : actuals
  }

  const teCanvis = computed(() => {
    return JSON.stringify(professorsOcupatsNets()) !== JSON.stringify(professorsOcupatsOriginals.value) ||
      JSON.stringify(checkboxes) !== JSON.stringify(checkboxesOriginals.value) ||
      JSON.stringify(professorsAlliberatsNets()) !== JSON.stringify(professorsAlliberatsOriginals.value) ||
      JSON.stringify(activitatsMarcades) !== JSON.stringify(activitatsMarcadesOriginals.value)
  })

  const professorsDe = (grup, hora) => professorsPerGrupHora.value[hora]?.[grup] || []

  const activitatsNoms = computed(() => Object.keys(activitatsPerHora.value))

  const professorsActivitat = (act, hora) => activitatsPerHora.value[act]?.[hora] || []

  const professorsReforcAvui = (act, hora) => (reforcsDelDia.value[act]?.[hora] || []).map(r => r.professor)

  const reforcAmbAlumnes = (act, hora, prof) =>
    (reforcsDelDia.value[act]?.[hora] || []).some(r => r.professor === prof && r.amb_alumnes)

  const professorsFranja = (f) => {
    if (f.tipus === 'activitat') return professorsActivitat(f.nom, f.hora)
    if (f.tipus === 'reforc') return professorsReforcAvui(f.nom, f.hora)
    return professorsDe(f.nom, f.hora)
  }

  const dataCurta = (iso) => {
    const [y, m, d] = (iso || '').split('-')
    return d ? `${d}/${m}/${y}` : ''
  }

  const estaAlliberat = (prof, hora) => (professorsAlliberats[hora] || []).includes(prof)

  const alliberatsDe = (grup, hora) => professorsDe(grup, hora).filter(prof => estaAlliberat(prof, hora))

  // Lliure aquell dia: amb alumnes i alliberat aquell dia, o sense alumnes i no ocupat aquell dia
  const lliureReforcAvui = (act, hora, prof) =>
    reforcAmbAlumnes(act, hora, prof) ? estaAlliberat(prof, hora) : !estaOcupat(prof, hora)

  // Els que aquell dia canvien respecte del seu estat (per destacar la icona)
  const alliberatsReforcAvui = (act, hora) =>
    professorsReforcAvui(act, hora).filter(prof =>
      reforcAmbAlumnes(act, hora, prof) ? estaAlliberat(prof, hora) : estaOcupat(prof, hora))

  const lliuresReforcAvui = (act, hora) =>
    professorsReforcAvui(act, hora).filter(prof => lliureReforcAvui(act, hora, prof)).length

  const alliberatsActivitat = (act, hora) =>
    professorsActivitat(act, hora).filter(prof => estaAlliberat(prof, hora))

  const marcaProfessor = (prof, hora, valor) => {
    const actuals = (professorsAlliberats[hora] || []).filter(p => p !== prof)
    professorsAlliberats[hora] = valor ? [...actuals, prof] : actuals
  }

  const treureProfessor = (prof) => {
    for (const hora in professorsAlliberats) {
      professorsAlliberats[hora] = professorsAlliberats[hora].filter(p => p !== prof)
    }
  }

  const obrirProfessors = (event, tipus, nom, hora) => {
    franja.value = { tipus, nom, hora }
    panellProfessors.value.toggle(event)
  }

  // Un xip per professor amb les seves hores, en l'ordre de l'horari
  const resumProfessors = computed(() => {
    const perProfessor = {}
    hores.value.forEach(hora => {
      (professorsAlliberats[hora] || []).forEach(prof => {
        (perProfessor[prof] ||= []).push(hora)
      })
    })
    return Object.keys(perProfessor).sort().map(professor => ({ professor, hores: perProfessor[professor] }))
  })

  // ===== Reforços: franges amb alumnes a partir d'un dia =====
  const reforc = reactive({
    visible: false, activitat: '', professor: null, data: '',
    dies: [], hores: [], professors: {}, desant: false, nomesPendents: false,
    vista: 'professor'   // 'professor' (desplegable i graella) o 'setmana' (hores × dies)
  })



  const carregarReforc = async () => {
    const resposta = await apiGrups.reforc(reforc.activitat, reforc.data)
    reforc.dies = resposta.dies || []
    reforc.hores = resposta.hores || []
    reforc.professors = resposta.professors || {}
  }

  const obrirReforc = async (activitat) => {
    // Marcar una franja recarrega el dia: primer cal desar (o descartar) el que s'hagi marcat
    if (!(await potSortir())) return
    Object.assign(reforc, { activitat, professor: null, data: isoDe(dataCarregada.value), visible: true })
    try {
      await carregarReforc()
    } catch (err) {
      avisaError(err, () => toast.add({ severity: 'error', summary: t('common.error'), detail: err.response?.data?.detail || '', life: 5000 }))
    }
  }

  // Si canvia la data, l'estat de les franges és el d'aquella data
  watch(() => reforc.data, (nova, vella) => {
    if (reforc.visible && nova && vella && nova !== vella) carregarReforc().catch(() => {})
  })

  const frangesProfessor = computed(() => reforc.professors[reforc.professor] || [])
  const frangaReforc = (dia, hora) => frangesProfessor.value.find(f => f.dia === dia && f.hora === hora) || null
  const diesReforc = computed(() => reforc.dies.filter(d => frangesProfessor.value.some(f => f.dia === d)))
  const horesReforc = computed(() => reforc.hores.filter(h => frangesProfessor.value.some(f => f.hora === h)))

  // Opcions del desplegable: cada professor amb quantes franges tenen alumnes
  const opcionsProfessorsReforc = computed(() =>
    Object.entries(reforc.professors)
      .map(([nom, franges]) => {
        const amb = franges.filter(f => f.amb_alumnes).length
        const total = franges.length
        return { nom, amb, total, icona: amb === total ? '●' : (amb ? '◐' : '○') }
      })
      .filter(o => !reforc.nomesPendents || o.amb < o.total || o.nom === reforc.professor))

  // Vista «Setmana»: franges de tots els professors visibles (amb el filtre), per dia i hora
  const frangesVisiblesSetmana = computed(() => {
    const visibles = new Set(opcionsProfessorsReforc.value.map(o => o.nom))
    return Object.entries(reforc.professors)
      .filter(([nom]) => visibles.has(nom))
      .flatMap(([professor, franges]) => franges.map(f => ({ professor, ...f })))
  })
  const diesSetmana = computed(() => reforc.dies.filter(d => frangesVisiblesSetmana.value.some(f => f.dia === d)))
  const horesSetmana = computed(() => reforc.hores.filter(h => frangesVisiblesSetmana.value.some(f => f.hora === h)))
  const frangesSetmana = (dia, hora) =>
    frangesVisiblesSetmana.value.filter(f => f.dia === dia && f.hora === hora)

  // Text en passar el ratolí per sobre: estat actual, historial i què fa el clic
  const titolFranja = (f) => {
    if (!f) return ''
    const estat = f.amb_alumnes
      ? `${t('groups.reforcBusy')} ${t('groups.reforcSince', { data: dataCurta(f.des_de) })}`
      : t('groups.reforcFree')
    const linies = [estat]
    if (f.historial?.length) {
      linies.push(`${t('groups.reforcHistory')}:`)
      f.historial.forEach(h => {
        linies.push(`  ${dataCurta(h.des_de)} → ${h.amb_alumnes ? t('groups.reforcBusy') : t('groups.reforcFree')}`)
      })
    }
    linies.push(f.amb_alumnes ? t('groups.reforcMakeFree') : t('groups.reforcMakeBusy'))
    return linies.join('\n')
  }

  const resumReforc = computed(() => {
    const totes = Object.values(reforc.professors).flat()
    return { amb: totes.filter(f => f.amb_alumnes).length, total: totes.length }
  })

  const canviaFranjaReforc = async (dia, hora, professor = reforc.professor) => {
    const franja = (reforc.professors[professor] || []).find(f => f.dia === dia && f.hora === hora)
    if (!franja || !reforc.data) return
    reforc.desant = true
    try {
      const resposta = await apiGrups.desaPeriode({
        tipus: 'professor', clau: professor, hores: [hora], data: reforc.data,
        dia_setmana: dia, alliberat: franja.amb_alumnes   // amb alumnes → torna a estar alliberat
      })
      avisaSubstitutsTrets(toast, t, resposta?.substituts_trets)
      await carregarReforc()
      await recarregarDiaCarregat()
    } catch (err) {
      avisaError(err, () => toast.add({ severity: 'error', summary: t('common.error'), detail: err.response?.data?.detail || '', life: 5000 }))
    } finally {
      reforc.desant = false
    }
  }

  const inicialitzarActivitats = (perHora = {}, seleccionades = {}) => {
    activitatsPerHora.value = perHora
    for (const key in activitatsMarcades) {
      delete activitatsMarcades[key]
    }
    Object.keys(perHora).forEach(act => {
      activitatsMarcades[act] = {}
      Object.keys(perHora[act]).forEach(hora => {
        activitatsMarcades[act][hora] = (seleccionades[hora] || []).includes(act)
      })
    })
    activitatsMarcadesOriginals.value = JSON.parse(JSON.stringify(activitatsMarcades))
  }

  const inicialitzarOcupats = (seleccionats = {}) => {
    for (const key in professorsOcupats) {
      delete professorsOcupats[key]
    }
    Object.entries(seleccionats).forEach(([hora, profs]) => {
      professorsOcupats[hora] = [...profs]
    })
    professorsOcupatsOriginals.value = professorsOcupatsNets()
  }

  const inicialitzarProfessors = (seleccionats = {}) => {
    for (const key in professorsAlliberats) {
      delete professorsAlliberats[key]
    }
    Object.entries(seleccionats).forEach(([hora, profs]) => {
      professorsAlliberats[hora] = [...profs]
    })
    professorsAlliberatsOriginals.value = professorsAlliberatsNets()
  }

  const totalGrupsSeleccionats = computed(() => {
    const grupsUnics = new Set()
    for (const grup in checkboxes) {
      for (const hora in checkboxes[grup]) {
        if (checkboxes[grup][hora]) {
          grupsUnics.add(grup)
        }
      }
    }
    return grupsUnics.size
  })

  const totalHoresSeleccionades = computed(() => {
    const horesAmbGrups = new Set()
    for (const grup in checkboxes) {
      for (const hora in checkboxes[grup]) {
        if (checkboxes[grup][hora]) {
          horesAmbGrups.add(hora)
        }
      }
    }
    return horesAmbGrups.size
  })

  const inicialitzarCheckboxes = (grups, horasList, seleccionats = {}) => {
    // Netejar checkboxes
    for (const key in checkboxes) {
      delete checkboxes[key]
    }

    // Crear estructura de checkboxes
    grups.forEach(grup => {
      checkboxes[grup] = {}
      horasList.forEach(hora => {
        checkboxes[grup][hora] = seleccionats[hora]?.includes(grup) || false
      })
    })

    // Guardar còpia dels originals
    checkboxesOriginals.value = JSON.parse(JSON.stringify(checkboxes))
  }

  const carregarConfiguracio = async (data = dataTreball.value) => {
    loading.value = true
    error.value = null

    try {
      const resposta = await apiGrups.llista(isoDe(data), { _silent: true })
      dataCarregada.value = data

      hores.value = resposta.hores
      grupsDisponibles.value = resposta.grups_disponibles

      inicialitzarCheckboxes(
        resposta.grups_disponibles,
        resposta.hores,
        resposta.grups_seleccionats_per_hora
      )
      professorsPerGrupHora.value = resposta.professors_per_grup_hora || {}
      inicialitzarProfessors(resposta.professors_alliberats_per_hora || {})
      inicialitzarActivitats(resposta.activitats_per_hora || {}, resposta.activitats_seleccionades_per_hora || {})
      activitatsPerDefecte.value = resposta.activitats_per_defecte || []
      reforcsDelDia.value = resposta.reforcs_per_hora || {}
      inicialitzarOcupats(resposta.ocupats_per_hora || {})
    } catch (err) {
      console.error('Error carregant configuració:', err)
      avisaError(err, () => { error.value = t('groups.errors.load') })
    } finally {
      loading.value = false
    }
  }

  // Torna a carregar el dia que es mostra (després d'un canvi d'estat)
  const recarregarDiaCarregat = () => carregarConfiguracio(dataCarregada.value)

  const onCheckboxChange = () => {
    // Aquest mètode es crida quan canvia un checkbox individual
    // El computed teCanvis detectarà automàticament el canvi
  }

  const toggleGrupComplet = (grup) => {
    // Comprova si alguna hora està marcada
    const algunaMarcada = hores.value.some(hora => checkboxes[grup][hora])

    // Marca/desmarca totes les hores d'aquest grup
    const nouEstat = !algunaMarcada
    hores.value.forEach(hora => {
      checkboxes[grup][hora] = nouEstat
    })
  }

  const marcarTots = () => {
    grupsDisponibles.value.forEach(grup => {
      hores.value.forEach(hora => {
        checkboxes[grup][hora] = true
      })
    })
  }

  const desmarcarTots = () => {
    grupsDisponibles.value.forEach(grup => {
      hores.value.forEach(hora => {
        checkboxes[grup][hora] = false
      })
    })
  }

  // Retorna si s'ha pogut desar
  const desarGrups = async () => {
    desant.value = true

    try {
      // Convertir checkboxes a format backend: Dict[hora, List[grups]]
      const grupsPerHora = {}

      hores.value.forEach(hora => {
        const grupsHora = []
        grupsDisponibles.value.forEach(grup => {
          if (checkboxes[grup][hora]) {
            grupsHora.push(grup)
          }
        })
        if (grupsHora.length > 0) {
          grupsPerHora[hora] = grupsHora
        }
      })

      const professorsPerHora = professorsAlliberatsNets()
      const activitatsPerHoraMarcades = {}
      Object.entries(activitatsMarcades).forEach(([act, perHora]) => {
        Object.entries(perHora).forEach(([hora, marcada]) => {
          if (marcada) (activitatsPerHoraMarcades[hora] ||= []).push(act)
        })
      })
      const resposta = await apiGrups.desa(isoDe(dataCarregada.value), {
        grups: grupsPerHora,
        professors: professorsPerHora,
        activitats: activitatsPerHoraMarcades,
        ocupats: professorsOcupatsNets()
      })

      // Actualitzar originals
      checkboxesOriginals.value = JSON.parse(JSON.stringify(checkboxes))
      inicialitzarProfessors(professorsPerHora)
      activitatsMarcadesOriginals.value = JSON.parse(JSON.stringify(activitatsMarcades))
      professorsOcupatsOriginals.value = professorsOcupatsNets()

      toast.add({
        severity: 'success',
        summary: t('common.saved'),
        detail: resposta.message,
        life: 3000
      })
      avisaSubstitutsTrets(toast, t, resposta.substituts_trets)
      return true
    } catch (err) {
      console.error('Error desant configuració:', err)
      avisaError(err, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('groups.errors.save'),
        life: 5000
      }))
      return false
    } finally {
      desant.value = false
    }
  }

  // Canvis sense desar: pregunta com els programes d'escriptori i diu si es
  // pot continuar (després de desar o de descartar) o no (cancel·lat o error)
  const avis = reactive({ visible: false, resolve: null })

  const respon = (resposta) => {
    const resolve = avis.resolve
    avis.resolve = null
    avis.visible = false
    resolve?.(resposta)
  }

  const potSortir = async () => {
    if (!teCanvis.value) return true
    const resposta = await new Promise(resolve => {
      avis.resolve = resolve
      avis.visible = true
    })
    if (resposta === 'desa') return await desarGrups()
    return resposta === 'descarta'
  }

  // Carregar quan canvia la data
  watch(dataTreball, async () => {
    if (await potSortir()) {
      carregarConfiguracio()
    }
  }, { immediate: true })

  // Tancar o recarregar el navegador amb canvis sense desar: avís del navegador
  const avisSortida = (event) => {
    if (!teCanvis.value) return
    event.preventDefault()
    event.returnValue = ''
  }

  onMounted(() => {
    carregarConfiguracio()
    window.addEventListener('beforeunload', avisSortida)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', avisSortida)
  })

  return {
    hores,
    grupsDisponibles,
    checkboxes,
    checkboxesOriginals,
    professorsPerGrupHora,
    professorsAlliberats,
    professorsAlliberatsOriginals,
    professorsOcupats,
    professorsOcupatsOriginals,
    panellProfessors,
    franja,
    activitatsPerHora,
    activitatsMarcades,
    activitatsMarcadesOriginals,
    activitatsPerDefecte,
    reforcsDelDia,
    loading,
    desant,
    error,
    dataCarregada,
    isoDe,
    dataFormatada,
    professorsAlliberatsNets,
    professorsOcupatsNets,
    estaOcupat,
    marcaOcupat,
    teCanvis,
    professorsDe,
    activitatsNoms,
    professorsActivitat,
    professorsReforcAvui,
    reforcAmbAlumnes,
    professorsFranja,
    dataCurta,
    estaAlliberat,
    alliberatsDe,
    lliureReforcAvui,
    alliberatsReforcAvui,
    lliuresReforcAvui,
    alliberatsActivitat,
    marcaProfessor,
    treureProfessor,
    obrirProfessors,
    resumProfessors,
    reforc,
    carregarReforc,
    obrirReforc,
    frangesProfessor,
    frangaReforc,
    diesReforc,
    horesReforc,
    opcionsProfessorsReforc,
    frangesVisiblesSetmana,
    diesSetmana,
    horesSetmana,
    frangesSetmana,
    titolFranja,
    resumReforc,
    canviaFranjaReforc,
    inicialitzarActivitats,
    inicialitzarOcupats,
    inicialitzarProfessors,
    totalGrupsSeleccionats,
    totalHoresSeleccionades,
    inicialitzarCheckboxes,
    carregarConfiguracio,
    recarregarDiaCarregat,
    onCheckboxChange,
    toggleGrupComplet,
    marcarTots,
    desmarcarTots,
    desarGrups,
    avis,
    respon,
    potSortir,
    avisSortida,
  }
}
