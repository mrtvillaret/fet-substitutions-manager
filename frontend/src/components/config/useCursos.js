import { ref, computed } from 'vue'
import axios from 'axios'

// Estat compartit a nivell de mòdul: el tab Cursos (llista + CRUD) i el tab
// Sistema (avisos XML + suggeriment de curs futur) llegeixen la mateixa llista,
// de manera que crear/esborrar un curs actualitza els avisos en viu.
const cursos = ref([])
const carregantCursos = ref(false)

// Cursos vigents/futurs que arrencarien amb l'horari d'un curs anterior
const avisosXml = ref([])

const parseIsoDate = (value) => {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const formatIsoDate = (dateObj) => {
  if (!dateObj) return null
  const year = dateObj.getFullYear()
  const month = String(dateObj.getMonth() + 1).padStart(2, '0')
  const day = String(dateObj.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const carregarCursos = async () => {
  carregantCursos.value = true
  try {
    const { data } = await axios.get('/api/cursos')
    cursos.value = data
  } finally {
    carregantCursos.value = false
  }
}

const carregarAvisosXml = async () => {
  try {
    const { data } = await axios.get('/api/cursos/validacio-xml')
    avisosXml.value = data
  } catch (error) {
    avisosXml.value = []
  }
}

// Si hi ha un curs que comença en el futur, oferir la seva data d'inici com a drecera:
// és el cas típic de "preparar l'horari del curs vinent".
const cursFuturSuggerit = computed(() => {
  const avui = formatIsoDate(new Date())
  return [...cursos.value]
    .filter(c => c.data_inici > avui)
    .sort((a, b) => a.data_inici.localeCompare(b.data_inici))[0] || null
})

export function useCursos() {
  return {
    cursos,
    carregantCursos,
    avisosXml,
    parseIsoDate,
    formatIsoDate,
    carregarCursos,
    carregarAvisosXml,
    cursFuturSuggerit,
  }
}
