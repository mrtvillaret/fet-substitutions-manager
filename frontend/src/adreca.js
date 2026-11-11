// L'adreça de la pàgina: pantalla, data de treball i diàleg obert.
//   /vigilancies?data=2026-11-10&obert=estadistiques   (sota el `base` de Vite)
// Funcions pures: qui les fa servir (useAplicacio.js) decideix quan s'escriu
// l'adreça i què hi pot obrir cada rol. Un valor desconegut és el de per defecte.
import { dataIso } from './dates.js'

export const PANTALLES = ['substitucions', 'grups', 'vigilancies', 'scheduler']
export const PANTALLA_PER_DEFECTE = 'substitucions'
export const DIALEGS = ['configuracio', 'configuracio-examens', 'estadistiques', 'perfil', 'ajuda', 'menu']

// AAAA-MM-DD d'una data que existeix (no 2026-02-30); si no, null
export const dataValida = (text) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text || '')
  if (!m) return null
  const data = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return dataIso(data) === text ? text : null
}

// Data local (sense hora) a partir d'AAAA-MM-DD ja validat
export const dataDeIso = (iso) => {
  const [any, mes, dia] = iso.split('-').map(Number)
  return new Date(any, mes - 1, dia)
}

// { pantalla, data (AAAA-MM-DD o null), obert (o null) } d'una adreça
export function llegeixAdreca({ pathname = '', search = '' }, base = '/') {
  const relatiu = pathname.startsWith(base) ? pathname.slice(base.length) : ''
  const nom = relatiu.replace(/\/+$/, '').replace(/^index\.html$/, '')
  const params = new URLSearchParams(search)
  const obert = params.get('obert')
  return {
    pantalla: PANTALLES.includes(nom) ? nom : PANTALLA_PER_DEFECTE,
    data: dataValida(params.get('data')),
    obert: DIALEGS.includes(obert) ? obert : null
  }
}

// Adreça (camí + consulta) d'un estat. La data d'avui no s'hi escriu: un enllaç
// desat sense data obre sempre el dia en què s'obre.
export function escriuAdreca({ pantalla, data, obert }, base = '/', avui = null) {
  const params = new URLSearchParams()
  if (data && data !== avui) params.set('data', data)
  if (obert) params.set('obert', obert)
  const consulta = params.toString()
  return `${base}${pantalla}${consulta ? `?${consulta}` : ''}`
}

// Com anar d'una adreça a l'altra a l'historial del navegador:
//  - canviar de pantalla, una entrada nova («Enrere» hi torna); si se'n surt des
//    d'un diàleg (p. ex. el menú del mòbil), la substitueix: «Enrere» no el reobre;
//  - obrir un diàleg, una entrada nova;
//  - tancar un diàleg que té una entrada pròpia, tornar enrere (així «Endavant»
//    el reobre i «Enrere» no); sense entrada pròpia (enllaç directe), substituir;
//  - canviar de data o d'un diàleg a un altre, substituir (la data no omple
//    l'historial).
// Un diàleg de dins d'una pantalla (`intern`, dialegsInterns.js) compta com un
// diàleg més, tot i que no s'escriu a l'adreça.
export function pasHistorial(actual, nou, entradaDeDialeg) {
  const dialegActual = actual.obert || actual.intern || null
  const dialegNou = nou.obert || nou.intern || null
  const igual = actual.pantalla === nou.pantalla && actual.data === nou.data && actual.obert === nou.obert
    && (actual.intern || null) === (nou.intern || null)
  if (igual) return 'res'
  if (actual.pantalla !== nou.pantalla) return dialegActual ? 'substitueix' : 'afegeix'
  if (dialegActual && !dialegNou) return entradaDeDialeg ? 'enrere' : 'substitueix'
  if (!dialegActual && dialegNou) return 'afegeix'
  return 'substitueix'
}
