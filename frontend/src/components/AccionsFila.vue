<template>
  <!-- Les accions de la fila tocada, en pantalles tàctils (useFilaTactil): una
       barra plana just a sota de la fila (o a sobre, si a sota no hi cap), a
       prop d'on s'ha tocat i sempre dins de la pantalla. Fora de la taula
       perquè no la talli el desplaçament de costat. Només icones: el text, a
       aria-label i title. -->
  <Teleport to="body">
    <div
      v-if="element"
      ref="barra"
      class="accions-fila"
      :style="estil"
      role="toolbar"
      :aria-label="$t('common.actions')"
    >
      <button
        v-for="accio in accions"
        :key="accio.clau"
        type="button"
        class="accions-fila__boto"
        :class="{ 'accions-fila__boto--perill': accio.perill }"
        :disabled="accio.desactivada"
        :title="accio.etiqueta"
        :aria-label="accio.etiqueta"
        @click="fes(accio)"
      ><i :class="['pi', accio.icona]" aria-hidden="true"></i></button>
    </div>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  element: { type: Object, default: null }, // el <tr> de la fila; null: tancada
  x: { type: Number, default: null }, // on s'ha tocat (horitzontalment); null: el centre de la fila
  // [{ clau, icona, etiqueta, fer, desactivada, perill, deixaOberta }]
  accions: { type: Array, default: () => [] }
})
const emit = defineEmits(['tanca'])

const barra = ref(null)
const estil = ref({ visibility: 'hidden' })
let quadre = null

// Espai que deixa lliure la barra de navegació inferior del mòbil
const MARGE_INFERIOR = 90
// Distància mínima a les vores de la pantalla
const MARGE = 8

// A cada quadre mentre és oberta: segueix la fila quan es desplaça la pàgina o
// la taula, o quan la fila canvia de lloc (↑/↓)
const situa = () => {
  const fila = props.element
  if (!fila) return
  if (!fila.isConnected) {
    emit('tanca')
    return
  }
  const r = fila.getBoundingClientRect()
  const amplada = barra.value?.offsetWidth ?? 0
  const alcada = barra.value?.offsetHeight ?? 0
  const centre = props.x ?? (r.left + r.right) / 2
  const amunt = r.bottom + alcada + 2 > window.innerHeight - MARGE_INFERIOR
  estil.value = {
    left: `${Math.min(Math.max(centre - amplada / 2, MARGE), window.innerWidth - amplada - MARGE)}px`,
    top: `${amunt ? r.top - alcada - 2 : r.bottom + 2}px`,
    // El primer quadre encara no se sap la mida; fora de la pantalla, no es veu
    visibility: !amplada || r.bottom < 0 || r.top > window.innerHeight ? 'hidden' : 'visible'
  }
  quadre = requestAnimationFrame(situa)
}

// Tocar fora de la barra i de la fila la tanca (tocar una altra fila obre la seva)
const tocaFora = (event) => {
  if (barra.value?.contains(event.target) || props.element?.contains(event.target)) return
  emit('tanca')
}

const atura = () => {
  cancelAnimationFrame(quadre)
  document.removeEventListener('pointerdown', tocaFora, true)
}

watch(
  () => props.element,
  (element) => {
    atura()
    if (!element) return
    situa()
    document.addEventListener('pointerdown', tocaFora, true)
  }
)

onBeforeUnmount(atura)

const fes = (accio) => {
  accio.fer()
  if (!accio.deixaOberta) emit('tanca')
}
</script>

<style scoped>
/* Una barra plana, poc alta: tapa el mínim la fila de sota */
.accions-fila {
  position: fixed;
  z-index: 1000;
  display: flex;
  gap: 0.125rem;
  padding: 0.125rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

/* Prou grans per al dit */
.accions-fila__boto {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #4b5563;
  font-size: 0.95rem;
}

.accions-fila__boto:active {
  background: #eef2f7;
}

.accions-fila__boto--perill {
  color: #dc2626;
}

.accions-fila__boto:disabled {
  opacity: 0.35;
}
</style>
