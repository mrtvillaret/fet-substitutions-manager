import { avisaError, detallDError, filaJaNoExisteix } from '../api/errors.js'
import { computed } from 'vue'
import * as apiSubstitucions from '../api/substitucions.js'

// Edició de les files: manté les confirmacions, els conflictes i les recàrregues.
export function useEdicioSubstitucions({ dataISO, totesAbsencies, substitucions, toast, t, confirm, obreSiConflicte, carregarSubstitucions }) {
  // Un altre dispositiu ha esborrat la fila: es diu i es torna a carregar la llista
  const siJaNoExisteix = async (error) => {
    if (!filaJaNoExisteix(error)) return false
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('common.rowGone'), life: 5000 })
    await carregarSubstitucions()
    return true
  }

  // Si el professor triat ja substitueix algú altre a la mateixa hora (en vermell),
  // es pot moure aquí: l'altra substitució queda pendent.
  const actualitzarSubstitut = (substitucio) => {
    const opcio = (substitucio.disponibles || []).find(d => d.professor === substitucio.substitut)
    const nomesJaAssignat = opcio?.ja_assignat && !opcio.absent && !opcio.de_baixa && !opcio.ocupat_vigilancia
    if (!nomesJaAssignat) return desarSubstitut(substitucio)

    const altra = totesAbsencies.value.find(s => s.hora === substitucio.hora && s.substitut === substitucio.substitut &&
      s.professor_absent !== substitucio.professor_absent)
    confirm.require({
      header: t('substitutions.confirm.moveTitle'),
      message: t('substitutions.confirm.moveMessage', {
        name: substitucio.substitut, absent: altra?.professor_absent || '—', hora: substitucio.hora
      }),
      icon: 'pi pi-arrow-right-arrow-left',
      acceptLabel: t('substitutions.confirm.moveAccept'),
      rejectLabel: t('common.cancel'),
      accept: () => desarSubstitut(substitucio, true),
      reject: () => carregarSubstitucions()   // torna el desplegable com era
    })
  }

  const desarSubstitut = async (substitucio, moure = false) => {
    try {
      const data = dataISO.value
      const resposta = await apiSubstitucions.actualitza(
        data,
        substitucio.hora,
        substitucio.professor_absent,
        { id: substitucio.id, substitut: substitucio.substitut, updated_at: substitucio.updated_at, moure },
        { silent: true }
      )

      if (resposta?.updated_at) {
        substitucio.updated_at = resposta.updated_at
      }

      // Sempre es torna a carregar tot: pot haver canviat una altra fila (la que
      // s'ha deixat pendent en moure el substitut o una encadenada) i els colors
      // dels disponibles (algun pot passar a «JA ASSIGNAT»)
      await carregarSubstitucions()

      const alliberades = resposta?.alliberades || []
      toast.add(alliberades.length
        ? {
            severity: 'info',
            summary: t('common.updated'),
            detail: t('substitutions.messages.substituteMoved', {
              name: substitucio.substitut, absent: alliberades.map(a => a.professor_absent).join(', ')
            }),
            life: 5000
          }
        : {
            severity: 'success',
            summary: t('common.updated'),
            detail: t('substitutions.messages.substituteAssigned', { name: substitucio.substitut || t('common.none') }),
            life: 2000
          })
    } catch (error) {
      console.error('Error actualitzant substitut:', error)
      if (obreSiConflicte(error, actual => apiSubstitucions.actualitza(dataISO.value, substitucio.hora, substitucio.professor_absent, {
        id: substitucio.id, substitut: substitucio.substitut, updated_at: actual.updated_at, force: true, moure
      }))) return
      if (await siJaNoExisteix(error)) return

        const errorDetail = detallDError(error) || t('substitutions.errors.updateSubstitute')

      avisaError(error, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: errorDetail,
        life: 4000
      }))

      // Recarregar substitucions per restaurar els valors correctes de la BD
      await carregarSubstitucions()
    }
  }

  const actualitzarComentari = async (substitucio) => {
    try {
      const data = dataISO.value
      const resposta = await apiSubstitucions.actualitza(
        data,
        substitucio.hora,
        substitucio.professor_absent,
        {
          id: substitucio.id,
          substitut: substitucio.substitut,
          comentaris: substitucio.comentaris,
          updated_at: substitucio.updated_at
        },
        { silent: true }
      )

      if (resposta?.updated_at) {
        substitucio.updated_at = resposta.updated_at
      }

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('substitutions.messages.commentSaved'),
        life: 2000
      })
    } catch (error) {
      console.error('Error actualitzant comentari:', error)
      if (obreSiConflicte(error, actual => apiSubstitucions.actualitza(dataISO.value, substitucio.hora, substitucio.professor_absent, {
        id: substitucio.id, substitut: substitucio.substitut, comentaris: substitucio.comentaris, updated_at: actual.updated_at, force: true
      }))) return
      if (await siJaNoExisteix(error)) return
      avisaError(error, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('substitutions.errors.saveComment'),
        life: 3000
      }))
    }
  }

  const formatDisponibles = (disponibles, substitutActual = '') => {
    // Sempre afegir una opció neutra al principi (valor buit per esborrar substitut)
    const opcioNeutra = { label: t('common.selectOption'), value: '', color: '#F3F4F6' };

    // L'ordre i el text de cada opció els dona el backend (substitucions/_consultes.py)
    const llistaDisponibles = Array.isArray(disponibles) ? disponibles : []
    const opcionsDisponibles = llistaDisponibles.map(disp => ({
      label: disp.text_display,
      value: disp.professor,
      color: disp.color || 'transparent'
    }))

    const valors = new Set(opcionsDisponibles.map(op => op.value))
    const opcions = [opcioNeutra, ...opcionsDisponibles]

    if (substitutActual && !valors.has(substitutActual)) {
      opcions.push({
        label: `${substitutActual} (${t('common.inactive')})`,
        value: substitutActual,
        color: '#F3F4F6'
      })
    }

    return opcions
  }

  // Les opcions del substitut de cada fila (una sola vegada per fila: la taula
  // no les ha de tornar a calcular a cada repintat)
  const opcionsPerFila = computed(() =>
    new Map(substitucions.value.map(fila => [fila, formatDisponibles(fila.disponibles, fila.substitut)]))
  )
  const disponiblesDe = (fila) => opcionsPerFila.value.get(fila) || []

  // Un canvi a la taula (el substitut o les observacions)
  const canviaCamp = (fila, camp, valor) => {
    if (camp === 'substitut') {
      fila.substitut = valor
      return actualitzarSubstitut(fila)
    }
    if (camp === 'comentaris') {
      fila.comentaris = valor
      return actualitzarComentari(fila)
    }
  }


  return { disponiblesDe, canviaCamp }
}
