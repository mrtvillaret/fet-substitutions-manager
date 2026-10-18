// Configuració d'ESLint del frontend.
//   npm run lint
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

export default [
  { ignores: ['dist/**', '.vite/**'] },
  js.configs.recommended,
  // Regles bàsiques ara; strongly-recommended i recommended, més endavant.
  ...pluginVue.configs['flat/essential'],
  {
    files: ['**/*.{js,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser },
    },
  },
  {
    // Fitxers de configuració: s'executen amb Node, no al navegador.
    files: ['*.config.js'],
    languageOptions: { globals: { ...globals.node } },
  },
  {
    // Deute conegut: SchedulerDialogs.vue modifica props. Avís fins que es
    // refaci el planificador (fase 3), perquè no aturi la CI.
    rules: { 'vue/no-mutating-props': 'warn' },
  },
  {
    rules: {
      // `_nom`: paràmetre que es rep però no es fa servir; i el patró
      // `({ a, b, ...rest }) => rest` per treure camps d'un objecte.
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', ignoreRestSiblings: true }],
    },
  },
  {
    // La plantilla és externa (<template src>) i ESLint no veu què s'hi fa
    // servir: totes les variables del script semblen sense ús.
    files: ['src/views/SchedulerView.vue'],
    rules: { 'no-unused-vars': 'off' },
  },
]
