import clientApi from './client.js'

const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }
const get = async (client, url) => (await client.get(url)).data
const post = async (client, url, cos, opcions) =>
  (await (opcions ? client.post(url, cos, opcions) : client.post(url, cos))).data
const put = async (client, url, cos) => (await client.put(url, cos)).data
const del = async (client, url, opcions) =>
  (await (opcions ? client.delete(url, opcions) : client.delete(url))).data

export const nivellsAmb = (client) => get(client, '/api/config/nivells')
export const nivells = () => nivellsAmb(clientApi)
export const creaNivellAmb = (client, cos) => post(client, '/api/config/nivells', cos)
export const creaNivell = (cos) => creaNivellAmb(clientApi, cos)
export const assignaturesAmb = (client, nivell) => get(client, `/api/config/assignatures/${nivell}`)
export const assignatures = (nivell) => assignaturesAmb(clientApi, nivell)
export const creaAssignaturaAmb = (client, nivell, cos) => post(client, `/api/config/assignatures/${nivell}`, cos)
export const creaAssignatura = (nivell, cos) => creaAssignaturaAmb(clientApi, nivell, cos)
export const esborraAssignaturaAmb = (client, nivell, nom) =>
  del(client, `/api/config/assignatures/${nivell}/${encodeURIComponent(nom)}`)
export const esborraAssignatura = (nivell, nom) => esborraAssignaturaAmb(clientApi, nivell, nom)
export const grupsAmb = (client, nivell) => get(client, `/api/config/grups/${nivell}`)
export const grups = (nivell) => grupsAmb(clientApi, nivell)
export const creaGrupAmb = (client, nivell, cos) => post(client, `/api/config/grups/${nivell}`, cos)
export const creaGrup = (nivell, cos) => creaGrupAmb(clientApi, nivell, cos)
export const aulesAmb = (client) => get(client, '/api/config/aules')
export const aules = () => aulesAmb(clientApi)
export const creaAulaAmb = (client, cos) => post(client, '/api/config/aules', cos)
export const creaAula = (cos) => creaAulaAmb(clientApi, cos)
export const esborraAulaAmb = (client, codi) => del(client, `/api/config/aules/${encodeURIComponent(codi)}`)
export const esborraAula = (codi) => esborraAulaAmb(clientApi, codi)
export const comptaAssignacionsAmb = (client, url) => get(client, `${url}/assignacions`)
export const comptaAssignacions = (url) => comptaAssignacionsAmb(clientApi, url)
export const esborraElementAmb = (client, url, ambAssignacions) =>
  del(client, url, { params: { amb_assignacions: ambAssignacions } })
export const esborraElement = (url, ambAssignacions) => esborraElementAmb(clientApi, url, ambAssignacions)

export const assignacionsObsoletesAmb = (client) => get(client, '/api/config/assignacions-obsoletes')
export const assignacionsObsoletes = () => assignacionsObsoletesAmb(clientApi)
export const assignacionsAmb = (client) => get(client, '/api/config/assignacions')
export const assignacions = () => assignacionsAmb(clientApi)
export const creaAssignacioAmb = (client, cos) => post(client, '/api/config/assignacions', cos)
export const creaAssignacio = (cos) => creaAssignacioAmb(clientApi, cos)
export const editaAssignacioAmb = (client, id, cos) => put(client, `/api/config/assignacions/${id}`, cos)
export const editaAssignacio = (id, cos) => editaAssignacioAmb(clientApi, id, cos)
export const esborraAssignacioAmb = (client, id) => del(client, `/api/config/assignacions/${id}`)
export const esborraAssignacio = (id) => esborraAssignacioAmb(clientApi, id)
export const esborraAssignacionsAmb = (client, cos) => del(client, '/api/config/assignacions', { data: cos })
export const esborraAssignacions = (cos) => esborraAssignacionsAmb(clientApi, cos)

export const previsualitzaImportacioAmb = (client) => get(client, '/api/config/importar-assignacions/preview')
export const previsualitzaImportacio = () => previsualitzaImportacioAmb(clientApi)
export const simulaImportacioAmb = (client, cos) => post(client, '/api/config/importar-assignacions/dry-run', cos)
export const simulaImportacio = (cos) => simulaImportacioAmb(clientApi, cos)
export const simulaImportacioCsvAmb = (client, formData) =>
  post(client, '/api/config/importar-assignacions-csv/dry-run', formData, multipart)
export const simulaImportacioCsv = (formData) => simulaImportacioCsvAmb(clientApi, formData)
export const importaCsvAmb = (client, formData) =>
  post(client, '/api/config/importar-assignacions-csv', formData, multipart)
export const importaCsv = (formData) => importaCsvAmb(clientApi, formData)
export const importaAmb = (client, cos) => post(client, '/api/config/importar-assignacions', cos)
export const importa = (cos) => importaAmb(clientApi, cos)

export const afinitatsAmb = (client) => get(client, '/api/config/afinitats')
export const afinitats = () => afinitatsAmb(clientApi)
export const desaAfinitatsAmb = (client, cos) => put(client, '/api/config/afinitats', cos)
export const desaAfinitats = (cos) => desaAfinitatsAmb(clientApi, cos)
export const editaElementAmb = (client, url, cos) => put(client, url, cos)
export const editaElement = (url, cos) => editaElementAmb(clientApi, url, cos)
