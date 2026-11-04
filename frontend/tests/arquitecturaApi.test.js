import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join, relative } from 'node:path'

const arrel = fileURLToPath(new URL('../src/', import.meta.url))
const fitxers = (carpeta) => readdirSync(carpeta, { withFileTypes: true }).flatMap(entrada => {
  const ruta = join(carpeta, entrada.name)
  return entrada.isDirectory() ? fitxers(ruta) : [ruta]
})

test('només api/ pot esmentar axios; useAplicacio només configura el client compartit', () => {
  const infraccions = []
  for (const ruta of fitxers(arrel)) {
    const nom = relative(arrel, ruta)
    if (nom.startsWith('api/') || !/\.(?:js|ts|vue|html|jsx|tsx)$/.test(nom)) continue
    const text = readFileSync(ruta, 'utf8')
    if (/\baxios\b/i.test(text)) infraccions.push(`${nom}: axios fora de la capa API`)
    if (/from\s*['"][^'"]*\/api\/client(?:\.js)?['"]/.test(text)) {
      if (nom !== 'composables/useAplicacio.js') infraccions.push(`${nom}: importa el client HTTP directament`)
      if (/\bclientHttp\s*\.\s*(?:get|post|put|patch|delete|request|head|options)\s*\(/.test(text)) {
        infraccions.push(`${nom}: fa peticions fora d'un mòdul de domini`)
      }
    }
  }
  assert.deepEqual(infraccions, [])
})

test('els mòduls de domini comparteixen client.js i només aquest importa axios', () => {
  const carpeta = join(arrel, 'api')
  for (const ruta of fitxers(carpeta).filter(r => r.endsWith('.js'))) {
    const nom = relative(carpeta, ruta)
    const text = readFileSync(ruta, 'utf8')
    if (nom === 'client.js') {
      assert.match(text, /import axios from 'axios'/)
      continue
    }
    assert.doesNotMatch(text, /from\s*['"]axios['"]/, nom)
    if (nom !== 'errors.js') assert.match(text, /import clientApi from '\.\/client\.js'/, nom)
  }
})
