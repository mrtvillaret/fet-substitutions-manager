import { test } from 'node:test'
import assert from 'node:assert/strict'
import { llegeixAdreca, escriuAdreca, pasHistorial, dataValida } from '../src/adreca.js'

const llegeix = (url, base = '/') => {
  const { pathname, search } = new URL(url, 'http://prova')
  return llegeixAdreca({ pathname, search }, base)
}

test('Adreça: pantalla, data i diàleg, també sota el base de la demo', () => {
  assert.deepEqual(llegeix('/vigilancies?data=2026-11-10&obert=estadistiques'),
    { pantalla: 'vigilancies', data: '2026-11-10', obert: 'estadistiques' })
  assert.deepEqual(llegeix('/demo/grups/?obert=menu', '/demo/'), { pantalla: 'grups', data: null, obert: 'menu' })
  assert.deepEqual(llegeix('/demo/scheduler', '/demo/'), { pantalla: 'scheduler', data: null, obert: null })
  for (const arrel of ['/', '/index.html', '/substitucions']) {
    assert.deepEqual(llegeix(arrel), { pantalla: 'substitucions', data: null, obert: null })
  }
})

test('Adreça: valors desconeguts, la pantalla per defecte sense error', () => {
  for (const url of ['/xyz?data=ahir&obert=res', '/grups/extra?data=2026-02-30', '/?data=2026-1-5&obert=constructor', '/vigilancies']) {
    const adreca = llegeix(url, url === '/vigilancies' ? '/demo/' : '/')
    assert.equal(adreca.data, null)
    assert.equal(adreca.obert, null)
    assert.equal(adreca.pantalla, 'substitucions')
  }
  assert.equal(dataValida('2028-02-29'), '2028-02-29')
  assert.equal(dataValida('2026-02-29'), null)
})

test('Adreça: escriptura; la data d’avui no s’hi posa', () => {
  assert.equal(escriuAdreca({ pantalla: 'vigilancies', data: '2026-11-11', obert: 'estadistiques' }, '/', '2026-11-10'),
    '/vigilancies?data=2026-11-11&obert=estadistiques')
  assert.equal(escriuAdreca({ pantalla: 'grups', data: '2026-11-10', obert: null }, '/demo/', '2026-11-10'), '/demo/grups')
  const anada = { pantalla: 'grups', data: '2026-11-12', obert: 'perfil' }
  assert.deepEqual(llegeix(escriuAdreca(anada, '/demo/', '2026-11-10'), '/demo/'), anada)
})

test('Adreça: entrades de l’historial', () => {
  const a = (pantalla, obert = null, data = '2026-11-10') => ({ pantalla, data, obert })
  assert.equal(pasHistorial(a('grups'), a('grups'), false), 'res')
  assert.equal(pasHistorial(a('grups'), a('vigilancies'), false), 'afegeix')
  assert.equal(pasHistorial(a('grups'), a('grups', 'ajuda'), false), 'afegeix')
  assert.equal(pasHistorial(a('grups', 'ajuda'), a('grups'), true), 'enrere')
  assert.equal(pasHistorial(a('grups', 'ajuda'), a('grups'), false), 'substitueix')
  assert.equal(pasHistorial(a('grups', 'menu'), a('grups', 'perfil'), true), 'substitueix')
  assert.equal(pasHistorial(a('grups', 'menu'), a('scheduler'), true), 'substitueix')
  assert.equal(pasHistorial(a('grups'), a('grups', null, '2026-11-11'), false), 'substitueix')
})

test('Adreça: un diàleg de dins de la pantalla compta com un diàleg més', () => {
  const a = (pantalla, intern = null, obert = null) => ({ pantalla, data: '2026-11-10', obert, intern })
  assert.equal(pasHistorial(a('grups', 'grups-reforc'), a('grups', 'grups-reforc'), true), 'res')
  assert.equal(pasHistorial(a('grups'), a('grups', 'grups-reforc'), false), 'afegeix')
  assert.equal(pasHistorial(a('grups', 'grups-reforc'), a('grups'), true), 'enrere')
  assert.equal(pasHistorial(a('grups', 'grups-reforc'), a('grups'), false), 'substitueix')
  // Del menú al PDF del dia (o del PDF als avisos): d'un diàleg a un altre
  assert.equal(pasHistorial(a('substitucions', null, 'menu'), a('substitucions', 'substitucions-pdf'), true), 'substitueix')
  assert.equal(pasHistorial(a('substitucions', 'substitucions-pdf'), a('substitucions', 'substitucions-pdf-avisos'), true), 'substitueix')
})
