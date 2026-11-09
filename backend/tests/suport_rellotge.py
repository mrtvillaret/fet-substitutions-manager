"""Rellotge determinista: dia fix i avanç mínim per distingir les escriptures."""

from datetime import UTC, datetime, timedelta
from threading import Lock

ARA = datetime(2026, 11, 4, 12, tzinfo=UTC)
AVUI = ARA.date()


class RellotgeDeProva:
    def __init__(self, moment=ARA):
        self.moment = moment
        self._lock = Lock()

    def avui(self):
        return self.moment.date()

    def ara(self, tz=None):
        with self._lock:
            resultat = self.moment
            # updated_at ha de distingir dues escriptures, també amb hora fixada.
            self.moment += timedelta(microseconds=1)
        return resultat.astimezone(tz) if tz else resultat.replace(tzinfo=None)

    def avanca(self, **interval):
        self.moment += timedelta(**interval)
