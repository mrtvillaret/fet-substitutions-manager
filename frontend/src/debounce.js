// Crida `fn` un cop han passat `ms` sense cap altra crida (p. ex., els moviments
// seguits de l'editor de l'horari fan un sol recàlcul)
export const debounce = (fn, ms) => {
  let temporitzador
  return (...args) => {
    clearTimeout(temporitzador)
    temporitzador = setTimeout(() => fn(...args), ms)
  }
}
