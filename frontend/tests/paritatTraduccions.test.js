// Els quatre idiomes tenen les mateixes claus i, a cada clau, els mateixos
// paràmetres {x}. Abans, una clau nova només en català sortia en català a la
// pantalla castellana o anglesa (fallbackLocale) sense que ningú se n'adonés.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const IDIOMES = ['ca', 'es', 'en', 'it']
const cataleg = idioma => JSON.parse(readFileSync(new URL(`../src/locales/${idioma}.json`, import.meta.url), 'utf8'))

// { 'a.b.c': text } de totes les fulles del catàleg
const textos = (objecte, prefix = '', resultat = {}) => {
  for (const [clau, valor] of Object.entries(objecte)) {
    if (valor && typeof valor === 'object') textos(valor, `${prefix}${clau}.`, resultat)
    else resultat[prefix + clau] = valor
  }
  return resultat
}

// Paràmetres amb nom de vue-i18n ({nom}, { nom }), sense repeticions
const parametres = text => [...new Set([...String(text).matchAll(/\{\s*([\w.]+)\s*\}/g)].map(m => m[1]))].sort()

const catalegs = Object.fromEntries(IDIOMES.map(idioma => [idioma, textos(cataleg(idioma))]))
const claus = idioma => Object.keys(catalegs[idioma]).sort()

for (const idioma of IDIOMES.slice(1)) {
  test(`${idioma} té les mateixes claus que el català`, () => {
    const ca = new Set(claus('ca')), altre = new Set(claus(idioma))
    assert.deepEqual({ falten: [...ca].filter(c => !altre.has(c)), sobren: [...altre].filter(c => !ca.has(c)) }, { falten: [], sobren: [] })
  })

  test(`${idioma} fa servir els mateixos paràmetres que el català`, () => {
    const diferents = claus('ca')
      .filter(clau => clau in catalegs[idioma])
      .filter(clau => parametres(catalegs.ca[clau]).join() !== parametres(catalegs[idioma][clau]).join())
      .map(clau => `${clau}: ca {${parametres(catalegs.ca[clau])}} / ${idioma} {${parametres(catalegs[idioma][clau])}}`)
    assert.deepEqual(diferents, [])
  })
}

test('el guardià detecta una clau que falta i un paràmetre diferent', () => {
  assert.deepEqual(Object.keys(textos({ a: { b: 'x', c: { d: 'y' } } })), ['a.b', 'a.c.d'])
  assert.deepEqual(parametres('{n} de { total } ({n})'), ['n', 'total'])
  assert.notDeepEqual(parametres('{count} files'), parametres('{n} files'))
})
