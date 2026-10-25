<template>
  <!-- Una vigilància. Cada camp es mostra com a text i el desplegable es crea
       en fer-hi clic (CampDesplegable). La fila no es modifica ella mateixa:
       avisa del canvi (`canvi`) i qui la mostra el desa. -->
  <tr
    class="fila-vigilancia taula-fila"
    :class="{
      'taula-fila--seleccionada': seleccionada,
      'taula-fila--activa': activa,
      'fila-vigilancia--ressaltada': ressaltada,
      'fila-vigilancia--titular-lliure': titularLliure,
      'fila-vigilancia--arrossegada': arrossegada
    }"
    :data-fila-id="fila.id"
    :draggable="agafada"
    @dragstart="emit('comenca-arrossegar', $event, fila)"
    @dragend="agafada = false; emit('acaba-arrossegar')"
  >
    <td class="fila-vigilancia__seleccio">
      <input
        type="checkbox"
        :checked="seleccionada"
        :aria-label="$t('vigilancies.table.selectRow', { hora: fila.hora })"
        @change="emit('selecciona', fila, $event.target.checked)"
      />
    </td>
    <td class="fila-vigilancia__ordre">
      <!-- Pantalles tàctils: on tocar per veure les accions de la fila -->
      <i class="pi pi-ellipsis-v fila-vigilancia__mes" aria-hidden="true"></i>
      <template v-if="mobil">
        <span
          class="fila-vigilancia__nansa"
          :title="$t('vigilancies.table.dragHandle')"
          aria-hidden="true"
          @mousedown="agafada = true"
          @mouseup="agafada = false"
        ><i class="pi pi-bars"></i></span>
        <button
          type="button"
          class="fila-vigilancia__moure"
          :disabled="primera"
          :aria-label="$t('vigilancies.table.moveUp')"
          @click="emit('mou', fila, -1)"
        ><i class="pi pi-angle-up"></i></button>
        <button
          type="button"
          class="fila-vigilancia__moure"
          :disabled="ultima"
          :aria-label="$t('vigilancies.table.moveDown')"
          @click="emit('mou', fila, 1)"
        ><i class="pi pi-angle-down"></i></button>
      </template>
    </td>
    <td class="fila-vigilancia__cella-hora">
      <CampDesplegable
        :modelValue="fila.hora"
        :options="opcions.hores"
        :etiqueta="$t('common.hour')"
        @change="emit('canvi', fila, 'hora', $event)"
      >
        <template #valor><span class="fila-vigilancia__hora">{{ fila.hora }}</span></template>
      </CampDesplegable>
    </td>
    <td>
      <CampDesplegable
        :modelValue="fila.nivell || ''"
        :options="[$t('vigilancies.placeholders.level'), ...opcions.nivells]"
        :placeholder="$t('vigilancies.placeholders.level')"
        :etiqueta="$t('vigilancies.columns.level')"
        @change="emit('canvi', fila, 'nivell', $event)"
      />
    </td>
    <td>
      <CampDesplegable
        :modelValue="fila.tipus || ''"
        :options="opcions.tipusDe(fila.nivell)"
        :placeholder="$t('vigilancies.placeholders.type')"
        :etiqueta="$t('vigilancies.columns.type')"
        @change="emit('canvi', fila, 'tipus', $event)"
      />
    </td>
    <td>
      <CampDesplegable
        :modelValue="fila.grups || ''"
        :options="[$t('vigilancies.placeholders.groups'), ...opcions.grupsDe(fila.nivell)]"
        :placeholder="$t('vigilancies.placeholders.groups')"
        :etiqueta="$t('common.group')"
        @change="emit('canvi', fila, 'grups', $event)"
      />
    </td>
    <td>
      <CampDesplegable
        :modelValue="fila.aula || ''"
        :options="[$t('vigilancies.placeholders.room'), ...opcions.aules]"
        :placeholder="$t('vigilancies.placeholders.room')"
        :etiqueta="$t('common.room')"
        @change="emit('canvi', fila, 'aula', $event)"
      />
    </td>
    <td>
      <AjudaVigilant :data="data" :hora="fila.hora" :nom="fila.vigilant" :text="etiquetaVigilant" :color="colorVigilant">
        <SelectorVigilant
          :modelValue="fila.vigilant || ''"
          :opcions="disponibles"
          :etiqueta-valor="etiquetaVigilant"
          @change="emit('canvi', fila, 'vigilant', $event)"
        />
      </AjudaVigilant>
    </td>
    <td>
      <input
        class="fila-vigilancia__observacions"
        type="text"
        :value="fila.comentaris || ''"
        :placeholder="$t('common.commentsPlaceholder')"
        :aria-label="$t('common.comments')"
        @change="emit('canvi', fila, 'comentaris', $event.target.value)"
      />
    </td>
    <td class="fila-vigilancia__accions taula-accions">
      <button
        type="button"
        class="taula-accio"
        :title="$t('vigilancies.actions.duplicateRow')"
        :aria-label="$t('vigilancies.actions.duplicateRow')"
        @click="emit('afegeix', fila)"
      ><i class="pi pi-clone" aria-hidden="true"></i></button>
      <button
        type="button"
        class="taula-accio"
        :title="$t('common.delete')"
        :aria-label="$t('common.delete')"
        @click="emit('esborra', fila)"
      ><i class="pi pi-trash" aria-hidden="true"></i></button>
    </td>
  </tr>
