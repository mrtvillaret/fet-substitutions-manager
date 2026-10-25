"""
Punt d'entrada del backend del Gestor de Substitucions: crea l'aplicació,
registra els gestors d'errors, els middlewares i tots els routers. Mapa del
codi: ARQUITECTURA.md.
"""

# Carregar variables d'entorn ABANS de qualsevol altre import
from dotenv import load_dotenv

load_dotenv()

import logging
import os
import time
from datetime import datetime

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from absencia_coberta.router import router as absencia_coberta_router
from auth.dependencies import get_current_user, require_admin
from auth.router import router as auth_router
from auth.security import decode_access_token, registra_renovacio_sessio
from auth.services import crea_usuaris_inicials
from config.auth import COOKIE_NAME, IS_DEVELOPMENT
from database import create_auth_tables
from errors_servidor import registra_gestors_errors
from helpers import MissingXmlError
from prioritats.router import router as prioritats_router
from rate_limit import limit_superat, limiter
from routes import (
    config_examens,
    cursos,
    dades,
    disponibles,
    estadistiques,
    files,
    general,
    grups,
    grups_amagats,
    horari,
    informes,
    pdf,
    scheduler,
    settings,
    substitucions,
)
from usuaris.router import router as usuaris_router
from vigilancies.router import router as vigilancies_router

log = logging.getLogger(__name__)
access_logger = logging.getLogger("uvicorn.error")
access_logger.setLevel(logging.INFO)

# Crear taules si no existeixen
create_auth_tables()
crea_usuaris_inicials()

# Les taules de dades (exam_*, etc.) es creen automàticament
# dins de get_data_db_session() la primera vegada que s'usa


# Carregar prioritats des de la BD (per web, no usem JSON)
def _inicialitzar_prioritats():
    """Carrega prioritats des de la BD en iniciar el backend"""
    from config.settings import config
    from database import get_data_db_session
    from prioritats.services import carrega_prioritats

    try:
        institucio = os.getenv("APP_INSTITUCIO") or config.global_data.get("institucio") or "exemple"
        with get_data_db_session(institucio) as db:
            carrega_prioritats(db)
    except Exception as e:
        log.warning(f"⚠️  No s'han pogut carregar prioritats des de BD: {e}")
        log.warning("   Es faran servir les constants del JSON per defecte")


_inicialitzar_prioritats()

# Fora de desenvolupament no es publica ni la documentació interactiva ni
# l'esquema OpenAPI: donen el mapa complet de l'API a qui no ha entrat.
app = FastAPI(
    title="Gestor Substitucions API",
    description="API REST per gestionar substitucions i vigilàncies",
    version="1.0.0",
    docs_url="/docs" if IS_DEVELOPMENT else None,
    redoc_url="/redoc" if IS_DEVELOPMENT else None,
    openapi_url="/openapi.json" if IS_DEVELOPMENT else None,
)


# Errors del domini → 4xx; errors interns → només una referència (errors_servidor.py)
registra_gestors_errors(app)


@app.exception_handler(MissingXmlError)
async def missing_xml_exception_handler(request: Request, exc: MissingXmlError):
    return JSONResponse(
        status_code=400, content={"detail": str(exc), "xml_missing": True, "institucio": exc.institucio}
    )


registra_renovacio_sessio(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_request(request, duration_ms, 500)
        raise
    duration_ms = int((time.perf_counter() - start) * 1000)
    _log_request(request, duration_ms, response.status_code)
    return response


def _log_request(request: Request, duration_ms: int, status_code: int) -> None:
    username = "-"
    role = "-"
    instit = "-"
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            payload = decode_access_token(token)
            username = payload.get("sub") or "-"
            role = payload.get("role") or "-"
            instit = payload.get("institucio") or "-"
        except Exception:
            pass

    path = request.url.path
    query = request.url.query
    full_path = f"{path}?{query}" if query else path
    ip = request.client.host if request.client else "-"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    access_logger.info(
        f"{timestamp} | {username} ({role}@{instit}) | {ip} | {request.method} {full_path} | {status_code} | {duration_ms}ms"
    )


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, limit_superat)
app.add_middleware(SlowAPIMiddleware)

# CORS: només cal en desenvolupament, quan el frontend de Vite (localhost:5173)
# crida el backend en un altre port. En producció el frontend i l'API són al
# mateix domini, i cap altre origen ha de poder fer crides amb la sessió.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"] if IS_DEVELOPMENT else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Registre de routers modularitzats =====
app.include_router(auth_router)
app.include_router(config_examens.router, dependencies=[Depends(require_admin)])
app.include_router(grups.router, dependencies=[Depends(get_current_user)])
app.include_router(grups_amagats.router, dependencies=[Depends(require_admin)])
app.include_router(pdf.router, dependencies=[Depends(get_current_user)])
app.include_router(vigilancies_router, dependencies=[Depends(get_current_user)])
app.include_router(substitucions.router, dependencies=[Depends(get_current_user)])
app.include_router(settings.router, dependencies=[Depends(require_admin)])
app.include_router(estadistiques.router, dependencies=[Depends(require_admin)])
app.include_router(prioritats_router, dependencies=[Depends(require_admin)])
app.include_router(absencia_coberta_router, dependencies=[Depends(require_admin)])
app.include_router(horari.router, dependencies=[Depends(get_current_user)])
app.include_router(files.router, dependencies=[Depends(require_admin)])
app.include_router(usuaris_router, dependencies=[Depends(get_current_user)])
app.include_router(disponibles.router, dependencies=[Depends(get_current_user)])
app.include_router(scheduler.router, dependencies=[Depends(require_admin)])
app.include_router(informes.router, dependencies=[Depends(require_admin)])
app.include_router(cursos.router, dependencies=[Depends(get_current_user)])
app.include_router(dades.router, dependencies=[Depends(require_admin)])
app.include_router(general.router, dependencies=[Depends(get_current_user)])


# ===== Endpoints generals (no modularitzats) =====


@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "Gestor Substitucions API", "docs": "/docs"}


@app.get("/api/health")
async def health():
    """Health check per l'API"""
    return {"status": "ok"}


# ===== Punt d'entrada per executar amb uvicorn =====
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
