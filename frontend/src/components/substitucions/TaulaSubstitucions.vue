<template>
  <!-- Les substitucions del dia, agrupades per hores (com Vigilàncies). Dins de
       cada hora, per curs (grup) i, si empaten, per professor absent. Sense
       paginació ni ordenació per columnes. -->
  <div class="taula-substitucions taula-dades" :class="{ 'taula-substitucions--carregant': carregant }" :aria-busy="carregant">
    <!-- Un sol gestor per a tota la taula: el toc d'una fila (pantalles tàctils) -->
    <table @click="tocaTaula">
      <colgroup>
        <col class="col-hora" />
        <col class="col-absent" />
        <col class="col-assignatura" />
        <col class="col-grup" />
        <col class="col-substitut" />
        <col class="col-observacions" />
        <col class="col-estat" />
        <col class="col-accions" />
      </colgroup>
      <thead>
        <tr>
          <th>{{ $t('common.hour') }}</th>
          <th>{{ $t('substitutions.columns.absentTeacher') }}</th>
          <th>{{ $t('common.subject') }}</th>
          <th>{{ $t('common.group') }}</th>
          <th>{{ $t('substitutions.columns.substitute') }}</th>
          <th>{{ $t('common.comments') }}</th>
          <th>{{ $t('common.status') }}</th>
          <th class="taula-accions"></th>
        </tr>
      </thead>
      <tbody v-for="bloc in blocs" :key="bloc.hora">
        <tr class="taula-substitucions__capcalera-bloc taula-separador-hora">
          <td colspan="8">
            <span class="taula-hora">{{ bloc.hora }}</span>
            <span class="taula-substitucions__compte">{{ $t('substitutions.table.rowsInBlock', { count: bloc.files.length }, bloc.files.length) }}</span>
          </td>
        </tr>
        <FilaSubstitucio
          v-for="{ fila, clau } in bloc.files"
          :key="clau"
          :fila="fila"
          :clau="clau"
          :data="data"
          :disponibles="disponiblesDe(fila)"
          :activa="esActiva(clau)"
          @canvi="reenviaCanvi"
          @edita="reenviaEdita"
          @esborra="reenviaEsborra"
        />
      </tbody>
    </table>

    <!-- Pantalles tàctils: les accions de la fila tocada -->
    <AccionsFila :element="activa?.element" :x="activa?.x" :accions="accionsFilaActiva" @tanca="tanca" />

    <div v-if="!files.length" class="taula-substitucions__buida">
      <i class="pi pi-inbox" aria-hidden="true"></i>
      <p>{{ $t('substitutions.empty.title') }}</p>
      <small>{{ $t('substitutions.empty.hint') }}</small>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import FilaSubstitucio from './FilaSubstitucio.vue'
import AccionsFila from '../AccionsFila.vue'
import { useFilaTactil } from '../../composables/useFilaTactil'

const props = defineProps({
  files: { type: Array, required: true }, // les substitucions que es veuen
  hores: { type: Array, default: () => [] }, // l'ordre dels blocs (les hores de l'horari)
  data: { type: String, required: true },
  disponiblesDe: { type: Function, required: true }, // fila -> opcions del substitut
  carregant: { type: Boolean, default: false } // es recarrega: la taula es queda, difuminada
})
// canvi(fila, camp, valor) · edita(fila) · esborra(fila)
const emit = defineEmits(['canvi', 'edita', 'esborra'])

const { t, locale } = useI18n()
const collator = computed(() => new Intl.Collator(locale.value || 'ca', { numeric: true, sensitivity: 'base' }))

// La substitució no té id: l'hora, el professor absent i la classe la identifiquen
const clauDe = (fila) => [fila.hora, fila.professor_absent, fila.assignatura, fila.grup].join('|')

