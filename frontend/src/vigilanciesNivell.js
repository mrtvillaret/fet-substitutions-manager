// Regla única del formulari i de la taula quan una vigilància canvia de nivell.
export const adaptaVigilanciaAlNivell = (fila, nivell, { tipusDe, grupsDe }) => ({
  ...fila,
  nivell,
  tipus: fila.tipus && tipusDe(nivell).includes(fila.tipus) ? fila.tipus : '',
  grups: fila.grups && grupsDe(nivell).includes(fila.grups) ? fila.grups : ''
})
