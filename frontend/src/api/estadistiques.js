import clientApi from './client.js'

// Resposta HTTP completa: conserva el cos, les capçaleres i el rebuig original.
export const resumAmb = (client, ...args) =>
  client.get('/api/estadistiques/resum', ...args)
export const resum = (...args) => resumAmb(clientApi, ...args)

export const professorsAmb = (client, ...args) =>
  client.get('/api/estadistiques/professors', ...args)
export const professors = (...args) => professorsAmb(clientApi, ...args)

export const temporalAmb = (client, ...args) =>
  client.get('/api/estadistiques/temporal', ...args)
export const temporal = (...args) => temporalAmb(clientApi, ...args)

export const classesAmb = (client, ...args) =>
  client.get('/api/estadistiques/classes', ...args)
export const classes = (...args) => classesAmb(clientApi, ...args)

export const taulaAmb = (client, ...args) =>
  client.get('/api/estadistiques/taula', ...args)
export const taula = (...args) => taulaAmb(clientApi, ...args)

export const frangesAmb = (client, ...args) =>
  client.get('/api/estadistiques/franges', ...args)
export const franges = (...args) => frangesAmb(clientApi, ...args)

export const professorAmb = (client, nom, ...args) =>
  client.get(`/api/estadistiques/professor/${encodeURIComponent(nom)}`, ...args)
export const professor = (nom, ...args) => professorAmb(clientApi, nom, ...args)

export const detallClassesAmb = (client, ...args) =>
  client.get('/api/estadistiques/classes/detall', ...args)
export const detallClasses = (...args) => detallClassesAmb(clientApi, ...args)

export const horesAmb = (client, ...args) =>
  client.get('/api/estadistiques/hores', ...args)
export const hores = (...args) => horesAmb(clientApi, ...args)

export const batchAmb = (client, ...args) =>
  client.get('/api/estadistiques/batch', ...args)
export const batch = (...args) => batchAmb(clientApi, ...args)
