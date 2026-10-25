<template>
  <!-- Les vigilàncies del dia, agrupades per hores, en l'ordre desat. Sense
       paginació ni ordenació per columnes: l'ordre el canvien «Ordena» i
       l'arrossegament (només dins del bloc de la mateixa hora). -->
  <div class="taula-vigilancies taula-dades" :class="{ 'taula-vigilancies--carregant': carregant }" :aria-busy="carregant">
    <!-- Un sol gestor per a tota la taula: el toc d'una fila (pantalles tàctils) -->
    <table @click="tocaTaula">
      <colgroup>
        <col class="col-seleccio" />
        <col class="col-ordre" />
        <col class="col-hora" />
        <col class="col-nivell" />
        <col class="col-tipus" />
        <col class="col-grups" />
        <col class="col-aula" />
        <col class="col-vigilant" />
        <col class="col-observacions" />
        <col class="col-accions" />
      </colgroup>
      <thead>
        <tr>
          <th class="taula-vigilancies__seleccio">
            <input
              type="checkbox"
              :checked="totesSeleccionades"
              :indeterminate.prop="algunaSeleccionada && !totesSeleccionades"
              :disabled="!files.length"
              :aria-label="$t('vigilancies.table.selectAll')"
              @change="seleccionaFiles(files, $event.target.checked)"
            />
          </th>
          <th></th>
          <th>{{ $t('common.hour') }}</th>
          <th>{{ $t('vigilancies.columns.level') }}</th>
          <th>{{ $t('vigilancies.columns.type') }}</th>
          <th>{{ $t('common.group') }}</th>
          <th>{{ $t('common.room') }}</th>
          <th>{{ $t('vigilancies.columns.supervisor') }}</th>
          <th>{{ $t('common.comments') }}</th>
          <th class="taula-accions"></th>
        </tr>
      </thead>
      <tbody
        v-for="bloc in blocs"
        :key="bloc.hora"
        class="taula-vigilancies__bloc"
        :class="{ 'taula-vigilancies__bloc--desti': blocDesti === bloc.hora }"
        @dragover="sobreBloc($event, bloc)"
        @drop="deixaA($event, bloc)"
      >
        <tr class="taula-vigilancies__capcalera-bloc taula-separador-hora">
          <td class="taula-vigilancies__seleccio">
            <input
              type="checkbox"
              :checked="bloc.files.every(esSeleccionada)"
              :indeterminate.prop="bloc.files.some(esSeleccionada) && !bloc.files.every(esSeleccionada)"
              :aria-label="$t('vigilancies.table.selectBlock', { hora: bloc.hora })"
              @change="seleccionaFiles(bloc.files, $event.target.checked)"
            />
          </td>
          <td colspan="9">
            <span class="taula-vigilancies__hora taula-hora">{{ bloc.hora }}</span>
            <span class="taula-vigilancies__compte">{{ $t('vigilancies.table.rowsInBlock', { count: bloc.files.length }, bloc.files.length) }}</span>
          </td>
        </tr>
        <FilaVigilancia
          v-for="(fila, index) in bloc.files"
          :key="fila.id"
          :fila="fila"
          :data="data"
          :opcions="opcions"
          :disponibles="disponiblesDe(fila)"
          :etiqueta-vigilant="etiquetaVigilantDe(fila)"
          :seleccionada="esSeleccionada(fila)"
          :activa="esActiva(String(fila.id))"
          :ressaltada="ressaltades.has(String(fila.id))"
          :titular-lliure="titularsLliures.has(String(fila.id))"
          :mobil="ordreEditable"
          :primera="index === 0"
          :ultima="index === bloc.files.length - 1"
          :arrossegada="arrossegada?.id === fila.id"
          @comenca-arrossegar="comencaArrossegar"
          @acaba-arrossegar="acabaArrossegar"
          @canvi="reenviaCanvi"
          @selecciona="seleccionaFila"
          @afegeix="reenviaAfegeix"
          @esborra="reenviaEsborra"
          @mou="mouFila"
        />
      </tbody>
    </table>

    <!-- Pantalles tàctils: les accions de la fila tocada -->
    <AccionsFila :element="activa?.element" :x="activa?.x" :accions="accionsFilaActiva" @tanca="tanca" />

    <div v-if="!files.length" class="taula-vigilancies__buida">
      <i class="pi pi-inbox" aria-hidden="true"></i>
      <p>{{ $t('vigilancies.empty.title') }}</p>
      <small>{{ $t('vigilancies.empty.hint') }}</small>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import FilaVigilancia from './FilaVigilancia.vue'
