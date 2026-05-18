import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import Tooltip from 'primevue/tooltip'
import i18n, { primeLocales } from './i18n'

// Estils de PrimeVue
import 'primevue/resources/themes/lara-light-blue/theme.css'
import 'primevue/resources/primevue.min.css'
import 'primeicons/primeicons.css'

import App from './App.vue'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(PrimeVue, {
  locale: primeLocales[i18n.global.locale.value] || primeLocales.ca,
  zIndex: { modal: 1200, overlay: 1200, menu: 1200, tooltip: 1100, toast: 1300 }
})
app.use(ToastService)
app.use(ConfirmationService)
app.use(i18n)
app.directive('tooltip', Tooltip)

const DEFAULT_TOAST_LIFE = 5000
const rawToastService = app.config.globalProperties.$toast

if (rawToastService?.add) {
  const originalToastAdd = rawToastService.add.bind(rawToastService)
  rawToastService.add = (message) => {
    if (Array.isArray(message)) {
      message.forEach((msg) => rawToastService.add(msg))
      return
    }
    const msg = { ...(message || {}) }
    if (msg.sticky !== true && typeof msg.life !== 'number') {
      msg.life = DEFAULT_TOAST_LIFE
    }
    originalToastAdd(msg)
  }
}

watch(i18n.global.locale, (nextLocale) => {
  const primevue = app.config.globalProperties.$primevue
  if (primevue?.config) {
    primevue.config.locale = primeLocales[nextLocale] || primeLocales.ca
  }
})

app.mount('#app')
