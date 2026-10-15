# Arquitectura

## Mapa de dependències

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vue 3)                          │
│                                                                  │
│  main.js → App.vue (i18n, PrimeVue, Pinia) — navegació per tabs  │
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
│                    StepRestrictions, StepAnalysis, StepResults   │
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
│  ├── SlotDropZone.vue                                            │
│  └── config/: pestanyes de Configuració (Baixes, Prioritats,     │
│               Grups, Cursos, Usuaris, Gestió de dades...)        │
│                                                                  │
│  substitutsTrets.js ← avís dels substituts trets per un canvi    │
│  locales/: ca.json, es.json, en.json, it.json                    │
│  i18n.js ← configuració vue-i18n                                 │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP (Vite proxy dev / Nginx prod)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                             │
│                                                                  │
│  main.py  ← punt d'entrada, registra tots els routers            │
│                                                                  │
│  CAPA DE ROUTES (/api/*)                                         │
│  ├── auth.py             → login, cookie JWT                     │
│  ├── substitucions.py    → absències, substitucions, reassignar  │
│  ├── vigilancies.py      → CRUD vigilàncies                      │
│  ├── disponibles.py      → professors disponibles/forat          │
│  ├── prioritats.py       → categories, prioritats, baixes        │
│  ├── estadistiques.py    → recomptes i estadístiques             │
│  ├── informes.py         → PDF informe direcció/professors       │
│  ├── pdf.py              → PDF substitucions/vigilàncies/int.    │
│  ├── horari.py           → consultes horari XML                  │
│  ├── grups.py            → grups i professors alliberats per dia │
│  │                         i per període                         │
│  ├── grups_amagats.py    → grups que el centre no mostra         │
│  ├── files.py            → upload XML horari                     │
│  ├── cursos.py           → cursos acadèmics                      │
│  ├── dades.py            → purga de dades antigues (RGPD)        │
│  ├── users.py            → gestió usuaris                        │
│  ├── settings.py         → configuració del centre               │
│  ├── config_examens.py   → config assignatures/aules examens     │
│  └── scheduler.py        → planificador exàmens (orquestra)      │
│        ├── scheduler_service.py    ← CRUD config scheduler       │
│        ├── scheduler_helpers.py    ← helpers intermedis          │
│        └── scheduler_analysis_helpers.py                         │
│                                                                  │
│  SERVEIS (serveis/): la lògica que criden les rutes              │
│  ├── dia_escolar.py     ← DiaEscolar: l'estat d'un dia llegit un │
│  │                        cop; motius_substitut i                │
│  │                        substituts_no_valids (regla única)     │
│  ├── generacio.py       ← «Genera pendents» / «Regenera tot»     │
│  ├── absencies.py       ← marcar o treure absències d'un dia     │
│  ├── cobertures.py      ← files que cobreixen la classe d'un     │
│  │                        vigilant i de vigilant absent          │
│  ├── validacions_pdf.py ← conflictes i avisos abans del PDF      │
│  ├── prioritat.py       ← hi ha un substitut de més prioritat?   │
│  ├── baixes.py          ← què es treu en desar una baixa         │
│  └── vigilancia_absent.py ← files de vigilant absent             │
│                                                                  │
│  CAPA DE LÒGICA DE NEGOCI                                        │
│  ├── horari_web.py                ← GestorHorariWeb (parser XML  │
│  │                                  FET + abreviatures BD;       │
│  │                                  singleton via helpers.       │
│  │                                  get_horari())                │
│  ├── core/substitucions.py        ← motor d'assignació automàtica│
│  ├── core/alliberats.py           ← grups, professors i          │
│  │                                  activitats alliberats;       │
│  │                                  sense_classe (qui no té      │
│  │                                  classe a una hora)           │
│  ├── core/absencies.py            ← filtre absències reals       │
│  ├── core/baixes.py               ← professors_de_baixa          │
│  ├── core/vigilancia_core.py      ← lògica vigilàncies           │
│  └── core/vigilancia_assignacio.py                               │
│                                                                  │
│  SCHEDULER ENGINE (planificador exàmens)                         │
│  ├── factory.py                   ← selecciona motor             │
│  ├── defaults.py                  ← valors per defecte           │
│  ├── validacio.py                 ← genera logs d'incidències    │
│  ├── estadistiques.py             ← estadístiques del pla        │
│  ├── domain/models.py             ← models de domini             │
│  ├── generators/base.py           ← classe base motors           │
│  ├── generators/v2_intents.py                                    │
│  ├── generators/v2_backtrack.py                                  │
│  ├── generators/v3_sa.py          ← Simulated Annealing          │
│  └── core/: context, constraints, scoring, availability,         │
│             durada, date_mapping, diagnostic,                    │
│             normalitzacio, restriction_engine                    │
│                                                                  │
│  CAPA D'ACCÉS A DADES                                            │
│  ├── database.py          ← sessions SQLAlchemy (auth + dades)   │
│  ├── repositories.py      ← CRUD genèric (UserRepo, ConfigRepo…) │
│  ├── models.py            ← models SQLAlchemy (taules principals)│
│  └── schemas.py           ← models Pydantic (request/response)   │
│                                                                  │
│  EXPORTACIÓ PDF                                                  │
│  ├── export/pdf_styles.py         ← estils comuns                │
│  ├── export/pdf_images.py         ← imatges embegudes            │
│  └── export/pdf/                                                 │
│        ├── engine.py              ← motor principal              │
│        ├── informe_direccio.py                                   │
│        └── informe_professors.py                                 │
│                                                                  │
│  INFRAESTRUCTURA                                                 │
│  ├── config/settings.py   ← Config global (institucions)         │
│  ├── config/auth.py       ← JWT, usuaris per defecte             │
│  ├── config/constants.py  ← PRIORITATS, NO_SUBST, baixes: vistes │
│  │                           de les dades de cada centre         │
│  ├── config/pdf.json      ← perfils visuals PDF                  │
│  ├── auth_utils.py        ← decoradors autenticació              │
│  ├── dependencies.py      ← Depends FastAPI                      │
│  ├── helpers.py           ← utils generals                       │
│  ├── i18n_setup.py        ← traduccions backend (PDF)            │
│  ├── rate_limit.py        ← limitació de peticions               │
│  ├── errors_servidor.py   ← errors no previstos: es registren    │
│  │                           amb una referència; l'usuari només  │
│  │                           rep la referència                   │
│  └── utils/                                                      │
│        ├── hores.py / date_context.py                            │
│        ├── grups_utils.py                                        │
│        └── exception_chain.py                                    │
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

## Regles de funcionament

Les decisions de negoci viuen en un sol lloc i les fan servir totes les parts
(generació, assignació a mà, validacions del PDF i «Reassigna»):

- **Qui té classe a una hora** — `core/alliberats.sense_classe`: un professor
  queda lliure si el grup de la seva classe és, exactament, un dels marcats
  sense classe aquella hora, o si ell mateix està alliberat (directament o per
  una activitat alliberada). Una agrupació («ESO1AB», «A,B») només queda lliure
  si es marca l'agrupació. Per a substitucions, que el grup tingui un examen no
  allibera el professor; per a vigilàncies, sí.
- **Quan un substitut ja no pot ser-ho** — `DiaEscolar.motius_substitut`: vigila
  un examen a aquella hora, està de baixa, és absent o hi té classe.
- **Qui assigna substituts** — només els botons «Genera pendents» (omple les
  files pendents i deixa tal com estan les que ja tenen substitut), «Regenera
  tot» i «Reassigna» (validació del PDF). Els canvis del dia (grups i professors
  alliberats, estats per període, absències, baixes) no n'assignen cap: treuen
  els que ja no poden ser-ho i la fila queda pendent, amb un avís.
- **Baixes** — un professor de baixa ni substitueix ni és substituït. En desar
  la baixa, d'avui endavant, se li esborren les absències i se'l treu de
  vigilant i de substitut. Els dies passats no es toquen.

## Generar les substitucions d'un dia

```
routes/substitucions.py  POST /api/substitucions/{data}/generar
  └── serveis/generacio.genera_substitucions_dia
        ├── llegeix_estat        absències, alliberats i vigilants de la BD
        ├── core/substitucions   GestorSubstitucions.assignar_substitucions
        ├── _esborra             tot (menys vigilant absent) o només pendents
        ├── _desa_files_motor    cobertures de vigilància, files noves
        ├── _desa_hores_sense_substitucio
        └── _resum               assignades i pendents
```

## Tests

`backend/tests/`: més de 500 tests amb pytest, sobre institucions temporals amb
l'horari d'exemple (`data/exemple/teachers.xml`). La majoria passen per l'API
(com la pantalla) i comproven el que queda desat a la BD; els del motor i del
planificador fan servir dades simulades.

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/
```
