"""Ruta mínima del registre HTTP i retenció del fitxer d'accés opcional."""

import logging
import os
from logging.handlers import TimedRotatingFileHandler


def request_route(request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path_format", None) or request.url.path


def configure_access_logger() -> logging.Logger:
    # Uvicorn escriu altrament un segon registre amb la URI i la IP originals.
    logging.getLogger("uvicorn.access").disabled = True
    logger = logging.getLogger("gestor.access")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    path = os.getenv("ACCESS_LOG_PATH")
    if not path:
        logger = logging.getLogger("uvicorn.error")
    else:
        handler = TimedRotatingFileHandler(
            path, when="midnight", interval=1, backupCount=30, encoding="utf-8", utc=True
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger
