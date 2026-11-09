import { readFileSync, existsSync } from 'node:fs'
import { avisaError, marcaAvisat, esErrorSilencios } from '../../src/errorsApi.js'

// Caracterització: executa els fragments originals abans de moure'ls i el
// composable real després, amb els mateixos dobles d'API i navegador.
export function carregaBlocVista(vista, nom, fragments, noms, dependencies) {
  dependencies = { avisaError, marcaAvisat, esErrorSilencios, ...dependencies }
  const arrel = new URL('../../src/', import.meta.url)
  const fitxer = new URL(`composables/${nom}.js`, arrel)
  if (existsSync(fitxer)) {
    const codi = readFileSync(fitxer, 'utf8').replace(/^import .*\n/gm, '').replace('export function', 'function')
    return new Function(...Object.keys(dependencies), `${codi}; return ${nom}(dependents)`)(...Object.values(dependencies))
  }
  const original = readFileSync(new URL(vista, arrel), 'utf8')
  const codi = fragments.map(([inici, fi]) => {
    const des = original.indexOf(inici)
    const fins = Math.min(...[fi].flat().map(final => original.indexOf(final, des)).filter(posicio => posicio >= 0))
    if (des < 0 || !Number.isFinite(fins)) throw new Error(`Fragment inexistent: ${inici}`)
    return original.slice(des, fins)
  }).join('\n')
  const externes = Object.fromEntries(Object.entries(dependencies).filter(([nom]) => !new RegExp(`^const ${nom}\\b`, 'm').test(codi)))
  return new Function(...Object.keys(externes), `${codi}; return { ${noms.join(', ')} }`)(...Object.values(externes))
}