</template>

<script setup>
import { computed, ref } from 'vue'
import AjudaVigilant from './AjudaVigilant.vue'
import CampDesplegable from './CampDesplegable.vue'
import SelectorVigilant from './SelectorVigilant.vue'

const props = defineProps({
  fila: { type: Object, required: true },
  data: { type: String, required: true }, // el dia (ISO), per a l'ajuda del vigilant
  // { hores, nivells, aules, tipusDe(nivell), grupsDe(nivell) }
  opcions: { type: Object, required: true },
  disponibles: { type: Array, default: () => [] }, // opcions del vigilant
  etiquetaVigilant: { type: String, default: '' },
  seleccionada: { type: Boolean, default: false },
  activa: { type: Boolean, default: false }, // pantalles tàctils: la fila tocada, amb les accions a sota
  ressaltada: { type: Boolean, default: false },
  titularLliure: { type: Boolean, default: false },
  mobil: { type: Boolean, default: true }, // es pot canviar d'ordre (sense filtres)
  primera: { type: Boolean, default: false },
  ultima: { type: Boolean, default: false },
  arrossegada: { type: Boolean, default: false } // la que s'està arrossegant
})
// Cada esdeveniment porta la fila: així qui la mostra hi passa funcions fixes i
// la fila només es torna a pintar quan canvia (amb moltes files, important)
const emit = defineEmits(['canvi', 'selecciona', 'afegeix', 'esborra', 'mou', 'comenca-arrossegar', 'acaba-arrossegar'])

// El color de l'opció del vigilant triat (per a l'ajuda)
const colorVigilant = computed(() => props.disponibles.find((d) => d.value === props.fila.vigilant)?.color || '')

// Només s'arrossega des de la nansa: la resta de la fila es pot seleccionar i editar
const agafada = ref(false)
</script>

<style scoped>
/* L'aspecte de la fila (alçada, espais, ratolí, seleccionada) i dels botons
   d'acció, a taules.css (.taula-fila, .taula-accio) */
.fila-vigilancia--arrossegada {
  opacity: 0.4;
}

.fila-vigilancia--titular-lliure > td {
  background-color: rgba(250, 204, 21, 0.18);
}

/* Fila nova o que ha canviat d'hora: es ressalta uns segons */
.fila-vigilancia--ressaltada > td {
  animation: ressalta 4s ease-out;
}

@keyframes ressalta {
  0%, 60% { background-color: #fde68a; }
  100% { background-color: transparent; }
}

.fila-vigilancia__seleccio {
  text-align: center;
}

.fila-vigilancia__seleccio input {
  width: 1rem;
  height: 1rem;
  accent-color: var(--primary-color, #6366f1);
  cursor: pointer;
}

.fila-vigilancia__ordre {
  white-space: nowrap;
  color: #9ca3af;
}

.fila-vigilancia__nansa {
  display: inline-block;
  padding: 0.2rem;
  cursor: grab;
}

.fila-vigilancia__moure {
  padding: 0.1rem 0.15rem;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  opacity: 0;
}

.fila-vigilancia:hover .fila-vigilancia__moure,
.fila-vigilancia__moure:focus-visible {
  opacity: 1;
}

.fila-vigilancia__moure:disabled {
  visibility: hidden;
}

/* Pantalles tàctils: arrossegar només va amb el ratolí i les fletxes surten
   amb les altres accions en tocar la fila (AccionsFila); la cel·la mostra on
   tocar */
.fila-vigilancia__mes {
  display: none;
}

@media (hover: none) {
  .fila-vigilancia__nansa,
  .fila-vigilancia__moure {
    display: none;
  }

  .fila-vigilancia__mes {
    display: inline-block;
    padding: 0.5rem;
  }
}

/* L'hora de la fila, discreta i centrada: la que destaca és la del bloc */
.fila-vigilancia__cella-hora :deep(.camp-desplegable__text) {
  justify-content: center;
}

.fila-vigilancia__hora {
  white-space: nowrap;
  color: #6b7280;
  font-size: 0.9rem;
}

.fila-vigilancia__observacions {
  width: 100%;
  min-height: 2rem;
  padding: 0.3rem 0.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font: inherit;
}

.fila-vigilancia__observacions:focus {
  border-color: var(--primary-color, #6366f1);
  outline: none;
}

.fila-vigilancia__accions {
  white-space: nowrap;
}
</style>
