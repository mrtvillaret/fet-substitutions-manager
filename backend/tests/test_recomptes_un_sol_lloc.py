"""
Els recomptes surten d'un sol lloc (recomptes/): per al mateix interval, la
pantalla Estadístiques, els informes PDF i el «(n/total)» del desplegable de
substituts donen el mateix, i ni les rutes d'Estadístiques ni les dades dels
informes no compten pel seu compte (FUNCIONAMENT.md, apartat 6).
"""

import ast
import re
import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi import Depends
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from auth.dependencies import require_admin
from database import get_data_db_session
from estadistiques.router import router as estadistiques_router
from models import Curs, GrupAlliberat, NoSubstituir, Substitucio, Vigilancia
from pdf import services as informes
from rate_limit import limiter
from substitucions import router as substitucions

BACKEND = Path(__file__).resolve().parent.parent
APP = crea_app(substitucions.router)
APP.include_router(estadistiques_router, dependencies=[Depends(require_admin)])
INICI, FINAL = "2026-03-01", "2026-03-31"

# data, hora, absent, assignatura, grup, substitut, tipus
FILES = [
    ("2026-03-02", "08:00", "Prof 1", "Català", "1-ESO-A", "Prof 5", "ABSENCIA"),
    ("2026-03-02", "09:00", "Prof 1", "Català", "1-ESO-B", "", "ABSENCIA"),
    ("2026-03-02", "09:00", "Prof 2", "Física", "1-ESO-A", "Prof 6", "SERVEI"),
    ("2026-03-02", "10:00", "Prof 3", "VIGILÀNCIA", "1-ESO-B", "Prof 7", "VIGILANCIA_ABSENT"),
    ("2026-03-02", "08:00", "Prof 5", "Biblioteca", "", "Prof 8", "ENCADENADA"),
    ("2026-03-03", "11:30", "Prof 4", "Anglès", "1-ESO-C", "Prof 5", "VIGILANCIA"),
    ("2026-03-03", "PATI", "Prof 9", "VP", "", "Prof 6", "ABSENCIA"),
    ("2026-03-03", "PATI", "Prof 10", "VP", "", "Prof 7", "ABSENCIA"),  # alliberat
    ("2026-03-04", "12:30", "Prof 1", "Guàrdia", "1-ESO-A", "", "ABSENCIA"),  # «No substituir»
    ("2026-03-04", "12:30", "Prof 11", "Tecnologia", "1-ESO-C", "Prof 12", "ABSENCIA"),
    ("2026-04-01", "08:00", "Prof 1", "Català", "1-ESO-A", "Prof 5", "ABSENCIA"),  # fora
]


def _centre():
    limiter.reset()
    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        db.add(NoSubstituir(assignatura="Guàrdia"))
        # El curs és el mes: el «(n/total)» del desplegable compta el curs
        db.add(Curs(nom="Març", data_inici=date(2026, 3, 1), data_fi=date(2026, 3, 31)))
        db.add(Curs(nom="Abril", data_inici=date(2026, 4, 1)))
        for data, hora, absent, assignatura, grup, substitut, tipus in FILES:
            db.add(
                Substitucio(
                    data=date.fromisoformat(data),
                    hora=hora,
                    professor_absent=absent,
                    assignatura=assignatura,
                    grup=grup,
                    substitut=substitut,
                    tipus_absencia=tipus,
                )
            )
        db.add(GrupAlliberat(data=date(2026, 3, 3), hora="PATI", grups="professor:Prof 10"))
        db.add(
            Vigilancia(
                data=date(2026, 3, 2),
                hora="10:00",
                tipus="Examen",
                grups="1-ESO-B",
                aula="A01",
                vigilant="Prof 3",
                nivell="1-ESO",
            )
        )
        db.commit()
    usuari = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(usuari, centre, "admin")
    return centre, entra(client_per(APP), usuari)


