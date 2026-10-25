// L'ajuda del vigilant (tot el que té un professor a una hora), amb una
// memòria per no tornar-la a demanar cada cop que s'hi passa per damunt. Tota
// recàrrega del dia l'ha d'oblidar: qualsevol canvi la pot fer quedar vella.
import { ajudaVigilant } from '../api/vigilancies'

const memoria = new Map()

export const useAjudaVigilant = () => {
  const carrega = (data, hora, nom) => {
    const clau = `${data}|${hora}|${nom}`
    if (!memoria.has(clau)) {
      const peticio = ajudaVigilant(data, hora, nom).catch((err) => {
        memoria.delete(clau) // un error no es guarda: es tornarà a provar
        throw err
      })
      memoria.set(clau, peticio)
    }
    return memoria.get(clau)
  }
  const oblida = () => memoria.clear()
  return { carrega, oblida }
}
