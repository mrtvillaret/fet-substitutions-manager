"""Data i hora del sistema, substituïbles als tests des d'un sol punt."""

from datetime import date, datetime, tzinfo
from typing import Protocol


class Rellotge(Protocol):
    def avui(self) -> date: ...

    def ara(self, tz: tzinfo | None = None) -> datetime: ...


class RellotgeSistema:
    def avui(self) -> date:
        return date.today()

    def ara(self, tz: tzinfo | None = None) -> datetime:
        return datetime.now(tz)


_rellotge: Rellotge = RellotgeSistema()


def avui() -> date:
    return _rellotge.avui()


def ara(tz: tzinfo | None = None) -> datetime:
    return _rellotge.ara(tz)
