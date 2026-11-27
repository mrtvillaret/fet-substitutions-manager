// Desa al navegador un PDF rebut de l'API (`responseType: 'blob'`) amb el nom donat.
export const desaPdf = (dades, nom) => {
  const url = URL.createObjectURL(new Blob([dades], { type: 'application/pdf' }))
  const enllac = document.createElement('a')
  enllac.href = url
  enllac.download = nom
  document.body.appendChild(enllac)
  enllac.click()
  document.body.removeChild(enllac)
  URL.revokeObjectURL(url)
}
