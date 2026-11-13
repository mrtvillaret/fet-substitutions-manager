import { expect, request } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { administrador, backendURL, contrasenya, escenaris } from './entorn.js'

export default async function prepara() {
  const api = await request.newContext({ baseURL: backendURL })
  try {
    const desa = async (metode, ruta, opcions) => {
      const resposta = await api[metode](ruta, opcions)
      expect(resposta.ok(), `${metode} ${ruta}: ${await resposta.text()}`).toBeTruthy()
      return resposta.json()
    }
    await desa('post', '/api/login', { data: { username: administrador, password: contrasenya } })
    await desa('post', '/api/files/upload-xml', { multipart: {
      data_inici: '2020-01-01',
      file: { name: 'teachers.xml', mimeType: 'application/xml', buffer: await readFile(new URL('../../data/exemple/teachers.xml', import.meta.url)) }
    } })
    await desa('put', '/api/prioritats/desar-tot', { data: {
      ordre_categories: [['alliberat'], ['Guàrdia']], pesos: { alliberat: 1, 'Guàrdia': 1 }, categories_actives: [true, true]
    } })
    // Evita encadenades i files d'hores buides en aquest escenari mínim.
    for (const assignatura of ['', 'Guàrdia']) {
      await desa('post', '/api/prioritats/no-substituir', { data: { assignatura } })
    }
    // Abans de les absències: la importació d'exàmens només proposa els nivells
    // que ja surten a les substitucions, si n'hi ha
    await preparaPlanificador(desa)
    await desa('post', '/api/config/nivells', { data: { codi: '3-ESO' } })
    await desa('post', '/api/config/grups/3-ESO', { data: { codi: '3-ESO-A' } })
    for (const { data, seguent, calendari } of Object.values(escenaris)) {
      for (const [dia, professor, hora] of [[data, 'Prof 15', '10:00'], [seguent, 'Prof 1', '08:00'], [calendari, 'Prof 1', '10:00']]) {
        await desa('put', `/api/substitucions/${dia}/absencies/${encodeURIComponent(professor)}`, {
          data: { hores_absencia: [hora], updated_at_map: {} }
        })
      }
      await desa('post', `/api/vigilancies/${data}`, { data: {
        hora: '11:30', tipus: 'VIGILÀNCIA', grups: '3-ESO-A', aula: 'Aula E2E', nivell: '3-ESO', vigilant: ''
      } })
    }
  } finally {
    await api.dispose()
  }
}

// Planificador: exàmens de 1r i 2n de Batxillerat, dues dates i un horari generat
// i recalculat (queda com a últim horari, amb el desglossament del cost)
export const DATES_PLANIFICADOR = ['2026-04-20', '2026-04-21']
async function preparaPlanificador(desa) {
  const { propostes } = await desa('get', '/api/config/importar-assignacions/preview')
  const nivells = ['1-BAT', '2-BAT']
  const triades = propostes.filter((p) => nivells.includes(p.nivell) && ['Anglès', 'Català', 'Filosofia'].includes(p.assignatura))
  await desa('post', '/api/config/importar-assignacions', { data: { propostes: triades, overwrite: true } })
  const config = Object.fromEntries(DATES_PLANIFICADOR.map((d) => [d, { '09:00': { a: true, i: true }, '11:30': { a: true, i: true } }]))
  await desa('put', '/api/scheduler/config', { data: {
    nivells_actius: nivells, durada_titular: 1, durada_examen: 1,
    alliberaments_per_nivell: Object.fromEntries(nivells.map((n) => [n, { durada: 1, dates: DATES_PLANIFICADOR, config }]))
  } })
  const peticio = { data_inici: DATES_PLANIFICADOR[0], data_final: DATES_PLANIFICADOR[1], selected_dates: DATES_PLANIFICADOR, dies_utilitzar: ['Dilluns', 'Dimarts'] }
  const { horari } = await desa('post', '/api/scheduler/generate', { data: { ...peticio, motor: 'v2-backtrack', random_seed: 1 } })
  await desa('post', '/api/scheduler/recalcular-cost', { data: { horari, data_referencia: DATES_PLANIFICADOR[0], selected_dates: DATES_PLANIFICADOR } })
}