import AccionsFila from '../AccionsFila.vue'
import { ambFilaMoguda } from '../../composables/useOrdreFiles'
import { useFilaTactil } from '../../composables/useFilaTactil'

const props = defineProps({
  files: { type: Array, required: true }, // les que es veuen (filtrades), en l'ordre desat
  hores: { type: Array, default: () => [] }, // l'ordre dels blocs (les hores de l'horari)
  data: { type: String, required: true },
  opcions: { type: Object, required: true },
  disponiblesDe: { type: Function, required: true }, // fila -> opcions del vigilant
  etiquetaVigilantDe: { type: Function, required: true }, // fila -> text del vigilant
  ressaltades: { type: Set, default: () => new Set() },
  titularsLliures: { type: Set, default: () => new Set() }, // ids
  ordreEditable: { type: Boolean, default: true }, // fals amb filtres posats
  carregant: { type: Boolean, default: false } // es recarrega: la taula es queda, difuminada
})
const seleccionades = defineModel('seleccionades', { type: Array, default: () => [] })
// canvi(fila, camp, valor) · afegeix(fila) · esborra(fila) · mou(hora, ids)
const emit = defineEmits(['canvi', 'afegeix', 'esborra', 'mou'])

// Blocs per hora, en l'ordre de l'horari (una hora que no hi és, al final)
const blocs = computed(() => {
  const perHora = new Map()
  for (const fila of props.files) {
    if (!perHora.has(fila.hora)) perHora.set(fila.hora, [])
    perHora.get(fila.hora).push(fila)
  }
  const posicio = (hora) => {
    const i = props.hores.indexOf(hora)
    return i === -1 ? Number.POSITIVE_INFINITY : i
  }
  return [...perHora.entries()]
    .sort(([a], [b]) => posicio(a) - posicio(b) || String(a).localeCompare(String(b)))
    .map(([hora, files]) => ({ hora, files }))
})

// ------------------------------------------------------------ selecció

const idsSeleccionats = computed(() => new Set(seleccionades.value.map((f) => String(f.id))))
const esSeleccionada = (fila) => idsSeleccionats.value.has(String(fila.id))
const totesSeleccionades = computed(() => props.files.length > 0 && props.files.every(esSeleccionada))
const algunaSeleccionada = computed(() => props.files.some(esSeleccionada))

// Funcions fixes per a les files (una funció nova a cada repintat les faria
// tornar a pintar totes)
const reenviaCanvi = (fila, camp, valor) => emit('canvi', fila, camp, valor)
const reenviaAfegeix = (fila) => emit('afegeix', fila)
const reenviaEsborra = (fila) => emit('esborra', fila)
const seleccionaFila = (fila, marcar) => seleccionaFiles([fila], marcar)

const seleccionaFiles = (files, marcar) => {
  const ids = new Set(files.map((f) => String(f.id)))
  const resta = seleccionades.value.filter((f) => !ids.has(String(f.id)))
  seleccionades.value = marcar ? [...resta, ...files] : resta
}

// ------------------------------------------------------------ pantalles tàctils

// En tocar una fila (no un camp) surten les seves accions: afegeix, esborra i,
// si l'ordre es pot canviar, les fletxes; a l'ordinador, a la fila mateixa
const { t } = useI18n()
const { activa, tocaFila, tanca, esActiva } = useFilaTactil()

const tocaTaula = (event) => {
  const tr = event.target.closest('tr[data-fila-id]')
  if (tr) tocaFila(event, tr.dataset.filaId)
}

const accionsFilaActiva = computed(() => {
  const id = activa.value?.clau
  const bloc = id && blocs.value.find((b) => b.files.some((f) => String(f.id) === id))
  if (!bloc) return []
  const index = bloc.files.findIndex((f) => String(f.id) === id)
  const fila = bloc.files[index]
  const accions = [
    { clau: 'duplica', icona: 'pi-clone', etiqueta: t('vigilancies.actions.duplicateRow'), fer: () => reenviaAfegeix(fila) },
    { clau: 'esborra', icona: 'pi-trash', perill: true, etiqueta: t('common.delete'), fer: () => reenviaEsborra(fila) }
  ]
  if (props.ordreEditable) {
    accions.push(
      { clau: 'amunt', icona: 'pi-angle-up', etiqueta: t('vigilancies.table.moveUp'), desactivada: index === 0, deixaOberta: true, fer: () => mouFila(fila, -1) },
      { clau: 'avall', icona: 'pi-angle-down', etiqueta: t('vigilancies.table.moveDown'), desactivada: index === bloc.files.length - 1, deixaOberta: true, fer: () => mouFila(fila, 1) }
    )
  }
  return accions
})

