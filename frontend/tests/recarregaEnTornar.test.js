import { test } from 'node:test'
import assert from 'node:assert/strict'
import { carregaBlocVista } from './support/carregaBlocVista.js'

// Temps, visibilitat i pàgina falsos: la pestanya s'amaga, passa el temps i torna
function prepara({ ocupada = () => false, desant = () => false } = {}) {
  let ara = 0, escolta = null, interval = null, oberts = false, focus = null
  const recarregues = []
  const document = {
    visibilityState: 'visible',
    addEventListener: (_nom, f) => { escolta = f },
    removeEventListener: () => { escolta = null },
    querySelector: () => (oberts ? {} : null),
    get activeElement() { return focus }
  }
  const muntats = [], desmuntats = []
  const dependents = { recarrega: () => recarregues.push(ara), ocupada }
  carregaBlocVista('useRecarregaEnTornar', {
    dependents, document, Date: { now: () => ara }, hiHaDesatsEnCurs: desant,
    setInterval: (f) => { interval = f; return 1 }, clearInterval: () => { interval = null },
    onMounted: f => muntats.push(f), onBeforeUnmount: f => desmuntats.push(f)
  })
  muntats.forEach(f => f())
  const amagaIMostra = (ms) => {
    document.visibilityState = 'hidden'; escolta()
    ara += ms
    document.visibilityState = 'visible'; escolta()
  }
  return {
    recarregues, amagaIMostra,
    obre: (v) => { oberts = v }, enfoca: (el) => { focus = el },
    passaInterval: () => interval?.(), hiHaInterval: () => interval !== null,
    desmunta: () => desmuntats.forEach(f => f()), escolta: () => escolta
  }
}

const MIN = 60 * 1000

test('tornar a la pestanya: més de 2 minuts oculta recarrega una vegada; menys, res', () => {
  const p = prepara()
  p.amagaIMostra(2 * MIN)
  assert.deepEqual(p.recarregues, [])
  p.amagaIMostra(2 * MIN + 1)
  assert.equal(p.recarregues.length, 1)
  assert.equal(p.hiHaInterval(), false)
})

test('tornar a la pestanya a mig canvi: espera que s’acabi i llavors recarrega', () => {
  let desant = true
  const p = prepara({ desant: () => desant })
  p.obre(true)
  p.enfoca({ matches: () => true })
  p.amagaIMostra(3 * MIN)
  assert.deepEqual(p.recarregues, [])
  p.obre(false); p.passaInterval()             // encara amb el focus al text
  desant = false; p.passaInterval()            // i desant
  assert.deepEqual(p.recarregues, [])
  p.enfoca(null); p.passaInterval()
  assert.equal(p.recarregues.length, 1)
  assert.equal(p.hiHaInterval(), false)
  p.passaInterval()
  assert.equal(p.recarregues.length, 1)
})

test('tornar a la pestanya amb la pantalla ocupada (càrrega o selecció): espera; en sortir, ja no escolta', () => {
  let ocupada = true
  const p = prepara({ ocupada: () => ocupada })
  p.amagaIMostra(5 * MIN)
  assert.deepEqual(p.recarregues, [])
  ocupada = false; p.passaInterval()
  assert.equal(p.recarregues.length, 1)
  p.desmunta()
  assert.equal(p.escolta(), null)
})
