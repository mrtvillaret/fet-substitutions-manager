export const buildId = () => Math.random().toString(36).slice(2, 10)

export const extreuNivell = (nom) => {
  if (!nom || !nom.includes('(')) return ''
  const match = nom.match(/\(([^)]+)\)\s*$/)
  return match ? match[1].trim() : ''
}
