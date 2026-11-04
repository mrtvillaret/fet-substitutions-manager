// Crides HTTP de les substitucions d'un dia (/api/substitucions).
import clientApi from './client.js'

const base = (data) => `/api/substitucions/${data}`

export const llistaAmb = async (client, data, ordre) =>
  (await client.get(base(data), { params: { ordre }, _silent: true })).data
export const llista = async (data, ordre) => llistaAmb(clientApi, data, ordre)

export const llistaSimpleAmb = async (client, data) => (await client.get(base(data))).data
export const llistaSimple = async (data) => llistaSimpleAmb(clientApi, data)

export const llistaTotesAmb = async (client, data, { silent = false } = {}) => {
  const url = `${base(data)}?include_all=true`
  return (await (silent ? client.get(url, { _silent: true }) : client.get(url))).data
}
export const llistaTotes = async (data, opcions) => llistaTotesAmb(clientApi, data, opcions)

export const generaAmb = async (client, data, regenerarTot) =>
  (await client.post(`${base(data)}/generar?regenerar_tot=${regenerarTot}`)).data
export const genera = async (data, regenerarTot) => generaAmb(clientApi, data, regenerarTot)

export const actualitzaAmb = async (client, data, hora, professorAbsent, cos, { silent = false } = {}) => {
  const peticio = [
    `${base(data)}/${hora}/${professorAbsent}`,
    cos
  ]
  if (silent) peticio.push({ _silent: true })
  return (await client.put(...peticio)).data
}
export const actualitza = async (data, hora, professorAbsent, cos, opcions) =>
  actualitzaAmb(clientApi, data, hora, professorAbsent, cos, opcions)

export const desaAbsenciesAmb = async (client, data, professor, cos, { silent = false } = {}) => {
  const peticio = [`${base(data)}/absencies/${encodeURIComponent(professor)}`, cos]
  if (silent) peticio.push({ _silent: true })
  return (await client.put(...peticio)).data
}
export const desaAbsencies = async (data, professor, cos, opcions) =>
  desaAbsenciesAmb(clientApi, data, professor, cos, opcions)

export const horesProfessorAmb = async (client, data, professor) =>
  (await client.get(`${base(data)}/hores-professor/${encodeURIComponent(professor)}`)).data
export const horesProfessor = async (data, professor) => horesProfessorAmb(clientApi, data, professor)

export const reassignaProblematiquesAmb = async (client, data) =>
  (await client.post(`${base(data)}/reassign-problematics`)).data
export const reassignaProblematiques = async (data) => reassignaProblematiquesAmb(clientApi, data)

// La dependència injectable permet comprovar que totes les hores viatgen en
// una sola petició sense lligar el test a axios.
export const disponiblesEnBlocAmb = async (client, data, hores) =>
  (await client.post(
    `${base(data)}/disponibles-batch`,
    { hores },
    { _silent: true }
  )).data?.results || {}

export const disponiblesEnBloc = async (data, hores) => disponiblesEnBlocAmb(clientApi, data, hores)
