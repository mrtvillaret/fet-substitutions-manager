import { provaCrides, COS, LECTURA } from './support/crides.js'
import * as api from '../src/api/planificador.js'

// Cada funció: [funció, mètode HTTP, arguments, URL, arguments HTTP que passen tal qual]
provaCrides([
  [api.horariAmb, 'get', [], '/api/scheduler/horari', LECTURA],
  [api.pinsAmb, 'post', [], '/api/scheduler/restriccions/pin', COS],
  [api.recalculaCostAmb, 'post', [], '/api/scheduler/recalcular-cost', COS],
  [api.publicaAmb, 'post', [], '/api/scheduler/publicar', COS],
  [api.restriccionsAmb, 'get', [], '/api/scheduler/restriccions', LECTURA],
  [api.treuInexistentsAmb, 'post', [], '/api/scheduler/restriccions/treure-inexistents', COS],
  [api.ultimResultatAmb, 'get', [], '/api/scheduler/ultim-resultat', LECTURA],
  [api.cursDatesAmb, 'get', [], '/api/scheduler/curs-dates', LECTURA],
  [api.desaConfiguracioAmb, 'put', [], '/api/scheduler/config', COS],
  [api.desaDatesAmb, 'put', [], '/api/scheduler/dates', COS],
  [api.sessionsInfoAmb, 'get', ['ESO,BATX'], '/api/scheduler/sessions-info?nivells=ESO,BATX', LECTURA],
  [api.configuracioAmb, 'get', [], '/api/scheduler/config', LECTURA],
  [api.datesAmb, 'get', [], '/api/scheduler/dates', LECTURA],
  [api.assignaturesActivesAmb, 'get', [], '/api/scheduler/assignatures-actives', LECTURA],
  [api.motorsAmb, 'get', [], '/api/scheduler/motors', LECTURA],
  [api.costosProfessorsAmb, 'get', [], '/api/scheduler/costos-professors', LECTURA],
  [api.generaAmb, 'post', [], '/api/scheduler/generate', COS],
  [api.analisiAmb, 'post', [], '/api/scheduler/analisi', COS],
  [api.desaRestriccionsAmb, 'put', [], '/api/scheduler/restriccions', COS],
  [api.desaCostosProfessorsAmb, 'put', [], '/api/scheduler/costos-professors', COS]
])
