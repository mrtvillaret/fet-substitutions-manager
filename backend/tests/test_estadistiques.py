"""
Els recomptes de la pantalla Estadístiques per l'API, amb els criteris de
FUNCIONAMENT.md (apartats 5 i 6).
"""

import uuid
from datetime import date

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import require_admin
from database import get_data_db_session
from estadistiques.router import router as estadistiques_router
from models import GrupAlliberat, NoSubstituir, Substitucio, Vigilancia
from rate_limit import limiter

APP = crea_app()
APP.include_router(estadistiques_router, dependencies=[Depends(require_admin)])  # com a main.py

DILLUNS = date(2026, 3, 2)
INTERVAL = {"data_inici": "2026-03-01", "data_final": "2026-03-31"}


@pytest.fixture
def centre():
    limiter.reset()
    nom = nova_institucio(amb_xml=True)
    with get_data_db_session(nom) as db:
        db.add(NoSubstituir(assignatura="Guàrdia"))
        db.commit()
    return nom


@pytest.fixture
def client(centre):
    usuari = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(usuari, centre, "admin")
    return entra(client_per(APP), usuari)


def _afegeix(centre, *files, alliberats=()):
    """files: (hora, absent, assignatura, grup, substitut, tipus)"""
    with get_data_db_session(centre) as db:
        for hora, absent, assignatura, grup, substitut, tipus in files:
            db.add(
                Substitucio(
                    data=DILLUNS,
                    hora=hora,
                    professor_absent=absent,
                    assignatura=assignatura,
                    grup=grup,
                    substitut=substitut,
                    tipus_absencia=tipus,
                )
            )
        for hora, grups in alliberats:
            db.add(GrupAlliberat(data=DILLUNS, hora=hora, grups=grups))
        db.commit()


def _get(client, ruta, **params):
    resposta = client.get(f"/api/estadistiques/{ruta}", params={**INTERVAL, **params})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_un_professor_alliberat_no_compta_encara_que_la_fila_no_tingui_grup(centre, client):
    # La regla única de qui té classe (sense_classe), com als informes: abans,
    # a les files sense grup (una guàrdia de pati) no es mirava
    _afegeix(
        centre,
        ("PATI", "Prof 9", "VP", "", "Prof 5", "ABSENCIA"),
        ("PATI", "Prof 8", "VP", "", "Prof 6", "ABSENCIA"),
        alliberats=[("PATI", "professor:Prof 9")],
    )

    assert [p["professor"] for p in _get(client, "professors")["professors_absents"]] == ["Prof 8"]
    # La substitució feta sí que compta: si té substitut, algú hi ha anat
    taula = {p["professor"]: p for p in _get(client, "taula")["professors"]}
    assert (taula["Prof 5"]["total_absencies"], taula["Prof 5"]["substitucions_fetes"]) == (0, 1)
    assert "Prof 9" not in taula


def test_les_absencies_compten_el_que_es_veu_a_la_pantalla_substitucions(centre, client):
    # Una activitat de «No substituir» no compta, tingui grup o no; les hores
    # sense activitat (assignatura buida) compten si el centre no té el buit a
    # «No substituir» (es veuen a la pantalla) i no si el té
    _afegeix(
        centre,
        ("08:00", "Prof 1", "Guàrdia", "1-ESO-A", "", "ABSENCIA"),
        ("09:00", "Prof 1", "", "", "", "ABSENCIA"),
        ("10:00", "Prof 1", "Català", "1-ESO-A", "Prof 5", "ABSENCIA"),
    )
    assert _get(client, "resum")["cobertura"]["a_cobrir"] == 2

    with get_data_db_session(centre) as db:
        db.add(NoSubstituir(assignatura=""))
        db.commit()
    assert _get(client, "resum")["cobertura"]["a_cobrir"] == 1


def test_classes_no_compta_les_activitats_de_no_substituir(centre, client):
    _afegeix(
        centre,
        ("08:00", "Prof 1", "Guàrdia", "1-ESO-A", "", "ABSENCIA"),
        ("09:00", "Prof 1", "Català", "1-ESO-A", "Prof 5", "ABSENCIA"),
    )

    (classe,) = _get(client, "classes")["classes"]
    assert classe["grup"] == "1-ESO-A"
    assert classe["professor_top"] == "Prof 1 (1)"
    detall = _get(client, "classes/detall", grups=["1-ESO-A"])
    assert [f["assignatura"] for f in detall["resultats"]] == ["Català"]


