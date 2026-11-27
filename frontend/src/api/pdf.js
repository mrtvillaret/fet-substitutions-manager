import clientApi from './client.js'

// Resposta HTTP completa: conserva el cos, les capçaleres i el rebuig original.

// Els PDF (i els informes en PDF) arriben com a Blob
const ambBlob = (params) => ({ params, responseType: 'blob' })

export const completAmb = (client, data, params) => client.get(`/api/pdf/complete/${data}`, ambBlob(params))
export const complet = (data, params) => completAmb(clientApi, data, params)

export const vigilanciesDelDiaAmb = (client, data, params) => client.get(`/api/pdf/vigilancies/${data}`, ambBlob(params))
export const vigilanciesDelDia = (data, params) => vigilanciesDelDiaAmb(clientApi, data, params)

export const vigilanciesIntervalAmb = (client, params) => client.get('/api/pdf/vigilancies/interval', ambBlob(params))
export const vigilanciesInterval = (params) => vigilanciesIntervalAmb(clientApi, params)

export const informeDireccioAmb = (client, params) => client.get('/api/informes/direccio', ambBlob(params))
export const informeDireccio = (params) => informeDireccioAmb(clientApi, params)

export const informeProfessorAmb = (client, params) => client.get('/api/informes/professor', ambBlob(params))
export const informeProfessor = (params) => informeProfessorAmb(clientApi, params)

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
