<template>
  <!-- Una substitució. El substitut es mostra com a text i el desplegable es
       crea en fer-hi clic (SelectorVigilant, com el vigilant). La fila no es
       modifica ella mateixa: avisa del canvi (`canvi`) i qui la mostra el desa. -->
  <tr
    class="fila-substitucio taula-fila"
    :class="{ 'taula-fila--activa': activa }"
    :data-fila-id="clau"
  >
    <td class="fila-substitucio__hora">{{ fila.hora }}</td>
    <td class="fila-substitucio__absent">{{ fila.professor_absent }}</td>
    <td class="fila-substitucio__text">{{ fila.assignatura }}</td>
    <td class="fila-substitucio__grup">
      <!-- Els grups que van junts («4-ESO-A,4-ESO-B»): es parteixen per les comes, no pels guionets -->
      <template v-for="(part, i) in grups" :key="i"><span class="fila-substitucio__un-grup">{{ part }}<template v-if="i < grups.length - 1">,</template></span><wbr /></template>
    </td>
    <td>
      <AjudaVigilant :data="data" :hora="fila.hora" :nom="fila.substitut" :text="opcioSubstitut?.label" :color="opcioSubstitut?.color" :recompte-dia="false">
        <SelectorVigilant
          :modelValue="fila.substitut || ''"
          :opcions="disponibles"
          :etiqueta-valor="opcioSubstitut?.label || ''"
          :placeholder="$t('substitutions.columns.pickSubstitute')"
          :etiqueta="$t('substitutions.columns.substitute')"
          @change="emit('canvi', fila, 'substitut', $event)"
        />
      </AjudaVigilant>
    </td>
    <td>
      <!-- Només de lectura fins que s'hi entra: que el navegador no l'empleni sol -->
      <input
        class="fila-substitucio__observacions"
        type="text"
        :value="fila.comentaris || ''"
        :title="fila.comentaris || null"
        :placeholder="$t('common.commentsPlaceholder')"
        :aria-label="$t('common.comments')"
        autocomplete="new-password"
        autocapitalize="off"
        spellcheck="false"
        data-lpignore="true"
        data-form-type="other"
        readonly
        @focus="$event.target.removeAttribute('readonly')"
        @change="emit('canvi', fila, 'comentaris', $event.target.value)"
      />
    </td>
    <td>
      <span class="fila-substitucio__estat" :class="`fila-substitucio__estat--${assignada ? 'assignada' : 'pendent'}`">
        {{ assignada ? $t('substitutions.status.assigned') : $t('substitutions.status.pending') }}
      </span>
    </td>
    <td class="fila-substitucio__accions taula-accions">
      <button
        type="button"
        class="taula-accio"
        :title="$t('substitutions.actions.manageAbsences')"
        :aria-label="$t('substitutions.actions.manageAbsences')"
        @click="emit('edita', fila)"
      ><i class="pi pi-pencil" aria-hidden="true"></i></button>
      <button
        type="button"
        class="taula-accio taula-accio--perill"
        :title="$t('substitutions.actions.deleteAbsences', { professor: fila.professor_absent })"
        :aria-label="$t('substitutions.actions.deleteAbsences', { professor: fila.professor_absent })"
        @click="emit('esborra', fila)"
      ><i class="pi pi-trash" aria-hidden="true"></i></button>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import AjudaVigilant from '../vigilancies/AjudaVigilant.vue'
import SelectorVigilant from '../vigilancies/SelectorVigilant.vue'

const props = defineProps({
  fila: { type: Object, required: true },
  clau: { type: String, required: true }, // identifica la fila (la substitució no té id)
  data: { type: String, required: true }, // el dia (ISO)
  disponibles: { type: Array, default: () => [] }, // opcions del substitut
  activa: { type: Boolean, default: false } // pantalles tàctils: la fila tocada, amb les accions a sota
})
// Cada esdeveniment porta la fila: així qui la mostra hi passa funcions fixes i
// la fila només es torna a pintar quan canvia
const emit = defineEmits(['canvi', 'edita', 'esborra'])

// L'opció del substitut triat: el seu text (a la cel·la i a l'ajuda) i el color
const opcioSubstitut = computed(() =>
  props.fila.substitut ? props.disponibles.find((d) => d.value === props.fila.substitut) : null
)
const assignada = computed(() => props.fila.estat === 'assignada')
const grups = computed(() => (props.fila.grup || '').split(','))
</script>

<style scoped>
/* L'aspecte de la fila (alçada, espais, ratolí) i dels botons d'acció, a
   taules.css (.taula-fila, .taula-accio) */
.fila-substitucio__hora {
  white-space: nowrap;
  color: #6b7280;
  font-size: 0.9rem;
  text-align: center;
}

.fila-substitucio__absent {
  color: #2c3e50;
  font-weight: 500;
}

.fila-substitucio__text {
  color: #495057;
}

.fila-substitucio__grup {
  color: #6c757d;
  font-weight: 500;
}

.fila-substitucio__un-grup {
  white-space: nowrap;
}

.fila-substitucio__observacions {
  width: 100%;
  min-height: 2rem;
  padding: 0.3rem 0.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font: inherit;
}

.fila-substitucio__observacions:focus {
  border-color: var(--primary-color, #6366f1);
  outline: none;
}

.fila-substitucio__estat {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  border: 1px solid;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
}

.fila-substitucio__estat--assignada {
  border-color: #c3e6cb;
  background: #d4edda;
  color: #155724;
}

.fila-substitucio__estat--pendent {
  border-color: #ffeaa7;
  background: #fff3cd;
  color: #856404;
}

.fila-substitucio__accions {
  white-space: nowrap;
}
</style>
