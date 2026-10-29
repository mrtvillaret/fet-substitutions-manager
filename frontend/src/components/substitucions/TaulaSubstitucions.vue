<template>
  <!-- Les substitucions del dia, agrupades per hores (com Vigilàncies), en
       l'ordre de l'API, el mateix que el PDF (SubstitucioRepository.ordena):
       dins de cada hora, per curs o per professor absent (es canvia a la
       capçalera «Professor absent»), i cada encadenada sota la substitució
       que la provoca. Sense paginació. -->
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
          <th>
            <!-- L'ordre dins de cada hora: cada capçalera ordena per ella mateixa -->
            <button
              type="button"
              class="taula-substitucions__ordre"
              :title="$t('substitutions.table.sortByTeacher')"
              :aria-label="$t('substitutions.table.sortByTeacher')"
              :aria-pressed="ordre === 'professor'"
              @click="emit('canvia-ordre', 'professor')"
            >
              {{ $t('substitutions.columns.absentTeacher') }}
              <i class="pi" :class="ordre === 'professor' ? 'pi-sort-alpha-down taula-substitucions__ordre--actiu' : 'pi-sort-alt'" aria-hidden="true"></i>
            </button>
          </th>
          <th>{{ $t('common.subject') }}</th>
          <th>
            <button
              type="button"
              class="taula-substitucions__ordre"
              :title="$t('substitutions.table.sortByCourse')"
              :aria-label="$t('substitutions.table.sortByCourse')"
              :aria-pressed="ordre === 'curs'"
              @click="emit('canvia-ordre', 'curs')"
            >
              {{ $t('common.group') }}
              <i class="pi" :class="ordre === 'curs' ? 'pi-sort-amount-down-alt taula-substitucions__ordre--actiu' : 'pi-sort-alt'" aria-hidden="true"></i>
            </button>
          </th>
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
  data: { type: String, required: true },
  disponiblesDe: { type: Function, required: true }, // fila -> opcions del substitut
  ordre: { type: String, default: 'curs' }, // dins de cada hora: 'curs' o 'professor'
  carregant: { type: Boolean, default: false } // es recarrega: la taula es queda, difuminada
})
// canvi(fila, camp, valor) · edita(fila) · esborra(fila) · canvia-ordre(ordre)
const emit = defineEmits(['canvi', 'edita', 'esborra', 'canvia-ordre'])

const { t } = useI18n()


// La substitució no té id: l'hora, el professor absent i la classe la identifiquen
const clauDe = (fila) => [fila.hora, fila.professor_absent, fila.assignatura, fila.grup].join('|')

// Blocs per hora, en l'ordre en què arriben (el de l'API)
const blocs = computed(() => {
  const perHora = new Map()
  for (const fila of props.files) {
    if (!perHora.has(fila.hora)) perHora.set(fila.hora, [])
    perHora.get(fila.hora).push({ fila, clau: clauDe(fila) })
  }
  return [...perHora.entries()].map(([hora, files]) => ({ hora, files }))
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

/* La capçalera que canvia l'ordre: com el text de la capçalera, amb la icona */
.taula-substitucions__ordre {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.taula-substitucions__ordre .pi {
  color: #9ca3af;
  font-size: 0.8rem;
}

.taula-substitucions__ordre--actiu,
.taula-substitucions__ordre .taula-substitucions__ordre--actiu {
  color: var(--primary-color, #6366f1);
  font-size: 0.8rem;
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
