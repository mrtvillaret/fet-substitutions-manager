import clientApi from './client.js'

// Es conserva la resposta HTTP completa (cos i capçaleres) i el rebuig original.
export const llistaAmb = (client, ...args) =>
  client.get('/api/settings/institucions', ...args)
export const llista = (...args) => llistaAmb(clientApi, ...args)

export const editaAmb = (client, slug, ...args) =>
  client.put(`/api/settings/institucions/${slug}`, ...args)
export const edita = (slug, ...args) => editaAmb(clientApi, slug, ...args)

export const creaAmb = (client, ...args) =>
  client.post('/api/settings/institucions', ...args)
export const crea = (...args) => creaAmb(clientApi, ...args)

export const estatAmb = (client, slug, ...args) =>
  client.put(`/api/settings/institucions/${slug}/status`, ...args)
export const estat = (slug, ...args) => estatAmb(clientApi, slug, ...args)
