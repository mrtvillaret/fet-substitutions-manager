// A Prioritats, en afegir activitats a «No substituir»: les noves (no hi eren
// abans) que tenen grup a l'horari vigent. Quan falti qui les fa, el grup
// quedarà sense professor, perquè l'hora no sortirà a Substitucions; la
// pantalla ho avisa, però deixa desar.
export const novesAmbGrup = (seleccio, previes, ambGrup) =>
  seleccio.filter(a => !previes.includes(a) && ambGrup.includes(a))
