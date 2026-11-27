import { provaCrides, COS, ESBORRA, LECTURA } from './support/crides.js'
import * as api from '../src/api/usuaris.js'

// Cada funció: [funció, mètode HTTP, arguments, URL, arguments HTTP que passen tal qual]
provaCrides([
  [api.surtAmb, 'post', [], '/api/logout', COS],
  [api.perfilAmb, 'get', [], '/api/users/profile', LECTURA],
  [api.entraAmb, 'post', [], '/api/login', COS],
  [api.entraDelegacioAmb, 'post', ['/demo/'], '/demo/api/login', COS],
  [api.canviaContrasenyaAmb, 'put', [], '/api/users/profile/password', COS],
  [api.tancaAltresSessionsAmb, 'post', [], '/api/users/profile/tancar-altres-sessions', COS],
  [api.canviaCentreAmb, 'post', [], '/api/users/profile/institucio', COS],
  [api.llistaAmb, 'get', [], '/api/users', LECTURA],
  [api.editaAmb, 'put', ['7'], '/api/users/7', COS],
  [api.creaAmb, 'post', [], '/api/users', COS],
  [api.desactivaAmb, 'delete', ['7'], '/api/users/7', ESBORRA],
  [api.esborraAmb, 'delete', ['7'], '/api/users/7/hard', ESBORRA]
])
