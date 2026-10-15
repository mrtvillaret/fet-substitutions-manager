// Avís dels substituts que el backend ha tret després d'un canvi
// (camp `substituts_trets` de la resposta): ja no podien fer la substitució
// i la fila ha quedat pendent.

// "2026-10-19" → "19/10"
export const dataCurta = (iso) => {
  const [, mes, dia] = (iso || '').split('-')
  return dia && mes ? `${dia}/${mes}` : iso
}

// `ambData`: posa el dia a cada línia (si no, només quan n'hi ha de diversos)
export const avisaSubstitutsTrets = (toast, t, trets, { ambData = false } = {}) => {
  if (!trets?.length) return
  const diversos = trets.some(x => x.data !== trets[0].data)
  const linies = trets.map(f => {
    const motiu = f.motiu === 'classe'
      ? t('substitutions.substitutsTrets.classe', { grup: f.classe_grup })
      : t(`substitutions.substitutsTrets.${f.motiu}`)
    const data = (ambData || diversos) && f.data ? `${dataCurta(f.data)} ` : ''
    return `${data}${f.hora} — ${f.professor_absent}: ${f.substitut} (${motiu})`
  })
  toast.add({
    severity: 'warn',
    summary: t('substitutions.substitutsTrets.titol', { count: trets.length }),
    detail: linies.join('\n'),
    life: 15000
  })
}
