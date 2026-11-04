import clientApi from './client.js'

const getAmb = async (client, url, opcions) => (await client.get(url, opcions)).data

export const configuracioAmb = (client, opcions) => getAmb(client, '/api/config', opcions)
export const configuracio = (opcions) => configuracioAmb(clientApi, opcions)

export const professorsAmb = (client, opcions) => getAmb(client, '/api/professors', opcions)
export const professors = (opcions) => professorsAmb(clientApi, opcions)

export const professorsHorariAmb = (client, opcions) =>
  getAmb(client, '/api/horari/professors', opcions)
export const professorsHorari = (opcions) => professorsHorariAmb(clientApi, opcions)

export const professorsTotsAmb = (client, opcions) =>
  getAmb(client, '/api/horari/professors/all', opcions)
export const professorsTots = (opcions) => professorsTotsAmb(clientApi, opcions)

export const horesAmb = (client, opcions) => getAmb(client, '/api/hores', opcions)
export const hores = (opcions) => horesAmb(clientApi, opcions)

export const detectaGrupsAmb = (client, opcions) =>
  getAmb(client, '/api/horari/grups/detectar', opcions)
export const detectaGrups = (opcions) => detectaGrupsAmb(clientApi, opcions)

export const detectaAssignaturesAmb = (client, opcions) =>
  getAmb(client, '/api/horari/assignatures/detectar', opcions)
export const detectaAssignatures = (opcions) => detectaAssignaturesAmb(clientApi, opcions)
