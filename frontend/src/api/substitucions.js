// Crides HTTP de les substitucions d'un dia (/api/substitucions).
import axios from 'axios'

// La dependència injectable permet comprovar que totes les hores viatgen en
// una sola petició sense lligar el test a axios.
export const disponiblesEnBlocAmb = async (client, data, hores) =>
  (await client.post(
    `/api/substitucions/${data}/disponibles-batch`,
    { hores },
    { _silent: true }
  )).data?.results || {}

export const disponiblesEnBloc = async (data, hores) => disponiblesEnBlocAmb(axios, data, hores)
