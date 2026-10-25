// Opcions comunes dels PDF de substitucions i de vigilàncies (també de
// l'interval): les fa servir el component PdfOpcionsComunes.vue.

export const MIDES_LLETRA = [
  { valor: 1, etiqueta: 'pdfOptions.fontNormal' },
  { valor: 1.2, etiqueta: 'pdfOptions.fontLarge' },
  { valor: 1.35, etiqueta: 'pdfOptions.fontLarger' }
]

// Sense cap mida desada: ×1,2 per hores (la lletra que tenia aquest format) i
// ×1 per a la taula del dia
export const midaPerDefecte = (format) => (format === 'dia' ? 1 : 1.2)

// Aplica les preferències desades (`prefs`) a la configuració d'un diàleg
// (`config`, un ref) per a les claus donades
export const aplicaPreferencies = (config, prefs, claus) => {
  if (prefs) {
    claus.forEach((clau) => {
      if (prefs[clau] !== undefined) config.value[clau] = prefs[clau]
    })
  }
  if (!prefs || prefs.midaLletra === undefined) {
    config.value.midaLletra = midaPerDefecte(config.value.format)
  }
}

// Els paràmetres de la petició del PDF per a les opcions comunes
export const parametresComuns = (config) => ({
  format: config.format,
  mida_lletra: config.midaLletra,
  show_comments: config.showComments,
  show_hours: config.showHours,
  compress: config.compress
})