# Una hora de cada tipus, totes amb grup i substitut llevat del servei
TOTS_ELS_TIPUS = [
    ("08:00", "Prof 1", "Català", "1-ESO-A", "Prof 5", "ABSENCIA"),
    ("09:00", "Prof 2", "Física", "1-ESO-A", "", "SERVEI"),
    ("10:00", "Prof 3", "VIGILÀNCIA", "1-ESO-B", "Prof 6", "VIGILANCIA_ABSENT"),
    ("08:00", "Prof 5", "Biblioteca", "1-ESO-B", "Prof 7", "ENCADENADA"),
    ("11:30", "Prof 4", "Anglès", "1-ESO-B", "Prof 8", "VIGILANCIA"),
]


def test_la_cobertura_nomes_compta_les_absencies_i_els_serveis(centre, client):
    # FUNCIONAMENT.md, apartat 6: cap altre tipus hi compta, ni a dalt ni a baix
    _afegeix(centre, *TOTS_ELS_TIPUS)

    resum = _get(client, "resum")
    assert resum["cobertura"] == {
        "absencies": 1,
        "serveis": 1,
        "a_cobrir": 2,
        "cobertes": 1,
        "pendents": 1,
        "percentatge": 50.0,
    }
    assert resum["activitat"]["dies_amb_absencies"] == 1

    temporal = _get(client, "temporal")
    assert temporal["dies"][0] == {"dia": "Dilluns", "a_cobrir": 2, "cobertes": 1, "vigilancies": 0}
    assert [(h["hora"], h["a_cobrir"], h["cobertes"]) for h in temporal["hores"]] == [("08:00", 1, 1), ("09:00", 1, 0)]
    assert temporal["totals"] == {"a_cobrir": 2, "cobertes": 1, "vigilancies": 0}

    assert _get(client, "classes")["classes"] == [
        {
            "grup": "1-ESO-A",
            "a_cobrir": 2,
            "cobertes": 1,
            "percentatge": 50,
            "assignatura_top": "Català (1)",
            "professor_top": "Prof 1 (1)",
        }
    ]
    detall = _get(client, "classes/detall", grups=["1-ESO-A", "1-ESO-B"])
    assert [f["assignatura"] for f in detall["resultats"]] == ["Català", "Física"]


def test_les_absencies_per_professor_nomes_compten_absencies_i_serveis(centre, client):
    # La vigilància d'un vigilant absent no és una absència més
    _afegeix(centre, *TOTS_ELS_TIPUS)

    assert _get(client, "professors")["professors_absents"] == [
        {"professor": "Prof 1", "absencies": 1, "serveis": 0, "total": 1},
        {"professor": "Prof 2", "absencies": 0, "serveis": 1, "total": 1},
    ]
    absents = {
        p["professor"]: p["total_absencies"] for p in _get(client, "taula")["professors"] if p["total_absencies"]
    }
    assert absents == {"Prof 1": 1, "Prof 2": 1}
    assert _get(client, "professor/Prof 3")["absencies"] == []


def test_les_substitucions_fetes_compten_totes_les_files_amb_substitut(centre, client):
    # La feina de cada professor, de qualsevol tipus de fila (FUNCIONAMENT.md, 6)
    _afegeix(centre, *TOTS_ELS_TIPUS)

    top = {p["professor"]: p["total"] for p in _get(client, "professors")["top_substituts"]}
    assert top == {"Prof 5": 1, "Prof 6": 1, "Prof 7": 1, "Prof 8": 1}
    assert len(_get(client, "professor/Prof 8")["substitucions"]) == 1


