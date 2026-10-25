<template>
  <!-- Opcions dels PDF (substitucions, vigilàncies i interval). Les pròpies de
       cada diàleg arriben per `opcionsPropies` i es pinten igual que les comunes:
       totes fan servir el mateix element (casella i text en línia). -->
  <div class="pdf-opcions">
    <div v-if="contingut.length" class="pdf-opcions__grup">
      <div class="pdf-opcions__titol">{{ $t(titolContingut) }}</div>
      <div class="pdf-opcions__llista">
        <div v-for="opcio in contingut" :key="opcio.clau" class="pdf-opcio">
          <Checkbox v-model="config[opcio.clau]" :inputId="`${prefix}-${opcio.clau}`" :binary="true" />
          <label :for="`${prefix}-${opcio.clau}`">{{ $t(opcio.etiqueta) }}</label>
        </div>
      </div>
    </div>

    <div class="pdf-opcions__grup">
      <div class="pdf-opcions__titol">{{ $t('pdfOptions.format') }}</div>
      <div class="pdf-opcions__llista">
        <div v-for="f in FORMATS" :key="f.valor" class="pdf-opcio">
          <RadioButton v-model="config.format" :inputId="`${prefix}Format-${f.valor}`" :value="f.valor" />
          <label :for="`${prefix}Format-${f.valor}`">{{ $t(f.etiqueta) }}</label>
        </div>
      </div>
    </div>

    <div class="pdf-opcions__grup">
      <div class="pdf-opcions__titol">{{ $t('pdfOptions.fontSize') }}</div>
      <div class="pdf-opcions__llista pdf-opcions__llista--fila">
        <div v-for="mida in MIDES_LLETRA" :key="mida.valor" class="pdf-opcio">
          <RadioButton v-model="config.midaLletra" :inputId="`${prefix}Mida-${mida.valor}`" :value="mida.valor" />
          <label :for="`${prefix}Mida-${mida.valor}`">{{ $t(mida.etiqueta) }}</label>
        </div>
      </div>
    </div>

    <div class="pdf-opcions__grup">
      <div class="pdf-opcions__titol">{{ $t('pdfOptions.options') }}</div>
      <div class="pdf-opcions__llista">
        <div v-for="opcio in opcions" :key="opcio.clau" class="pdf-opcio">
          <Checkbox
            v-model="config[opcio.clau]"
            :inputId="`${prefix}-${opcio.clau}`"
            :binary="true"
          />
          <label :for="`${prefix}-${opcio.clau}`" v-tooltip.top="opcio.ajuda ? $t(opcio.ajuda) : null">
            {{ $t(opcio.etiqueta) }}
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Checkbox from 'primevue/checkbox'
import RadioButton from 'primevue/radiobutton'
import { MIDES_LLETRA } from '../pdfOpcions'

const FORMATS = [
  { valor: 'hores', etiqueta: 'pdfOptions.formatHours' },
  { valor: 'dia', etiqueta: 'pdfOptions.formatDay' }
]

// v-model:config: l'objecte d'opcions del diàleg
const config = defineModel('config', { type: Object, required: true })
const props = defineProps({
  prefix: { type: String, required: true }, // per als id dels camps (n'hi ha diversos a la pàgina)
  ambConflictes: { type: Boolean, default: false },
  ambDiaPerPagina: { type: Boolean, default: false },
  // Les opcions pròpies del diàleg: [{ clau, etiqueta, ajuda?, amagada? }]
  // (`amagada`: quan no s'aplica no surt, com la columna d'hores a la taula del dia)
  opcionsPropies: { type: Array, default: () => [] },
  // Què inclou el PDF (un primer grup, opcional): [{ clau, etiqueta }]
  contingut: { type: Array, default: () => [] },
  titolContingut: { type: String, default: '' }
})

// Totes les caselles, en ordre; la columna d'hores només quan té efecte
// (format per hores): a la taula del dia l'hora ja és la primera columna
const opcions = computed(() => [
  { clau: 'showComments', etiqueta: 'pdfOptions.showComments' },
  ...(config.value.format === 'dia' ? [] : [{ clau: 'showHours', etiqueta: 'pdfOptions.showHours' }]),
  ...(props.ambConflictes ? [{ clau: 'showConflicts', etiqueta: 'pdfOptions.showConflicts' }] : []),
  { clau: 'compress', etiqueta: 'pdfOptions.compress' },
  ...(props.ambDiaPerPagina ? [{ clau: 'diaPerPagina', etiqueta: 'pdfOptions.dayPerPage' }] : []),
  ...props.opcionsPropies.filter((opcio) => !opcio.amagada)
])
</script>

<style scoped>
/* Estils propis: l'aplicació no carrega PrimeFlex (field, mt-3... no fan res) */
.pdf-opcions__grup + .pdf-opcions__grup {
  margin-top: 1.1rem;
}

.pdf-opcions__titol {
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.pdf-opcions__llista {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.pdf-opcions__llista--fila {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 1rem;
}

/* Casella (o botó) i text en línia, amb el mateix espai a totes; el text
   llarg passa a la línia següent en lloc de tallar-se */
.pdf-opcio {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.pdf-opcio :deep(.p-checkbox),
.pdf-opcio :deep(.p-radiobutton) {
  flex: 0 0 auto;
}

.pdf-opcio label {
  margin: 0;
  white-space: normal;
  overflow-wrap: anywhere;
  cursor: pointer;
}
</style>
