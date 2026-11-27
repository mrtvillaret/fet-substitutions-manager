"""
substitucions/prioritat.py: si per a un substitut assignat hi ha un disponible de
més prioritat, el PDF n'avisa i «Reassignar problemàtics» el canvia.

Dilluns 20/04/2026 a les 10:00: Prof 15 fa Anglès (3-ESO-A), Prof 3 fa guàrdia,
Prof 1 té classe amb 3-ESO-C i Prof 30 amb 1-ESO-A. Prioritats de suport_api:
primer els alliberats, després les guàrdies. Quan Prof 3 substitueix, la seva
guàrdia queda per cobrir (fila encadenada) i en generar s'hi posa un alliberat.
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date

import pytest
from suport_api import XML_EXEMPLE, client_per, crea_app, crea_usuari, entra, nova_institucio, text_pdf
from suport_noms import unic
from suport_xml import amb_versions

from config import constants
from database import get_data_db_session, get_data_dir_for_institucio
from grups import router as grups
from pdf import router as pdf
from pdf.validacions import valida_dia
from prioritats.memoria import categoria_de_prioritat
from rate_limit import limiter
from substitucions import router as substitucions
from substitucions.files import FilaSubstitucio
from substitucions.prioritat import MillorsSubstituts

APP = crea_app(substitucions.router, grups.router, pdf.router)
DATA = "2026-04-20"


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"admin_{unic()}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _fila(client):
    return next(
        s
        for s in client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
        if s["hora"] == "10:00" and s["professor_absent"] == "Prof 15"
    )


def _guardia_amb_alliberats(client):
    """Prof 3 (guàrdia) substitueix Prof 15 i, després, Prof 1 i Prof 30 queden alliberats."""
    client.put(f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["10:00"], "updated_at_map": {}})
    resp = client.put(
        f"/api/substitucions/{DATA}/10:00/Prof 15",
        json={"substitut": "Prof 3", "updated_at": _fila(client)["updated_at"]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.put(
        f"/api/grups/{DATA}",
        json={"grups": {"10:00": ["3-ESO-C", "1-ESO-A"]}, "professors": {}, "activitats": {}, "ocupats": {}},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("format", ["hores", "dia"])
def test_el_pdf_complet_porta_l_avis_del_substitut_de_mes_prioritat(client, format):
    # El PDF fa la mateixa validació que la ruta de validacions (abans hi
    # faltava el Dia i l'avís no hi sortia)
    _guardia_amb_alliberats(client)
    resp = client.get(f"/api/pdf/complete/{DATA}", params={"format": format})
    assert resp.status_code == 200, resp.text
    text = " ".join(text_pdf(resp.content))
    assert "disponible en lloc de Prof 3" in text, text[-600:]


def test_un_alliberat_te_mes_prioritat_que_una_guardia(client):
    client.put(f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["10:00"], "updated_at_map": {}})
    resp = client.put(
        f"/api/substitucions/{DATA}/10:00/Prof 15",
        json={"substitut": "Prof 3", "updated_at": _fila(client)["updated_at"]},
    )
    assert resp.status_code == 200, resp.text
    # Ara els grups de Prof 1 i Prof 30 no tenen classe: tots dos queden alliberats
    resp = client.put(
        f"/api/grups/{DATA}",
        json={"grups": {"10:00": ["3-ESO-C", "1-ESO-A"]}, "professors": {}, "activitats": {}, "ocupats": {}},
    )
    assert resp.status_code == 200, resp.text
    assert _fila(client)["substitut"] == "Prof 3"  # continua sent vàlid

    avisos = client.get(f"/api/pdf/{DATA}/validacions").json()["warnings"]
    assert any("(alliberat) disponible en lloc de Prof 3 (Guàrdia)" in a for a in avisos), avisos

    resp = client.post(f"/api/substitucions/{DATA}/reassign-problematics")
    assert resp.status_code == 200, resp.text
    fila = _fila(client)
    assert fila["substitut"] in ("Prof 1", "Prof 30")


def _amb_jornada_intensiva():
    """L'horari d'exemple fins al 30/04/2026 i, des de l'1/05, el mateix amb el
    PATI abans de les 10:00 (com una jornada intensiva amb unes altres franges)."""
    centre = amb_versions(("actual.xml", date(2026, 1, 1), date(2026, 4, 30)), ("futur.xml", date(2026, 5, 1), None))
    arbre = ET.parse(XML_EXEMPLE)
    for dia in arbre.getroot().iter("Day"):
        hores = dia.findall("Hour")
        pati = next(h for h in hores if h.get("name") == "PATI")
        dia.remove(pati)
        dia.insert(list(dia).index(next(h for h in hores if h.get("name") == "10:00")), pati)
    arbre.write(get_data_dir_for_institucio(centre) / "futur.xml", encoding="utf-8")
    return centre


@pytest.mark.parametrize(
    "data, ordre",
    [
        # El PATI a la seva franja, entre les 10:00 i les 11:30, i no al final
        ("2026-04-20", ["08:00", "10:00", "PATI", "11:30"]),
        # Amb l'horari de la data (jornada intensiva), el PATI abans de les 10:00
        ("2026-05-04", ["08:00", "PATI", "10:00", "11:30"]),
    ],
)
def test_ordre_dels_avisos_de_la_revisio_amb_el_pati(data, ordre):
    centre = _amb_jornada_intensiva()
    avisos = {
        hora: f"• {hora}: Prof {i} (alliberat) disponible en lloc de Prof 3 (Guàrdia)"
        for i, hora in enumerate(["PATI", "11:30", "10:00", "08:00"])
    }
    # Dins d'una hora, l'ordre en què arriben
    segon_de_les_10 = "• 10:00: Prof 9 (alliberat) disponible en lloc de Prof 8 (Guàrdia)"
    with get_data_db_session(centre, lectura=True) as db:
        validacio = valida_dia(
            db,
            date.fromisoformat(data),
            centre,
            lambda _dia: [*avisos.values(), segon_de_les_10],
            amb_substitucions=True,
            amb_vigilancies=True,
        )
    esperat = [avisos[hora] for hora in ordre]
    esperat.insert(ordre.index("10:00") + 1, segon_de_les_10)
    assert validacio["warnings"] == esperat


# ------------------------------ la millora final de «Reassigna problemàtics»


class DiaDeProva:
    nom_del_dia = "Dilluns"
    files = []
    alliberats = defaultdict(set)
    absents_per_hora = defaultdict(set)
    vigilants_per_hora = defaultdict(set)


class MotorDeProva:
    _obtenir_categoria = staticmethod(categoria_de_prioritat)


class DisponiblesDeProva:
    def get_tots_disponibles(self, _dia, _hora, _grups_alliberats):
        return [
            ("Prof Mateix Nivell", "mateix nivell", "mateix nivell"),
            ("Prof Alliberat", "alliberat", "tenia classe"),
        ]


def test_reassignar_una_guardia_tria_l_alliberat_i_no_el_primer_que_la_millora(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"alliberat"}, {"mateix nivell"}, {"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True, True, True])
    gestors = (MotorDeProva(), None, DisponiblesDeProva(), None)
    millors = MillorsSubstituts(DiaDeProva(), gestors)

    millor = millors.millor(
        FilaSubstitucio(
            **{
                "hora": "09:00",
                "substitut": "Prof Guàrdia",
                "tipus_substitut": "disponible (Guàrdia)",
            }
        )
    )

    assert millor[:3] == ("Prof Alliberat", "alliberat", "tenia classe")
