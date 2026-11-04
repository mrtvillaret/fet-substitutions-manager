import clientApi from './client.js'

// Resposta HTTP completa: conserva el cos, les capçaleres i el rebuig original.
export const descarregaAmb = (client, url, ...args) =>
  client.get(url, ...args)
export const descarrega = (url, ...args) => descarregaAmb(clientApi, url, ...args)

export const professorsInformeAmb = (client, ...args) =>
  client.get('/api/informes/professors-llista', ...args)
export const professorsInforme = (...args) => professorsInformeAmb(clientApi, ...args)

export const creaDisponiblesTotsDiesAmb = (client, ...args) =>
  client.post('/api/pdf/disponibles-tots-dies', ...args)
export const creaDisponiblesTotsDies = (...args) => creaDisponiblesTotsDiesAmb(clientApi, ...args)

export const preferenciesAmb = (client, ...args) =>
  client.get('/api/pdf/preferences', ...args)
export const preferencies = (...args) => preferenciesAmb(clientApi, ...args)

export const desaPreferenciesAmb = (client, ...args) =>
  client.put('/api/pdf/preferences', ...args)
export const desaPreferencies = (...args) => desaPreferenciesAmb(clientApi, ...args)

export const validacionsAmb = (client, data, ...args) =>
  client.get(`/api/pdf/${data}/validacions`, ...args)
export const validacions = (data, ...args) => validacionsAmb(clientApi, data, ...args)

export const comptesSenseNivellAmb = (client, ...args) =>
  client.get('/api/pdf/vigilancies/comptes-sense-nivell', ...args)
export const comptesSenseNivell = (...args) => comptesSenseNivellAmb(clientApi, ...args)
