"""Instantànies profundes de dades JSON, sense dependències del domini."""

from collections.abc import Mapping
from types import MappingProxyType

_ESCALARS_JSON = frozenset((str, int, float, bool, type(None)))


def congela(valor):
    """Instantània profunda: conserva ordre, valors, absències i tipus JSON."""
    if type(valor) in _ESCALARS_JSON:
        return valor
    if isinstance(valor, (dict, MappingProxyType)) or isinstance(valor, Mapping):
        return MappingProxyType({clau: congela(dada) for clau, dada in valor.items()})
    if isinstance(valor, (list, tuple)):
        return tuple(congela(dada) for dada in valor)
    if isinstance(valor, (set, frozenset)):
        return frozenset(valor)
    return valor


def descongela(valor):
    """Projecció pròpia per al càlcul; no comparteix contenidors mutables."""
    if type(valor) in _ESCALARS_JSON:
        return valor
    if isinstance(valor, (dict, MappingProxyType)) or isinstance(valor, Mapping):
        return {clau: descongela(dada) for clau, dada in valor.items()}
    if isinstance(valor, tuple):
        return [descongela(dada) for dada in valor]
    if isinstance(valor, frozenset):
        return set(valor)
    return valor
