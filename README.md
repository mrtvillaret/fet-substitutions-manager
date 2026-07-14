# Gestor de Guàrdies, Substitucions i Vigilàncies d'Exàmens

> Aplicació web **de codi obert** per organitzar les **guàrdies i substitucions**
> del professorat i les **vigilàncies d'exàmens** d'un centre educatiu: assignació
> automàtica i equitativa, informes en PDF i importació de l'horari des de
> [FET](https://lalescu.ro/liviu/fet/).

**Català** · [Castellano](README.es.md) · [English](README.en.md)

[![Llicència: AGPL v3](https://img.shields.io/badge/Llic%C3%A8ncia-AGPLv3-blue.svg)](LICENSE)
![Stack](https://img.shields.io/badge/FastAPI-Vue%203-009688)
![Self-hosted](https://img.shields.io/badge/self--hosted-Docker%20%2B%20Caddy-2496ED)

**Demo pública:** [gestor.alienamrt.org](https://gestor.alienamrt.org) — entra amb `user_demo` o `admin_demo` (per veure les funcions d'administració), contrasenya `demo1234`. _La demo es reinicia cada dia._

<!--
  Paraules clau (per a la descoberta a cercadors):
  gestió de guàrdies · substitucions del professorat · vigilàncies d'exàmens ·
  cobertura d'absències · guardias y sustituciones · reparto de guardias ·
  teacher cover / substitute scheduling · exam invigilation · cover supervision.
-->

Si busques un **programa de guàrdies escolars**, un **gestor de substitucions de
professorat** o una eina per **repartir vigilàncies d'exàmens** de manera justa,
aquest projecte cobreix tot el flux en una sola aplicació, autoallotjable i gratuïta.

---

## Captures de pantalla

| Substitucions diàries | Vigilàncies i grups | Planificador d'exàmens |
|---|---|---|
| ![Vista de substitucions](docs/img/substitucions.png) | ![Vista de vigilàncies](docs/img/vigilancies.png) | ![Planificador d'exàmens](docs/img/planificador.png) |

> _Captures fetes amb la institució d'exemple (`Prof 1`, `Prof 2`…); cap dada real._

---

## Funcionalitats

- **Guàrdies i substitucions diàries** amb assignació automàtica de substituts
- **Vigilàncies d'exàmens** i gestió de grups sense classe
- **Repartiment equitatiu** de tasques segons càrrega i restriccions configurables
- **Exportació a PDF** (substitucions, vigilàncies, intervals, informes de direcció)
- **Planificador d'exàmens** amb optimització automàtica (3 motors de generació)
- **Importació d'horari des de FET** (XML de _Free Timetabling Software_)
- **Multi-institució**: una base de dades per centre, autenticació global
- **Rols**: `super_admin`, `admin`, `user`
- **Multilingüe**: català, castellà i anglès

## Arquitectura

**Stack:** FastAPI + Vue 3 + PrimeVue · SQLite · Docker + Caddy

### Topologia (runtime)

```
Caddy (reverse proxy + HTTPS)
  ├── /api/*  →  backend:8000  (FastAPI)
  └── /*      →  frontend:80   (Vue 3 + Nginx)

data/
  ├── auth.db          # Usuaris globals
  └── {institucio}/
      ├── gestor.db    # Dades del centre
      ├── *.xml        # Horari FET del centre
      └── exports/     # PDFs generats
```

### Backend (FastAPI)

- `main.py` — punt d'entrada, registra 15 routers a `/api/*`
- `routes/` — endpoints per àrea funcional (substitucions, vigilàncies,
  scheduler, informes, PDFs, auth, files, settings...)
- `core/` — lògica de negoci (parseig d'horari XML, assignació automàtica
  de substituts i vigilàncies, gestió d'absències i baixes)
- `scheduler_engine/` — motor de planificació d'exàmens amb 3 generadors
  (v2-intents, v2-backtrack, v3-SA Simulated Annealing) i model de
  restriccions configurable
- `export/` — exportadors PDF (substitucions, vigilàncies, intervals,
  informes de direcció i professorat)
- `repositories.py` + `models.py` — accés a dades SQLAlchemy
- `auth_utils.py` — autenticació JWT amb cookie httpOnly

### Frontend (Vue 3)

- Sense Vue Router: navegació per pestanyes amb PrimeVue TabView
- 4 vistes principals: `SubstitucionsView`, `VigilanciesView`, `GrupsView`,
  `SchedulerView` (planificador d'exàmens)
- Composables a `views/scheduler/use*.js` per a la lògica de cada subàrea
  del planificador (API, resultats, restriccions, slots, incidències)
- i18n amb `vue-i18n`: traduccions a `locales/{ca,es,en}.json`
- Pinia per a estat compartit (preparada però amb poc ús actual)

Per al mapa de dependències complet veure [ARQUITECTURA.md](ARQUITECTURA.md).

---

## Prova ràpida en local

Per provar l'aplicació amb les dades d'exemple incloses, sense Docker ni domini.

**Requisits:** Python 3.10+ i Node.js 18+

### 1. Clonar

```bash
git clone https://github.com/mrtvillaret/fet-substitutions-manager.git
cd fet-substitutions-manager
```

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install -r requirements.txt

cp .env.example .env
# Edita .env: posa rutes absolutes a DATA_DIR i AUTH_DB_PATH apuntant a
# {ruta del projecte}/data i {ruta del projecte}/data/auth.db

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

El backend crea automàticament les BDs (`auth.db` i `data/{APP_INSTITUCIO}/gestor.db`)
al primer arrencat, i un super_admin segons `ADMIN_USERNAME`/`ADMIN_PASSWORD` del `.env`.

API disponible a `http://localhost:8000` · Documentació a `http://localhost:8000/docs`.

### 3. Frontend

En una altra terminal:

```bash
cd frontend
npm install
npm run dev
```

Obre `http://localhost:5173` i entra amb les credencials `super_admin` definides
al `.env` del backend (per defecte `admin123`). El frontend en dev apunta al backend
mitjançant el proxy de Vite.

### 4. Carregar les dades d'exemple

Un cop dins, ves a **Configuració > Importar XML** i puja `data/exemple/teachers.xml`.
Aquest XML és la plantilla "Spain / 2-secondary-school" del programari FET amb noms
genèrics (`Prof 1`, `Prof 2`...).

---

## Docker local (sense domini)

Si vols provar-ho amb Docker sense haver de configurar un domini ni HTTPS, hi ha un
`docker-compose.local.yml.example` que aixeca només backend + frontend (sense Caddy)
i serveix l'app a `http://localhost:8080`.

```bash
cp .env.example .env
cp docker-compose.local.yml.example docker-compose.local.yml
# Edita .env: posa COOKIE_SECURE=false (cal per HTTP plain) i una ADMIN_PASSWORD

docker compose -f docker-compose.local.yml up --build -d
```

Obre `http://localhost:8080`.

> ⚠️ Aquest mode no té HTTPS; només per a desenvolupament local. **No usar en
> producció**, els tokens viatgen en clar.

---

## Desplegar en producció

Recomanat amb Docker + Caddy (HTTPS automàtic). Et caldrà:

- Un servidor amb Docker i Docker Compose
- Un domini apuntant al servidor

### 1. Clonar i configurar

```bash
git clone https://github.com/mrtvillaret/fet-substitutions-manager.git
cd fet-substitutions-manager

cp .env.example .env
cp Caddyfile.example Caddyfile
cp docker-compose.yml.example docker-compose.yml
```

Edita el `.env`:

```env
SECRET_KEY=        # genera amb: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
APP_INSTITUCIO=nom_del_centre      # slug sense espais/accents
ADMIN_INSTITUCIO=nom_del_centre    # idèntic a APP_INSTITUCIO
ADMIN_PASSWORD=una-contrasenya-segura
```

Edita el `Caddyfile` i substitueix `el-teu-domini.exemple.com` pel teu domini real
(amb DNS apuntant ja al servidor).

### 2. Arrencar

```bash
docker compose up --build -d
```

Caddy obté el certificat TLS automàticament. L'aplicació estarà a
`https://{el-teu-domini}`.

### 3. Primer accés

- Entra com a `super_admin` amb la contrasenya definida a `ADMIN_PASSWORD`
- **Canvia la contrasenya** immediatament des de Configuració > Usuaris
- Puja l'XML del teu centre (generat per [FET](https://lalescu.ro/liviu/fet/))
  des de Configuració > Importar XML

### Actualitzacions

```bash
cd /ruta/al/projecte
git pull
docker compose up --build -d
```

---

## Estructura del projecte

```
fet-substitutions-manager/
├── backend/
│   ├── main.py                # FastAPI app + startup
│   ├── routes/                # Endpoints: substitucions, vigilancies, scheduler...
│   ├── core/                  # Lògica de negoci (horari, alliberats, substitucions)
│   ├── scheduler_engine/      # Motor de planificació d'exàmens
│   ├── config/                # Configuració, constants, settings
│   ├── repositories/          # Accés a dades (SQLAlchemy)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── views/             # SubstitucionsView, VigilanciesView, SchedulerView...
│   │   ├── components/        # Dialogs, navbar, etc.
│   │   └── locales/           # Traduccions ca/es/en
│   ├── Dockerfile
│   └── package.json
├── data/
│   └── exemple/
│       └── teachers.xml       # XML d'exemple (FET Spain secondary school)
├── scripts/
│   └── sync-server.sh.example # Script de sincronització al servidor
├── docker-compose.yml.example # Plantilla Docker Compose (copia a docker-compose.yml)
├── Caddyfile.example          # Plantilla Caddy (copia a Caddyfile)
└── .env.example               # Plantilla variables d'entorn (copia a .env)
```

---

## Dades d'exemple

El directori `data/exemple/` inclou un `teachers.xml` basat en l'exemple oficial
**"Spain / 2-secondary-school"** de [FET - Free Timetabling Software](https://lalescu.ro/liviu/fet/)
(Liviu Lalescu, [AGPL v3](https://www.gnu.org/licenses/agpl-3.0.html)).
Els noms de professors han estat substituïts per identificadors genèrics (`Prof 1`, `Prof 2`...).

---

## Backups

Totes les dades es troben a la carpeta `./data/`. Fes còpies periòdiques d'aquesta carpeta amb l'eina que prefereixis (cron + rsync, rclone a un núvol, etc.).

```bash
# Exemple mínim amb rsync
rsync -a /opt/gestor/data/ /backup/gestor-data/
```

---

## Llicència

Publicat sota la [GNU Affero General Public License v3.0](LICENSE).

Copyright (C) 2026 Martí Villaret Ausellé.
