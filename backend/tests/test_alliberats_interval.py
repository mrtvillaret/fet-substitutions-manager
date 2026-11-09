"""Equivalència d'un curs sencer, amb versions d'XML i canvis de període."""

import hashlib
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import event
from suport_api import nova_institucio

from config.context import fixa_institucio_peticio
from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session, get_data_dir_for_institucio
from grups.lectures import AlliberatsDelDia
from horari.repositories import XMLVersionRepository
from models import AbsenciaCoberta, AlliberamentPeriode, GrupAlliberat


@pytest.fixture
def escenari():
    centre = nova_institucio(amb_xml=True)
    fixa_institucio_peticio(centre)
    directori = get_data_dir_for_institucio(centre)
    xml = (directori / "teachers.xml").read_text()
    (directori / "segon.xml").write_text(xml.replace("Reforç", "Suport"))
    dates = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(366)]
    with get_data_db_session(centre) as db:
        # Inclou dates abans de la primera versió, després de l'última,
        # un forat, i una versió inexistent: mateix fallback que get_horari.
        for path, inici, final in [
            ("teachers.xml", "2026-02-01", "2026-04-30"),
            ("segon.xml", "2026-05-15", "2026-09-30"),
            ("inexistent.xml", "2026-10-01", "2026-10-10"),
        ]:
            v = XMLVersionRepository.create(db, path, date.fromisoformat(inici))
            v.data_fi = date.fromisoformat(final)
        ConfiguracioRepository.set(db, "activitats_alliberades_per_defecte", json.dumps(["Reforç", "Suport"]))
        db.add(AbsenciaCoberta(professor="Prof 18", data_inici=date(2026, 3, 2), data_final=date(2026, 6, 15)))
        for i, d in enumerate(dates):
            # Grups, professors, activitats i excepcions «ocupat»; duplicats
            # i hores fora de l'XML, com poden quedar en dades històriques.
            for j, clau in enumerate(
                ["1-ESO-A", "professor:Prof 18", "activitat:Reforç", "activitat:Suport", "ocupat:Prof 31"]
            ):
                if (i + j) % 3 == 0:
                    db.add(
                        GrupAlliberat(data=date.fromisoformat(d), hora=["09:00", "10:00", "fora"][j % 3], grups=clau)
                    )
            if i % 7 == 0:
                for dia in ["Dilluns", "Dimecres"]:
                    db.add(
                        AlliberamentPeriode(
                            tipus="professor",
                            clau="Prof 31",
                            dia_setmana=dia,
                            hora="09:00",
                            des_de=date.fromisoformat(d),
                            alliberat=i % 2 == 0,
                        )
                    )
        # Dos canvis el mateix dia: el darrer id preval.
        for alliberat in [True, False]:
            db.add(
                AlliberamentPeriode(
                    tipus="professor",
                    clau="Prof 18",
                    dia_setmana="Dilluns",
                    hora="09:00",
                    des_de=date(2026, 3, 1),
                    alliberat=alliberat,
                )
            )
        db.commit()
        yield db, dates
    fixa_institucio_peticio(None)


def test_interval_identic_a_dia_a_dia_en_366_dates(escenari):
    db, dates = escenari
    esperat = {d: AlliberatsDelDia.get_by_date(db, d) for d in dates}
    resultat = AlliberatsDelDia.get_entre_dates(db, list(reversed(dates)) + dates[:5])
    # Empremta obtinguda amb el codi anterior, abans de la refactorització.
    assert hashlib.sha256(json.dumps(esperat, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == (
        "bfcfeb175c7621d044aec22e1164536434ca83c61ae5d2786987e6a631e4da48"
    )
    assert resultat == esperat  # també l'ordre i els duplicats de cada llista
    assert AlliberatsDelDia.get_entre_dates(db, []) == {}
    # Una nova petició veu les marques noves: cap memòria cau persistent.
    db.add(GrupAlliberat(data=date(2026, 3, 2), hora="09:00", grups="nou"))
    db.commit()
    assert "nou" in AlliberatsDelDia.get_entre_dates(db, ["2026-03-02"])["2026-03-02"]["09:00"]


def test_les_consultes_no_creixen_amb_els_dies(escenari):
    db, dates = escenari

    def consultes(dies):
        sql = []

        def compta(*args):
            sql.append(args[2])

        event.listen(db.bind, "before_cursor_execute", compta)
        try:
            AlliberatsDelDia.get_entre_dates(db, dies)
        finally:
            event.remove(db.bind, "before_cursor_execute", compta)
        return len(sql)

    # Dins la mateixa versió: un dia o un trimestre, el mateix cost SQL.
    consultes(dates[40:41])  # escalfa només la lectura i el processament de l’XML
    assert consultes(dates[40:41]) == consultes(dates[40:115])
    assert consultes(dates) < 40