def test_la_taula_per_professor_dona_el_balanc_i_el_pati_compta_com_qualsevol_hora(centre, client):
    # Balanç = substitucions fetes − absències; els serveis no resten. Cap
    # categoria de pati: una hora de pati compta com qualsevol altra.
    _afegeix(centre, *TOTS_ELS_TIPUS, ("PATI", "Prof 9", "VP", "", "Prof 5", "ABSENCIA"))

    files = _get(client, "taula")["professors"]
    assert files[0] == {
        "professor": "Prof 5",
        "absencies": 0,
        "serveis": 0,
        "total_absencies": 0,
        "substitucions_fetes": 2,
        "vigilancies_fetes": 0,
        "balanc": 2,
    }
    # Per balanç i, en empat, per ordre alfabètic
    assert [(f["professor"], f["balanc"]) for f in files] == [
        ("Prof 5", 2),
        ("Prof 6", 1),
        ("Prof 7", 1),
        ("Prof 8", 1),
        ("Prof 2", 0),
        ("Prof 1", -1),
        ("Prof 9", -1),
    ]


def test_el_detall_d_un_professor_diu_el_mateix_que_el_pdf_per_professor(centre, client):
    from recomptes.services import dades_professors

    _afegeix(centre, *TOTS_ELS_TIPUS, ("12:30", "Prof 5", "Català", "1-ESO-C", "", "ABSENCIA"))

    detall = _get(client, "professor/Prof 5")
    assert [(f["hora"], f["tipus_absencia"]) for f in detall["absencies"]] == [("12:30", "ABSENCIA")]
    assert [(f["hora"], f["professor_absent"], f["tipus_absencia"]) for f in detall["substitucions"]] == [
        ("08:00", "Prof 1", "ABSENCIA")
    ]
    with get_data_db_session(centre) as db:
        for professor in ("Prof 5", "Prof 7", "Prof 8"):
            (pdf,) = dades_professors(db, INTERVAL["data_inici"], INTERVAL["data_final"], professor)
            web = _get(client, f"professor/{professor}")
            assert len(web["absencies"]) == len(pdf["absencies"])
            assert [f["tipus_absencia"] for f in web["substitucions"]] == [
                s["tipus_absencia"] for s in pdf["substitucions_fetes"]
            ]


def test_les_vigilancies_es_compten_per_resultat(centre, client):
    # Coberta si hi va el vigilant o si la seva fila de vigilant absent té
    # substitut; si no, descoberta. Les vigilàncies fetes per professor són
    # només les del vigilant que hi va (FUNCIONAMENT.md, apartats 5 i 6)
    _afegeix(
        centre,
        ("08:00", "Prof 37", "VIGILÀNCIA", "1-ESO-A", "Prof 42", "VIGILANCIA_ABSENT"),
        ("08:00", "Prof 41", "VIGILÀNCIA", "1-ESO-B", "", "VIGILANCIA_ABSENT"),
        ("09:00", "Prof 10", "Religió", "4-ESO-B", "", "ABSENCIA"),
    )
    with get_data_db_session(centre) as db:
        for hora, vigilant in (
            ("08:00", "Prof 37"),
            ("08:00", "Prof 41"),
            ("08:00", "Prof 20"),
            ("08:00", ""),
            ("09:00", "Prof 10"),
        ):
            db.add(
                Vigilancia(
                    data=DILLUNS,
                    hora=hora,
                    tipus="Examen",
                    grups="1-ESO-A",
                    aula="A01",
                    vigilant=vigilant,
                    nivell="1-ESO",
                )
            )
        db.commit()

    resum = _get(client, "resum")
    assert resum["vigilancies"] == {
        "total": 5,
        "vigilant": 1,
        "substitut": 1,
        "cobertes": 2,
        "descobertes": 3,
        "percentatge": 40.0,
    }
    assert resum["activitat"]["dies_amb_vigilancies"] == 1
    assert "top_vigilants" not in _get(client, "professors")
    files = {f["professor"]: f for f in _get(client, "taula")["professors"]}
    assert files["Prof 20"]["vigilancies_fetes"] == 1
    # Qui cobreix la fila de vigilant absent ho té a les substitucions fetes
    assert (files["Prof 42"]["substitucions_fetes"], files["Prof 42"]["vigilancies_fetes"]) == (1, 0)


