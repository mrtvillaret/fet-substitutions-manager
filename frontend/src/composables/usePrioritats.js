import { ref, computed, onMounted, watch } from 'vue'
import * as apiPdf from '../api/pdf'
import { ambDataTreball, dataTreball } from '../dataTreball'
import { detectaAssignatures } from '../api/horari'
import * as apiPrioritats from '../api/prioritats'
import { dataIso } from '../dates'
import { jaAvisat } from '../errorsApi'
import { novesAmbGrup } from '../noSubstituirAmbGrup'

export function usePrioritats(dependents) {
  const { t, locale, toast, confirmaEsborrar } = dependents

  // Data en format ISO (per l'endpoint) i text (per mostrar), + versió d'XML vigent
  const dataISO = computed(() => dataIso(dataTreball.value))
  const dataText = computed(() =>
    dataTreball.value.toLocaleDateString(locale.value || 'ca-ES',
      { day: '2-digit', month: '2-digit', year: 'numeric' })
  )
  const xmlDataInici = ref(null)
  const teBuits = ref(false)
  const xmlVersioText = computed(() => {
    if (!xmlDataInici.value) return ''
    const [y, m, d] = xmlDataInici.value.split('-')
    return `${d}/${m}/${y}`
  })

  // Assignatures que no surten a l'XML però es poden assignar (grups sense classe)
  const ASSIGNATURES_SINTETIQUES = ['alliberat']

  // No substituir
  const noSubstituir = ref([])
  const mostrarDialogNoSubstituir = ref(false)
  const novesNoSubstituir = ref([])

  // Prioritats
  const ordreCategories = ref([])  // Array de {categories: ["Reforç", "alliberat"], activa: true}
  const pesos = ref({})  // {assignatura: pes}
  const prioritiesSnapshot = ref('')
  const categoriaSeleccionada = ref(null)
  const categoriaSeleccionadaIndex = ref(null)
  const accordionActiveIndexes = ref([])  // Índexos dels accordions oberts
  const mostrarDialogAfegirCategoria = ref(false)
  const novaCategoria = ref('')
  const desantPrioritats = ref(false)

  // Diàleg afegir assignatura a categoria
  const mostrarDialogAfegirAssignatura = ref(false)
  const categoriaAfegirAssignaturaIdx = ref(null)
  const assignaturesDisponibles = ref([])
  // Les activitats que tenen grup a l'horari vigent (per a l'avís de «No substituir»)
  const assignaturesAmbGrup = ref([])

  // Opcions dels desplegables: assignatures de l'XML + les sintètiques
  // (alliberat…) + les que ja estan configurades (encara que vinguin d'un altre
  // XML), perquè totes es mostrin marcades i no se'n perdi cap en canviar de data.
  const opcionsCategoria = computed(() => {
    const idx = categoriaAfegirAssignaturaIdx.value
    const existents = idx !== null ? (ordreCategories.value[idx]?.categories || []) : []
    return Array.from(new Set([
      ...assignaturesDisponibles.value,
      ...ASSIGNATURES_SINTETIQUES,
      ...existents,
    ])).sort()
  })
  // El «no substituir» pot incloure l'opció BUIDA (hores amb Subject buit), que
  // necessita etiqueta pròpia; per això les opcions són objectes {label, value}.
  const opcionsNoSubst = computed(() => {
    const vals = new Set([
      ...assignaturesDisponibles.value,
      ...ASSIGNATURES_SINTETIQUES,
      ...noSubstituir.value,
    ])
    if (teBuits.value || noSubstituir.value.includes('')) vals.add('')
    return Array.from(vals).sort().map(v => ({
      label: v === '' ? t('common.empty') : v,
      value: v,
    }))
  })
  const assignaturesSeleccionades = ref([])
  // Les que s'afegeixen a «No substituir» i tenen grup: avís informatiu
  const avisAmbGrup = computed(() =>
    novesAmbGrup(novesNoSubstituir.value, noSubstituir.value, assignaturesAmbGrup.value)
      .map(a => a === '' ? t('common.empty') : a)
  )

  // Activitats sense grup que es poden alliberar
  const activitatsAlliberables = ref([])
  const activitatsPerDefecte = ref([])
  const activitatsDisponibles = ref([])
  const desantAlliberables = ref(false)
  const filtreAlliberables = ref('')
  // Les marcades primer; la resta, per ordre alfabètic
  const activitatsFiltrades = computed(() => {
    const filtre = filtreAlliberables.value.trim().toLowerCase()
    return activitatsDisponibles.value
      .filter(a => !filtre || a.toLowerCase().includes(filtre))
      .sort((a, b) => (activitatsAlliberables.value.includes(b) - activitatsAlliberables.value.includes(a)) || a.localeCompare(b))
  })

  const carregarActivitatsAlliberables = async () => {
    try {
      const resposta = await apiPrioritats.activitatsAlliberables(ambDataTreball())
      activitatsAlliberables.value = resposta.activitats || []
      activitatsPerDefecte.value = resposta.per_defecte || []
      // Les configurades que ja no són a l'horari també s'han de poder treure
      activitatsDisponibles.value = [...new Set([...(resposta.disponibles || []), ...activitatsAlliberables.value])].sort()
    } catch (error) {
      console.error('Error carregant activitats alliberables:', error)
    }
  }

  const desarActivitatsAlliberables = async () => {
    desantAlliberables.value = true
    try {
      const resposta = await apiPrioritats.desaActivitatsAlliberables({
        activitats: activitatsAlliberables.value,
        per_defecte: activitatsPerDefecte.value.filter(a => activitatsAlliberables.value.includes(a))
      })
      activitatsAlliberables.value = resposta.activitats
      activitatsPerDefecte.value = resposta.per_defecte
      toast.add({ severity: 'success', summary: t('common.saved'), life: 2500 })
    } catch (error) {
      toast.add({ severity: 'error', summary: t('common.error'), detail: error.response?.data?.detail || '', life: 5000 })
    } finally {
      desantAlliberables.value = false
    }
  }

  // Llista de disponibles (PDF)
  const generantPDFDisponibles = ref(false)
  const dataInicialPDF = ref('')

  // Estat collapsed dels Panels de prioritats (guardat a localStorage)
  const panelsPrioritatsCollapsed = ref({
    ordre: false,
    pesos: false,
    noSubst: false,
    alliberables: false,
    disponibles: true
  })

  // Carregar estat dels panels des de localStorage
  const carregarEstatPanels = () => {
    try {
      const saved = localStorage.getItem('prioritats_panels_collapsed')
      if (saved) {
        panelsPrioritatsCollapsed.value = JSON.parse(saved)
      }
    } catch (e) {
      console.error('Error carregant estat panels:', e)
    }
  }

  // Guardar estat dels panels a localStorage
  const guardarEstatPanels = () => {
    try {
      localStorage.setItem('prioritats_panels_collapsed', JSON.stringify(panelsPrioritatsCollapsed.value))
    } catch (e) {
      console.error('Error guardant estat panels:', e)
    }
  }

  const getPrioritatsSnapshot = () => JSON.stringify({
    ordreCategories: ordreCategories.value,
    pesos: pesos.value
  })

  const teCanvisPrioritats = computed(() => {
    if (!prioritiesSnapshot.value) return false
    return getPrioritatsSnapshot() !== prioritiesSnapshot.value
  })

  // ===== FUNCIONS PRIORITATS =====

  const onCategoriaSelect = (event) => {
    categoriaSeleccionadaIndex.value = ordreCategories.value.indexOf(event.data)
  }

  const onCategoriaUnselect = () => {
    categoriaSeleccionadaIndex.value = null
  }

  const moureCategoriaAmunt = () => {
    if (categoriaSeleccionadaIndex.value === null || categoriaSeleccionadaIndex.value === 0) return

    const idx = categoriaSeleccionadaIndex.value
    const temp = ordreCategories.value[idx]
    ordreCategories.value[idx] = ordreCategories.value[idx - 1]
    ordreCategories.value[idx - 1] = temp

    categoriaSeleccionadaIndex.value = idx - 1
    categoriaSeleccionada.value = ordreCategories.value[idx - 1]
  }

  const moureCategoriaAvall = () => {
    if (categoriaSeleccionadaIndex.value === null || categoriaSeleccionadaIndex.value >= ordreCategories.value.length - 1) return

    const idx = categoriaSeleccionadaIndex.value
    const temp = ordreCategories.value[idx]
    ordreCategories.value[idx] = ordreCategories.value[idx + 1]
    ordreCategories.value[idx + 1] = temp

    categoriaSeleccionadaIndex.value = idx + 1
    categoriaSeleccionada.value = ordreCategories.value[idx + 1]
  }

  const afegirCategoriaDialog = () => {
    if (!novaCategoria.value.trim()) return

    // Dividir per comes i netejar
    const categories = novaCategoria.value.split(',').map(c => c.trim()).filter(c => c)

    if (categories.length === 0) return

    ordreCategories.value.push({ categories, activa: true })  // Per defecte activa

    // Inicialitzar pesos a 1 per a cada assignatura nova
    categories.forEach(cat => {
      if (!pesos.value[cat]) {
        pesos.value[cat] = 1
      }
    })

    toast.add({
      severity: 'success',
      summary: t('common.added'),
      detail: t('config.priorities.categoryAdded', { count: categories.length }, categories.length),
      life: 3000
    })

    mostrarDialogAfegirCategoria.value = false
    novaCategoria.value = ''
  }

  const eliminarCategoria = () => {
    if (categoriaSeleccionadaIndex.value === null) return

    const idx = categoriaSeleccionadaIndex.value
    const categoria = ordreCategories.value[idx]

    confirmaEsborrar({
      message: t('config.priorities.deleteCategoryConfirm', {
        index: idx + 1,
        count: categoria.categories.length
      }, categoria.categories.length),
      header: t('common.confirmation'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: () => {
        ordreCategories.value.splice(idx, 1)
        categoriaSeleccionada.value = null
        categoriaSeleccionadaIndex.value = null

        toast.add({
          severity: 'success',
          summary: t('common.deleted'),
          detail: t('config.priorities.categoryDeleted'),
          life: 3000
        })
      }
    })
  }

  const afegirAssignaturaCategoria = async (categoriaIdx) => {
    // Obrir diàleg amb les assignatures actuals ja marcades (desmarcar-les les treu)
    categoriaAfegirAssignaturaIdx.value = categoriaIdx
    assignaturesSeleccionades.value = [...(ordreCategories.value[categoriaIdx]?.categories || [])]
    mostrarDialogAfegirAssignatura.value = true
  }

  const desarAssignaturaCategoria = () => {
    const categoriaIdx = categoriaAfegirAssignaturaIdx.value
    const categoria = ordreCategories.value[categoriaIdx]
    const seleccio = assignaturesSeleccionades.value
    const previes = categoria.categories

    // Les que segueixen marcades (preservant l'ordre existent) + les noves al final.
    // Desmarcar-ne una equival a treure-la de la categoria.
    const mantingudes = previes.filter(a => seleccio.includes(a))
    const nous = seleccio.filter(a => !previes.includes(a))
    categoria.categories = [...mantingudes, ...nous]

    // Pes 1 per a les noves que no en tinguin (preserva els valors ja configurats)
    for (const assignatura of nous) {
      if (!pesos.value[assignatura]) {
        pesos.value[assignatura] = 1
      }
    }

    toast.add({
      severity: 'success',
      summary: t('common.updated'),
      detail: t('config.priorities.categoryUpdated', { index: categoriaIdx + 1 }),
      life: 3000
    })

    // Tancar diàleg
    mostrarDialogAfegirAssignatura.value = false
    assignaturesSeleccionades.value = []
  }

  const eliminarAssignaturaCategoria = (assignatura, categoriaIdx) => {
    confirmaEsborrar({
      message: t('config.priorities.deleteSubjectConfirm', { subject: assignatura, index: categoriaIdx + 1 }),
      header: t('common.confirmation'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: () => {
        const idx = ordreCategories.value[categoriaIdx].categories.indexOf(assignatura)
        if (idx !== -1) {
          ordreCategories.value[categoriaIdx].categories.splice(idx, 1)

          toast.add({
            severity: 'success',
            summary: t('common.deleted'),
            detail: t('config.priorities.subjectDeleted', { subject: assignatura }),
            life: 3000
          })
        }
      }
    })
  }

  const carregarAssignaturesXML = async () => {
    try {
      const resposta = await detectaAssignatures(ambDataTreball())
      assignaturesDisponibles.value = resposta.assignatures || []
      xmlDataInici.value = resposta.xml_data_inici || null
      teBuits.value = !!resposta.te_buits
      assignaturesAmbGrup.value = resposta.amb_grup || []
    } catch (error) {
      console.error('Error carregant assignatures XML:', error)
    }
  }

  // Si canvia la data del calendari general, tornar a detectar sobre el nou XML
  watch(dataISO, () => { carregarAssignaturesXML() })

  const carregarNoSubstituir = async () => {
    try {
      const resposta = await apiPrioritats.noSubstituir()
      noSubstituir.value = resposta.assignatures
    } catch (error) {
      console.error('Error carregant no substituir:', error)
    }
  }

  const carregarPrioritats = async () => {
    try {
      const [assignaturesResp, categoriesResp] = await Promise.all([
        apiPrioritats.assignatures(),
        apiPrioritats.categories(),
        carregarAssignaturesXML()  // Carregar assignatures de l'XML
      ])

      // Crear mapa de categories per obtenir l'estat activa
      const categoriesMap = {}
      categoriesResp.categories.forEach(cat => {
        categoriesMap[cat.id] = {
          activa: cat.activa,
          ordre: cat.ordre
        }
      })

      // Agrupar assignatures per categoria_id
      const categoriesById = {}

      assignaturesResp.assignatures.forEach(assig => {
        if (!categoriesById[assig.categoria_id]) {
          categoriesById[assig.categoria_id] = {
            id: assig.categoria_id,
            assignatures: [],
            activa: categoriesMap[assig.categoria_id]?.activa || true
          }
        }

        categoriesById[assig.categoria_id].assignatures.push({
          nom: assig.assignatura,
          pes: assig.pes,
          ordre: assig.ordre,
          auto_assignada: assig.auto_assignada
        })

        // Guardar pes
        pesos.value[assig.assignatura] = assig.pes
      })

      // Convertir a ordreCategories: array de {categories: [...], activa: true/false}
      // Ordenar categories per ID (que correspon a l'ordre)
      ordreCategories.value = Object.keys(categoriesById)
        .sort((a, b) => parseInt(a) - parseInt(b))
        .map(catId => {
          const cat = categoriesById[catId]
          // Ordenar assignatures dins la categoria per ordre
          const assignaturesOrdenades = cat.assignatures
            .sort((a, b) => a.ordre - b.ordre)
            .map(a => a.nom)

          // Determinar si la categoria està activa: totes les assignatures tenen auto_assignada=true
          const activa = cat.assignatures.every(a => a.auto_assignada === true)

          return {
            categories: assignaturesOrdenades,
            activa: activa
          }
        })

      prioritiesSnapshot.value = getPrioritatsSnapshot()
    } catch (error) {
      console.error('Error carregant prioritats:', error)
    }
  }

  const desarPrioitats = async () => {
    desantPrioritats.value = true

    try {
      // Preparar dades per enviar
      const ordreCategoriesArray = ordreCategories.value.map(cat => cat.categories)
      const categoriesActives = ordreCategories.value.map(cat => cat.activa !== false)  // Default true si no està definit

      const resposta = await apiPrioritats.desaTot({
        ordre_categories: ordreCategoriesArray,
        pesos: pesos.value,
        categories_actives: categoriesActives
      })

      toast.add({
        severity: 'success',
        summary: t('common.saved'),
        detail: resposta.message,
        life: 3000
      })

      // Recarregar prioritats per assegurar sincronització
      await carregarPrioritats()
    } catch (error) {
      console.error('Error desant prioritats:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('config.errors.savePriorities'),
        life: 3000
      })
    } finally {
      desantPrioritats.value = false
    }
  }

  // Llista de disponibles - PDF de tots els dies
  const generarPDFDisponiblesTotsDies = async () => {
    generantPDFDisponibles.value = true

    try {
      const response = await apiPdf.creaDisponiblesTotsDies({ data_inici: dataInicialPDF.value || dataISO.value }, { responseType: 'blob' })

      // Crear link de descàrrega
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url

      const filename = response.headers['content-disposition']?.split('filename=')[1]?.replace(/"/g, '') ||
                       `disponibles_tots_dies_${dataIso(new Date())}.pdf`

      link.download = filename
      link.click()
      window.URL.revokeObjectURL(url)

      toast.add({
        severity: 'success',
        summary: t('common.success'),
        detail: t('config.priorities.pdfGenerated'),
        life: 3000
      })
    } catch (error) {
      console.error('Error generant PDF:', error)
      // Els errors de l'API ja els avisa l'interceptor, amb el missatge del backend
      if (!jaAvisat(error)) {
        toast.add({
          severity: 'error',
          summary: t('common.error'),
          detail: error.response?.data?.detail || t('config.errors.generatePDF'),
          life: 3000
        })
      }
    } finally {
      generantPDFDisponibles.value = false
    }
  }

  // ===== FUNCIONS NO SUBSTITUIR =====

  const obrirDialogNoSubstituir = () => {
    // Obrir amb les assignatures actuals ja marcades (desmarcar-les les treu)
    novesNoSubstituir.value = [...noSubstituir.value]
    mostrarDialogNoSubstituir.value = true
  }

  const desarNoSubstituir = async () => {
    const seleccio = novesNoSubstituir.value
    const previes = noSubstituir.value

    const afegir = seleccio.filter(a => !previes.includes(a))
    const treure = previes.filter(a => !seleccio.includes(a))

    try {
      for (const assignatura of afegir) {
        await apiPrioritats.afegeixNoSubstituir(assignatura)
      }
      for (const assignatura of treure) {
        await apiPrioritats.esborraNoSubstituir(assignatura)
      }

      // Recarregar no substituir
      const resposta = await apiPrioritats.noSubstituir()
      noSubstituir.value = resposta.assignatures

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('config.priorities.noSubstUpdated'),
        life: 3000
      })

      cancelarNoSubstituir()
    } catch (error) {
      console.error('Error desant no substituir:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('config.errors.addNoSubst'),
        life: 3000
      })
    }
  }

  const eliminarNoSubstituir = async (assignatura) => {
    try {
      await apiPrioritats.esborraNoSubstituir(assignatura)

      toast.add({
        severity: 'success',
        summary: t('common.deleted'),
        detail: t('config.priorities.noSubstDeleted'),
        life: 3000
      })

      // Recarregar no substituir
      const resposta = await apiPrioritats.noSubstituir()
      noSubstituir.value = resposta.assignatures
    } catch (error) {
      console.error('Error eliminant no substituir:', error)
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: error.response?.data?.detail || t('config.errors.deleteNoSubst'),
        life: 3000
      })
    }
  }

  const cancelarNoSubstituir = () => {
    mostrarDialogNoSubstituir.value = false
    novesNoSubstituir.value = []
  }

  // Fer que tot el header dels panels sigui clicable
  const handlePanelHeaderClick = (event) => {
    const header = event.target.closest('.p-panel-header')
    if (!header) return

    // Si ja s'ha clicat al botó toggle directament, no fer res
    if (event.target.closest('.p-panel-toggler')) return

    // Trobar el botó toggle i fer-hi clic
    const toggleBtn = header.querySelector('.p-panel-toggler')
    if (toggleBtn) {
      toggleBtn.click()
    }
  }

  onMounted(() => {
    carregarEstatPanels()
    carregarNoSubstituir()
    carregarActivitatsAlliberables()
    carregarPrioritats()
  })

  return {
    dataISO,
    dataText,
    xmlDataInici,
    teBuits,
    xmlVersioText,
    ASSIGNATURES_SINTETIQUES,
    noSubstituir,
    mostrarDialogNoSubstituir,
    novesNoSubstituir,
    ordreCategories,
    pesos,
    prioritiesSnapshot,
    categoriaSeleccionada,
    categoriaSeleccionadaIndex,
    accordionActiveIndexes,
    mostrarDialogAfegirCategoria,
    novaCategoria,
    desantPrioritats,
    mostrarDialogAfegirAssignatura,
    categoriaAfegirAssignaturaIdx,
    assignaturesDisponibles,
    assignaturesAmbGrup,
    opcionsCategoria,
    opcionsNoSubst,
    assignaturesSeleccionades,
    avisAmbGrup,
    activitatsAlliberables,
    activitatsPerDefecte,
    activitatsDisponibles,
    desantAlliberables,
    filtreAlliberables,
    activitatsFiltrades,
    carregarActivitatsAlliberables,
    desarActivitatsAlliberables,
    generantPDFDisponibles,
    dataInicialPDF,
    panelsPrioritatsCollapsed,
    carregarEstatPanels,
    guardarEstatPanels,
    getPrioritatsSnapshot,
    teCanvisPrioritats,
    onCategoriaSelect,
    onCategoriaUnselect,
    moureCategoriaAmunt,
    moureCategoriaAvall,
    afegirCategoriaDialog,
    eliminarCategoria,
    afegirAssignaturaCategoria,
    desarAssignaturaCategoria,
    eliminarAssignaturaCategoria,
    carregarAssignaturesXML,
    carregarNoSubstituir,
    carregarPrioritats,
    desarPrioitats,
    generarPDFDisponiblesTotsDies,
    obrirDialogNoSubstituir,
    desarNoSubstituir,
    eliminarNoSubstituir,
    cancelarNoSubstituir,
    handlePanelHeaderClick,
  }
}
