import clientApi from './client.js'

export const reforcAmb = async (client, activitat, data) =>
  (await client.get(`/api/grups/reforcos/${encodeURIComponent(activitat)}`, { params: { data } })).data
export const reforc = (activitat, data) => reforcAmb(clientApi, activitat, data)

export const desaPeriodeAmb = async (client, cos) => (await client.post('/api/grups/periode', cos)).data
export const desaPeriode = (cos) => desaPeriodeAmb(clientApi, cos)

export const llistaAmb = async (client, data) => (await client.get(`/api/grups/${data}`)).data
export const llista = (data) => llistaAmb(clientApi, data)

export const desaAmb = async (client, data, cos) => (await client.put(`/api/grups/${data}`, cos)).data
export const desa = (data, cos) => desaAmb(clientApi, data, cos)

export const amagatsAmb = async (client) => (await client.get('/api/grups-amagats')).data
export const amagats = () => amagatsAmb(clientApi)

export const desaAmagatsAmb = async (client, grups) =>
  (await client.put('/api/grups-amagats', { grups })).data
export const desaAmagats = (grups) => desaAmagatsAmb(clientApi, grups)

export const abreviaturesAmb = async (client) => (await client.get('/api/config/abreviatures')).data
export const abreviatures = () => abreviaturesAmb(clientApi)
export const creaAbreviaturaAmb = async (client, cos) =>
  (await client.post('/api/config/abreviatures', cos)).data
export const creaAbreviatura = (cos) => creaAbreviaturaAmb(clientApi, cos)
export const editaAbreviaturaAmb = async (client, id, cos) =>
  (await client.put(`/api/config/abreviatures/${id}`, cos)).data
export const editaAbreviatura = (id, cos) => editaAbreviaturaAmb(clientApi, id, cos)
export const esborraAbreviaturaAmb = async (client, id) =>
  (await client.delete(`/api/config/abreviatures/${id}`)).data
export const esborraAbreviatura = (id) => esborraAbreviaturaAmb(clientApi, id)
