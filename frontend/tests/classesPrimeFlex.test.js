import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { parse } from '@vue/compiler-sfc'

// PrimeFlex no és una dependència: una utilitat només és vàlida si el
// projecte la defineix al mateix component o en un full global.
const utilitat = /^(?:field|flex(?:-(?:wrap|column|row|1))?|align-items-\w+|justify-content-\w+|w-full|[mp][trblxy]?-\d+|gap-\d+|grid|col-\d+|text-(?:xs|sm|lg|xl|center|right|color-secondary)|font-(?:bold|semibold)|border-round|block|uppercase|shadow-sm|bg-primary-light|bg-slate-50|text-muted)$/
const definides = css => new Set([...css.matchAll(/\.([a-zA-Z_][\w-]*)/g)].map(m => m[1]))
const inactives = (source, css) => {
  const noms = definides(css)
  return [...source.matchAll(/(?<!:)\b(?:class|bodyClass|headerClass)="([^"]*)"/g)].flatMap(m => m[1].split(/\s+/)).filter(c => utilitat.test(c) && !noms.has(c))
}
test('cap classe utilitària depèn de PrimeFlex sense tenir definició pròpia', () => {
  const arrel = new URL('../src/', import.meta.url)
  const fitxers = readdirSync(arrel, { recursive: true }).filter(f => /\.(vue|css|html)$/.test(f))
  const estils = (f, styles) => styles.map(s => s.src ? readFileSync(new URL(`${dirname(f)}/${s.src}`, arrel), 'utf8') : s.content).join('\n')
  const globals = fitxers.flatMap(f => {
    const source = readFileSync(new URL(f, arrel), 'utf8')
    if (f.endsWith('.css') && !/^(components|views)\//.test(f)) return source
    if (f.endsWith('.vue')) return estils(f, parse(source).descriptor.styles.filter(s => !s.scoped))
    return []
  }).join('\n')
  const errors = []
  for (const f of fitxers.filter(f => f.endsWith('.vue') || f.endsWith('.template.html'))) {
    const source = readFileSync(new URL(f, arrel), 'utf8')
    const css = f.endsWith('.vue') ? estils(f, parse(source).descriptor.styles) : ''
    for (const c of inactives(source, globals + '\n' + css)) errors.push(`${f}: ${c}`)
  }
  assert.deepEqual(errors, [])
})
test('el guardià distingeix una utilitat definida d’una classe que no fa res', () => {
  assert.deepEqual(inactives('<div class="flex gap-2 component" />', '.flex { display: flex }'), ['gap-2'])
})
