import { createI18n } from 'vue-i18n'
import ca from './locales/ca.json'
import es from './locales/es.json'
import en from './locales/en.json'

const storedLocale = localStorage.getItem('app_locale') || 'ca'

export const primeLocales = {
  ca: {
    firstDayOfWeek: 1,
    dayNames: ['diumenge', 'dilluns', 'dimarts', 'dimecres', 'dijous', 'divendres', 'dissabte'],
    dayNamesShort: ['dg', 'dl', 'dt', 'dc', 'dj', 'dv', 'ds'],
    dayNamesMin: ['dg', 'dl', 'dt', 'dc', 'dj', 'dv', 'ds'],
    monthNames: ['gener', 'febrer', 'març', 'abril', 'maig', 'juny', 'juliol', 'agost', 'setembre', 'octubre', 'novembre', 'desembre'],
    monthNamesShort: ['gen', 'feb', 'març', 'abr', 'maig', 'juny', 'jul', 'ag', 'set', 'oct', 'nov', 'des'],
    today: 'Avui',
    clear: 'Neteja',
    weekHeader: 'Set',
    dateFormat: 'dd/mm/yy'
  },
  es: {
    firstDayOfWeek: 1,
    dayNames: ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'],
    dayNamesShort: ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'],
    dayNamesMin: ['do', 'lu', 'ma', 'mi', 'ju', 'vi', 'sá'],
    monthNames: ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'],
    monthNamesShort: ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'],
    today: 'Hoy',
    clear: 'Limpiar',
    weekHeader: 'Sem',
    dateFormat: 'dd/mm/yy'
  },
  en: {
    firstDayOfWeek: 1,
    dayNames: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
    dayNamesShort: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    dayNamesMin: ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'],
    monthNames: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    monthNamesShort: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    today: 'Today',
    clear: 'Clear',
    weekHeader: 'Wk',
    dateFormat: 'dd/mm/yy'
  }
}

const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: storedLocale,
  fallbackLocale: 'ca',
  messages: { ca, es, en }
})

export const setLocale = (locale) => {
  const next = locale || 'ca'
  i18n.global.locale.value = next
  localStorage.setItem('app_locale', next)
}

export default i18n
