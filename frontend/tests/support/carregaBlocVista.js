import { readFileSync } from 'node:fs'
import * as errors from '../../src/api/errors.js'
import * as ordreAlfabetic from '../../src/ordreAlfabetic.js'

// Executa el composable real (src/composables/<nom>.js) amb les dependències
// de navegador i API com a dobles explícits, sense xarxa: el cos del
// composable, sense els seus imports, rep `dependencies` com a paràmetres.
export function carregaBlocVista(nom, dependencies) {
  // Els avisos d'error i l'ordre alfabètic, els reals, com els importen els composables
  dependencies = { ...errors, ...ordreAlfabetic, ...dependencies }
  const fitxer = new URL(`../../src/composables/${nom}.js`, import.meta.url)
  const codi = readFileSync(fitxer, 'utf8').replace(/^import .*\n/gm, '').replace('export function', 'function')
  return new Function(...Object.keys(dependencies), `${codi}; return ${nom}(dependents)`)(...Object.values(dependencies))
}
