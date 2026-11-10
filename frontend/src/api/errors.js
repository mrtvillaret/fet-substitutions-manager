// El cos d'un error de l'API. Amb responseType 'blob' (les descàrregues de
// PDF), axios el deixa com a Blob: si és JSON, es llegeix.
const cosDError = async (error) => {
  const cos = error?.response?.data
  if (typeof Blob !== 'undefined' && cos instanceof Blob) {
    if (!cos.type.includes('json')) return null
    try {
      return JSON.parse(await cos.text())
    } catch {
      return null
    }
  }
  return cos
}

// Errors de domini traduïts: el backend hi afegeix un `codi` estable i els
// `params` (errors_servidor.py). Si la web té la clau `errors.<codi>`, el
// missatge surt a l'idioma de la pantalla; si no, el `detail` del servidor.
// main.js hi registra el vue-i18n global; sense registre (tests), el detail.
let traductor = null
export const registraTraductorErrors = (i18n) => { traductor = i18n }

export const textDelCos = (cos) => {
  const detail = cos?.detail
  const clau = typeof cos?.codi === 'string' && cos.codi ? `errors.${cos.codi}` : null
  return typeof detail === 'string' && clau && traductor?.te(clau)
    ? traductor.t(clau, cos.params ?? {})
    : detail
}

// El text de l'error d'una resposta JSON ja llegida (crides sense blob).
export const detallDError = error => textDelCos(error?.response?.data)

// El missatge d'un error de l'API per a l'usuari: el `detail` del backend
// (traduït si es pot) si en porta; si no, un de genèric. Els errors 5xx no
// porten detall (és al registre del servidor), només una referència.
export const missatgeDError = async (error, t) => {
  const status = error?.response?.status
  const cos = await cosDError(error)
  const detail = textDelCos(cos)
  const ref = cos?.error_ref
  return typeof detail === 'string' ? detail
    : !error?.response ? t('app.errors.connection')
    : status >= 500 ? t('app.errors.server') + (ref ? ` (ref. ${ref})` : '')
    : t('app.errors.unexpected')
}

// La marca correspon a una presentació real: un mateix error pot travessar
// l'interceptor i diverses pantalles. WeakSet no altera l'error ni el reté.
const avisats = new WeakSet()
const esObjecte = error => error !== null && (typeof error === 'object' || typeof error === 'function')

export const jaAvisat = error => esObjecte(error) && avisats.has(error)
export const marcaAvisat = error => { if (esObjecte(error)) avisats.add(error) }

export const avisaError = (error, mostrar) => {
  if (jaAvisat(error)) return
  marcaAvisat(error)
  return mostrar()
}

// true: la pantalla gestiona l'error. Una llista: només els estats esperats
// (p. ex. 404 d'un logo opcional); qualsevol altre error s'avisa globalment.
export const esErrorSilencios = error => {
  const silent = error?.config?._silent
  return silent === true || (Array.isArray(silent) && silent.includes(error?.response?.status))
}
