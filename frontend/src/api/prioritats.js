import clientApi from './client.js'

export const activitatsAlliberablesAmb = async (client, opcions) =>
  (await client.get('/api/prioritats/activitats-alliberables', opcions)).data
export const activitatsAlliberables = (opcions) => activitatsAlliberablesAmb(clientApi, opcions)
export const desaActivitatsAlliberablesAmb = async (client, cos) =>
  (await client.put('/api/prioritats/activitats-alliberables', cos)).data
export const desaActivitatsAlliberables = (cos) => desaActivitatsAlliberablesAmb(clientApi, cos)
export const noSubstituirAmb = async (client) => (await client.get('/api/prioritats/no-substituir')).data
export const noSubstituir = () => noSubstituirAmb(clientApi)
export const assignaturesAmb = async (client) => (await client.get('/api/prioritats/assignatures')).data
export const assignatures = () => assignaturesAmb(clientApi)
export const categoriesAmb = async (client) => (await client.get('/api/prioritats/categories')).data
export const categories = () => categoriesAmb(clientApi)
export const desaTotAmb = async (client, cos) => (await client.put('/api/prioritats/desar-tot', cos)).data
export const desaTot = (cos) => desaTotAmb(clientApi, cos)
export const afegeixNoSubstituirAmb = async (client, assignatura) =>
  (await client.post('/api/prioritats/no-substituir', { assignatura })).data
export const afegeixNoSubstituir = (assignatura) => afegeixNoSubstituirAmb(clientApi, assignatura)
export const esborraNoSubstituirAmb = async (client, assignatura) =>
  (await client.delete(`/api/prioritats/no-substituir/${encodeURIComponent(assignatura)}`)).data
export const esborraNoSubstituir = (assignatura) => esborraNoSubstituirAmb(clientApi, assignatura)
