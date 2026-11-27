import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

// `@click="fn"` crida fn(event). Si fn té paràmetres opcionals (`silent =
// false`, `item = null`), l'esdeveniment hi arriba com si fos un valor: el
// diàleg s'obria en mode edició amb el clic com a fila, i «Detecta grups» no
// avisava. Aquestes funcions s'han de cridar `@click="() => fn()"`.

const SRC = new URL('../src/', import.meta.url).pathname
const fitxers = (dir) => readdirSync(dir).flatMap((nom) => {
  const cami = join(dir, nom)
  return statSync(cami).isDirectory() ? fitxers(cami) : /\.(vue|js)$/.test(nom) ? [cami] : []
})

const definicio = /(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>|function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)/g

test('cap gestor de la plantilla no passa l\'esdeveniment a una funció amb paràmetres opcionals', () => {
  const textos = fitxers(SRC).map((f) => [f, readFileSync(f, 'utf8')])
  const opcionals = new Set()
  for (const [, text] of textos) {
    for (const m of text.matchAll(definicio)) {
      if ((m[2] ?? m[4] ?? '').includes('=')) opcionals.add(m[1] ?? m[3])
    }
  }
  const trobats = []
  for (const [fitxer, text] of textos.filter(([f]) => f.endsWith('.vue'))) {
    for (const m of text.matchAll(/@[\w:.-]+="([A-Za-z_$][\w$]*)"/g)) {
      if (opcionals.has(m[1])) trobats.push(`${fitxer.slice(SRC.length)}: ${m[0]}`)
    }
  }
  assert.deepEqual(trobats, [])
})
