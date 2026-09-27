import ipaddress
import math
import time

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import Response


def _es_proxy_intern(host: str) -> bool:
    """Connexió des de la mateixa màquina o d'una xarxa interna (on hi ha
    Caddy o el nginx del frontend, p.ex. la xarxa de Docker)."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def get_client_ip(request: Request) -> str:
    """IP del client per al límit de peticions.

    X-Forwarded-For només es té en compte si la connexió ve d'un proxy
    intern, i se n'agafa l'últim valor: és el que hi afegeix el proxy. Els
    anteriors els pot haver escrit el mateix client (nginx amb
    $proxy_add_x_forwarded_for hi afegeix la IP al final), i si es fes cas
    del primer, canviant-lo a cada intent se saltaria el límit. Una connexió
    directa des de fora ignora la capçalera.
    """
    directa = request.client.host if request.client else "unknown"
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada and _es_proxy_intern(directa):
        return reenviada.split(",")[-1].strip() or directa
    return directa


limiter = Limiter(key_func=get_client_ip)


def limit_superat(request: Request, exc: RateLimitExceeded) -> Response:
    """Resposta 429 amb Retry-After: els segons que falten perquè es
    reiniciï la finestra del límit (el frontend ho mostra a l'usuari)."""
    resposta = _rate_limit_exceeded_handler(request, exc)
    if "Retry-After" not in resposta.headers:
        try:
            limit, claus = request.state.view_rate_limit
            reinici, _ = request.app.state.limiter.limiter.get_window_stats(limit, *claus)
            segons = max(1, math.ceil(reinici - time.time()))
        except Exception:
            segons = exc.limit.limit.get_expiry()
        resposta.headers["Retry-After"] = str(segons)
    return resposta
