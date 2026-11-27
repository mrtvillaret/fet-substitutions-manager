"""Els dos modes del guió amb centres temporals."""

from datetime import date

from suport_api import nova_institucio

import database
from grups.repositories import AlliberamentsPeriodeRepository, GrupsAlliberatsRepository
from prioritats.repositories import NoSubstituirRepository
from scripts.treu_substituts_amagats import main
from substitucions.repositories import SubstitucioRepository

DATA = "2026-04-20"
ABANS = "2026-04-13"
DESPRES = "2026-04-27"


def test_recompte_i_aplica_amb_bd_temporals(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(database, "DATA_BASE_DIR", tmp_path)
    centre = nova_institucio(amb_xml=True)
    sense_horari = nova_institucio()
    mare = {
        "data": DATA,
        "hora": "09:00",
        "professor_absent": "Prof 1",
        "grup": "3-ESO-A",
        "assignatura": "E.F.",
        "substitut": "Prof 2",
        "tipus_substitut": "disponible (Guàrdia)",
        "tipus_absencia": "SERVEI",
    }
    with database.get_data_db_session(centre) as db:
        AlliberamentsPeriodeRepository.afegeix(db, "professor", "Prof 1", "Dilluns", ["09:00"], DATA, True)
        NoSubstituirRepository.create(db, "E.F.")
        SubstitucioRepository.create(db, mare)
        SubstitucioRepository.create(
            db,
            mare
            | {
                "professor_absent": "Prof 2",
                "grup": "",
                "assignatura": "Guàrdia",
                "tipus_absencia": "ENCADENADA",
                "substitut": "Prof 9",
            },
        )
        db.commit()
    with database.get_data_db_session(sense_horari) as db:
        GrupsAlliberatsRepository.afegeix(db, DATA, "09:00", "3-ESO-A")
        SubstitucioRepository.create(db, mare)
        dia = date.fromisoformat(DATA)
        NoSubstituirRepository.create(db, "Pares", vigent_des_de=dia)
        [entrada] = NoSubstituirRepository.de_l_activitat(db, "Pares")
        NoSubstituirRepository.tanca(db, entrada, dia)
        pares = mare | {"assignatura": "Pares", "grup": "", "professor_absent": "Prof 3"}
        for data in (ABANS, DATA, DESPRES):
            SubstitucioRepository.create(db, pares | {"data": data})
        tipus_vigilancia = "alliberat (tenia E.F.)"
        SubstitucioRepository.create(
            db,
            pares
            | {
                "professor_absent": "Prof 4",
                "tipus_absencia": "VIGILANCIA_ABSENT",
                "tipus_substitut": tipus_vigilancia,
            },
        )
        db.commit()

    centres = sorted((centre, sense_horari))
    camins = [tmp_path / nom / "gestor.db" for nom in centres]
    abans = [cami.read_bytes() for cami in camins]
    assert main(["--recompte"]) == 0
    captura = capsys.readouterr()
    assert captura.out.splitlines() == [
        f"{i} 1 {int(nom == sense_horari)} {int(nom == centre)} {3 * int(nom == sense_horari)}"
        for i, nom in enumerate(centres, 1)
    ]
    assert captura.err == ""
    assert [cami.read_bytes() for cami in camins] == abans

    assert main(["--aplica"]) == 0
    for nom in centres:
        with database.get_data_db_session(nom) as db:
            files = SubstitucioRepository.get_by_date(db, DATA)
            esperades = {("Prof 1", "09:00", "SERVEI"): ("", "")}
            if nom == sense_horari:
                esperades[("Prof 3", "09:00", "SERVEI")] = ("", "")
                esperades[("Prof 4", "09:00", "VIGILANCIA_ABSENT")] = ("Prof 2", tipus_vigilancia)
                for data in (ABANS, DESPRES):
                    [fila] = SubstitucioRepository.get_by_date(db, data)
                    assert (fila.substitut, fila.tipus_substitut) == ("Prof 2", "disponible (Guàrdia)")
            assert {
                (fila.professor_absent, fila.hora, fila.tipus_absencia): (fila.substitut, fila.tipus_substitut)
                for fila in files
            } == esperades

    assert main(["--recompte"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"{i} 0 0 0 {3 * int(nom == sense_horari)}" for i, nom in enumerate(centres, 1)
    ]
