# Arquitectura

Què és cada fila de substitució i què compta cada pantalla, PDF i informe:
[`FUNCIONAMENT.md`](FUNCIONAMENT.md).

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
│  └── config/: pestanyes de Configuració (Absències cobertes,     │
│               Prioritats, Grups, Cursos, Usuaris, Gestió de      │
│               dades...)                                          │
│                                                                  │
│  substitutsTrets.js ← avís dels substituts trets per un canvi    │
│  dataTreball.js ← data de treball (data del calendari), store    │
│  dates.js       ← dataIso / dataAmbAny (mai toISOString)         │
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
│  MÒDULS (estructura nova; vegeu «Estructura d'un mòdul»)         │
│  ├── auth/               → entrar, sortir, perfil propi, cookie  │
│  │                         JWT i Depends de l'usuari i del rol   │
│  ├── usuaris/            → gestió d'usuaris (admin i superadmin) │
│  ├── prioritats/         → categories i pesos, «No substituir» i │
│  │                         la càrrega a memòria; de pas, les     │
│  │                         activitats alliberables               │
│  ├── absencia_coberta/   → absències cobertes (abans «baixes»):  │
│  │                         l'horari del dia ja no té l'absent    │
│  ├── vigilancies/        → vigilàncies: assignació per hora,     │
│  │                         ordre desat, ajuda del vigilant       │
│  ├── substitucions/      → absències, substitucions, encadenades,│
│  │                         generació (assignacio.py), regles del │
│  │                         dia (domain.py) i cobertures          │
│  └── pdf/                → PDF del dia, de vigilàncies, de       │
│                            disponibles i informes (/api/pdf/*,   │
│                            /api/informes/*); vegeu EXPORTACIÓ    │
│                                                                  │
│  CAPA DE ROUTES (/api/*) — estructura antiga, es va migrant      │
│  ├── disponibles.py      → professors disponibles/forat          │
│  ├── estadistiques.py    → recomptes i estadístiques             │
│  ├── horari.py           → consultes horari XML                  │
│  ├── grups.py            → grups i professors alliberats per dia │
│  │                         i per període                         │
│  ├── grups_amagats.py    → grups que el centre no mostra         │
│  ├── files.py            → upload XML horari                     │
│  ├── cursos.py           → cursos acadèmics                      │
│  ├── dades.py            → purga de dades antigues (RGPD)        │
│  ├── settings.py         → configuració del centre               │
│  ├── config_examens.py   → config assignatures/aules examens     │
│  ├── parametres.py       → DataISO: validació de les dates       │
│  └── scheduler.py        → planificador exàmens (orquestra)      │
│        ├── scheduler_config.py     ← ConfigPlanificador, durades │
│        ├── scheduler_planificacio.py ← prepara_planificacio      │
│        │                             (generar i analitzar)       │
│        ├── scheduler_cost.py       ← recàlcul del cost           │
│        ├── scheduler_service.py    ← CRUD config scheduler       │
│        ├── scheduler_helpers.py    ← helpers intermedis          │
│        └── scheduler_analysis_helpers.py                         │
│                                                                  │
│  SERVEIS (serveis/): la lògica que criden les rutes              │
│  ├── dia.py             ← Dia: una data d'un centre i el seu     │
│  │                        horari XML (versió vigent aquell dia)  │
│  └── publicacio_examens.py ← publicar l'horari d'exàmens         │
│                                                                  │
│  CAPA DE LÒGICA DE NEGOCI                                        │
│  ├── horari_web.py                ← GestorHorariWeb (parser XML  │
│  │                                  FET + abreviatures BD;       │
│  │                                  singleton via helpers.       │
│  │                                  get_horari())                │
│  ├── core/alliberats.py           ← grups, professors i          │
│  │                                  activitats alliberats;       │
│  │                                  sense_classe (qui no té      │
│  │                                  classe a una hora)           │
│  ├── core/absencies.py            ← filtre absències reals       │
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
│  └── pdf/ (mòdul)                 ← rutes, casos d'ús, dibuix    │
│        ├── router.py              ← rutes /api/pdf/*             │
│        ├── informes.py            ← rutes /api/informes/*        │
│        ├── generacio.py           ← dia, vigilàncies, interval   │
│        ├── disponibles.py         ← professors disponibles       │
│        ├── services.py            ← càlculs dels informes        │
│        ├── repositories.py        ← preferències, consultes      │
│        ├── domain.py              ← opcions, resultat, errors    │
│        ├── validacions.py         ← conflictes i avisos          │
│        ├── engine.py              ← motor principal              │
│        ├── taula.py               ← model de la taula del dia    │
│        ├── informe_direccio.py    ← dibuix informe direcció      │
│        └── informe_professors.py  ← dibuix informe professor     │
│                                                                  │
│  INFRAESTRUCTURA                                                 │
│  ├── config/settings.py   ← Config global (institucions)         │
│  ├── config/auth.py       ← JWT, usuaris per defecte             │
│  ├── config/constants.py  ← PRIORITATS, NO_SUBST, baixes: vistes │
│  │                           de les dades de cada centre         │
│  ├── config/pdf.json      ← perfils visuals PDF                  │
│  ├── dependencies.py      ← Depends FastAPI: get_db (la BD de la │
│  │                           institució de l'usuari) i el Dia    │
│  │                           (calendari / planificació / avui)   │
│  ├── helpers.py           ← utils generals                       │
│  ├── i18n_setup.py        ← traduccions backend (PDF)            │
│  ├── rate_limit.py        ← limitació de peticions               │
│  ├── errors_servidor.py   ← errors no previstos: es registren    │
│  │                           amb una referència; l'usuari només  │
│  │                           rep la referència                   │
│  ├── noms.py              ← la regla dels noms: nom_net, NomNet  │
│  ├── errors_domini.py     ← errors de les regles (NoTrobat,      │
│  │                           NoPermes, NoValid, Conflicte)       │
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
                                              → pdf/ → FileResponse
```

## Estructura d'un mòdul del backend

El backend es va reorganitzant per mòduls de domini. Cada mòdul és una carpeta
a `backend/` amb aquests fitxers (només els que necessita):

| Fitxer | Què hi va |
|---|---|
| `router.py` | Només HTTP: rutes, paràmetres, status, galetes i la crida al servei. Cap consulta ni regla. |
| `schemas.py` | Models Pydantic d'entrada i de sortida; cada ruta declara el seu `response_model`. |
| `services.py` | Les regles de negoci, sense res d'HTTP: reben la sessió i les dades, retornen objectes o llancen errors del domini. |
| `repositories.py` | Totes les consultes a la BD del mòdul (cap `db.query` fora d'aquí). |
| `domain.py` | Objectes del domini del mòdul, si en té (a `auth/`: `Rol` i `UsuariActual`, l'usuari immutable que reben les rutes). |
| `dependencies.py` | Els `Depends` propis del mòdul, si en té. |
| `security.py` | Només a `auth/`: contrasenyes, testimonis JWT i galeta. |

Noms: els fitxers que fan un paper estàndard, en anglès; el domini (funcions,
classes i regles), en català: `autentica`, `canvia_contrasenya`,
`comprova_no_protegit`.

**Errors.** Un servei que troba una regla incomplerta llança un error de
`errors_domini.py`, segons la mena: `NoTrobat` (404), `NoPermes` (403),
`NoValid` (400) o `Conflicte` (409). Tots són `ErrorDeDomini`, que no es
llança directament i porta el missatge per a l'usuari, un `codi` obligatori i
uns `params` opcionals per quan el frontend tradueixi els missatges.
`errors_domini.py` no sap res d'HTTP: la taula categoria → status
(`STATUS_PER_CATEGORIA`) i l'únic gestor són a `errors_servidor.py`
(`registra_gestors_errors`), que respon com sempre, `{"detail": "<missatge>"}`;
el codi i els paràmetres encara no hi surten. Els errors que són pròpiament d'HTTP (els 401 de sessió i de
credencials) continuen sent `HTTPException` a `dependencies.py` i al router.

```python
# services.py
def canvia_contrasenya(db, current_user, actual, nova) -> User:
    user = _usuari_propi(db, current_user)          # NoTrobat / NoPermes
    if not verify_password(actual, user.password_hash):
        raise NoValid("Contrasenya actual incorrecta", codi="contrasenya_actual_incorrecta")
    ...

# router.py
user = services.canvia_contrasenya(db, current_user, payload.current_password, payload.new_password)
set_auth_cookie(response, testimoni_de_sessio(user, current_user.institucio))
```

**Estructura antiga.** `routes/` (rutes amb consultes i lògica barrejades),
`serveis/` i `core/` són l'organització anterior. Es buiden mòdul a mòdul cap a
l'estructura nova, amb un arnès de caracterització que comprova que les
respostes no canvien.

Mòduls migrats: `auth/` (entrar, sessió, perfil propi), `usuaris/` (gestió
d'usuaris de l'admin i el superadmin) i `prioritats/` (categories i pesos de
prioritat, «No substituir» i la seva càrrega a memòria, `carrega_prioritats`;
les rutes de les activitats alliberables hi són de pas fins que es migri el
mòdul de grups) i `absencia_coberta/` (abans «baixes»: `/api/absencies-cobertes`,
i el punt únic que treu l'absent de l'horari de cada data), `vigilancies/` i
`substitucions/` (absències, substitucions, encadenades i cobertures; el motor
d'assignació és a `assignacio.py`, les regles del dia —`DiaEscolar`— a
`domain.py`, i les consultes i la presentació del llistat a `_consultes.py`) i
`pdf/` (`/api/pdf/*` i `/api/informes/*`: rutes primes a `router.py` i
`informes.py`; els PDF del dia, de vigilàncies i de l'interval a
`generacio.py` i el de disponibles a `disponibles.py`; els càlculs dels
informes a `services.py` i les consultes a `repositories.py`; els
renderitzadors amb ReportLab, a `engine.py`, `informe_direccio.py` i
`informe_professors.py`).

### Transaccions de substitucions

Cada acció de l'usuari que escriu substitucions és una sola transacció. Els
mètodes de mutació de `substitucions/repositories.py` fan `flush()` per obtenir
identificadors i detectar errors, però no fan `commit()`. El límit és al servei
que orquestra l'operació: generar, desar absències, assignar a mà i reassignar
confirmen només després d'actualitzar encadenades i cobertures.

Els consumidors externs conserven el mateix contracte: els serveis de
`vigilancies/` i `absencia_coberta/`, les rutes encara no migrades de
`routes/grups.py` i la publicació de `routes/scheduler.py` reconcilien les
substitucions abans del seu únic `commit()`. Una excepció desfà tant el canvi
principal com els derivats; els errors interns arriben a la pantalla amb la
referència de `errors_servidor.py`.

«Reassigna» és l'única excepció deliberada: la reassignació bàsica forma part
de la transacció principal, però la millora opcional segons les prioritats
s'executa dins d'un savepoint (`db.begin_nested()`). Si aquesta millora falla,
se'n desfan tots els canvis parcials, es conserva la base coherent i es retorna
l'avís perquè l'usuari ho revisi.

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
- **Noms** — `noms.py`: un nom de professor, assignatura o aula és el text
  sense espais al principi ni al final, normalitzat en entrar (lectors de l'XML
  i API amb `NomNet`), amb tests guardians. El buit és vàlid; l'ordre és el de
  l'XML, que es desa tal com es puja. Les dades ja desades es migren amb
  `migracions/noms_nets.py` (fusiona només dins de la mateixa llista).
- **Usuaris** — `usuaris/services.py`: cap operació (desactivar, esborrar,
  treure el rol, canviar de centre) pot deixar un centre sense cap admin
  actiu, i ningú no es pot desactivar ni esborrar a si mateix. Els usuaris
  inicials només es creen en una instal·lació nova (`auth/services.py:
  crea_usuaris_inicials`); el superadmin es recupera amb
  `ADMIN_PASSWORD_RECUPERACIO`.
- **Absència coberta** (abans «baixa») — `absencia_coberta/`: l'absent té les
  classes cobertes a l'XML. Durant el període, l'horari de cada data ja no el
  té (`sense_absents_coberts`, cridat des de `helpers.get_horari`, per on passa
  `Dia`): ni substitueix, ni és substituït, ni vigila, ni surt com a
  disponible; ho vigila `tests/test_absencia_coberta_punt_unic.py`. En desar-la,
  d'avui endavant, se li esborren les absències i se'l treu de vigilant i de
  substitut (els dies passats no es toquen), i s'avisa si alguna classe seva
  no té cap altre professor a l'XML. El planificador no la té en compte; en
  publicar, el titular amb una absència coberta no vigila i se n'avisa.

- **Quin horari (XML) es fa servir** — cada versió de l'XML té una data
  d'inici i la de fi la calcula el backend (`XMLVersionRepository.encadena`).
  Substitucions, Vigilàncies, PDF i Configuració fan servir la data del
  calendari; el planificador, la primera data planificada (amb avís si l'horari
  canvia dins de les dates); la sincronització de professors actius, avui. Les
  rutes reben el `Dia` per dependència i no criden mai `get_horari` sense data
  (ho comprova `tests/test_horari_sempre_amb_data.py`).

## Generar les substitucions d'un dia

```
substitucions/router.py  POST /api/substitucions/{data}/generar
  └── substitucions/generacio.genera_substitucions_dia
        ├── llegeix_estat        absències, alliberats i vigilants de la BD
        ├── substitucions/assignacio   GestorSubstitucions.assignar_substitucions
        ├── _esborra             tot (menys vigilant absent) o només pendents
        ├── _desa_files_motor    cobertures de vigilància, files noves
        ├── _desa_hores_sense_substitucio
        └── _resum               assignades i pendents
```

## Tests

`backend/tests/`: més de 600 tests amb pytest, sobre institucions temporals amb
l'horari d'exemple (`data/exemple/teachers.xml`). La majoria passen per l'API
(com la pantalla) i comproven el que queda desat a la BD; els del motor i del
planificador fan servir dades simulades.

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/
```
