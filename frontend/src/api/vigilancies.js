// Crides HTTP de les vigilàncies d'un dia (/api/vigilancies). Només les crides:
// cap estat ni cap missatge a l'usuari, que són de qui les fa servir.
import clientApi from './client.js'

const base = (data) => `/api/vigilancies/${data}`

// Les vigilàncies del dia, en l'ordre desat dins de cada hora
export const llistaAmb = async (client, data, ...opcions) => (await client.get(base(data), ...opcions)).data
export const llista = async (data, ...opcions) => llistaAmb(clientApi, data, ...opcions)

// Crea una vigilància; retorna la fila creada (amb l'id)
export const creaAmb = async (client, data, fila) => (await client.post(base(data), fila)).data.vigilancia
export const crea = async (data, fila) => creaAmb(clientApi, data, fila)

// Canvia els camps de `canvis`; retorna la resposta (amb el nou updated_at)
export const editaAmb = async (client, data, id, canvis, ...opcions) =>
  (await client.put(`${base(data)}/${id}`, canvis, ...opcions)).data
export const edita = async (data, id, canvis, ...opcions) => editaAmb(clientApi, data, id, canvis, ...opcions)

export const esborraAmb = async (client, data, id, { updatedAt = null, force = false, silent = false } = {}) => {
  const params = {}
  if (updatedAt) params.updated_at = updatedAt
  if (force) params.force = true
  const opcions = { params }
  if (silent) opcions._silent = true
  await client.delete(`${base(data)}/${id}`, opcions)
}
export const esborra = async (data, id, opcions) => esborraAmb(clientApi, data, id, opcions)

// Disponibles d'una consulta ({tipus, grups, aula}); els paràmetres buits no
// s'envien, igual que feia la vista quan construïa l'URL.
export const disponiblesAmb = async (client, data, hora, { tipus, grups, aula, vigilancia_id } = {}) => {
  let url = `${base(data)}/${hora}/disponibles`
  const params = new URLSearchParams()
  if (tipus) params.append('tipus', tipus)
  if (grups) params.append('grups', grups)
  if (aula) params.append('aula', aula)
  if (vigilancia_id) params.append('vigilancia_id', vigilancia_id)
  if (params.toString()) url += `?${params.toString()}`
  return (await client.get(url)).data
}
export const disponibles = async (data, hora, opcions) =>
  disponiblesAmb(clientApi, data, hora, opcions)

// Disponibles per a moltes consultes ({hora, tipus, grups, aula}): {clau: [professors]}
export const disponiblesEnBlocAmb = async (client, data, queries, ...opcions) =>
  (await client.post(`${base(data)}/disponibles-batch`, { queries }, ...opcions)).data?.results || {}
export const disponiblesEnBloc = async (data, queries, ...opcions) =>
  disponiblesEnBlocAmb(clientApi, data, queries, ...opcions)

// Tot el que té un professor a una hora (l'ajuda del vigilant)
export const ajudaVigilantAmb = async (client, data, hora, nom) =>
  (await client.get(`${base(data)}/${hora}/professor`, { params: { nom }, _silent: true })).data
export const ajudaVigilant = async (data, hora, nom) =>
  ajudaVigilantAmb(clientApi, data, hora, nom)

export const configuracioAmb = async (client, opcions) =>
  (await client.get('/api/vigilancies/config', opcions)).data
export const configuracio = async (opcions) => configuracioAmb(clientApi, opcions)

// Si l'ordre del dia té retocs fets a mà (que «Ordena» perdria)
export const teOrdreManualAmb = async (client, data) =>
  (await client.get(`${base(data)}/ordre`)).data.ordre_manual
export const teOrdreManual = async (data) => teOrdreManualAmb(clientApi, data)

// Desa l'ordre de les files d'una hora (els ids, de la primera a l'última)
export const desaOrdreAmb = async (client, data, hora, ids) => {
  await client.put(`${base(data)}/ordre`, { hora, ids })
}
export const desaOrdre = async (data, hora, ids) => desaOrdreAmb(clientApi, data, hora, ids)

// «Ordena»: desa l'ordre automàtic de totes les hores
export const ordenaAmb = async (client, data) => (await client.post(`${base(data)}/sort`)).data
export const ordena = async (data) => ordenaAmb(clientApi, data)

export const assignaTitularsAmb = async (client, data) =>
  (await client.post(`${base(data)}/assign/titulars`)).data
export const assignaTitulars = async (data) => assignaTitularsAmb(clientApi, data)

export const assignaPendentsAmb = async (client, data, disponibles) =>
  (await client.post(`${base(data)}/assign/pendents?disponibles=${disponibles}`)).data
export const assignaPendents = async (data, disponibles) =>
  assignaPendentsAmb(clientApi, data, disponibles)

export const netejaAmb = async (client, data) => (await client.post(`${base(data)}/clear`)).data
export const neteja = async (data) => netejaAmb(clientApi, data)


// Conflictes del dia: la mateixa regla que la revisió i els PDF.
export const analisiAmb = async (client, data, ...opcions) => (await client.get(`${base(data)}/analisi`, ...opcions)).data
export const analisi = async (data, ...opcions) => analisiAmb(clientApi, data, ...opcions)
