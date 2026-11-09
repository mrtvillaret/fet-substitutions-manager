import { avisaError } from '../errorsApi.js'
import { ref, computed } from 'vue'
import * as apiSubstitucions from '../api/substitucions.js'
import { llista as llistaVigilancies } from '../api/vigilancies.js'
import * as apiPdf from '../api/pdf.js'
import * as apiHorari from '../api/horari.js'
import { ambDataTreball } from '../dataTreball.js'
import { dataIso } from '../dates.js'

// Publica el dia complet amb els disponibles i descarta les càrregues antigues.
export function useDadesSubstitucions({ dataTreball, locale, toast, t }) {
  // State
  const avisosEncadenades = ref([])
  const substitucions = ref([])
  const substitucionsFiltrades = ref([])
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

  const collator = computed(() => new Intl.Collator(locale.value || 'ca', { sensitivity: 'base' }))

  const substitucionsAssignades = computed(() =>
    substitucionsFiltrades.value.filter(s => s.substitut).length
  )

  const substitucionsPendents = computed(() =>
    substitucionsFiltrades.value.filter(s => !s.substitut).length
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

  const carregarSubstitucions = async () => {
    const idCarrega = ++idCarregaSubstitucions
    const data = dataISO.value
    loading.value = true
    errorCarregaSubstitucions.value = false
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
      substitucionsFiltrades.value = filesAmbDisponibles
      totesAbsencies.value = totes
      vigilanciesCount.value = recompteVigilancies
      avisosEncadenades.value = revisio.data.avisos_encadenades || []
    } catch (error) {
      if (idCarrega !== idCarregaSubstitucions) return
      console.error('Error carregant substitucions:', error)
      substitucions.value = []
      substitucionsFiltrades.value = []
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


  const carregarProfessors = async () => {
    try {
      const resposta = await apiHorari.professorsHorari(ambDataTreball())
      if (resposta?.xml_missing && !xmlMissingNotified.value) {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('common.xmlMissing'),
          life: 4000
        })
        xmlMissingNotified.value = true
      }
      const llista = resposta.professors || []
      professors.value = [...llista].sort((a, b) => collator.value.compare(a, b))
      absenciesCobertes.value = resposta.absencies_cobertes || []
    } catch (error) {
      console.error('Error carregant professors:', error)
    }
  }


  const carregarHores = async () => {
    try {
      const resposta = await apiHorari.hores(ambDataTreball())
      if (resposta?.xml_missing && !xmlMissingNotified.value) {
        toast.add({
          severity: 'warn',
          summary: t('common.warning'),
          detail: t('common.xmlMissing'),
          life: 4000
        })
        xmlMissingNotified.value = true
      }
      horesDisponibles.value = resposta.hores
    } catch (error) {
      console.error('Error carregant hores:', error)
    }
  }


  return { avisosEncadenades, substitucions, substitucionsFiltrades, totesAbsencies, vigilanciesCount, professors, absenciesCobertes, horesDisponibles, xmlMissingNotified, loading, errorCarregaSubstitucions, dataISO, dataFormatada, dataISOCurta, collator, substitucionsAssignades, substitucionsPendents, CLAU_ORDRE, llegeixOrdre, ordreFiles, canviaOrdre, carregarSubstitucions, carregarTotesAbsencies, obtenirVigilanciesCount, carregarProfessors, carregarHores }
}