// Blocs per hora, en l'ordre de l'horari (una hora que no hi és, al final);
// dins de cada hora, per curs (el grup comença pel nivell) i professor absent
const blocs = computed(() => {
  const perHora = new Map()
  for (const fila of props.files) {
    if (!perHora.has(fila.hora)) perHora.set(fila.hora, [])
    perHora.get(fila.hora).push({ fila, clau: clauDe(fila) })
  }
  const posicio = (hora) => {
    const i = props.hores.indexOf(hora)
    return i === -1 ? Number.POSITIVE_INFINITY : i
  }
  const compara = (a, b) =>
    collator.value.compare(a.fila.grup || '', b.fila.grup || '') ||
    collator.value.compare(a.fila.professor_absent || '', b.fila.professor_absent || '')
  return [...perHora.entries()]
    .sort(([a], [b]) => posicio(a) - posicio(b) || String(a).localeCompare(String(b)))
    .map(([hora, files]) => ({ hora, files: files.sort(compara) }))
})

// Funcions fixes per a les files (una funció nova a cada repintat les faria
// tornar a pintar totes)
const reenviaCanvi = (fila, camp, valor) => emit('canvi', fila, camp, valor)
const reenviaEdita = (fila) => emit('edita', fila)
const reenviaEsborra = (fila) => emit('esborra', fila)

// ------------------------------------------------------------ pantalles tàctils

// En tocar una fila (no un camp) surten les seves accions; a l'ordinador, a la
// fila mateixa en passar-hi el ratolí
const { activa, tocaFila, tanca, esActiva } = useFilaTactil()

const tocaTaula = (event) => {
  const tr = event.target.closest('tr[data-fila-id]')
  if (tr) tocaFila(event, tr.dataset.filaId)
}

const accionsFilaActiva = computed(() => {
  const clau = activa.value?.clau
  const fila = clau && props.files.find((f) => clauDe(f) === clau)
  if (!fila) return []
  return [
    { clau: 'edita', icona: 'pi-pencil', etiqueta: t('substitutions.actions.manageAbsences'), fer: () => reenviaEdita(fila) },
    {
      clau: 'esborra',
      icona: 'pi-trash',
      perill: true,
      etiqueta: t('substitutions.actions.deleteAbsences', { professor: fila.professor_absent }),
      fer: () => reenviaEsborra(fila)
    }
  ]
})
</script>

<style scoped>
/* L'aspecte (capçalera, files, hora...), a taules.css (.taula-dades) */
.taula-substitucions {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 56rem;
  border-collapse: collapse;
  table-layout: fixed;
}

/* Les columnes de text, justes; l'espai que sobra, per a les observacions */
.col-hora { width: 4.5rem; }
.col-absent { width: 10.5rem; }
.col-assignatura { width: 9rem; }
.col-grup { width: 7.5rem; }
.col-substitut { width: 16rem; }
.col-observacions { width: auto; min-width: 10rem; }
.col-estat { width: 7.5rem; }
.col-accions { width: 4.75rem; }

/* Pantalles tàctils: les accions surten en tocar la fila (AccionsFila) */
@media (hover: none) {
  .col-accions { width: 0; }
}

thead th {
  position: sticky;
  top: 0;
  z-index: 1;
}

/* La capçalera de cada bloc d'hora (el separador i l'etiqueta, a taules.css) */
.taula-substitucions__capcalera-bloc > td {
  height: auto;
  background: var(--taula-fila-seleccionada);
}

.taula-substitucions__compte {
  margin-left: 0.6rem;
  color: #4b5563;
  font-size: 0.85rem;
}

/* Mentre es recarrega, la taula es queda */
.taula-substitucions--carregant {
  opacity: 0.6;
  pointer-events: none;
  transition: opacity 0.15s;
}

.taula-substitucions__buida {
  padding: 3rem 1rem;
  color: #6b7280;
  text-align: center;
}

.taula-substitucions__buida .pi {
  margin-bottom: 1rem;
  font-size: 3rem;
  color: #ccc;
}

.taula-substitucions__buida p {
  margin-bottom: 0.5rem;
  font-size: 1.1rem;
}
</style>
