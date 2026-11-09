// Configuració d'ESLint del frontend.
//   npm run lint
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import errorUnic from './eslint-rules/errors-unics.js'

export default [
  { ignores: ['dist/**', '.vite/**', 'test-results/**', 'playwright-report/**'] },
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
    files: ['*.config.js', 'e2e/**/*.js'],
    languageOptions: { globals: { ...globals.node } },
  },
  {
    rules: {
      // `_nom`: paràmetre que es rep però no es fa servir; i el patró
      // `({ a, b, ...rest }) => rest` per treure camps d'un objecte.
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', ignoreRestSiblings: true }],
    },
  },
  {
    files: ['src/**/*.{js,vue}'],
    plugins: { avisos: { rules: { 'error-unic': errorUnic } } },
    rules: { 'avisos/error-unic': 'error' },
  },
  {
    // El botó d'acceptar de les confirmacions d'esborrar, sempre vermell i
    // des d'un sol lloc: useConfirmaEsborrar (composables/useConfirmaEsborrar.js).
    files: ['src/**/*.{js,vue}'],
    ignores: ['src/composables/useConfirmaEsborrar.js'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: "Property[key.name='acceptClass']",
          message: "Les confirmacions d'esborrar, amb useConfirmaEsborrar: el botó ja hi surt vermell.",
        },
        {
          selector: "CallExpression[callee.property.name='require'] Property[key.name='acceptLabel'] Literal[value='common.delete']",
          message: "Una confirmació amb «Elimina» s'ha de fer amb useConfirmaEsborrar, perquè el botó surti vermell.",
        },
      ],
    },
  },
]
