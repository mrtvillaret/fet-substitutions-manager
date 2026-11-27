import { avisaError, filaJaNoExisteix } from '../api/errors.js'
import { ref } from 'vue'
import * as apiVigilancies from '../api/vigilancies.js'
import { adaptaVigilanciaAlNivell } from '../vigilanciesNivell.js'
import { useConflicte } from './useConflicte.js'

// Edició de les files de Vigilàncies: canvis, altes, esborrats, ordre i conflictes.
export function useEdicioVigilancies({ dataISO, vigilancies, seleccionades, vigilanciesFiltrades, hores, opcionsFiles, toast, t, confirmaEsborrar, oblidaAjudes, ressalta, carregarVigilancies, carregarSubstitucionsCount, refrescarDisponiblesHora, carregarDisponibles, getDisponiblesPerHora }) {
  const { mostrarDialogConflicte, obreSiConflicte, gestionarConflicte, executarOverwrite } = useConflicte(carregarVigilancies)

  // Un altre dispositiu ha esborrat la vigilància: es diu i es torna a carregar la llista
  const siJaNoExisteix = async (error) => {
    if (!filaJaNoExisteix(error)) return false
    toast.add({ severity: 'warn', summary: t('common.warning'), detail: t('common.rowGone'), life: 5000 })
    await carregarVigilancies()
    return true
  }

  // Una resposta d'un dia que ja no és a la pantalla no es publica (com useCarregaVigilancies)
  const recarregaLlistat = async () => {
    const data = dataISO.value
    const files = await apiVigilancies.llista(data)
    if (data === dataISO.value) vigilancies.value = files
  }

  const canviaCamp = async (fila, camp, valor) => {
    if ((camp !== 'nivell' && !fila.nivell) || (camp === 'nivell' && !valor)) {
      toast.add({
        severity: 'warn',
        summary: t('common.warning'),
        detail: t('vigilancies.errors.levelRequired'),
        life: 4000
      })
      return
    }
    const horaAbans = fila.hora
    if (camp === 'nivell') {
      Object.assign(fila, adaptaVigilanciaAlNivell(fila, valor, opcionsFiles.value))
    } else {
      fila[camp] = valor
    }
    await actualitzarVigilancia(fila, { horaAbans })
  }

  const actualitzarVigilancia = async (vigilancia, { horaAbans = vigilancia.hora } = {}) => {
    const esPlaceholder = (value, fallback) =>
      !value || value.startsWith('--') || value === fallback

    const tipusNormalitzat = esPlaceholder(vigilancia.tipus, t('vigilancies.placeholders.type')) ? '' : vigilancia.tipus
    const grupsNormalitzat = esPlaceholder(vigilancia.grups, t('vigilancies.placeholders.groups')) ? '' : vigilancia.grups
    const aulaNormalitzada = esPlaceholder(vigilancia.aula, t('vigilancies.placeholders.room')) ? '' : vigilancia.aula
    const nivellNormalitzat = esPlaceholder(vigilancia.nivell, t('vigilancies.placeholders.level')) ? '' : vigilancia.nivell

    try {
      const resposta = await apiVigilancies.edita(dataISO.value, vigilancia.id, {
        hora: vigilancia.hora,
        tipus: tipusNormalitzat,
        grups: grupsNormalitzat,
        aula: aulaNormalitzada,
        vigilant: vigilancia.vigilant,
        comentaris: vigilancia.comentaris,
        nivell: nivellNormalitzat,
        updated_at: vigilancia.updated_at
      }, { _silent: true })

      if (resposta?.updated_at) {
        vigilancia.updated_at = resposta.updated_at
      }

      oblidaAjudes()
      if (horaAbans !== vigilancia.hora) {
        await recarregaLlistat()
        await refrescarDisponiblesHora(horaAbans)
        await refrescarDisponiblesHora(vigilancia.hora)
        ressalta(vigilancia.id)
      } else {
        // Disponibles de l'hora afectada, perquè els candidats siguin coherents
        await refrescarDisponiblesHora(vigilancia.hora)
      }

      // Actualitzar recompte de substitucions (assignar vigilant amb classe en genera)
      await carregarSubstitucionsCount()

      toast.add({
        severity: 'success',
        summary: t('common.updated'),
        detail: t('vigilancies.messages.updated'),
        life: 2000
      })
    } catch (err) {
      console.error('Error actualitzant vigilància:', err)
      if (obreSiConflicte(err, actual => apiVigilancies.edita(dataISO.value, vigilancia.id, {
        hora: vigilancia.hora,
        tipus: tipusNormalitzat,
        grups: grupsNormalitzat,
        aula: aulaNormalitzada,
        vigilant: vigilancia.vigilant,
        comentaris: vigilancia.comentaris,
        nivell: nivellNormalitzat,
        updated_at: actual.updated_at,
        force: true
      }))) return
      if (await siJaNoExisteix(err)) return
      avisaError(err, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('vigilancies.errors.update'),
        life: 3000
      }))
      // Recarregar per restaurar estat original
      await carregarVigilancies()
    }
  }

  const confirmarEliminar = (vigilancia) => {
    confirmaEsborrar({
      message: t('vigilancies.confirm.deleteMessage', { hour: vigilancia.hora }),
      header: t('common.confirmDelete'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('common.delete'),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        await eliminarVigilancia(vigilancia)
      }
    })
  }

  const confirmarEliminarSeleccionades = () => {
    const count = seleccionades.value.length
    confirmaEsborrar({
      message: t('vigilancies.confirm.deleteSelectedMessage', { count }, count),
      header: t('common.confirmDelete'),
      icon: 'pi pi-exclamation-triangle',
      acceptLabel: t('vigilancies.actions.deleteSelected', { count }),
      rejectLabel: t('common.cancel'),
      accept: async () => {
        const llistaAEliminar = [...seleccionades.value]
        seleccionades.value = []
        let errors = 0
        await Promise.all(llistaAEliminar.map(async (vig) => {
          try {
            await apiVigilancies.esborra(dataISO.value, vig.id, { updatedAt: vig.updated_at, silent: true })
          } catch {
            errors++
          }
        }))
        await carregarVigilancies()
        if (errors === 0) {
          toast.add({
            severity: 'success',
            summary: t('common.deleted'),
            detail: t('vigilancies.messages.deletedSelected', { count: llistaAEliminar.length }, llistaAEliminar.length),
            life: 3000
          })
        } else {
          toast.add({
            severity: 'warn',
            summary: t('common.warning'),
            detail: t('vigilancies.messages.deletedSelectedPartial', { ok: llistaAEliminar.length - errors, errors }),
            life: 5000
          })
        }
      }
    })
  }

  const eliminarVigilancia = async (vigilancia) => {
    try {
      await apiVigilancies.esborra(dataISO.value, vigilancia.id, { updatedAt: vigilancia.updated_at, silent: true })

      toast.add({
        severity: 'success',
        summary: t('common.deleted'),
        detail: t('vigilancies.messages.deleted'),
        life: 3000
      })

      await carregarVigilancies()
    } catch (err) {
      console.error('Error eliminant vigilància:', err)
      if (obreSiConflicte(err, actual => apiVigilancies.esborra(dataISO.value, vigilancia.id, {
        updatedAt: actual.updated_at, force: true
      }))) return
      if (await siJaNoExisteix(err)) return
      avisaError(err, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('vigilancies.errors.delete'),
        life: 3000
      }))
    }
  }

  const mostrarFormulariNova = ref(false)

  const creantVigilancia = ref(false)

  const propostaNova = ref({})

  const afegirNovaVigilancia = () => {
    const darrera = vigilanciesFiltrades.value[vigilanciesFiltrades.value.length - 1]
    propostaNova.value = {
      hora: darrera?.hora || hores.value[0] || '',
      nivell: darrera?.nivell || '',
      tipus: darrera?.tipus || ''
    }
    mostrarFormulariNova.value = true
  }

  const disponiblesDelFormulari = async ({ hora, tipus, grups, aula }) => {
    await carregarDisponibles(hora, tipus, grups, aula)
    return getDisponiblesPerHora(hora, tipus, grups, aula)
  }

  const creaVigilancia = async (fila) => {
    creantVigilancia.value = true
    try {
      const nova = await apiVigilancies.crea(dataISO.value, fila)
      mostrarFormulariNova.value = false
      toast.add({ severity: 'success', summary: t('common.created'), detail: t('vigilancies.messages.added'), life: 2000 })
      await carregarVigilancies()
      if (nova?.id) ressalta(nova.id)
    } catch (err) {
      console.error('Error creant vigilància:', err)
      avisaError(err, () => toast.add({ severity: 'error', summary: t('common.error'), detail: t('vigilancies.errors.create'), life: 3000 }))
    } finally {
      creantVigilancia.value = false
    }
  }

  const afegirVigilanciaDesprés = async (vigilancia) => {
    try {
      const esPlaceholder = (value, fallback) =>
        !value || value.startsWith('--') || value === fallback

      const novaVig = {
        hora: vigilancia.hora,
        nivell: vigilancia.nivell || null,
        tipus: vigilancia.tipus || '',
        grups: vigilancia.grups,
        aula: vigilancia.aula,
        vigilant: '',
        comentaris: ''
      }
      const payload = {
        ...novaVig,
        nivell: esPlaceholder(novaVig.nivell, t('vigilancies.placeholders.level')) ? '' : (novaVig.nivell || ''),
        tipus: esPlaceholder(novaVig.tipus, t('vigilancies.placeholders.type')) ? '' : (novaVig.tipus || ''),
        despres_de: String(vigilancia.id)
      }

      // La còpia va just a sota de la fila que copia (`despres_de`) i es ressalta
      const nova = await apiVigilancies.crea(dataISO.value, payload)

      toast.add({
        severity: 'success',
        summary: t('common.created'),
        detail: t('vigilancies.messages.added'),
        life: 2000
      })

      await carregarVigilancies()
      if (nova?.id) ressalta(nova.id)
    } catch (err) {
      console.error('Error creant vigilància:', err)
      avisaError(err, () => toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: t('vigilancies.errors.create'),
        life: 3000
      }))
    }
  }

  const mouFiles = async (hora, ids) => {
    const posicio = new Map(ids.map((id, i) => [String(id), i]))
    const deLhora = vigilancies.value.filter(v => v.hora === hora)
      .sort((a, b) => posicio.get(String(a.id)) - posicio.get(String(b.id)))
    let k = 0
    vigilancies.value = vigilancies.value.map(v => (v.hora === hora ? deLhora[k++] : v))
    try {
      await apiVigilancies.desaOrdre(dataISO.value, hora, ids)
      await recarregaLlistat() // desar l'ordre canvia els updated_at
    } catch (err) {
      console.error('Error desant l\'ordre:', err)
      avisaError(err, () => toast.add({
        severity: err.response?.status === 409 ? 'warn' : 'error',
        summary: err.response?.status === 409 ? t('common.warning') : t('common.error'),
        detail: err.response?.status === 409 ? t('vigilancies.messages.orderChanged') : t('vigilancies.errors.order'),
        life: 4000
      }))
      await carregarVigilancies()
    }
  }

  return { mostrarDialogConflicte, gestionarConflicte, executarOverwrite, canviaCamp, confirmarEliminar, confirmarEliminarSeleccionades, mostrarFormulariNova, creantVigilancia, propostaNova, afegirNovaVigilancia, disponiblesDelFormulari, creaVigilancia, afegirVigilanciaDesprés, mouFiles, recarregaLlistat, siJaNoExisteix }
}
