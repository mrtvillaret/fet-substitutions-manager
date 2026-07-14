# Gestor de Guardias, Sustituciones y Vigilancias de Exámenes

> Aplicación web **de código abierto** para organizar las **guardias y sustituciones**
> del profesorado y las **vigilancias de exámenes** de un centro educativo: asignación
> automática y equitativa, informes en PDF e importación del horario desde
> [FET](https://lalescu.ro/liviu/fet/).

[🇨🇦 Català](README.md) · **🇪🇸 Castellano** · [🇬🇧 English](README.en.md)

[![Licencia: AGPL v3](https://img.shields.io/badge/Licencia-AGPLv3-blue.svg)](LICENSE)
![Stack](https://img.shields.io/badge/FastAPI-Vue%203-009688)
![Self-hosted](https://img.shields.io/badge/self--hosted-Docker%20%2B%20Caddy-2496ED)

**Demo pública:** [gestor.alienamrt.org](https://gestor.alienamrt.org) — entra con `user_demo` o `admin_demo` (para ver las funciones de administración), contraseña `demo1234`. _La demo se reinicia cada día._

<!--
  Palabras clave (para descubrimiento en buscadores):
  gestión de guardias · sustituciones del profesorado · reparto de guardias ·
  vigilancias de exámenes · cobertura de ausencias · guardias docentes ·
  teacher cover / substitute scheduling · exam invigilation · cover supervision.
-->

Si buscas un **programa de guardias escolares**, un **gestor de sustituciones del
profesorado** o una herramienta para **repartir vigilancias de exámenes** de forma
justa, este proyecto cubre todo el flujo en una sola aplicación, autoalojable y gratuita.

---

## Capturas de pantalla

| Sustituciones diarias | Vigilancias y grupos | Planificador de exámenes |
|---|---|---|
| ![Vista de sustituciones](docs/img/substitucions.png) | ![Vista de vigilancias](docs/img/vigilancies.png) | ![Planificador de exámenes](docs/img/planificador.png) |

> _Capturas hechas con la institución de ejemplo (`Prof 1`, `Prof 2`…); ningún dato real._

---

## Funcionalidades

- **Guardias y sustituciones diarias** con asignación automática de sustitutos
- **Vigilancias de exámenes** y gestión de grupos sin clase
- **Reparto equitativo** de tareas según carga y restricciones configurables
- **Exportación a PDF** (sustituciones, vigilancias, intervalos, informes de dirección)
- **Planificador de exámenes** con optimización automática (3 motores de generación)
- **Importación de horario desde FET** (XML de _Free Timetabling Software_)
- **Multi-institución**: una base de datos por centro, autenticación global
- **Roles**: `super_admin`, `admin`, `user`
- **Multilingüe**: catalán, castellano e inglés

## Arquitectura

**Stack:** FastAPI + Vue 3 + PrimeVue · SQLite · Docker + Caddy

```
Caddy (reverse proxy + HTTPS)
  ├── /api/*  →  backend:8000  (FastAPI)
  └── /*      →  frontend:80   (Vue 3 + Nginx)

data/
  ├── auth.db          # Usuarios globales
  └── {institucion}/
      ├── gestor.db    # Datos del centro
      ├── *.xml        # Horario FET del centro
      └── exports/     # PDFs generados
```

El backend (FastAPI) expone la API en `/api/*`, gestiona el parseo del horario XML,
la asignación automática de sustitutos y vigilantes, y la exportación a PDF. El
frontend (Vue 3 + PrimeVue) organiza la navegación por pestañas: sustituciones,
vigilancias, grupos y planificador de exámenes. El motor de planificación
(`scheduler_engine/`) incluye 3 generadores (intentos, backtracking y Simulated
Annealing) con un modelo de restricciones configurable.

Para el mapa de dependencias completo, ver [ARQUITECTURA.md](ARQUITECTURA.md)
(en catalán).

---

## Prueba rápida en local

Para probar la aplicación con los datos de ejemplo incluidos, sin Docker ni dominio.

**Requisitos:** Python 3.10+ y Node.js 18+

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
# Edita .env: pon rutas absolutas en DATA_DIR y AUTH_DB_PATH apuntando a
# {ruta del proyecto}/data y {ruta del proyecto}/data/auth.db

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

El backend crea automáticamente las BD (`auth.db` y `data/{APP_INSTITUCIO}/gestor.db`)
en el primer arranque, y un super_admin según `ADMIN_USERNAME`/`ADMIN_PASSWORD` del `.env`.

API disponible en `http://localhost:8000` · Documentación en `http://localhost:8000/docs`.

### 3. Frontend

En otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173` y entra con las credenciales `super_admin` definidas
en el `.env` del backend (por defecto `admin123`). El frontend en dev apunta al
backend mediante el proxy de Vite.

### 4. Cargar los datos de ejemplo

Una vez dentro, ve a **Configuración > Importar XML** y sube `data/exemple/teachers.xml`.
Este XML es la plantilla "Spain / 2-secondary-school" del programa FET con nombres
genéricos (`Prof 1`, `Prof 2`...).

---

## Docker local (sin dominio)

Si quieres probarlo con Docker sin configurar dominio ni HTTPS, hay un
`docker-compose.local.yml.example` que levanta solo backend + frontend (sin Caddy)
y sirve la app en `http://localhost:8080`.

```bash
cp .env.example .env
cp docker-compose.local.yml.example docker-compose.local.yml
# Edita .env: pon COOKIE_SECURE=false (necesario para HTTP plano) y una ADMIN_PASSWORD

docker compose -f docker-compose.local.yml up --build -d
```

Abre `http://localhost:8080`.

> ⚠️ Este modo no tiene HTTPS; solo para desarrollo local. **No usar en
> producción**, los tokens viajan en claro.

---

## Desplegar en producción

Recomendado con Docker + Caddy (HTTPS automático). Necesitarás:

- Un servidor con Docker y Docker Compose
- Un dominio apuntando al servidor

### 1. Clonar y configurar

```bash
git clone https://github.com/mrtvillaret/fet-substitutions-manager.git
cd fet-substitutions-manager

cp .env.example .env
cp Caddyfile.example Caddyfile
cp docker-compose.yml.example docker-compose.yml
```

Edita el `.env`:

```env
SECRET_KEY=        # genera con: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
APP_INSTITUCIO=nombre_del_centro    # slug sin espacios/acentos
ADMIN_INSTITUCIO=nombre_del_centro  # idéntico a APP_INSTITUCIO
ADMIN_PASSWORD=una-contrasena-segura
```

Edita el `Caddyfile` y sustituye `el-teu-domini.exemple.com` por tu dominio real
(con DNS apuntando ya al servidor).

### 2. Arrancar

```bash
docker compose up --build -d
```

Caddy obtiene el certificado TLS automáticamente. La aplicación estará en
`https://{tu-dominio}`.

### 3. Primer acceso

- Entra como `super_admin` con la contraseña definida en `ADMIN_PASSWORD`
- **Cambia la contraseña** de inmediato desde Configuración > Usuarios
- Sube el XML de tu centro (generado por [FET](https://lalescu.ro/liviu/fet/))
  desde Configuración > Importar XML

### Actualizaciones

```bash
cd /ruta/al/proyecto
git pull
docker compose up --build -d
```

---

## Datos de ejemplo

El directorio `data/exemple/` incluye un `teachers.xml` basado en el ejemplo oficial
**"Spain / 2-secondary-school"** de [FET - Free Timetabling Software](https://lalescu.ro/liviu/fet/)
(Liviu Lalescu, [AGPL v3](https://www.gnu.org/licenses/agpl-3.0.html)).
Los nombres de profesores se han sustituido por identificadores genéricos (`Prof 1`, `Prof 2`...).

---

## Copias de seguridad

Todos los datos están en la carpeta `./data/`. Haz copias periódicas de esta carpeta
con la herramienta que prefieras (cron + rsync, rclone a la nube, etc.).

```bash
# Ejemplo mínimo con rsync
rsync -a /opt/gestor/data/ /backup/gestor-data/
```

---

## Licencia

Publicado bajo la [GNU Affero General Public License v3.0](LICENSE).

Copyright (C) 2026 Martí Villaret Ausellé.
