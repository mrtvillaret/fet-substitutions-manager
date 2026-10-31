"""Errors propis del mòdul de grups (la resposta és la de sempre:
{"detail": missatge} amb el seu status)."""

from errors_domini import NoTrobat, NoValid


class PeriodeNoValid(NoValid):
    """Un canvi per període amb un tipus, una clau, unes hores o un dia de la
    setmana que no valen."""


class ActivitatNoConfigurada(NoTrobat):
    pass