@pytest.mark.parametrize("hores", [None, ["08:00", "PATI"]], ids=["totes les hores", "hores triades"])
def test_la_web_i_els_informes_donen_el_mateix(hores):
    centre, client = _centre()
    filtre = {"hores": hores} if hores else {}

    def web(ruta, **params):
        resposta = client.get(
            f"/api/estadistiques/{ruta}", params={"data_inici": INICI, "data_final": FINAL, **filtre, **params}
        )
        assert resposta.status_code == 200, resposta.text
        return resposta.json()

    triades = frozenset(hores) if hores else None
    with get_data_db_session(centre) as db:
        direccio = informes.dades_direccio(db, INICI, FINAL, [], hores=triades)
        professors = {p["nom"]: p for p in informes.dades_professors(db, INICI, FINAL, hores=triades)}

    stats = direccio["stats"]
    cobertura = web("resum")["cobertura"]
    assert (cobertura["absencies"], cobertura["serveis"]) == (stats["total_absencies"], stats["total_serveis"])
    assert (cobertura["a_cobrir"], cobertura["cobertes"]) == (stats["total_necessiten"], stats["total_substitucions"])
    assert cobertura["percentatge"] == round(stats["cobertura_pct"], 1)
    assert web("resum")["activitat"]["dies_amb_absencies"] == stats["dies_actius"]

    absents = [(p["professor"], p["total"]) for p in web("professors")["professors_absents"]]
    assert absents == [(p["nom"], p["total"]) for p in direccio["professors_absencies"]]
    substituts = [(p["professor"], p["total"]) for p in web("professors")["top_substituts"]]
    assert substituts == [(p["nom"], p["total"]) for p in direccio["professors_substitucions"]]

    taula = {f["professor"]: f for f in web("taula")["professors"]}
    for nom, p in professors.items():
        assert taula[nom]["total_absencies"] == len(p["absencies"])
        assert taula[nom]["substitucions_fetes"] == len(p["substitucions_fetes"])
        detall = web(f"professor/{nom}")
        assert (len(detall["absencies"]), len(detall["substitucions"])) == (
            len(p["absencies"]),
            len(p["substitucions_fetes"]),
        )
    assert {n for n, f in taula.items() if f["total_absencies"] or f["substitucions_fetes"]} == set(professors)

    per_hora = {h["hora"]: (h["a_cobrir"], h["cobertes"]) for h in web("temporal")["hores"] if h["a_cobrir"]}
    assert per_hora == {h: (v["absencies"], v["substitucions"]) for h, v in direccio["per_hora"].items()}

    classes = {c["grup"]: (c["a_cobrir"], c["cobertes"]) for c in web("classes")["classes"]}
    assert classes == {g["nom"]: (g["absencies"], g["cobertes"]) for g in direccio["grups_data"]["grups_ordenats"]}

    # Els valors esperats, perquè el test no passi si totes dues s'equivoquen
    # igual. Les fetes són totes les files amb substitut: també la de Prof 7
    # a l'alliberat Prof 10 (si té substitut, algú hi ha anat)
    if hores:
        assert (cobertura["a_cobrir"], cobertura["cobertes"]) == (2, 2)
        assert substituts == [("Prof 5", 1), ("Prof 6", 1), ("Prof 7", 1), ("Prof 8", 1)]
    else:
        assert (cobertura["a_cobrir"], cobertura["cobertes"]) == (5, 4)
        assert substituts == [("Prof 5", 2), ("Prof 6", 2), ("Prof 7", 2), ("Prof 8", 1), ("Prof 12", 1)]


