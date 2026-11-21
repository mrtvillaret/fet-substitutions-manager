// Els informes d'Analitzar arriben com a dades; aquí només se'n fan els textos.
import { etiquetaDiaRestringit } from './textUtils.js'

const prefix = 'scheduler.steps.analysis.detalls.'

// El dia de l'informe: una data («Dilluns 20/04») o un nom de dia, traduït
export const etiquetaDiaInforme = (dia, t) => etiquetaDiaRestringit(dia, t)

// «Subst: A, B»; als detalls de les sessions per franja, les substitucions van separades per « | »
export const textDetall = ({ tipus, noms }, t, separadorSubst = ', ') =>
  `${t(prefix + tipus)}: ${noms.join(tipus === 'subst' ? separadorSubst : ', ')}`

export const textDetalls = (detalls, t) =>
  (detalls || []).length ? detalls.map((d) => textDetall(d, t)).join(' | ') : t(prefix + 'cap')

// «Prof 3 (Mates, 1-ESO-A)»
export const textProfessor = ({ professor, assignatura, grup }) => {
  const entre = [assignatura, grup].filter(Boolean).join(', ')
  return entre ? `${professor} (${entre})` : professor
}
