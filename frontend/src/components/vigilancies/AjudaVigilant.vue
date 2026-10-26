<template>
  <!-- Embolcalla el nom del vigilant (o del substitut): en passar-hi per damunt
       (o posar-hi el focus) mostra el mateix text que la seva opció del
       desplegable (l'estat i què fa a aquella hora) i, a sota, quantes
       vigilàncies porta aquell dia. A les pantalles tàctils, no: tocar el nom
       obre el desplegable, que ja ho mostra. -->
  <div
    ref="objectiu"
    class="ajuda-vigilant"
    @mouseenter="programa"
    @mouseleave="amaga"
    @focusin="programa"
    @focusout="amaga"
  >
    <slot />
    <!-- El panell es crea la primera vegada que cal: amb moltes files, crear-ne
         un per fila de bon principi feia més lenta la taula -->
    <OverlayPanel v-if="usat" ref="panell" :aria-label="$t('vigilancies.help.title', { nom })">
      <div class="ajuda">
        <div class="ajuda__opcio" :style="{ backgroundColor: color || undefined }">{{ text || nom }}</div>
        <div v-if="recompteDia" class="ajuda__dia">
          <template v-if="carregant">{{ $t('vigilancies.help.loading') }}</template>
          <template v-else-if="error">{{ $t('vigilancies.help.error') }}</template>
          <template v-else-if="ajuda">
            {{ $t('vigilancies.help.invigilationsDay', { count: ajuda.vigilancies_dia }, ajuda.vigilancies_dia) }}
          </template>
        </div>
      </div>
    </OverlayPanel>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref } from 'vue'
import OverlayPanel from 'primevue/overlaypanel'
import { useAjudaVigilant } from '../../composables/useAjudaVigilant'

const props = defineProps({
  data: { type: String, required: true },
  hora: { type: String, required: true },
  nom: { type: String, default: '' }, // sense vigilant no hi ha ajuda
  text: { type: String, default: '' }, // el text de la seva opció del desplegable
  color: { type: String, default: '' }, // el color de la seva opció
  recompteDia: { type: Boolean, default: true } // amb les vigilàncies del dia (les demana)
})

const { carrega } = useAjudaVigilant()
const objectiu = ref(null)
const panell = ref(null)
const ajuda = ref(null)
const carregant = ref(false)
const error = ref(false)
const usat = ref(false)
let temporitzador = null

// Pantalles tàctils: tocar el nom obre el desplegable, i l'ajuda el tapava
const tactil = window.matchMedia('(hover: none)')

// Un petit retard: passar el ratolí per sobre de la taula no ha d'obrir-les totes
const programa = (event) => {
  if (!props.nom || tactil.matches) return
  clearTimeout(temporitzador)
  temporitzador = setTimeout(() => mostra(event), 350)
}

// El recompte del dia el dona la ruta de l'ajuda (GET .../{hora}/professor)
const mostra = async (event) => {
  if (!usat.value) {
    usat.value = true
    await nextTick()
  }
  panell.value?.show(event, objectiu.value)
  if (!props.recompteDia) return
  carregant.value = true
  error.value = false
  try {
    ajuda.value = await carrega(props.data, props.hora, props.nom)
  } catch {
    error.value = true
  } finally {
    carregant.value = false
  }
}

const amaga = () => {
  clearTimeout(temporitzador)
  panell.value?.hide()
}

onBeforeUnmount(() => clearTimeout(temporitzador))
</script>

<style scoped>
.ajuda-vigilant {
  min-width: 0;
}

.ajuda {
  max-width: 24rem;
  font-size: 0.9rem;
}

/* Com l'opció del desplegable del vigilant */
.ajuda__opcio {
  padding: 0.5rem;
  border-radius: 4px;
  font-weight: 500;
}

.ajuda__dia {
  margin-top: 0.4rem;
  font-size: 0.8rem;
  color: var(--text-color-secondary, #6b7280);
}
</style>
