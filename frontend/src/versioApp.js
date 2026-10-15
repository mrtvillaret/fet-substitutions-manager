// Avís de versió nova: una pàgina oberta abans d'actualitzar el servidor
// continua amb el programa antic fins que es recarrega. Es compara la versió
// d'aquest programa amb la de version.json (vite.config.js) cada vegada que es
// torna a la pestanya i, si es queda visible tota l'estona, un cop al dia.
// No es recarrega sol: hi pot haver canvis sense desar.
import { BASE } from './basePath'

/* global __VERSIO_APP__ */
const VERSIO = typeof __VERSIO_APP__ !== 'undefined' ? __VERSIO_APP__ : ''
const CADA = 24 * 60 * 60 * 1000

export const vigilaVersio = (quanHiHaUnaNova) => {
  let avisat = false
  const comprova = async () => {
    if (avisat || document.visibilityState === 'hidden') return
    try {
      const resposta = await fetch(`${BASE}version.json?t=${Date.now()}`, { cache: 'no-store' })
      if (!resposta.ok) return
      const { versio } = await resposta.json()
      if (versio && VERSIO && versio !== VERSIO) {
        avisat = true
        quanHiHaUnaNova()
      }
    } catch {
      // sense connexió: ja es tornarà a provar
    }
  }
  document.addEventListener('visibilitychange', comprova)
  window.addEventListener('focus', comprova)
  const interval = setInterval(comprova, CADA)
  comprova()
  return () => {
    document.removeEventListener('visibilitychange', comprova)
    window.removeEventListener('focus', comprova)
    clearInterval(interval)
  }
}

// Un tros del programa que es baixa sota demanda ja no existeix (ha canviat
// de nom amb la versió nova): es recarrega la pàgina sencera.
window.addEventListener('vite:preloadError', () => window.location.reload())