// ------------------------------------------------------------ ordre

// ↑/↓: una posició amunt (-1) o avall (+1) dins del bloc de la seva hora
const mouFila = (fila, pas) => {
  const ids = blocs.value.find((b) => b.hora === fila.hora).files.map((f) => f.id)
  const index = ids.findIndex((id) => String(id) === String(fila.id))
  emit('mou', fila.hora, ambFilaMoguda(ids, fila.id, index + pas))
}

// Arrossegar: només dins del bloc de la seva hora
const arrossegada = ref(null)
const blocDesti = ref(null)

const comencaArrossegar = (event, fila) => {
  arrossegada.value = fila
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(fila.id))
}

const acabaArrossegar = () => {
  arrossegada.value = null
  blocDesti.value = null
}

// La posició on cauria: davant de la primera fila que té el centre per sota del punter
const posicioA = (event, bloc) => {
  const files = [...event.currentTarget.querySelectorAll('tr[data-fila-id]')]
  const index = files.findIndex((tr) => {
    const r = tr.getBoundingClientRect()
    return event.clientY < r.top + r.height / 2
  })
  return index === -1 ? bloc.files.length : index
}

const sobreBloc = (event, bloc) => {
  if (!arrossegada.value || arrossegada.value.hora !== bloc.hora) return // fora del seu bloc no es pot deixar
  event.preventDefault()
  blocDesti.value = bloc.hora
}

const deixaA = (event, bloc) => {
  if (!arrossegada.value || arrossegada.value.hora !== bloc.hora) return
  event.preventDefault()
  const ids = bloc.files.map((f) => f.id)
  const desti = posicioA(event, bloc)
  // La posició compta la fila arrossegada: si era a sobre, el destí baixa una posició
  const origen = ids.findIndex((id) => String(id) === String(arrossegada.value.id))
  const nou = ambFilaMoguda(ids, arrossegada.value.id, desti > origen ? desti - 1 : desti)
  acabaArrossegar()
  if (nou.some((id, i) => String(id) !== String(ids[i]))) emit('mou', bloc.hora, nou)
}
</script>

<style scoped>
/* L'aspecte (capçalera, files, hora...), a taules.css (.taula-dades) */
.taula-vigilancies {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 62rem;
  border-collapse: collapse;
  table-layout: fixed;
}

.col-seleccio { width: 2.5rem; }
.col-ordre { width: 4rem; }
.col-hora { width: 6rem; }
.col-nivell { width: 6.5rem; }
.col-tipus { width: 10rem; }
.col-grups { width: 7.5rem; }
.col-aula { width: 7rem; }
.col-vigilant { width: 15rem; }
.col-observacions { width: auto; min-width: 10rem; }
.col-accions { width: 4.5rem; }

/* Pantalles tàctils: les accions i les fletxes surten en tocar la fila
   (AccionsFila); la cel·la d'ordre només mostra on tocar */
@media (hover: none) {
  .col-ordre { width: 2.5rem; }
  .col-accions { width: 0; }
}

thead th {
  position: sticky;
  top: 0;
  z-index: 1;
}

.taula-vigilancies__seleccio {
  text-align: center;
}

.taula-vigilancies__seleccio input {
  width: 1rem;
  height: 1rem;
  accent-color: var(--primary-color, #6366f1);
  cursor: pointer;
}

/* La capçalera de cada bloc d'hora (el separador i l'etiqueta, a taules.css) */
.taula-vigilancies__capcalera-bloc > td {
  height: auto;
  background: var(--taula-fila-seleccionada);
}

.taula-vigilancies__compte {
  margin-left: 0.6rem;
  color: #4b5563;
  font-size: 0.85rem;
}

/* El bloc on es pot deixar la fila que s'arrossega */
.taula-vigilancies__bloc--desti {
  outline: 2px dashed var(--primary-color, #6366f1);
  outline-offset: -2px;
}

/* Mentre es recarrega, la taula es queda (tornar-la a crear era el que costava) */
.taula-vigilancies--carregant {
  opacity: 0.6;
  pointer-events: none;
  transition: opacity 0.15s;
}

.taula-vigilancies__buida {
  padding: 3rem 1rem;
  color: #6b7280;
  text-align: center;
}

.taula-vigilancies__buida .pi {
  margin-bottom: 1rem;
  font-size: 3rem;
  color: #ccc;
}

.taula-vigilancies__buida p {
  margin-bottom: 0.5rem;
  font-size: 1.1rem;
}
</style>
