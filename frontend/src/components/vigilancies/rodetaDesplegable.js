// Un desplegable tancat deixa passar el desplaçament natiu de la pàgina.
// Si és obert, tota la rodeta es consumeix a la seva llista, també als extrems.
export function rodaSenseCanviarValor(event, desplegable) {
  event.stopImmediatePropagation()
  if (!desplegable?.overlayVisible) return
  event.preventDefault()
  const llista = desplegable.overlay?.querySelector('[data-pc-section="wrapper"]')
  if (!llista) return
  // WheelEvent pot expressar el desplaçament en píxels, línies o pàgines.
  const unitat = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? llista.clientHeight : 1
  llista.scrollTop += event.deltaY * unitat
  llista.scrollLeft += event.deltaX * unitat
}