def test_el_desplegable_de_substituts_compta_les_substitucions_fetes_com_estadistiques():
    # El «(n/total)» de cada professor al desplegable de substituts: n, les
    # seves substitucions fetes del curs al mateix dia de la setmana i hora;
    # total, les del curs. Les mateixes de la taula d'Estadístiques: totes les
    # files amb substitut, de tots els tipus, sense els filtres de «No
    # substituir» ni d'alliberats (si té substitut, algú hi ha anat)
    centre, client = _centre()
    with get_data_db_session(centre) as db:
        for dia, hora, absent, assignatura, grup, substitut, tipus in [
            ("2026-03-09", "10:00", "Prof 1", "Català", "1-ESO-A", "Prof 21", "ABSENCIA"),  # dilluns
            ("2026-03-10", "10:00", "Prof 1", "Guàrdia", "1-ESO-A", "Prof 21", "ABSENCIA"),  # «No substituir»
            ("2026-03-11", "09:00", "Prof 10", "Català", "", "Prof 21", "ABSENCIA"),  # alliberat
            ("2026-04-06", "10:00", "Prof 1", "Català", "1-ESO-A", "Prof 21", "ABSENCIA"),  # un altre curs
            ("2026-03-03", "11:30", "Prof 4", "Anglès", "1-ESO-C", "Prof 28", "VIGILANCIA"),
        ]:
            db.add(
                Substitucio(
                    data=date.fromisoformat(dia),
                    hora=hora,
                    professor_absent=absent,
                    assignatura=assignatura,
                    grup=grup,
                    substitut=substitut,
                    tipus_absencia=tipus,
                )
            )
        db.add(GrupAlliberat(data=date(2026, 3, 11), hora="09:00", grups="professor:Prof 10"))
        db.commit()

    taula = client.get("/api/estadistiques/taula", params={"data_inici": INICI, "data_final": FINAL}).json()
    fetes = {f["professor"]: f["substitucions_fetes"] for f in taula["professors"]}
    desplegable = {}
    for hora in ("08:00", "10:00"):
        resposta = client.get(f"/api/substitucions/2026-03-02/{hora}/disponibles")
        assert resposta.status_code == 200, resposta.text
        for d in resposta.json()["disponibles"]:
            n, total = re.search(r"\((\d+)/(\d+)\)", d["text_display"]).groups()
            desplegable[(d["professor"], hora)] = (int(n), int(total))

    assert desplegable[("Prof 21", "10:00")] == (1, 3)
    assert desplegable[("Prof 28", "10:00")] == (0, 1)
    assert {(p, h): total for (p, h), (_, total) in desplegable.items()} == {
        (p, h): fetes.get(p, 0) for (p, h) in desplegable
    }


# Els fitxers que donen recomptes a la pantalla i als informes: només
# ajunten el que calcula recomptes/
FITXERS_SENSE_RECOMPTES_PROPIS = [
    *sorted((BACKEND / "estadistiques").glob("*.py")),
    BACKEND / "pdf" / "services.py",
    BACKEND / "pdf" / "informes.py",
]
# El que fa falta per comptar pel seu compte: els models, els filtres i els
# tipus de fila de substitució (copiar el camp tipus_absencia per mostrar-lo
# sí que es pot; triar per tipus, no)
PROHIBITS = {
    "noms": {"Substitucio", "Vigilancia", "sense_classe", "NoSubstituirRepository", "GrupsAlliberatsRepository"},
    "textos": {"ABSENCIA", "SERVEI", "VIGILANCIA_ABSENT", "ENCADENADA", "VIGILANCIA"},
    "atributs": {"tipus_absencia"},  # de les files de la BD (sub.tipus_absencia)
}


def test_ningu_no_compta_pel_seu_compte_fora_del_modul_comu():
    trobats = []
    for fitxer in FITXERS_SENSE_RECOMPTES_PROPIS:
        for node in ast.walk(ast.parse(fitxer.read_text(encoding="utf-8"))):
            nom = None
            if isinstance(node, ast.Name) and node.id in PROHIBITS["noms"]:
                nom = node.id
            elif isinstance(node, ast.alias) and node.name.split(".")[-1] in PROHIBITS["noms"]:
                nom = node.name
            elif isinstance(node, ast.Constant) and node.value in PROHIBITS["textos"]:
                nom = repr(node.value)
            elif isinstance(node, ast.Attribute) and node.attr in PROHIBITS["atributs"]:
                nom = node.attr
            if nom:
                trobats.append(f"{fitxer.relative_to(BACKEND)}:{getattr(node, 'lineno', '?')} {nom}")
    assert trobats == []


def test_la_pantalla_substitucions_i_les_absencies_fan_servir_la_mateixa_regla():
    # Quines files es veuen a Substitucions ho decideix una sola funció
    # (substitucions/visibilitat.py); la pantalla (backend) i recomptes/ la
    # criden, i cap dels dos ni el frontend no filtren pel seu compte
    for fitxer in (BACKEND / "substitucions" / "_consultes.py", BACKEND / "recomptes" / "services.py"):
        noms = {
            n.id if isinstance(n, ast.Name) else n.attr
            for n in ast.walk(ast.parse(fitxer.read_text(encoding="utf-8")))
            if isinstance(n, (ast.Name, ast.Attribute))
        }
        assert "es_visible_a_substitucions" in noms, fitxer
        assert "sense_classe" not in noms, fitxer
        assert "es_vigilancia_absent" not in noms, fitxer
    vista = (BACKEND.parent / "frontend" / "src" / "views" / "SubstitucionsView.vue").read_text(encoding="utf-8")
    assert "noSubstituir" not in vista
