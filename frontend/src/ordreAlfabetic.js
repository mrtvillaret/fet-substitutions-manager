// Les llistes de noms que van per ordre alfabètic (no per la posició a l'XML):
// natural («Prof 6» abans de «Prof 10») i en català, sense distingir
// majúscules ni accents. El mateix ordre que noms.ordre_alfabetic al backend.
const collator = new Intl.Collator('ca', { numeric: true, sensitivity: 'base' })

export const ordenaAlfabeticament = (noms) => [...noms].sort(collator.compare)
