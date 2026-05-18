# Gestor de Substitucions

Aplicació web per gestionar substitucions i vigilàncies d'un centre educatiu.

**Stack:** FastAPI + Vue 3 + PrimeVue · SQLite · Docker + Caddy

## Funcionalitats

- Gestió de substitucions diàries amb assignació de substituts
- Vigilàncies i grups sense classe
- Exportació PDF (substitucions, vigilàncies, intervals)
- Planificador d'exàmens amb optimització automàtica
- Multi-institució: una BD per centre, auth global
- Rols: `super_admin`, `admin`, `user`
- i18n: català, castellà, anglès

## Arquitectura

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

## Posada en marxa amb Docker (recomanat)

### Prerequisits

- Docker i Docker Compose
- Un domini apuntant al servidor (per HTTPS automàtic via Caddy)

### 1. Clonar i configurar

```bash
git clone https://github.com/mrtvillaret/fet-substitutions-manager.git
cd fet-substitutions-manager

# Copiar fitxers de configuració
cp .env.example .env
cp Caddyfile.example Caddyfile
cp docker-compose.yml.example docker-compose.yml
```

Editar `.env` com a mínim:

```env
SECRET_KEY=    # genera amb: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
APP_INSTITUCIO=nom_del_centre      # slug del centre (sense espais ni accents)
ADMIN_INSTITUCIO=nom_del_centre    # ha de ser igual que APP_INSTITUCIO
ADMIN_PASSWORD=una-contrasenya-segura
```

Editar `Caddyfile` i substituir `el-teu-domini.exemple.com` pel teu domini.

### 2. Crear la carpeta de dades

```bash
mkdir -p data
```

### 3. Arrencar

```bash
docker compose up --build -d
```

Caddy obté el certificat TLS automàticament. L'app estarà disponible a `https://el-teu-domini.exemple.com`.

### 4. Primer accés

En el primer arrencada es crea l'usuari `super_admin` amb la contrasenya definida a `ADMIN_PASSWORD` al `.env`. **Canvia-la immediatament** des de Configuració > Usuaris un cop dins l'app.

Per importar les dades del centre, entra com a `super_admin`, crea la institució i importa el fitxer `teachers.xml` generat per [FET](https://lalescu.ro/liviu/fet/).

---

## Desenvolupament local (sense Docker)

### Prerequisits

- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows

pip install -r requirements.txt

# Configuració local (diferent del .env arrel que usa Docker)
cp .env.example .env           # edita DATA_DIR i AUTH_DB_PATH amb rutes absolutes locals

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend disponible a: http://localhost:8000
Documentació API (dev): http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend disponible a: http://localhost:5173

> El frontend en dev apunta al backend a `localhost:8000` via proxy Vite.

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
(Liviu Lalescu, [GPL v2+](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)).
Els noms de professors han estat substituïts per identificadors genèrics (`Prof 1`, `Prof 2`...).

---

## Backups

Totes les dades es troben a la carpeta `./data/`. Fes còpies periòdiques d'aquesta carpeta amb l'eina que prefereixis (cron + rsync, rclone a un núvol, etc.).

```bash
# Exemple mínim amb rsync
rsync -a /opt/gestor/data/ /backup/gestor-data/
```

---

## Actualitzacions al servidor

```bash
# Sincronitzar codi (adaptar el script d'exemple)
cp scripts/sync-server.sh.example scripts/sync-server.sh
# editar SERVER_IP i SERVER_PATH
bash scripts/sync-server.sh

# Reconstruir i reiniciar
ssh root@SERVER_IP 'cd /opt/gestor && docker compose up --build -d'
```

---

## Llicència

Publicat sota la [GNU General Public License v3.0](LICENSE).

Copyright (C) 2026 Martí Villaret Ausellé.
