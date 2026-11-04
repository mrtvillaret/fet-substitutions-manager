import clientApi from './client.js'

// Es conserva la resposta HTTP completa (cos i capçaleres) i el rebuig original.
export const surtAmb = (client, ...args) =>
  client.post('/api/logout', ...args)
export const surt = (...args) => surtAmb(clientApi, ...args)

export const perfilAmb = (client, ...args) =>
  client.get('/api/users/profile', ...args)
export const perfil = (...args) => perfilAmb(clientApi, ...args)

export const entraAmb = (client, ...args) =>
  client.post('/api/login', ...args)
export const entra = (...args) => entraAmb(clientApi, ...args)

export const entraDelegacioAmb = (client, delegacio, ...args) =>
  client.post(`${delegacio.replace(/\/$/, '')}/api/login`, ...args)
export const entraDelegacio = (delegacio, ...args) => entraDelegacioAmb(clientApi, delegacio, ...args)

export const canviaContrasenyaAmb = (client, ...args) =>
  client.put('/api/users/profile/password', ...args)
export const canviaContrasenya = (...args) => canviaContrasenyaAmb(clientApi, ...args)

export const tancaAltresSessionsAmb = (client, ...args) =>
  client.post('/api/users/profile/tancar-altres-sessions', ...args)
export const tancaAltresSessions = (...args) => tancaAltresSessionsAmb(clientApi, ...args)

export const canviaCentreAmb = (client, ...args) =>
  client.post('/api/users/profile/institucio', ...args)
export const canviaCentre = (...args) => canviaCentreAmb(clientApi, ...args)

export const llistaAmb = (client, ...args) =>
  client.get('/api/users', ...args)
export const llista = (...args) => llistaAmb(clientApi, ...args)

export const editaAmb = (client, id, ...args) =>
  client.put(`/api/users/${id}`, ...args)
export const edita = (id, ...args) => editaAmb(clientApi, id, ...args)

export const creaAmb = (client, ...args) =>
  client.post('/api/users', ...args)
export const crea = (...args) => creaAmb(clientApi, ...args)

export const desactivaAmb = (client, id, ...args) =>
  client.delete(`/api/users/${id}`, ...args)
export const desactiva = (id, ...args) => desactivaAmb(clientApi, id, ...args)

export const esborraAmb = (client, id, ...args) =>
  client.delete(`/api/users/${id}/hard`, ...args)
export const esborra = (id, ...args) => esborraAmb(clientApi, id, ...args)