def test_les_hores_de_temporals_van_en_l_ordre_de_l_horari_i_els_empats_per_nom(centre, client):
    # Abans, per ordre de text: «PATI» després de «16:00»
    _afegeix(
        centre,
        ("11:30", "Prof 1", "Català", "1-ESO-A", "Prof 10", "ABSENCIA"),
        ("PATI", "Prof 2", "VP", "", "Prof 9", "ABSENCIA"),
        ("8:00", "Prof 3", "Física", "1-ESO-B", "Prof 2", "ABSENCIA"),
    )

    assert [h["hora"] for h in _get(client, "temporal")["hores"]] == ["08:00", "PATI", "11:30"]
    absents = [p["professor"] for p in _get(client, "professors")["professors_absents"]]
    assert absents == ["Prof 1", "Prof 2", "Prof 3"]
    assert [p["professor"] for p in _get(client, "professors")["top_substituts"]] == ["Prof 2", "Prof 9", "Prof 10"]


def test_el_filtre_per_hores_refa_tots_els_recomptes(centre, client):
    # Decidit el 30/10/2026: en lloc d'una categoria de pati, es pot triar
    # quines franges de l'horari es veuen (p. ex. només el PATI, o totes menys)
    _afegeix(
        centre,
        ("08:00", "Prof 1", "Català", "1-ESO-A", "Prof 5", "ABSENCIA"),
        ("PATI", "Prof 2", "VP", "", "Prof 6", "ABSENCIA"),
        ("PATI", "Prof 3", "VP", "", "", "SERVEI"),
        ("11:30", "Prof 4", "Anglès", "1-ESO-B", "Prof 7", "ABSENCIA"),
    )
    with get_data_db_session(centre) as db:
        for hora, vigilant in (("08:00", "Prof 8"), ("PATI", "Prof 9")):
            db.add(
                Vigilancia(
                    data=DILLUNS,
                    hora=hora,
                    tipus="Examen",
                    grups="1-ESO-A",
                    aula="A01",
                    vigilant=vigilant,
                    nivell="1-ESO",
                )
            )
        db.commit()

    pati = {"hores": ["PATI"]}
    resum = _get(client, "resum", **pati)
    assert (resum["cobertura"]["a_cobrir"], resum["cobertura"]["cobertes"]) == (2, 1)
    assert resum["vigilancies"]["total"] == 1
    assert [p["professor"] for p in _get(client, "professors", **pati)["professors_absents"]] == ["Prof 2", "Prof 3"]
    assert [h["hora"] for h in _get(client, "temporal", **pati)["hores"]] == ["PATI"]
    assert {f["professor"] for f in _get(client, "taula", **pati)["professors"]} == {
        "Prof 2",
        "Prof 3",
        "Prof 6",
        "Prof 9",
    }
    assert _get(client, "professor/Prof 1", **pati)["absencies"] == []
    assert _get(client, "classes", **pati)["classes"] == []

    # Totes menys el PATI, amb el format d'axios (hores[]) i l'hora sense zero
    resum = _get(client, "resum", **{"hores[]": ["8:00", "11:30"]})
    assert (resum["cobertura"]["a_cobrir"], resum["vigilancies"]["total"]) == (2, 1)
    # Sense filtre, totes
    assert _get(client, "resum")["cobertura"]["a_cobrir"] == 4


def test_les_franges_del_filtre_son_les_de_les_versions_de_l_horari_de_l_interval(centre, client):
    # La unió, pel nom, de les franges de les versions vigents a l'interval
    import xml.etree.ElementTree as ET

    from suport_api import XML_EXEMPLE

    from database import get_data_dir_for_institucio
    from models import XMLVersion

    arbre = ET.parse(XML_EXEMPLE)
    for hora in arbre.getroot().iter("Hour"):
        if hora.get("name", "").strip() == "PATI":
            hora.set("name", "ESBARJO")
    arbre.write(get_data_dir_for_institucio(centre) / "nou.xml", encoding="utf-8")
    with get_data_db_session(centre) as db:
        db.add(XMLVersion(path="teachers.xml", data_inici=date(2026, 3, 1), data_fi=date(2026, 3, 15)))
        db.add(XMLVersion(path="nou.xml", data_inici=date(2026, 3, 16), data_fi=None))
        db.commit()

    def hores(inici, final):
        return _get(client, "hores", data_inici=inici, data_final=final)["hores"]

    abans = hores("2026-03-01", "2026-03-15")
    assert "PATI" in abans and "ESBARJO" not in abans
    assert abans.index("10:00") < abans.index("PATI") < abans.index("11:30")
    assert hores("2026-03-01", "2026-03-31") == [*abans, "ESBARJO"]
    assert "PATI" not in hores("2026-03-16", "2026-03-31")
