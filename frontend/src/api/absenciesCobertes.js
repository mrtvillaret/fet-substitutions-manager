import clientApi from './client.js'

export const llistaAmb = async (client) => (await client.get('/api/absencies-cobertes')).data
export const llista = () => llistaAmb(clientApi)
export const creaAmb = async (client, cos) => (await client.post('/api/absencies-cobertes', cos)).data
export const crea = (cos) => creaAmb(clientApi, cos)
export const editaAmb = async (client, professor, cos) =>
  (await client.put(`/api/absencies-cobertes/${professor}`, cos)).data
export const edita = (professor, cos) => editaAmb(clientApi, professor, cos)
export const esborraAmb = async (client, id) => (await client.delete(`/api/absencies-cobertes/${id}`)).data
export const esborra = (id) => esborraAmb(clientApi, id)
