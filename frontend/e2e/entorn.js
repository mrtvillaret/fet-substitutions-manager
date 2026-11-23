// Valors públics i exclusius de prova; cap credencial de cap instal·lació.
export const backendURL = 'http://127.0.0.1:8765'
export const frontendURL = 'http://127.0.0.1:5183'
export const contrasenya = 'contrasenya-exclusiva-e2e'
export const administrador = 'e2e_preparacio'
// Administrador propi de la prova de càrrega fallida del planificador: el límit
// d'entrades és de 5 per minut i usuari, i el de la preparació ja els fa servir
export const administradorCarrega = 'e2e_planificador_carrega'
export const escenaris = {
  escriptori: { usuari: 'e2e_escriptori', data: '2030-04-01', seguent: '2030-04-02', calendari: '2030-04-04' },
  mobil: { usuari: 'e2e_mobil', data: '2030-04-08', seguent: '2030-04-09', calendari: '2030-04-11' }
}
