import { provaCrides, COS, LECTURA } from './support/crides.js'
import * as api from '../src/api/centres.js'

// Cada funció: [funció, mètode HTTP, arguments, URL, arguments HTTP que passen tal qual]
provaCrides([
  [api.llistaAmb, 'get', [], '/api/settings/institucions', LECTURA],
  [api.editaAmb, 'put', ['7'], '/api/settings/institucions/7', COS],
  [api.creaAmb, 'post', [], '/api/settings/institucions', COS],
  [api.estatAmb, 'put', ['7'], '/api/settings/institucions/7/status', COS]
])
