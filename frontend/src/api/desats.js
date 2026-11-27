// Les peticions que desen (tot el que no és GET) en curs: mentre n'hi ha, la
// pantalla no es recarrega sola (useRecarregaEnTornar).
import clientApi from './client.js'

let desantAra = 0
export const hiHaDesatsEnCurs = () => desantAra > 0

const acabaDesat = (config) => {
  if (config?._desant) desantAra--
}
clientApi.interceptors.request.use((config) => {
  if ((config.method || 'get').toLowerCase() !== 'get') {
    config._desant = true
    desantAra++
  }
  return config
})
clientApi.interceptors.response.use(
  (resposta) => { acabaDesat(resposta.config); return resposta },
  (error) => { acabaDesat(error?.config); return Promise.reject(error) }
)
