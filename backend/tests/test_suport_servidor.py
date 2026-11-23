"""El servidor dels tests de concurrència no espera per sempre una arrencada
que no arriba."""

import time
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from suport_servidor import servidor_uvicorn


def test_una_arrencada_que_falla_atura_el_test_de_seguida():
    @asynccontextmanager
    async def falla(_app):
        raise RuntimeError("arrencada fallida simulada")
        yield

    inici = time.monotonic()
    with pytest.raises(RuntimeError, match="abans d'arrencar"):
        with servidor_uvicorn(FastAPI(lifespan=falla)):
            pass
    assert time.monotonic() - inici < 10
