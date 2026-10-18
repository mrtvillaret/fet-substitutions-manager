// La data de treball: la del calendari de la capçalera. És l'única font de la
// data per a totes les pantalles (la llegeixen d'aquí, no la reben per props):
// les crides que depenen de l'horari la porten i, quan canvia, cada pantalla
// que la vigila (watch(dataTreball, ...)) es torna a carregar.
import { computed, ref } from 'vue'
import { dataIso } from './dates'

export const dataTreball = ref(new Date())

// AAAA-MM-DD, per a les crides a l'API
export const dataTreballIso = computed(() => dataIso(dataTreball.value))

// Opcions d'axios amb ?data= de la data de treball (i altres paràmetres)
export const ambDataTreball = (params = {}) => ({ params: { ...params, data: dataTreballIso.value } })
