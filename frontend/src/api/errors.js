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

// El missatge d'un error de l'API per a l'usuari: el `detail` del backend si
// en porta; si no, un de genèric. Els errors 5xx no porten detall (és al
// registre del servidor), només una referència per poder-lo trobar.
export const missatgeDError = async (error, t) => {
  const status = error?.response?.status
  const cos = await cosDError(error)
  const detail = cos?.detail
  const ref = cos?.error_ref
  return typeof detail === 'string' ? detail
    : !error?.response ? t('app.errors.connection')
    : status >= 500 ? t('app.errors.server') + (ref ? ` (ref. ${ref})` : '')
    : t('app.errors.unexpected')
}

// Si l'interceptor d'App.vue ja n'ha mostrat l'avís (tots els errors de
// l'API, tret dels de les peticions _silent), perquè la pantalla no en
// mostri un segon. 401: l'interceptor torna a la pantalla d'entrada.
export const jaAvisat = (error) => Boolean(error?.isAxiosError && !error.config?._silent)
