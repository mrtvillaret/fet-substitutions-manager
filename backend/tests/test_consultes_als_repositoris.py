"""
Les consultes a la BD són als repositoris (`repositories.py` de cada mòdul i
el general): cap altre fitxer del backend no fa `.query(`, `.execute(` ni
`select(` de SQLAlchemy. Fora: les migracions (SQL directe, a propòsit) i
`database.py` (la configuració de SQLite).
"""

import re
from datetime import date
from pathlib import Path

from suport_api import nova_institucio

from absencia_coberta.services import _dies_afectats
from configuracio_examens.propostes import nivells_amb_substitucions
from database import get_data_db_session
from models import Substitucio, Vigilancia

BACKEND = Path(__file__).resolve().parent.parent
EXCLOSOS = {"venv", "venv_old_py313_broken", "tests", "migracions", "__pycache__"}
CONSULTA = re.compile(r"\.query\(|\.execute\(|(?<![\w.])select\(")


def _fitxers():
    for cami in BACKEND.rglob("*.py"):
        relatiu = cami.relative_to(BACKEND)
        if relatiu.parts[0] in EXCLOSOS or cami.name == "repositories.py" or relatiu == Path("database.py"):
            continue
        yield relatiu, cami.read_text(encoding="utf-8")


def test_cap_consulta_fora_dels_repositoris():
    trobades = [
        f"{relatiu}:{n}"
        for relatiu, text in _fitxers()
        for n, linia in enumerate(text.splitlines(), 1)
        if CONSULTA.search(linia)
    ]
    assert trobades == []


def test_les_dates_d_una_absencia_coberta_i_els_grups_de_l_historial():
    """Les dues consultes que hi havia fora (absencia_coberta i propostes),
    ara als repositoris, donen el mateix."""
    centre = nova_institucio()
    with get_data_db_session(centre) as db:
        for d, grup in ((date(2026, 4, 20), "1-ESO-A"), (date(2026, 4, 27), ""), (date(2026, 5, 4), None)):
            db.add(Substitucio(data=d, hora="09:00", professor_absent="P", grup=grup, tipus_absencia="ABSENCIA"))
        db.add(
            Vigilancia(
                data=date(2026, 4, 22), hora="09:00", tipus="T", grups="2-BAT-A,2-BAT-B", aula="A", nivell="2-BAT"
            )
        )
        db.commit()
        assert _dies_afectats(db, "2026-04-21", "2026-05-04", date(2026, 4, 1)) == [
            "2026-04-22",
            "2026-04-27",
            "2026-05-04",
        ]
        assert _dies_afectats(db, "2026-04-01", "2026-04-30", date(2026, 4, 23)) == ["2026-04-27"]
        assert nivells_amb_substitucions(db) == {"1-ESO", "2-BAT"}
