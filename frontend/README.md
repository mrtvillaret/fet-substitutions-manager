# Frontend Vue 3 - Gestor Substitucions

## 🚀 Instal·lació

```bash
# Instal·lar Node.js si no el tens (necessites v18+)
# Descarrega de: https://nodejs.org/

# Des de web-prototype/frontend/
npm install
```

## ▶️ Executar

```bash
npm run dev
```

El frontend arrencarà a: http://localhost:5173

**IMPORTANT:** El backend FastAPI ha d'estar executant a `http://localhost:8000`

## 🏗️ Build per producció

```bash
npm run build
# Genera carpeta dist/ amb fitxers optimitzats
```

## 📚 Stack tecnològic

- **Vue 3** - Framework frontend
- **Vite** - Build tool (super ràpid)
- **PrimeVue** - Components UI
- **Pinia** - Gestió estat (preparat però encara no utilitzat)
- **Axios** - Crides HTTP a l'API

## 🎨 Funcionalitats implementades

### ✅ SubstitucionsView
- Calendari per triar data
- Taula interactiva de substitucions amb:
  - Ordenació per columnes
  - Paginació (10/20/50 files)
  - Dropdown per assignar substitut
- Generar substitucions automàticament
- Estadístiques (total, assignades, pendents)
- Notificacions toast
- Responsive design

### ✅ Vigilàncies i PDFs
- Taula de vigilàncies per dia
- Assignació de vigilants
- Export PDF diari i per interval

### ✅ Configuració
- Configuració general i d'exàmens
- Estadístiques i informes

### ✅ Login
- Pantalla de login amb JWT
- Guardat de token a localStorage

## 📂 Estructura

```
frontend/
├── index.html              # HTML base
├── package.json            # Dependències
├── vite.config.js          # Config Vite + proxy API
└── src/
    ├── main.js             # Entry point (Vue + PrimeVue)
    ├── App.vue             # Component principal (inclou login)
    ├── views/
    │   └── SubstitucionsView.vue
    ├── components/         # (per afegir components reutilitzables)
    └── stores/             # (per Pinia stores)
```

## 🔌 Crides API

El frontend fa crides a:

- `POST /api/login` - Login (token)
- `GET /api/config` - Configuració sistema
- `GET /api/substitucions/{data}` - Substitucions del dia
- `POST /api/substitucions/{data}/generar` - Generar automàticament
- `PUT /api/substitucions/{data}/{hora}/{professor}` - Actualitzar substitut
- `GET /api/professors` - Llista professors

## 🎯 Següents passos

1. **i18n** per català/espanyol (frontend)
2. **Millores responsive** per mòbil
3. **Vue Router** per navegació entre pàgines (si cal)

## 💡 Notes

- El proxy de Vite redirigeix `/api/*` → `http://localhost:8000/api/*`
- Hot Module Replacement (HMR) - canvis es veuen instantàniament
- PrimeVue té molts components: https://primevue.org/
