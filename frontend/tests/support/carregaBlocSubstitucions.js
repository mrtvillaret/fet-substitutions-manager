import { readFileSync, existsSync } from 'node:fs'
import { avisaError, marcaAvisat, esErrorSilencios } from '../../src/errorsApi.js'

// Executa el mateix bloc abans de l'extracció i el cos del composable després.
// Les dependències de navegador i API són dobles explícits, sense xarxa.
export function carregaBloc(nom, fragments, noms, dependencies) {
  dependencies = { avisaError, marcaAvisat, esErrorSilencios, ...dependencies }
  const arrel = new URL('../../src/', import.meta.url)
  const fitxer = new URL(`composables/${nom}.js`, arrel)
  let codi
  if (existsSync(fitxer)) {
    codi = readFileSync(fitxer, 'utf8').replace(/^import .*\n/gm, '').replace('export function', 'function')
    return new Function(...Object.keys(dependencies), `${codi}; return ${nom}(dependents)`)(...Object.values(dependencies))
  }
  const vista = readFileSync(new URL('views/SubstitucionsView.vue', arrel), 'utf8')
  codi = fragments.map(([inici, fi]) => vista.slice(vista.indexOf(inici), vista.indexOf(fi, vista.indexOf(inici)))).join('\n')
  codi = codi.replace(/defineExpose\(\{[\s\S]*?\}\)\n/, '')
  return new Function(...Object.keys(dependencies), `${codi}; return { ${noms.join(', ')} }`)(...Object.values(dependencies))
}
