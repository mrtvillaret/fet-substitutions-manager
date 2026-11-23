import clientApi from './client.js'

// Resposta HTTP completa: conserva el cos, les capçaleres i el rebuig original.
export const frangesAmb = (client, ...args) =>
  client.get('/api/estadistiques/franges', ...args)
export const franges = (...args) => frangesAmb(clientApi, ...args)

export const professorAmb = (client, nom, ...args) =>
  client.get(`/api/estadistiques/professor/${encodeURIComponent(nom)}`, ...args)
export const professor = (nom, ...args) => professorAmb(clientApi, nom, ...args)

export const detallClassesAmb = (client, ...args) =>
  client.get('/api/estadistiques/classes/detall', ...args)
export const detallClasses = (...args) => detallClassesAmb(clientApi, ...args)

export const batchAmb = (client, ...args) =>
  client.get('/api/estadistiques/batch', ...args)
export const batch = (...args) => batchAmb(clientApi, ...args)
