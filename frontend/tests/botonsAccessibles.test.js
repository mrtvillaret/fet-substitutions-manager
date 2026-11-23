import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

// Un <Button> de PrimeVue només amb icona no té nom per a un lector de
// pantalla ni per al teclat: cal `label`, `aria-label` o text a dins. El
// v-tooltip no en dona (PrimeVue 3 no hi posa cap atribut ARIA). ESLint no ho
// veu (no sap que <Button> és un botó): ho vigila aquest test.

const SRC = new URL('../src/', import.meta.url).pathname
const fitxers = (dir) => readdirSync(dir).flatMap((nom) => {
  const cami = join(dir, nom)
  return statSync(cami).isDirectory() ? fitxers(cami) : nom.endsWith('.vue') ? [cami] : []
})

// Cada <Button ...> (fins al `>` que no és dins de cap cometa) i el que hi ha a dins
export function botons(text) {
  const trobats = []
  const inici = /<Button(?=[\s>/])/g
  let m
  while ((m = inici.exec(text))) {
    let i = m.index + 7
    let cometa = null
    for (; i < text.length; i++) {
      const c = text[i]
      if (cometa) { if (c === cometa) cometa = null } else if (c === '"' || c === "'") cometa = c
      else if (c === '>') break
    }
    const cap = text.slice(m.index, i + 1)
    let contingut = ''
    if (!cap.endsWith('/>')) {
      const fi = text.indexOf('</Button>', i)
      contingut = fi >= 0 ? text.slice(i + 1, fi) : ''
    }
    trobats.push({ cap, contingut, linia: text.slice(0, m.index).split('\n').length })
  }
  return trobats
}

const te = (cap, atribut) => new RegExp(`(?:^|\\s)(?::|v-bind:)?${atribut}=`).test(cap)
export const senseNom = ({ cap, contingut }) =>
  te(cap, 'icon') && !te(cap, 'label') && !te(cap, 'aria-label') && !contingut.replace(/<[^>]*>/g, '').trim()

test('cap <Button> amb icona no queda sense nom accessible (label, aria-label o text)', () => {
  const sense = fitxers(SRC).flatMap((fitxer) =>
    botons(readFileSync(fitxer, 'utf8')).filter(senseNom).map((b) => `${fitxer.slice(SRC.length)}:${b.linia}`))
  assert.deepEqual(sense, [])
})

test('el detector distingeix els casos', () => {
  const casos = (text) => botons(text).map(senseNom)
  assert.deepEqual(casos('<Button icon="pi pi-x" v-tooltip="t(\'a\')" @click="f(a => a > 1)" />'), [true])
  assert.deepEqual(casos('<Button icon="pi pi-x" :aria-label="t(\'a\')" />'), [false])
  assert.deepEqual(casos('<Button :icon="x" :label="t(\'a\')" />'), [false])
  assert.deepEqual(casos('<Button icon="pi pi-x"><span>Text</span></Button>'), [false])
  assert.deepEqual(casos('<Button icon="pi pi-x"><i class="pi pi-y"></i></Button>'), [true])
  assert.deepEqual(casos('<Button label="Desa" />'), [false]) // sense icona: ja té el text
})
