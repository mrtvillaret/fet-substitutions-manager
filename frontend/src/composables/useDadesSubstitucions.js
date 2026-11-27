import { avisaError } from '../api/errors.js'
import { ref, computed } from 'vue'
import * as apiSubstitucions from '../api/substitucions.js'
import { llista as llistaVigilancies } from '../api/vigilancies.js'
import * as apiPdf from '../api/pdf.js'
import * as apiHorari from '../api/horari.js'
import { ambDataTreball } from '../dataTreball.js'
import { dataIso } from '../dates.js'
import { ordenaAlfabeticament } from '../ordreAlfabetic.js'

// Publica el dia complet amb els disponibles i descarta les càrregues antigues.
export function useDadesSubstitucions({ dataTreball, locale, toast, t }) {
  // State
  const avisosEncadenades = ref([])
  const substitucions = ref([]) // les files del dia que es veuen (les tria el backend)
  const totesAbsencies = ref([]) // TOTES les absències (amb i sense grup) per detectar professors absents
  const vigilanciesCount = ref(0)
  const professors = ref([])
  // Professors amb una absència coberta el dia que es mira: no són a la llista de
  // l'horari d'aquell dia (no se'ls poden posar absències), però es mostren al final
  // del desplegable, sense que es puguin triar, perquè qui els busqui els trobi
  const absenciesCobertes = ref([])  // [{ professor, data_final }]
  const horesDisponibles = ref([])
  const xmlMissingNotified = ref(false)
  const loading = ref(false)
  const errorCarregaSubstitucions = ref(false)
  let idCarregaSubstitucions = 0

  // Computed
  const dataISO = computed(() => dataIso(dataTreball.value))

  const dataFormatada = computed(() => {
    return dataTreball.value.toLocaleDateString(locale.value || 'ca-ES', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  })

  const dataISOCurta = computed(() =>
    dataTreball.value.toLocaleDateString(locale.value || 'ca-ES', {
      day: '2-digit', month: '2-digit', year: 'numeric'
    })
  )


  const substitucionsAssignades = computed(() =>
    substitucions.value.filter(s => s.substitut).length
  )

  const substitucionsPendents = computed(() =>
    substitucions.value.filter(s => !s.substitut).length
  )


  // Mètodes
  // L'ordre dins de cada hora ('curs' o 'professor'): el mateix a la pantalla i
  // al PDF (l'ordena el backend). Es recorda al navegador de cada usuari.
  const CLAU_ORDRE = 'substitucions_ordre'
  const llegeixOrdre = () => {
    try {
      return localStorage.getItem(CLAU_ORDRE) === 'professor' ? 'professor' : 'curs'
    } catch {
      return 'curs'
    }
  }
  const ordreFiles = ref(llegeixOrdre())
  const canviaOrdre = (ordre) => {
    ordreFiles.value = ordre
    try {
      localStorage.setItem(CLAU_ORDRE, ordre)
    } catch {
      // Sense el navegador per recordar-ho: només per a aquesta visita
    }
    carregarSubstitucions()
  }

  // `silenci`: la recàrrega en tornar a la pestanya, sense difuminar la taula
  // i, si falla, deixant-hi les dades que hi havia
  const carregarSubstitucions = async ({ silenci = false } = {}) => {
    const idCarrega = ++idCarregaSubstitucions
    const data = dataISO.value
    if (!silenci) {
      loading.value = true
      errorCarregaSubstitucions.value = false
    }
    // La taula d'abans es queda (difuminada i sense accions) fins que arriben
    // totes les dades: es substitueix de cop, sense parpelleig ni perdre el
    // desplaçament al mòbil
    try {
      const [files, totes, recompteVigilancies, revisio] = await Promise.all([
        apiSubstitucions.llista(data, ordreFiles.value),
        apiSubstitucions.llistaTotes(data, { silent: true }),
        obtenirVigilanciesCount(data),
        apiPdf.validacions(data, { _silent: true })
      ])
      if (idCarrega !== idCarregaSubstitucions) return

      const hores = [...new Set(files.map(substitucio => substitucio.hora))]
      const disponiblesPerHora = await apiSubstitucions.disponiblesEnBloc(data, hores)
      if (idCarrega !== idCarregaSubstitucions) return

      // Publicació atòmica: cap fila no es veu fins que totes les hores tenen
      // els disponibles. Quines files es veuen ja ho ha decidit el backend.
      const filesAmbDisponibles = files.map(substitucio => ({
        ...substitucio,
        disponibles: disponiblesPerHora[substitucio.hora]?.disponibles || []
      }))
      substitucions.value = filesAmbDisponibles
      totesAbsencies.value = totes
      vigilanciesCount.value = recompteVigilancies
      avisosEncadenades.value = revisio.data.avisos_encadenades || []
    } catch (error) {
      if (idCarrega !== idCarregaSubstitucions) return
      console.error('Error carregant substitucions:', error)
      if (silenci) return
      substitucions.value = []
      totesAbsencies.value = []
      vigilanciesCount.value = 0
      avisosEncadenades.value = []
      avisaError(error, () => { errorCarregaSubstitucions.value = true })
    } finally {
      if (idCarrega === idCarregaSubstitucions) loading.value = false
    }
  }

  // Nova funció per carregar TOTES les absències (incloses les sense grup: VP, Guàrdia, etc.)
  // Útil per editar absències i veure totes les hores marcades
  const carregarTotesAbsencies = async () => {
    // Si ja estan carregades (de carregarSubstitucions), retornar-les
    if (totesAbsencies.value.length > 0) {
      return totesAbsencies.value
    }

    // Sinó, carregar-les
    try {
      const totes = await apiSubstitucions.llistaTotes(dataISO.value)
      totesAbsencies.value = totes
      return totes
    } catch (error) {
      console.error('Error carregant totes les absències:', error)
      return []
    }
  }

  const obtenirVigilanciesCount = async (data) => {
    try {
      const vigilancies = await llistaVigilancies(data)
      return Array.isArray(vigilancies) ? vigilancies.length : 0
    } catch (error) {
      console.error('Error carregant vigilàncies:', error)
      return 0
    }
  }


  // Sense XML a la data: un sol avís per visita (el diuen tant les hores com els professors)
  const avisaSiFaltaXml = (resposta) => {
    if (!resposta?.xml_missing || xmlMissingNotified.value) return
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('common.xmlMissing'), life: 4000 })
    xmlMissingNotified.value = true
  }

  // Com les altres càrregues: una resposta d'un dia que ja no és a la pantalla no es publica
  const carregarProfessors = async () => {
    const data = dataISO.value
    try {
      const resposta = await apiHorari.professorsHorari(ambDataTreball())
      if (data !== dataISO.value) return
      avisaSiFaltaXml(resposta)
      const llista = resposta.professors || []
      professors.value = ordenaAlfabeticament(llista)
      absenciesCobertes.value = resposta.absencies_cobertes || []
    } catch (error) {
      console.error('Error carregant professors:', error)
    }
  }


  const carregarHores = async () => {
    const data = dataISO.value
    try {
      const resposta = await apiHorari.hores(ambDataTreball())
      if (data !== dataISO.value) return
      avisaSiFaltaXml(resposta)
      horesDisponibles.value = resposta.hores
    } catch (error) {
      console.error('Error carregant hores:', error)
    }
  }


  return { avisosEncadenades, substitucions, totesAbsencies, vigilanciesCount, professors, absenciesCobertes, horesDisponibles, loading, errorCarregaSubstitucions, dataISO, dataFormatada, dataISOCurta, substitucionsAssignades, substitucionsPendents, ordreFiles, canviaOrdre, carregarSubstitucions, carregarTotesAbsencies, carregarProfessors, carregarHores }
}
