import clientApi from './client.js'

// Es conserva la resposta HTTP completa (cos i capçaleres) i el rebuig original.
export const horariAmb = (client, ...args) =>
  client.get('/api/scheduler/horari', ...args)
export const horari = (...args) => horariAmb(clientApi, ...args)

export const pinsAmb = (client, ...args) =>
  client.post('/api/scheduler/restriccions/pin', ...args)
export const pins = (...args) => pinsAmb(clientApi, ...args)

export const recalculaCostAmb = (client, ...args) =>
  client.post('/api/scheduler/recalcular-cost', ...args)
export const recalculaCost = (...args) => recalculaCostAmb(clientApi, ...args)

export const publicaAmb = (client, ...args) =>
  client.post('/api/scheduler/publicar', ...args)
export const publica = (...args) => publicaAmb(clientApi, ...args)

export const restriccionsAmb = (client, ...args) =>
  client.get('/api/scheduler/restriccions', ...args)
export const restriccions = (...args) => restriccionsAmb(clientApi, ...args)

export const treuInexistentsAmb = (client, ...args) =>
  client.post('/api/scheduler/restriccions/treure-inexistents', ...args)
export const treuInexistents = (...args) => treuInexistentsAmb(clientApi, ...args)

export const ultimResultatAmb = (client, ...args) =>
  client.get('/api/scheduler/ultim-resultat', ...args)
export const ultimResultat = (...args) => ultimResultatAmb(clientApi, ...args)

export const cursDatesAmb = (client, ...args) =>
  client.get('/api/scheduler/curs-dates', ...args)
export const cursDates = (...args) => cursDatesAmb(clientApi, ...args)

export const desaConfiguracioAmb = (client, ...args) =>
  client.put('/api/scheduler/config', ...args)
export const desaConfiguracio = (...args) => desaConfiguracioAmb(clientApi, ...args)

export const desaDatesAmb = (client, ...args) =>
  client.put('/api/scheduler/dates', ...args)
export const desaDates = (...args) => desaDatesAmb(clientApi, ...args)

export const sessionsInfoAmb = (client, nivells, ...args) =>
  client.get(`/api/scheduler/sessions-info?nivells=${nivells}`, ...args)
export const sessionsInfo = (nivells, ...args) => sessionsInfoAmb(clientApi, nivells, ...args)

export const configuracioAmb = (client, ...args) =>
  client.get('/api/scheduler/config', ...args)
export const configuracio = (...args) => configuracioAmb(clientApi, ...args)

export const datesAmb = (client, ...args) =>
  client.get('/api/scheduler/dates', ...args)
export const dates = (...args) => datesAmb(clientApi, ...args)

export const assignaturesActivesAmb = (client, ...args) =>
  client.get('/api/scheduler/assignatures-actives', ...args)
export const assignaturesActives = (...args) => assignaturesActivesAmb(clientApi, ...args)

export const motorsAmb = (client, ...args) =>
  client.get('/api/scheduler/motors', ...args)
export const motors = (...args) => motorsAmb(clientApi, ...args)

export const costosProfessorsAmb = (client, ...args) =>
  client.get('/api/scheduler/costos-professors', ...args)
export const costosProfessors = (...args) => costosProfessorsAmb(clientApi, ...args)

export const generaAmb = (client, ...args) =>
  client.post('/api/scheduler/generate', ...args)
export const genera = (...args) => generaAmb(clientApi, ...args)

export const analisiAmb = (client, ...args) =>
  client.post('/api/scheduler/analisi', ...args)
export const analisi = (...args) => analisiAmb(clientApi, ...args)

export const desaRestriccionsAmb = (client, ...args) =>
  client.put('/api/scheduler/restriccions', ...args)
export const desaRestriccions = (...args) => desaRestriccionsAmb(clientApi, ...args)

export const desaCostosProfessorsAmb = (client, ...args) =>
  client.put('/api/scheduler/costos-professors', ...args)
export const desaCostosProfessors = (...args) => desaCostosProfessorsAmb(clientApi, ...args)
