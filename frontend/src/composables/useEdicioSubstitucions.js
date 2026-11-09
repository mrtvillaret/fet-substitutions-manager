import { avisaError } from '../errorsApi.js'
import { computed } from 'vue'
import * as apiSubstitucions from '../api/substitucions.js'

// Edició de les files: manté les confirmacions, els conflictes i les recàrregues.
export function useEdicioSubstitucions({ dataISO, totesAbsencies, substitucionsFiltrades, collator, toast, t, confirm, obrirDialogConflicte, mostrarAvisos, carregarSubstitucions }) {
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
      mostrarAvisos(resposta?.avisos)

      // Actualitzar estat
      substitucio.estat = substitucio.substitut ? 'assignada' : 'pendent'

      const alliberades = resposta?.alliberades || []
      if (alliberades.length) {
        // L'altra fila ha canviat: es torna a carregar tot
        await carregarSubstitucions()
        toast.add({
          severity: 'info',
          summary: t('common.updated'),
          detail: t('substitutions.messages.substituteMoved', {
            name: substitucio.substitut, absent: alliberades.map(a => a.professor_absent).join(', ')
          }),
          life: 5000
        })
        return
      }

      // S'ha creat o esborrat l'encadenada del substitut: la llista ha canviat (es
      // torna a carregar, amb els disponibles). Si no, només els disponibles, per
      // actualitzar els colors (algun pot passar a «JA ASSIGNAT»)
      const encadenades = resposta?.encadenades
      if (encadenades?.creades || encadenades?.esborrades) {
        await carregarSubstitucions()
      } else {
        await carregarSubstitucions()
      }

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('substitutions.messages.substituteAssigned', { name: substitucio.substitut || t('common.none') }),
        life: 2000
      })
    } catch (error) {
      console.error('Error actualitzant substitut:', error)
      if (error.response?.status === 409 && error.response?.data?.detail?.current_data) {
        const currentData = error.response.data.detail.current_data
        obrirDialogConflicte(async () => {
          const data = dataISO.value
          const resposta = await apiSubstitucions.actualitza(
            data,
            substitucio.hora,
            substitucio.professor_absent,
            {
              id: substitucio.id,
              substitut: substitucio.substitut,
              updated_at: currentData.updated_at,
              force: true,
              moure
            }
          )
          mostrarAvisos(resposta?.avisos)
          await carregarSubstitucions()
        })
        return
      }

      // Mostrar missatge d'error de l'API (si està disponible)
      const errorDetail = error.response?.data?.detail || t('substitutions.errors.updateSubstitute')

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
      mostrarAvisos(resposta?.avisos)

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('substitutions.messages.commentSaved'),
        life: 2000
      })
    } catch (error) {
      console.error('Error actualitzant comentari:', error)
      if (error.response?.status === 409 && error.response?.data?.detail?.current_data) {
        const currentData = error.response.data.detail.current_data
        obrirDialogConflicte(async () => {
          const data = dataISO.value
          const resposta = await apiSubstitucions.actualitza(
            data,
            substitucio.hora,
            substitucio.professor_absent,
            {
              id: substitucio.id,
              substitut: substitucio.substitut,
              comentaris: substitucio.comentaris,
              updated_at: currentData.updated_at,
              force: true
            }
          )
          mostrarAvisos(resposta?.avisos)
          await carregarSubstitucions()
        })
        return
      }
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

    const llistaDisponibles = Array.isArray(disponibles) ? disponibles : []
    const ordenats = [...llistaDisponibles].sort((a, b) => {
      const baixaA = a.de_baixa ? 1 : 0
      const baixaB = b.de_baixa ? 1 : 0
      if (baixaA !== baixaB) {
        return baixaA - baixaB
      }
      const ocupatA = a.ocupat ? 1 : 0
      const ocupatB = b.ocupat ? 1 : 0
      if (ocupatA !== ocupatB) {
        return ocupatA - ocupatB
      }
      const catA = Number.isFinite(Number(a.categoria)) ? Number(a.categoria) : 999
      const catB = Number.isFinite(Number(b.categoria)) ? Number(b.categoria) : 999
      if (catA !== catB) {
        return catA - catB
      }
      return collator.value.compare(a.professor || '', b.professor || '')
    })
    const opcionsDisponibles = ordenats.map(disp => {
      // Usar text_display del backend si existeix, sinó crear-lo manualment
      let label = disp.text_display || disp.professor

      // Fallback si no hi ha text_display (compatibilitat)
      if (!disp.text_display && disp.tipus && disp.detall) {
        label = `${disp.professor} (${disp.tipus} - ${disp.detall})`
      }

      return {
        label: label,
        value: disp.professor,
        color: disp.color || 'transparent'
      }
    });

    const valors = new Set(opcionsDisponibles.map(op => op.value))
    const opcions = [opcioNeutra, ...opcionsDisponibles]

    if (substitutActual && !valors.has(substitutActual)) {
      opcions.push({
        label: `${substitutActual} (${t('common.inactive')})`,
        value: substitutActual,
        color: '#F3F4F6'
      })
    }

    if (llistaDisponibles.length === 0) {
      return opcions
    }

    return opcions;
  }

  // Les opcions del substitut de cada fila (una sola vegada per fila: la taula
  // no les ha de tornar a calcular a cada repintat)
  const opcionsPerFila = computed(() =>
    new Map(substitucionsFiltrades.value.map(fila => [fila, formatDisponibles(fila.disponibles, fila.substitut)]))
  )
  const disponiblesDe = (fila) => opcionsPerFila.value.get(fila) || []

  // Un canvi a la taula (el substitut o les observacions)
  const canviaCamp = (fila, camp, valor) => {
    if (camp === 'substitut') {
      fila.substitut = valor
      actualitzarSubstitut(fila)
    } else if (camp === 'comentaris') {
      fila.comentaris = valor
      actualitzarComentari(fila)
    }
  }


  return { actualitzarSubstitut, desarSubstitut, actualitzarComentari, formatDisponibles, opcionsPerFila, disponiblesDe, canviaCamp }
}
