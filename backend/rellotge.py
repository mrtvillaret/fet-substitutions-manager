"""Data i hora del sistema, substituïbles als tests des d'un sol punt.

«Avui» i l'hora local són sempre els del centre (`ZONA_DEL_CENTRE`), no els
de la màquina: el servidor va en UTC i, entre les 0 i les 2 h, «avui» seria
encara el dia anterior. La zona ve del paquet `tzdata` si el sistema no la té."""

from collections.abc import Callable
from datetime import UTC, date, datetime, tzinfo
from typing import Protocol
from zoneinfo import ZoneInfo

ZONA_DEL_CENTRE = ZoneInfo("Europe/Madrid")


class Rellotge(Protocol):
    def avui(self) -> date: ...

    def ara(self, tz: tzinfo | None = None) -> datetime: ...


class RellotgeSistema:
    def __init__(self, instant: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self._instant = instant

    def avui(self) -> date:
        return self.ara().date()

    def ara(self, tz: tzinfo | None = None) -> datetime:
        """Amb `tz`, l'hora en aquella zona; sense, l'hora local del centre
        sense zona (com abans `datetime.now()` en una màquina del centre)."""
        moment = self._instant()
        return moment.astimezone(tz) if tz else moment.astimezone(ZONA_DEL_CENTRE).replace(tzinfo=None)


_rellotge: Rellotge = RellotgeSistema()


def avui() -> date:
    return _rellotge.avui()


def ara(tz: tzinfo | None = None) -> datetime:
    return _rellotge.ara(tz)
