"""
Errors interns (5xx): el detall es desa al registre del servidor i l'usuari
només rep una referència curta.

Moltes rutes responen `HTTPException(500, detail=f"...{str(e)}")`, i aquest
detall pot contenir informació interna (consultes SQL, rutes de fitxers...).
En lloc de canviar-les una per una, aquest gestor intercepta qualsevol
resposta 5xx: registra el detall amb una referència i respon només
{"error_ref": "a1b2c3d4"}, que la web mostra amb el seu missatge traduït
d'"Error intern del servidor". Els errors 4xx (missatges per a l'usuari) no
es toquen.
"""
import logging
import uuid

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("uvicorn.error")


def _resposta_error_intern(status_code: int, request: Request, detall) -> JSONResponse:
    ref = uuid.uuid4().hex[:8]
    logger.error("Error %s [ref %s] %s %s: %s", status_code, ref, request.method, request.url.path, detall)
    return JSONResponse(status_code=status_code, content={"error_ref": ref})


async def _gestor_http(request: Request, exc: StarletteHTTPException):
    if exc.status_code >= 500:
        return _resposta_error_intern(exc.status_code, request, exc.detail)
    return await http_exception_handler(request, exc)


async def _gestor_no_controlat(request: Request, exc: Exception):
    logger.exception("Excepció no controlada a %s %s", request.method, request.url.path)
    return _resposta_error_intern(500, request, f"{type(exc).__name__}: {exc}")


def registra_gestors_errors(app) -> None:
    app.add_exception_handler(StarletteHTTPException, _gestor_http)
    app.add_exception_handler(Exception, _gestor_no_controlat)
