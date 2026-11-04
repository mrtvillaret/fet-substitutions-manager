import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'

const camps = new Set('InputText InputNumber InputSwitch Password Textarea Dropdown MultiSelect Calendar Checkbox RadioButton Slider SelectButton AutoComplete input textarea select'.split(' '))
const atribut = (node, nom) => node.props.find(p => p.type === 6 ? p.name === nom : p.name === 'bind' && p.arg?.content === nom)
const valor = p => p?.type === 6 ? p.value?.content : p?.exp?.content
function senseEtiqueta(template) {
  const nodes = []
  const visita = node => { if (node.type === 1) nodes.push(node); for (const fill of node.children || []) visita(fill) }
  visita(baseParse(template))
  return nodes.filter(n => camps.has(n.tag)).filter(n => {
    if (atribut(n, 'aria-label') || atribut(n, 'aria-labelledby')) return false
    const id = atribut(n, 'inputId') || atribut(n, 'id')
    return !id || !nodes.some(l => l.tag === 'label' && atribut(l, 'for')?.type === id.type && valor(atribut(l, 'for')) === valor(id))
  })
}
test('cada camp té una etiqueta associada o un nom accessible explícit', () => {
  const arrel = new URL('../src/', import.meta.url), errors = []
  for (const f of readdirSync(arrel, { recursive: true }).filter(f => f.endsWith('.vue') || f.endsWith('.template.html'))) {
    const source = readFileSync(new URL(f, arrel), 'utf8')
    const template = f.endsWith('.vue') ? parse(source).descriptor.template?.content : source
    if (!template) continue
    for (const n of senseEtiqueta(template)) errors.push(`${f}:${n.loc.start.line} ${n.tag}`)
  }
  assert.deepEqual(errors, [])
})
test('el guardià rebutja un camp sense etiqueta i un for que no coincideix', () => {
  assert.equal(senseEtiqueta('<label for="nom">Nom</label><InputText id="altre" />').length, 1)
  assert.equal(senseEtiqueta('<Dropdown placeholder="Tria" />').length, 1)
  assert.equal(senseEtiqueta('<label for="nom">Nom</label><InputText id="nom" />').length, 0)
  assert.equal(senseEtiqueta('<Dropdown :aria-label="etiqueta" />').length, 0)
})

test('els noms accessibles fan servir claus de traducció existents', () => {
  const arrel = new URL('../src/', import.meta.url)
  const ca = JSON.parse(readFileSync(new URL('locales/ca.json', arrel), 'utf8'))
  for (const f of readdirSync(arrel, { recursive: true }).filter(f => f.endsWith('.vue'))) {
    const source = readFileSync(new URL(f, arrel), 'utf8')
    for (const attr of source.matchAll(/:(?:aria-label|filterInputProps)="([^"]*)"/g)) {
      for (const clau of attr[1].matchAll(/\$?t\('([^']+)'/g)) {
        assert.notEqual(clau[1].split('.').reduce((v, k) => v?.[k], ca), undefined, `${f}: ${clau[1]}`)
      }
    }
  }
})
