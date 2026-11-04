import clientApi from './client.js'

export const llistaAmb = async (client) => (await client.get('/api/cursos')).data
export const llista = () => llistaAmb(clientApi)
export const validacioXmlAmb = async (client) => (await client.get('/api/cursos/validacio-xml')).data
export const validacioXml = () => validacioXmlAmb(clientApi)
export const creaAmb = async (client, cos) => (await client.post('/api/cursos', cos)).data
export const crea = (cos) => creaAmb(clientApi, cos)
export const editaAmb = async (client, id, cos) => (await client.put(`/api/cursos/${id}`, cos)).data
export const edita = (id, cos) => editaAmb(clientApi, id, cos)
export const esborraAmb = async (client, id) => (await client.delete(`/api/cursos/${id}`)).data
export const esborra = (id) => esborraAmb(clientApi, id)
