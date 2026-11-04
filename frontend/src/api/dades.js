import clientApi from './client.js'

export const professorsAmb = async (client) => (await client.get('/api/dades/professors')).data
export const professors = () => professorsAmb(clientApi)
export const reanomenaProfessorAmb = async (client, cos) =>
  (await client.post('/api/dades/professors/reanomena', cos)).data
export const reanomenaProfessor = (cos) => reanomenaProfessorAmb(clientApi, cos)
export const analitzaPurgaAmb = async (client, cos) =>
  (await client.post('/api/dades/purga/analitzar', cos)).data
export const analitzaPurga = (cos) => analitzaPurgaAmb(clientApi, cos)
export const executaPurgaAmb = async (client, cos) =>
  (await client.post('/api/dades/purga/executar', cos)).data
export const executaPurga = (cos) => executaPurgaAmb(clientApi, cos)
