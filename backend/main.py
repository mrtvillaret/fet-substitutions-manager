"""
FastAPI Backend per Gestor de Substitucions
Versió modularitzada amb routes, schemas i helpers separats
"""
# IMPORTANT: Carregar variables d'entorn ABANS de qualsevol altre import
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
import logging
import os
import time
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# SQLAlchemy imports
from database import create_auth_tables
from auth_utils import ensure_default_users, get_current_user, require_admin
from rate_limit import limiter

# Imports de schemas i helpers
from schemas import ConfigResponse
from helpers import get_horari, MissingXmlError
from auth_utils import decode_access_token

access_logger = logging.getLogger("uvicorn.error")
access_logger.setLevel(logging.INFO)

# Crear taules si no existeixen
create_auth_tables()
ensure_default_users()

# Les taules de dades (exam_*, etc.) es creen automàticament
# dins de get_data_db_session() la primera vegada que s'usa

# Carregar prioritats des de la BD (per web, no usem JSON)
def _inicialitzar_prioritats():
    """Carrega prioritats des de la BD en iniciar el backend"""
    from database import get_data_db_session
    from config.settings import config
    from routes.prioritats import _recarregar_prioritats_desde_bd

    try:
        institucio = os.getenv("APP_INSTITUCIO") or config.global_data.get("institucio") or "exemple"
        with get_data_db_session(institucio) as db:
            _recarregar_prioritats_desde_bd(db)
    except Exception as e:
        print(f"⚠️  No s'han pogut carregar prioritats des de BD: {e}")
        print("   Es faran servir les constants del JSON per defecte")

_inicialitzar_prioritats()

app = FastAPI(
    title="Gestor Substitucions API",
    description="API REST per gestionar substitucions i vigilàncies",
    version="1.0.0"
)


@app.exception_handler(MissingXmlError)
async def missing_xml_exception_handler(request: Request, exc: MissingXmlError):
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
            "xml_missing": True,
            "institucio": exc.institucio
        }
    )


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
    token = request.cookies.get("gestor_token")
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
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS - permet crides des del frontend Vue (localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Registre de routers modularitzats =====
from routes import auth, config_examens, grups, pdf, vigilancies, substitucions, settings, estadistiques, prioritats, horari, files, users, disponibles, scheduler, informes

app.include_router(auth.router)
app.include_router(config_examens.router, dependencies=[Depends(require_admin)])
app.include_router(grups.router, dependencies=[Depends(get_current_user)])
app.include_router(pdf.router, dependencies=[Depends(get_current_user)])
app.include_router(vigilancies.router, dependencies=[Depends(get_current_user)])
app.include_router(substitucions.router, dependencies=[Depends(get_current_user)])
app.include_router(settings.router, dependencies=[Depends(require_admin)])
app.include_router(estadistiques.router, dependencies=[Depends(require_admin)])
app.include_router(prioritats.router, dependencies=[Depends(require_admin)])
app.include_router(horari.router, dependencies=[Depends(get_current_user)])
app.include_router(files.router, dependencies=[Depends(require_admin)])
app.include_router(users.router, dependencies=[Depends(get_current_user)])
app.include_router(disponibles.router, dependencies=[Depends(get_current_user)])
app.include_router(scheduler.router, dependencies=[Depends(require_admin)])
app.include_router(informes.router, dependencies=[Depends(require_admin)])


# ===== Endpoints generals (no modularitzats) =====

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "ok",
        "message": "Gestor Substitucions API",
        "docs": "/docs"
    }


@app.get("/api/health")
async def health():
    """Health check per l'API"""
    return {"status": "ok"}


@app.get("/api/config", response_model=ConfigResponse, dependencies=[Depends(get_current_user)])
async def get_config():
    """Retorna configuració actual del sistema"""
    try:
        horari = get_horari()
    except MissingXmlError:
        return ConfigResponse(
            data_actual=datetime.now().strftime("%Y-%m-%d"),
            horari_carregat=False,
            num_professors=0,
            num_hores=0,
            xml_missing=True
        )

    return ConfigResponse(
        data_actual=datetime.now().strftime("%Y-%m-%d"),
        horari_carregat=True,
        num_professors=len(horari.professors),
        num_hores=len(horari.hores)
    )


@app.get("/api/professors", dependencies=[Depends(get_current_user)])
async def get_professors():
    """Retorna llista de professors fins l'últim configurat"""
    try:
        horari = get_horari()
    except MissingXmlError:
        return {
            "professors": [],
            "xml_missing": True
        }
    # horari.professors ja té el límit aplicat (veure core/horari.py línia 50-62)
    return {
        "professors": sorted(horari.professors)
    }


@app.get("/api/hores", dependencies=[Depends(get_current_user)])
async def get_hores():
    """Retorna llista d'hores del dia en l'ordre de l'XML (no alfabètic)"""
    try:
        horari = get_horari()
    except MissingXmlError:
        return {
            "hores": [],
            "xml_missing": True
        }
    return {
        "hores": horari.hores  # Ja estan en l'ordre correcte de l'XML
    }


@app.get("/api/config/no-substituir", dependencies=[Depends(get_current_user)])
async def get_no_substituir():
    """Retorna llista d'activitats que no necessiten substitució"""
    from config.constants import NO_SUBST
    return {
        "no_substituir": list(NO_SUBST)
    }


# ===== Punt d'entrada per executar amb uvicorn =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
