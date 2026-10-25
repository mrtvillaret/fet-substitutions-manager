// Crides HTTP de les vigilàncies d'un dia (/api/vigilancies). Només les crides:
// cap estat ni cap missatge a l'usuari, que són de qui les fa servir.
import axios from 'axios'

const base = (data) => `/api/vigilancies/${data}`

// Les vigilàncies del dia, en l'ordre desat dins de cada hora
export const llista = async (data) => (await axios.get(base(data))).data

// Crea una vigilància; retorna la fila creada (amb l'id)
export const crea = async (data, fila) => (await axios.post(base(data), fila)).data.vigilancia

// Canvia els camps de `canvis`; retorna la resposta (amb el nou updated_at)
export const edita = async (data, id, canvis) => (await axios.put(`${base(data)}/${id}`, canvis)).data

export const esborra = async (data, id, { updatedAt = null, force = false } = {}) => {
  const params = {}
  if (updatedAt) params.updated_at = updatedAt
  if (force) params.force = true
  await axios.delete(`${base(data)}/${id}`, { params })
}

// Disponibles per a moltes consultes ({hora, tipus, grups, aula}): {clau: [professors]}
export const disponiblesEnBloc = async (data, queries) =>
  (await axios.post(`${base(data)}/disponibles-batch`, { queries })).data?.results || {}

// Tot el que té un professor a una hora (l'ajuda del vigilant)
export const ajudaVigilant = async (data, hora, nom) =>
  (await axios.get(`${base(data)}/${hora}/professor`, { params: { nom }, _silent: true })).data

// Si l'ordre del dia té retocs fets a mà (que «Ordena» perdria)
export const teOrdreManual = async (data) => (await axios.get(`${base(data)}/ordre`)).data.ordre_manual

// Desa l'ordre de les files d'una hora (els ids, de la primera a l'última)
export const desaOrdre = async (data, hora, ids) => {
  await axios.put(`${base(data)}/ordre`, { hora, ids })
}

// «Ordena»: desa l'ordre automàtic de totes les hores
export const ordena = async (data) => (await axios.post(`${base(data)}/sort`)).data
