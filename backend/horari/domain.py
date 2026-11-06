"""
Un dia per a un centre i l'horari (XML) que hi correspon.

És l'únic camí per arribar a l'horari des de les rutes: la data sempre hi és
(no es pot oblidar) i la regla de quina versió de l'XML toca és en un sol lloc
(XMLVersionRepository.vigent). Les rutes el reben amb una dependència
(dependencies.py): el dia de la petició, el del calendari o el del planificador.
"""

from dataclasses import dataclass
from datetime import date
from functools import cached_property

import rellotge
from database import get_data_db_session
from horari.context import _get_institucio_actual, _resolve_xml_path, get_horari
from horari.repositories import XMLVersionRepository
from substitucions.context import get_gestors
from vigilancies.context import get_vigilancia_core


@dataclass(frozen=True)
class Dia:
    data: date
    institucio: str

    @classmethod
    def avui(cls, institucio: str) -> "Dia":
        return cls(rellotge.avui(), institucio)

    @classmethod
    def de_text(cls, data_iso: str, institucio: str = None) -> "Dia":
        """El dia d'una data AAAA-MM-DD; sense institució, la de la petició en curs."""
        return cls(date.fromisoformat(data_iso), institucio or _get_institucio_actual())

    @property
    def iso(self) -> str:
        """La data com a AAAA-MM-DD (el format de l'API i de la BD)."""
        return self.data.isoformat()

    @cached_property
    def horari(self):
        """L'horari vigent aquest dia (MissingXmlError si no n'hi ha cap)."""
        return get_horari(self.institucio, data_iso=self.iso, xml_path=self.xml_path)

    @property
    def horari_amb_tothom(self):
        """L'horari vigent aquest dia amb tothom, també els que hi tenen una
        absència coberta (Dia.horari ja no els té): per a la configuració del
        curs (p.ex. els exàmens), no per decidir qui hi és aquell dia."""
        return getattr(self.horari, "sencer", self.horari)

    def gestors(self):
        """(substitucions, horari, alliberats, absències) d'aquest dia: nous a
        cada crida, perquè cada petició hi fixa el seu estat."""
        return get_gestors(self.institucio, data_iso=self.iso, horari=self.horari)

    def vigilancia_core(self, db):
        """El nucli de vigilàncies d'aquest dia (titulars, disponibles)."""
        return get_vigilancia_core(self.iso, db, self.institucio, horari=self.horari)

    @cached_property
    def xml_path(self):
        return _resolve_xml_path(self.institucio, self.iso, versio=self.versio)

    @cached_property
    def versio(self):
        """La versió de l'XML vigent aquest dia (o la més propera), o None."""
        with get_data_db_session(self.institucio, lectura=True) as db:
            versio = XMLVersionRepository.vigent(db, self.iso)
            if versio is not None:
                db.expunge(versio)
            return versio

    @property
    def versio_des_de(self):
        """Data d'inici (AAAA-MM-DD) de la versió de l'XML, per indicar-la."""
        return self.versio.data_inici.isoformat() if self.versio and self.versio.data_inici else None
