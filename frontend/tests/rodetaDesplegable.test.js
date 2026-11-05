import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'
import { rodaSenseCanviarValor } from '../src/components/vigilancies/rodetaDesplegable.js'

function event(deltaY = 120, deltaMode = 0) {
  return { deltaY, deltaX: 0, deltaMode, propagacio: 0, previngut: 0,
    stopImmediatePropagation() { this.propagacio++ },
    preventDefault() { this.previngut++ } }
}
test('rodeta tancada, amb focus o sense widget: conserva el desplaçament natiu i bloqueja els gestors de valor', () => {
  for (const widget of [null, { overlayVisible: false }]) {
    const e = event()
    rodaSenseCanviarValor(e, widget)
    assert.equal(e.propagacio, 1)
    assert.equal(e.previngut, 0)
  }
})
test('rodeta oberta: només mou la llista i consumeix també els extrems', () => {
  for (const [mode, pas] of [[0, 2], [1, 32], [2, 400]]) {
    const llista = { scrollTop: 100, scrollLeft: 0, clientHeight: 200 }
    const widget = { overlayVisible: true, overlay: { querySelector: () => llista } }
    const e = event(2, mode)
    rodaSenseCanviarValor(e, widget)
    assert.equal(llista.scrollTop, 100 + pas)
    assert.equal(e.previngut, 1)
    assert.equal(e.propagacio, 1)
    // Fins i tot sense recorregut: no s'encadena a la pàgina.
    Object.defineProperty(llista, 'scrollTop', { get: () => 0, set: () => {} })
    const extrem = event(-100)
    rodaSenseCanviarValor(extrem, widget)
    assert.equal(extrem.previngut, 1)
  }
})
test('la captura protegeix el control i el panell teletransportat de CampDesplegable', () => {
  const source = readFileSync(new URL('../src/components/vigilancies/CampDesplegable.vue', import.meta.url), 'utf8')
  const ast = baseParse(parse(source).descriptor.template.content)
  const arrel = ast.children.find(n => n.type === 1)
  assert(arrel.props.some(p => p.name === 'on' && p.arg?.content === 'wheel' && p.modifiers.some(m => (m.content || m) === 'capture')))
  const dropdown = arrel.children.find(n => n.tag === 'Dropdown')
  assert(dropdown.props.some(p => p.name === 'bind' && p.arg?.content === 'pt' && p.exp.content.includes('onWheelCapture: rodeta')))
  const selector = readFileSync(new URL('../src/components/vigilancies/SelectorVigilant.vue', import.meta.url), 'utf8')
  assert.match(selector, /<CampDesplegable/)
})


test('el panell obert consumeix la rodeta també mentre la llista es munta', () => {
  const e = event()
  rodaSenseCanviarValor(e, { overlayVisible: true, overlay: null })
  assert.equal(e.previngut, 1)
  assert.equal(e.propagacio, 1)
})
