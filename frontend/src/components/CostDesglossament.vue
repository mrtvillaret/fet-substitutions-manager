<template>
  <!-- Icona al costat del cost total: amb el ratolí, en passar-hi per damunt;
       amb el dit (mòbil) o el teclat, en tocar-la o prémer-la. Obre el
       desglossament (quantitat × pes = punts) dels conceptes amb punts. -->
  <span v-if="files.length" class="cost-desglossament">
    <button
      ref="boto"
      type="button"
      class="cost-desglossament__boto"
      :aria-label="t('scheduler.steps.results.costBreakdown.open')"
      :aria-expanded="obert ? 'true' : 'false'"
      @click="commuta"
      @mouseenter="mostraAmbRatoli"
      @mouseleave="amagaAmbRatoli"
    >
      <i class="pi pi-info-circle" aria-hidden="true"></i>
    </button>
    <OverlayPanel ref="panell" :aria-label="t('scheduler.steps.results.costBreakdown.title')" @show="obert = true" @hide="obert = false">
      <div class="cost-desglossament__panell">
        <div class="cost-desglossament__titol">{{ t('scheduler.steps.results.costBreakdown.title') }}</div>
        <table class="cost-desglossament__taula">
          <tbody>
            <tr v-for="fila in files" :key="fila.concepte">
              <th scope="row">{{ fila.etiqueta }}</th>
              <td class="calcul">{{ fila.calcul }}</td>
              <td class="punts">{{ text(fila.punts) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">{{ t('scheduler.steps.results.costBreakdown.total') }}</th>
              <td></td>
              <td class="punts">{{ text(total) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </OverlayPanel>
  </span>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import OverlayPanel from 'primevue/overlaypanel'
import { filesDesglossament } from '../views/scheduler/costDesglossament.js'

const props = defineProps({
  desglossament: { type: Array, default: () => [] }
})

const { t, locale } = useI18n()
const boto = ref(null)
const panell = ref(null)
const obert = ref(false)

const resultat = computed(() => filesDesglossament(props.desglossament, t, locale.value))
const files = computed(() => resultat.value.files)
const total = computed(() => resultat.value.total)
const text = (punts) => resultat.value.text(punts)

// Amb el dit, el navegador també envia mouseenter en tocar: només el ratolí obre en passar-hi
const ambRatoli = () => window.matchMedia?.('(hover: hover)').matches
let obertAmbRatoli = false

const commuta = (event) => {
  if (obertAmbRatoli) {
    // El ratolí ja l'havia obert: el clic el deixa obert (ara fix)
    obertAmbRatoli = false
    return
  }
  panell.value?.toggle(event, boto.value)
}
const mostraAmbRatoli = (event) => {
  if (!ambRatoli() || obert.value) return
  obertAmbRatoli = true
  panell.value?.show(event, boto.value)
}
const amagaAmbRatoli = () => {
  if (!obertAmbRatoli) return
  obertAmbRatoli = false
  panell.value?.hide()
}
</script>

<style scoped>
.cost-desglossament { display: inline-flex; align-items: center; margin-left: 0.35rem; }
.cost-desglossament__boto {
  border: none; background: transparent; color: #4f46e5; cursor: pointer;
  /* Prou gran per tocar-la amb el dit */
  min-width: 32px; min-height: 32px; padding: 0.25rem; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
}
.cost-desglossament__boto:focus-visible { outline: 2px solid #4f46e5; outline-offset: 1px; }
.cost-desglossament__panell { max-width: min(90vw, 360px); }
.cost-desglossament__titol { font-weight: 700; margin-bottom: 0.4rem; }
.cost-desglossament__taula { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
.cost-desglossament__taula th { text-align: left; font-weight: 500; padding: 0.15rem 0.6rem 0.15rem 0; }
.cost-desglossament__taula td { padding: 0.15rem 0 0.15rem 0.6rem; white-space: nowrap; }
.cost-desglossament__taula td.calcul { color: #475569; }
.cost-desglossament__taula td.punts { text-align: right; font-variant-numeric: tabular-nums; }
.cost-desglossament__taula tfoot th, .cost-desglossament__taula tfoot td { border-top: 1px solid #cbd5e1; font-weight: 700; padding-top: 0.3rem; }
</style>
