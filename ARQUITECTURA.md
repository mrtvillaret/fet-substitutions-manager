# Mapa de dependències del projecte

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vue 3)                           │
│                                                                  │
│  main.js → App.vue (i18n, PrimeVue, Pinia) — navegació per tabs   │
│                                                                  │
│  VISTES PRINCIPALS                                               │
│  ├── SubstitucionsView.vue                                       │
│  ├── VigilanciesView.vue                                         │
│  ├── GrupsView.vue                                               │
│  └── SchedulerView.vue                                           │
│        ├── SchedulerView.template.html  ← template extern        │
│        ├── SchedulerView.css                                     │
│        ├── useSchedulerApi.js           ← crides API             │
│        ├── useSchedulerResults.js       ← processa resultats     │
│        ├── useSchedulerIncidencies.js                            │
│        ├── useSchedulerRestrictions.js                           │
│        ├── useSchedulerSlotsConfig.js                            │
│        ├── useAlliberamentsPerNivell.js                          │
│        ├── analysisParsers.js                                    │
│        ├── dateUtils.js / idUtils.js / textUtils.js              │
│        ├── incidentFormatters.js                                 │
│        └── steps/: SchedulerDialogs, StepConfig, StepGroups,     │
│                    StepRestrictions, StepAnalysis, StepResults    │
│                                                                  │
│  COMPONENTS                                                      │
│  ├── ConfiguracioDialog.vue                                      │
│  ├── ConfiguracioExamensDialog.vue                               │
│  ├── EstadistiquesDialog.vue                                     │
│  ├── PublicarVigilanciesDialog.vue                               │
│  ├── ProfileDialog.vue                                           │
│  ├── AjudaDialog.vue                                             │
│  ├── ConflicteDialog.vue                                         │
│  ├── HorariEditable.vue                                          │
│  └── SlotDropZone.vue                                            │
│                                                                  │
│  locales/: ca.json, es.json, en.json                             │
│  i18n.js ← configuració vue-i18n                                 │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP (Vite proxy dev / Nginx prod)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                              │
│                                                                  │
│  main.py  ← punt d'entrada, registra tots els routers            │
│                                                                  │
│  CAPA DE ROUTES (/api/*)                                         │
│  ├── auth.py             → login, cookie JWT                     │
│  ├── substitucions.py    → CRUD substitucions diàries            │
│  ├── vigilancies.py      → CRUD vigilàncies                      │
│  ├── vigilancia_absent.py→ vigilants absents                     │
│  ├── disponibles.py      → professors disponibles/forat          │
│  ├── prioritats.py       → categories i prioritats               │
│  ├── estadistiques.py    → recomptes i estadístiques             │
│  ├── informes.py         → PDF informe direcció/professors       │
│  ├── pdf.py              → PDF substitucions/vigilàncies/int.    │
│  ├── horari.py           → consultes horari XML                  │
│  ├── grups.py            → grups per nivell                      │
│  ├── files.py            → upload XML horari                     │
│  ├── users.py            → gestió usuaris                        │
│  ├── settings.py         → gestió institucions                   │
│  ├── config_examens.py   → config assignatures/aules examens     │
│  └── scheduler.py        → planificador exàmens (orquestra)      │
│        ├── scheduler_service.py    ← CRUD config scheduler       │
│        ├── scheduler_helpers.py    ← helpers intermedis          │
│        └── scheduler_analysis_helpers.py                         │
│                                                                  │
│  Nota: vigilancia_absent.py viu a routes/ però NO és un router,  │
│        són helpers per substitucions.py i vigilancies.py         │
│                                                                  │
│  CAPA DE LÒGICA DE NEGOCI                                        │
│  ├── horari_web.py                ← GestorHorariWeb (parser XML  │
│  │                                  FET + abreviatures BD;       │
│  │                                  singleton via helpers.       │
│  │                                  get_horari())                │
│  ├── core/substitucions.py        ← assignació automàtica        │
│  ├── core/substitutions_data_manager.py ← persistència subs      │
│  ├── core/alliberats.py           ← professors disponibles forat │
│  ├── core/absencies.py            ← filtre absències reals       │
│  ├── core/baixes.py               ← gestió de baixes             │
│  ├── core/json_loader.py          ← càrrega fitxers JSON         │
│  ├── core/vigilancia_core.py      ← lògica vigilàncies           │
│  ├── core/vigilancia_assignacio.py                               │
│  └── core/vigilancia_data.py                                     │
│                                                                  │
│  SCHEDULER ENGINE (planificador exàmens)                         │
│  ├── factory.py                   ← selecciona motor             │
│  ├── defaults.py                  ← valors per defecte           │
│  ├── validacio.py                 ← genera logs d'incidències     │
│  ├── estadistiques.py             ← estadístiques del pla        │
│  ├── domain/models.py             ← models de domini             │
│  ├── generators/base.py           ← classe base motors           │
│  ├── generators/v2_intents.py                                    │
│  ├── generators/v2_backtrack.py                                  │
│  ├── generators/v3_sa.py          ← Simulated Annealing          │
│  └── core/: context, constraints, scoring, availability,         │
│             durada, date_mapping, diagnostic, analysis,           │
│             normalitzacio, restriction_engine                     │
│                                                                  │
│  CAPA D'ACCÉS A DADES                                            │
│  ├── database.py          ← sessions SQLAlchemy (auth + dades)   │
│  ├── repositories.py      ← CRUD genèric (UserRepo, ConfigRepo…) │
│  ├── models.py            ← models SQLAlchemy (taules principals) │
│  ├── schemas.py           ← models Pydantic (request/response)   │
│  └── data/                                                       │
│        ├── models.py      ← models addicionals                   │
│        ├── storage.py     ← accés a fitxers de dades             │
│        ├── json_helpers.py                                       │
│        └── google_storage.py ← integració Google Drive           │
│                                                                  │
│  EXPORTACIÓ PDF                                                  │
│  ├── export/base_pdf.py           ← classe base                  │
│  ├── export/pdf_styles.py         ← estils comuns                │
│  ├── export/pdf_images.py         ← imatges embegudes            │
│  ├── export/pdf.py                ← exportador substitucions     │
│  ├── export/pdf_interval.py       ← exportador intervals         │
│  └── export/pdf/                                                 │
│        ├── engine.py              ← motor principal              │
│        ├── combined_exporter.py   ← subs + vigilàncies           │
│        ├── dialogs.py             ← PDF diàlegs                  │
│        ├── informe_direccio.py                                   │
│        └── informe_professors.py                                 │
│                                                                  │
│  INFRAESTRUCTURA                                                 │
│  ├── config/settings.py   ← Config global (institucions)         │
│  ├── config/auth.py       ← JWT, usuaris per defecte             │
│  ├── config/constants.py  ← PRIORITATS, NO_SUBST globals         │
│  ├── config/pdf.json      ← perfils visuals PDF                  │
│  ├── auth_utils.py        ← decoradors autenticació              │
│  ├── dependencies.py      ← Depends FastAPI                      │
│  ├── helpers.py           ← utils generals                       │
│  ├── i18n_setup.py        ← traduccions backend (PDF)            │
│  ├── rate_limit.py        ← limitació de peticions               │
│  └── utils/                                                      │
│        ├── hores.py / date_manager.py / date_context.py          │
│        ├── grups_utils.py / grups_classifier.py                  │
│        ├── absence_utils.py                                      │
│        ├── fonts.py / text_cleanup.py                            │
│        ├── helpers.py / exception_chain.py                       │
│        └── unsaved_changes.py                                    │
└──────────────────────────────────────────────────────────────────┘
                         │
               ┌─────────┴─────────┐
               ▼                   ▼
     SQLite: auth.db        SQLite: gestor.db
     (usuaris globals)      (una per institució)
               │                   │
               └─────────┬─────────┘
                         │
                    ./data/
                    ├── auth.db
                    └── {institucio}/
                        ├── gestor.db
                        ├── *.xml  (horari FET)
                        └── exports/
```

## Flux típic d'una petició

```
Navegador → Caddy → Nginx (frontend) → Vue component
                  → FastAPI (backend) → route → core/lògica → SQLite
                                              → export/pdf → FileResponse
```

## Desplegament

```
.env.example          ← plantilla variables d'entorn
docker-compose.yml.example ← plantilla Docker Compose
Caddyfile.example     ← plantilla reverse proxy (HTTPS automàtic)
backend/Dockerfile    ← imatge backend
frontend/Dockerfile   ← imatge frontend (Nginx)
frontend/nginx.conf   ← config Nginx del frontend
scripts/setup-server.sh      ← configuració inicial del servidor
scripts/sync-server.sh.example ← sincronització codi al servidor
```
