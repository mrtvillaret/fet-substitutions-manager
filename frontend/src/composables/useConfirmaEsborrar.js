import { useConfirm } from 'primevue/useconfirm'

// Confirmació d'una acció que esborra (o que no es pot desfer): el botó
// d'acceptar sempre en vermell, a tota l'aplicació. ESLint no deixa posar
// acceptClass enlloc més, perquè no torni a divergir.
export function useConfirmaEsborrar() {
  const confirm = useConfirm()
  return (opcions) =>
    confirm.require({
      icon: 'pi pi-exclamation-triangle',
      ...opcions,
      acceptClass: 'p-button-danger'
    })
}
