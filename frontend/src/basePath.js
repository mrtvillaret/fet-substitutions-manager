// Ruta on s'ha publicat el frontend: '/' normalment, o p.ex. '/demo/' si es
// compila amb VITE_BASE_PATH=/demo/ per servir-lo sota una subruta del domini.
export const BASE = import.meta.env.BASE_URL

// Ruta dins de l'aplicació: ruta('scheduler') -> '/scheduler' o '/demo/scheduler'
export const ruta = (r = '') => BASE + r.replace(/^\//, '')

// Només rutes del mateix domini ("/..."), mai adreces externes ("//..." o "https://...")
export const esRutaLocal = (url) =>
  typeof url === 'string' && url.startsWith('/') && !url.startsWith('//') && !url.startsWith('/\\')
