"""
Seguretat de totes les rutes, amb l'app sencera (main.app: els permisos de
cada router com a main.py).

INVENTARI: cada ruta (mètode i camí) és en un dels quatre grups, amb el rol
mínim que la pot fer servir i una petició vàlida (la mateixa per a totes les
comprovacions; així, si es rebutja, és pels permisos):
- PUBLICA: sense sessió (entrar, sortir i les comprovacions de salut).
- SESSIO: amb sessió, qualsevol rol, sobre el mateix usuari (el perfil).
- GLOBAL: del superadmin, que ha de poder tocar altres centres (els centres,
  canviar de centre, esborrar del tot un usuari).
- CENTRE: lligades al centre de qui fa la petició.
Una ruta nova sense classificar fa fallar `test_totes_les_rutes_son_a_l_inventari`.

Dos centres temporals fets només amb el que hi ha al repositori: l'XML
d'exemple, amb els noms dels professors canviats («Prof 1» → «MARCAA 1» al
centre A, «MARCAB 1» al B), i les dades que el mateix test crea per l'API, amb
una marca a cada cosa (nivells, aules, cursos, usuaris, substitucions,
vigilàncies, preferències...). El centre per defecte del servidor (config) és el B: si una
ruta en fes servir el per defecte en lloc del de la sessió, es veuria.

Tres comprovacions independents:
a) Autenticació: sense sessió, amb un testimoni que no és bo o amb un
   testimoni d'un altre centre, 401; amb la sessió d'un centre desactivat,
   403. Les públiques responen sense sessió.
b) Autorització: les rutes de l'admin o del superadmin rebutgen (403) els
   rols inferiors.
c) Aïllament: un usuari del centre A (amb el rol mínim de cada ruta) fa totes
   les peticions de l'inventari: cap resposta no porta res del B, i després
   de cadascuna l'estat de les dues BD (totes les taules), dels fitxers de les
   dues carpetes i dels usuaris de cada centre és el que toca: les lectures no
   canvien res; les escriptures canvien només el centre A; les globals, només
   el centre que diuen.
Les peticions rebutjades a (a) i (b) tampoc no canvien res.
"""

import hashlib
import io
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from PIL import Image
from suport_api import CONTRASENYA, XML_EXEMPLE, crea_usuari, entra, nova_institucio, text_pdf
from suport_main import app_sencera
from suport_planificador import alliberaments

from auth import security
from config.settings import config
from database import DATA_BASE_DIR, AuthSessionLocal, get_data_db_session
from helpers import avui, get_horari, invalidar_horari
from models import User
from rate_limit import limiter
from repositories import ConfiguracioRepository

DATA = "2026-10-26"  # dilluns amb substitucions i vigilàncies (les crea _prepara)
DIA_A_PURGAR = "2026-09-07"  # amb substitucions, perquè la purga hi tingui què esborrar
DILLUNS_LLIURE = "2026-11-02"

PUBLICA, SESSIO, GLOBAL, CENTRE = "pública", "sessió", "global del superadmin", "del centre"
USER, ADMIN, SUPER = "user", "admin", "super_admin"
INFERIORS = {USER: [], ADMIN: [USER], SUPER: [USER, ADMIN]}


@dataclass
class Ruta:
    grup: str
    rol: Optional[str]  # el mínim (None: pública)
    url: str  # amb {camps} del context
    kw: dict = field(default_factory=dict)  # json, params, files: textos amb {camps}, o funcions del context
    escriu: tuple = ()  # els centres que canvia: "a" (el de la sessió) o "b" (només les globals)
    recull: Optional[Callable] = None  # (resposta, context): desa el que necessiten les següents
    comprova: Optional[Callable] = None  # (client, context): comprovacions pròpies després
    esperat: int = 200


def _r(grup, rol, metode, cami, url=None, **kw):
    camps = {k: kw.pop(k) for k in ("escriu", "recull", "comprova", "esperat") if k in kw}
    return (metode, cami), Ruta(grup, rol, url or cami, kw, **camps)


def _id(clau, camp="id"):
    def recull(resp, ctx):
        ctx[clau] = resp.json()[camp]

    return recull


def _csv(resp, ctx):
    ctx["csv"] = resp.content


def _vigilancies_de_les_deu(resp, ctx):
    ctx["ordre_10"] = [v["id"] for v in resp.json() if v["hora"] == "10:00"][::-1]


def _darrer_id(centre, taula):
    con = sqlite3.connect(DATA_BASE_DIR / centre / "gestor.db")
    try:
        return con.execute(f"SELECT max(id) FROM {taula}").fetchone()[0]
    finally:
        con.close()


def _logo(ctx):
    imatge = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(imatge, format="PNG")
    return {"file": ("logo.png", imatge.getvalue(), "image/png")}


def _treballa_al_centre_b(client, ctx):
    """El superadmin, després de canviar de centre, veu el B."""
    assert "MARCAB" in client.get("/api/settings").text
    resp = client.post("/api/users/profile/institucio", json={"institucio": ctx["A"]})
    assert resp.status_code == 200
    assert "MARCAA" in client.get("/api/settings").text


def _titular_posat(client, ctx):
    vigilancies = client.get(f"/api/vigilancies/{DATA}").json()
    assert [v["vigilant"] for v in vigilancies if v["id"] == ctx["vigilancia"]] == ["MARCAA 48"]


def _centre_nou_existeix(_client, ctx):
    assert (DATA_BASE_DIR / ctx["nou"] / "gestor.db").exists()


def _centre_nou_inactiu(_client, ctx):
    assert (DATA_BASE_DIR / ctx["nou"] / ".inactive").exists()


def _centre_nou_actiu(_client, ctx):
    assert not (DATA_BASE_DIR / ctx["nou"] / ".inactive").exists()


# L'ordre és el de la comprovació (c): les escriptures de cada objecte, de crear a esborrar
INVENTARI = dict(
    [
        # ----------------------------------------------------------- públiques
        _r(PUBLICA, None, "GET", "/"),
        _r(PUBLICA, None, "GET", "/api/health"),
        _r(PUBLICA, None, "POST", "/api/login", json={"username": "{admin_a}", "password": CONTRASENYA}),
        # ------------------------------------------- configuració d'exàmens
        _r(CENTRE, ADMIN, "GET", "/api/config/nivells"),
        _r(CENTRE, ADMIN, "POST", "/api/config/nivells", json={"codi": "{M}-NIV"}, escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/config/nivells/{codi}/assignacions", "/api/config/nivells/1-BAT/assignacions"),
        _r(CENTRE, ADMIN, "DELETE", "/api/config/nivells/{codi}", "/api/config/nivells/{M}-NIV", escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/config/assignatures/{nivell}", "/api/config/assignatures/1-BAT"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/config/assignatures/{nivell}",
            "/api/config/assignatures/1-BAT",
            json={"nom": "{M}-ASSIG"},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/config/assignatures/{nivell}/{nom}",
            "/api/config/assignatures/1-BAT/{M}-ASSIG",
            json={"nou_nom": "{M}-ASSIG2"},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "DELETE",
            "/api/config/assignatures/{nivell}/{nom}",
            "/api/config/assignatures/1-BAT/{M}-ASSIG2",
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "GET", "/api/config/grups/{nivell}", "/api/config/grups/1-BAT"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/config/grups/{nivell}",
            "/api/config/grups/1-BAT",
            json={"codi": "1-BAT-Z"},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/config/grups/{codi}",
            "/api/config/grups/1-BAT-Z",
            json={"nou_nom": "1-BAT-Y"},
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "GET", "/api/config/grups/{codi}/assignacions", "/api/config/grups/1-BAT-A/assignacions"),
        _r(CENTRE, ADMIN, "DELETE", "/api/config/grups/{codi}", "/api/config/grups/1-BAT-Y", escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/config/aules"),
        _r(CENTRE, ADMIN, "POST", "/api/config/aules", json={"codi": "{M}-AULA"}, escriu="a"),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/config/aules/{codi}",
            "/api/config/aules/{M}-AULA",
            json={"nou_nom": "{M}-AULA2"},
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "DELETE", "/api/config/aules/{codi}", "/api/config/aules/{M}-AULA2", escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/config/assignacions"),
        _r(CENTRE, ADMIN, "GET", "/api/config/assignacions-obsoletes"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/config/assignacions",
            json={"assignatura": "1.1 {M} 13", "grup": "1-BAT-A", "titular": "{M} 13", "aula": "A01"},
            escriu="a",
            recull=_id("assignacio"),
        ),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/config/assignacions/{assignacio_id}",
            "/api/config/assignacions/{assignacio}",
            json={"aula": "A02"},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "DELETE",
            "/api/config/assignacions/{assignacio_id}",
            "/api/config/assignacions/{assignacio}",
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "GET", "/api/config/exportar-assignacions-csv", recull=_csv),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/config/importar-assignacions-csv/dry-run",
            files=lambda ctx: {"file": ("a.csv", ctx["csv"], "text/csv")},
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/config/importar-assignacions-csv",
            files=lambda ctx: {
                "file": ("a.csv", ctx["csv"] + b"1-BAT,1.1 MARCAA 13,1-BAT-B,MARCAA 13,A04\r\n", "text/csv")
            },
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "DELETE", "/api/config/assignacions", json={"tot": True}, escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/config/importar-assignacions/preview"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/config/importar-assignacions/dry-run",
            json={"propostes": [{"assignatura": "1.1 {M} 13", "grup": "1-BAT-A", "nivell": "1-BAT"}]},
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/config/importar-assignacions",
            json={
                "propostes": [
                    {"assignatura": "1.1 {M} 13", "grup": "1-BAT-A", "nivell": "1-BAT"},
                    # El titular de l'examen de les vigilàncies: té classe amb 1-BAT-A a les 10:00
                    {"assignatura": "{M}-EXAMEN", "grup": "1-BAT-A", "nivell": "1-BAT", "titular": "{M} 48"},
                ]
            },
            escriu="a",
        ),
        # ------------------------------------------------- grups i alliberats
        _r(CENTRE, USER, "GET", "/api/grups/{data}", f"/api/grups/{DATA}"),
        _r(
            CENTRE,
            USER,
            "PUT",
            "/api/grups/{data}",
            f"/api/grups/{DATA}",
            # 1-BAT-A, també a les 10:00: allibera el titular de l'examen de les vigilàncies
            json={"grups": {"09:00": ["1-BAT-A"], "10:00": ["1-BAT-A"]}},
            escriu="a",
        ),
        _r(
            CENTRE,
            USER,
            "POST",
            "/api/grups/periode",
            json={"tipus": "professor", "clau": "{M} 18", "hores": ["09:00"], "data": DILLUNS_LLIURE},
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "GET", "/api/grups-amagats"),
        _r(CENTRE, ADMIN, "PUT", "/api/grups-amagats", json={"grups": ["{M}-AMAGAT"]}, escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/prioritats/activitats-alliberables"),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/prioritats/activitats-alliberables",
            json={"activitats": ["{M}-ACT", "Reforç"], "per_defecte": ["Reforç"]},
            escriu="a",
        ),
        _r(CENTRE, USER, "GET", "/api/grups/reforcos/{activitat}", "/api/grups/reforcos/Reforç", params={"data": DATA}),
        _r(CENTRE, ADMIN, "GET", "/api/config/abreviatures"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/config/abreviatures",
            json={"grups_originals": "1-BAT-B,2-BAT-B", "abreviatura": "{M}-2B"},
            escriu="a",
            recull=_id("abreviatura"),
        ),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/config/abreviatures/{abreviatura_id}",
            "/api/config/abreviatures/{abreviatura}",
            json={"abreviatura": "{M}-2BB"},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "DELETE",
            "/api/config/abreviatures/{abreviatura_id}",
            "/api/config/abreviatures/{abreviatura}",
            escriu="a",
        ),
        # ------------------------------------------------------------- PDF
        _r(CENTRE, USER, "GET", "/api/pdf/preferences"),
        _r(CENTRE, USER, "PUT", "/api/pdf/preferences", json={"substitucions": {"marca": "{M}"}}, escriu="a"),
        _r(CENTRE, USER, "GET", "/api/pdf/{data}/validacions", f"/api/pdf/{DATA}/validacions"),
        _r(CENTRE, USER, "GET", "/api/pdf/complete/{data}", f"/api/pdf/complete/{DATA}"),
        _r(
            CENTRE,
            USER,
            "GET",
            "/api/pdf/vigilancies/comptes-sense-nivell",
            params={"data_inici": DATA, "data_final": DATA},
        ),
        _r(
            CENTRE,
            USER,
            "GET",
            "/api/pdf/vigilancies/interval",
            params={"data_inici": "2026-09-07", "data_final": "2026-10-30"},
        ),
        _r(CENTRE, USER, "GET", "/api/pdf/vigilancies/{data}", f"/api/pdf/vigilancies/{DATA}"),
        _r(CENTRE, USER, "POST", "/api/pdf/disponibles-tots-dies", json={"data_inici": DATA}),
        # ------------------------------------------------------- vigilàncies
        _r(CENTRE, USER, "GET", "/api/vigilancies/config", params={"data": DATA}),
        _r(
            CENTRE,
            USER,
            "POST",
            "/api/vigilancies/{data}",
            f"/api/vigilancies/{DATA}",
            json={"hora": "10:00", "tipus": "{M}-EXAMEN", "grups": "1-BAT-A", "aula": "A02", "nivell": "1-BAT"},
            escriu="a",
            recull=lambda resp, ctx: ctx.update(vigilancia=resp.json()["vigilancia"]["id"]),
        ),
        _r(CENTRE, USER, "GET", "/api/vigilancies/{data}", f"/api/vigilancies/{DATA}", recull=_vigilancies_de_les_deu),
        _r(CENTRE, USER, "GET", "/api/vigilancies/{data}/ordre", f"/api/vigilancies/{DATA}/ordre"),
        _r(
            CENTRE,
            USER,
            "PUT",
            "/api/vigilancies/{data}/ordre",
            f"/api/vigilancies/{DATA}/ordre",
            json=lambda ctx: {"hora": "10:00", "ids": ctx["ordre_10"]},
            escriu="a",
        ),
        _r(
            CENTRE,
            USER,
            "GET",
            "/api/vigilancies/{data}/{hora}/disponibles",
            f"/api/vigilancies/{DATA}/09:00/disponibles",
        ),
        _r(
            CENTRE,
            USER,
            "GET",
            "/api/vigilancies/{data}/{hora}/professor",
            f"/api/vigilancies/{DATA}/09:00/professor",
            params={"nom": "{M} 1"},
        ),
        _r(
            CENTRE,
            USER,
            "POST",
            "/api/vigilancies/{data}/disponibles-batch",
            f"/api/vigilancies/{DATA}/disponibles-batch",
            json={"queries": [{"hora": "09:00"}, {"hora": "10:00"}]},
        ),
        _r(
            CENTRE,
            USER,
            "PUT",
            "/api/vigilancies/{data}/{vig_id}",
            f"/api/vigilancies/{DATA}/{{vigilancia}}",
            json={"vigilant": "{M} 18", "force": True},
            escriu="a",
        ),
        _r(CENTRE, USER, "POST", "/api/vigilancies/{data}/clear", f"/api/vigilancies/{DATA}/clear", escriu="a"),
        _r(
            CENTRE,
            USER,
            "POST",
            "/api/vigilancies/{data}/assign/titulars",
            f"/api/vigilancies/{DATA}/assign/titulars",
            escriu="a",
            comprova=_titular_posat,
        ),
        _r(
            CENTRE,
            USER,
            "POST",
            "/api/vigilancies/{data}/assign/pendents",
            f"/api/vigilancies/{DATA}/assign/pendents",
            params={"disponibles": "true"},
            escriu="a",
        ),
        _r(CENTRE, USER, "POST", "/api/vigilancies/{data}/sort", f"/api/vigilancies/{DATA}/sort", escriu="a"),
        _r(
            CENTRE,
            USER,
            "DELETE",
            "/api/vigilancies/{data}/{vig_id}",
            f"/api/vigilancies/{DATA}/{{vigilancia}}",
            params={"force": "true"},
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "GET", "/api/config/afinitats"),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/config/afinitats",
            json={"afinitats": [{"base": "1-BAT", "ordre": ["2-BAT"]}]},
            escriu="a",
        ),
        # ----------------------------------------------------- substitucions
        _r(CENTRE, USER, "GET", "/api/substitucions/{data}", f"/api/substitucions/{DATA}"),
        _r(
            CENTRE,
            USER,
            "PUT",
            "/api/substitucions/{data}/absencies/{professor}",
            f"/api/substitucions/{DATA}/absencies/{{M}} 5",
            json={"hores_absencia": ["09:00", "10:00"], "force": True},
            escriu="a",
        ),
        _r(CENTRE, USER, "POST", "/api/substitucions/{data}/generar", f"/api/substitucions/{DATA}/generar", escriu="a"),
        _r(
            CENTRE,
            USER,
            "PUT",
            "/api/substitucions/{data}/{hora}/{professor}",
            f"/api/substitucions/{DATA}/15:00/{{M}} 1",
            json={"substitut": "", "force": True},
            escriu="a",
        ),
        _r(
            CENTRE,
            USER,
            "POST",
            "/api/substitucions/{data}/reassign-problematics",
            f"/api/substitucions/{DATA}/reassign-problematics",
            escriu="a",
        ),
        _r(
            CENTRE,
            USER,
            "GET",
            "/api/substitucions/{data}/hores-professor/{professor}",
            f"/api/substitucions/{DATA}/hores-professor/{{M}} 1",
        ),
        _r(
            CENTRE,
            USER,
            "GET",
            "/api/substitucions/{data}/{hora}/disponibles",
            f"/api/substitucions/{DATA}/09:00/disponibles",
        ),
        _r(
            CENTRE,
            USER,
            "POST",
            "/api/substitucions/{data}/disponibles-batch",
            f"/api/substitucions/{DATA}/disponibles-batch",
            json={"hores": ["09:00", "10:00"]},
        ),
        # ---------------------------------------------------- configuració
        _r(CENTRE, ADMIN, "GET", "/api/settings"),
        _r(CENTRE, ADMIN, "PUT", "/api/settings", json={"data_inici_estadistiques": "2026-09-01"}, escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/settings/idiomes"),
        _r(CENTRE, ADMIN, "POST", "/api/files/upload-logo", files=_logo, escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/files/logo"),
        _r(
            CENTRE,
            ADMIN,
            "GET",
            "/api/settings/xml-versions",
            recull=lambda r, ctx: ctx.update(xml=r.json()["versions"][0]["id"]),
        ),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/settings/xml-versions/{version_id}",
            "/api/settings/xml-versions/{xml}",
            json={"data_inici": "2026-07-01"},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/files/upload-xml",
            files=lambda ctx: {"file": ("horari.xml", ctx["xml_a"] + b"<!-- una altra versio -->", "text/xml")},
            data={"data_inici": "2026-12-01"},
            escriu="a",
            recull=lambda _resp, ctx: ctx.update(xml_nou=_darrer_id(ctx["A"], "xml_versions")),
        ),
        _r(
            CENTRE,
            ADMIN,
            "DELETE",
            "/api/settings/xml-versions/{version_id}",
            "/api/settings/xml-versions/{xml_nou}",
            escriu="a",
        ),
        _r(CENTRE, USER, "GET", "/api/cursos/validacio-xml"),
        _r(CENTRE, USER, "GET", "/api/cursos"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/cursos",
            json={"nom": "{M}-CURS", "data_inici": "2027-09-01"},
            escriu="a",
            recull=_id("curs"),
        ),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/cursos/{curs_id}",
            "/api/cursos/{curs}",
            json={"nom": "{M}-CURS2", "data_inici": "2027-09-02"},
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "DELETE", "/api/cursos/{curs_id}", "/api/cursos/{curs}", escriu="a"),
        # -------------------------------------------------- l'horari (XML)
        _r(CENTRE, USER, "GET", "/api/config"),
        _r(CENTRE, USER, "GET", "/api/professors"),
        _r(CENTRE, USER, "GET", "/api/hores"),
        _r(CENTRE, USER, "GET", "/api/horari/professors/all"),
        _r(CENTRE, USER, "GET", "/api/horari/professors"),
        _r(CENTRE, USER, "GET", "/api/horari/grups/detectar"),
        _r(CENTRE, USER, "GET", "/api/horari/assignatures/detectar"),
        # ------------------------------------------------------ estadístiques
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/resum"),
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/professors"),
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/temporal"),
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/classes"),
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/classes/detall", params={"grups": "1-BAT-A"}),
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/taula"),
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/professor/{professor}", "/api/estadistiques/professor/{M} 1"),
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/franges", params={"dia": "Dilluns", "hora": "09:00"}),
        _r(CENTRE, ADMIN, "GET", "/api/estadistiques/hores"),
        _r(
            CENTRE,
            ADMIN,
            "GET",
            "/api/informes/direccio",
            params={"data_inici": "2026-09-01", "data_final": "2026-10-31"},
        ),
        _r(
            CENTRE,
            ADMIN,
            "GET",
            "/api/informes/professor",
            params={"data_inici": "2026-09-01", "data_final": "2026-10-31", "professor": "{M} 1"},
        ),
        _r(
            CENTRE,
            ADMIN,
            "GET",
            "/api/informes/professors-llista",
            params={"data_inici": "2026-09-01", "data_final": "2026-10-31"},
        ),
        # ---------------------------------------------------------- prioritats
        _r(CENTRE, ADMIN, "GET", "/api/prioritats/categories"),
        _r(CENTRE, ADMIN, "GET", "/api/prioritats/assignatures"),
        _r(CENTRE, ADMIN, "GET", "/api/prioritats/no-substituir"),
        _r(CENTRE, ADMIN, "POST", "/api/prioritats/no-substituir", json={"assignatura": "{M}-NS"}, escriu="a"),
        _r(
            CENTRE,
            ADMIN,
            "DELETE",
            "/api/prioritats/no-substituir/{assignatura}",
            "/api/prioritats/no-substituir/{M}-NS",
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/prioritats/desar-tot",
            json={"ordre_categories": [["alliberat"], ["Guàrdia", "{M}-ACT"]], "pesos": {"Guàrdia": 2}},
            escriu="a",
        ),
        # ------------------------------------------------- absències cobertes
        _r(CENTRE, ADMIN, "GET", "/api/absencies-cobertes"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/absencies-cobertes",
            json={"professor": "{M} 3", "data_inici": "2026-11-09", "data_final": "2026-11-13", "motiu": "{M}"},
            escriu="a",
            recull=_id("absencia"),
        ),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/absencies-cobertes/{absencia_id}",
            "/api/absencies-cobertes/{absencia}",
            json={"motiu": "{M} canviat"},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "DELETE",
            "/api/absencies-cobertes/{absencia_id}",
            "/api/absencies-cobertes/{absencia}",
            escriu="a",
        ),
        # ------------------------------------------------------- planificador
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/motors"),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/config"),
        _r(CENTRE, ADMIN, "PUT", "/api/scheduler/config", json={"durada_titular": 2}, escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/restriccions"),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/scheduler/restriccions",
            json={"restriccions": {"preferencies": {"mateix_dia": [{"assignatures": ["{M}-A", "{M}-B"]}]}}},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/scheduler/restriccions/pin",
            json={"pins": [{"nom": "{M}-FIX (1-BAT)", "dia": "Dilluns", "hora": "09:00"}]},
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "POST", "/api/scheduler/restriccions/treure-inexistents", escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/costos-professors"),
        _r(
            CENTRE,
            ADMIN,
            "PUT",
            "/api/scheduler/costos-professors",
            json={"globals": {"substitucio": 7}, "individuals": {"{M} 2": {"substitucio": 9}}},
            escriu="a",
        ),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/dates"),
        _r(CENTRE, ADMIN, "PUT", "/api/scheduler/dates", json={"selected_dates": ["2026-09-28"]}, escriu="a"),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/sessions-info"),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/assignatures-actives"),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/horari"),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/ultim-resultat"),
        _r(CENTRE, ADMIN, "GET", "/api/scheduler/curs-dates", params={"dates": "2026-09-28"}),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/scheduler/analisi",
            json={"data_inici": "2026-09-28", "selected_dates": ["2026-09-28"]},
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/scheduler/recalcular-cost",
            json={"horari": {"dies": [{"dia": "Dilluns", "data": "2026-09-28", "sessions": []}]}},
            escriu="a",  # el desa com a últim horari
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/scheduler/publicar",
            json={
                "horari": {"dies": [{"dia": "Dilluns", "data": DILLUNS_LLIURE, "sessions": []}]},
                "setmanes": [{"Dilluns": DILLUNS_LLIURE}],
                "dry_run": True,
            },
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/scheduler/generate",
            json={"data_inici": "2026-09-28", "selected_dates": ["2026-09-28"], "nivells_actius": ["1-BAT"]},
            escriu="a",
        ),
        # ------------------------------------------------------------- dades
        _r(CENTRE, ADMIN, "GET", "/api/dades/professors"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/dades/professors/reanomena",
            json={"nom_actual": "{M} 99", "nom_nou": "{M} 99 bis"},
            escriu="a",
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/dades/purga/analitzar",
            json={"data_inici": DIA_A_PURGAR, "data_final": DIA_A_PURGAR},
        ),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/dades/purga/executar",
            json={"data_inici": DIA_A_PURGAR, "data_final": DIA_A_PURGAR, "confirmar": True},
            escriu="a",
        ),
        # ------------------------------------------------------------ usuaris
        _r(CENTRE, ADMIN, "GET", "/api/users"),
        _r(
            CENTRE,
            ADMIN,
            "POST",
            "/api/users",
            json={"username": "{M}_nou", "password": "contrasenya-de-l-usuari-nou", "role": "user"},
            escriu="a",
            recull=_id("usuari"),
        ),
        _r(CENTRE, ADMIN, "PUT", "/api/users/{user_id}", "/api/users/{usuari}", json={"role": "admin"}, escriu="a"),
        _r(CENTRE, ADMIN, "DELETE", "/api/users/{user_id}", "/api/users/{usuari}", escriu="a"),
        # ------------------------------------------- centres i superadmin
        _r(CENTRE, ADMIN, "GET", "/api/settings/institucions"),
        _r(
            GLOBAL,
            SUPER,
            "POST",
            "/api/settings/institucions",
            json={"nom": "{nou}", "display_name": "Centre nou"},
            comprova=_centre_nou_existeix,
        ),
        _r(
            GLOBAL,
            SUPER,
            "PUT",
            "/api/settings/institucions/{slug}",
            "/api/settings/institucions/{B}",
            json={"display_name": "MARCAB canviat pel superadmin"},
            escriu="b",
        ),
        _r(
            GLOBAL,
            SUPER,
            "DELETE",
            "/api/settings/institucions/{slug}",
            "/api/settings/institucions/{nou}",
            # Des de la web, només desactivar-lo (l'esborrat definitiu, des del servidor)
            json={"mode": "soft", "confirm": "{nou}"},
            comprova=_centre_nou_inactiu,
        ),
        _r(
            GLOBAL,
            SUPER,
            "PUT",
            "/api/settings/institucions/{slug}/status",
            "/api/settings/institucions/{nou}/status",
            json={"active": True},
            comprova=_centre_nou_actiu,
        ),
        _r(GLOBAL, SUPER, "DELETE", "/api/users/{user_id}/hard", "/api/users/{usuari_b}/hard", escriu="b"),
        _r(
            GLOBAL,
            SUPER,
            "POST",
            "/api/users/profile/institucio",
            json={"institucio": "{B}"},
            comprova=_treballa_al_centre_b,
        ),
        # ------------------------------------- el perfil (al final: tanca sessions)
        _r(SESSIO, USER, "GET", "/api/users/profile"),
        _r(SESSIO, USER, "POST", "/api/users/profile/tancar-altres-sessions", escriu="a"),
        _r(
            SESSIO,
            USER,
            "PUT",
            "/api/users/profile/password",
            json={"current_password": CONTRASENYA, "new_password": "una-altra-contrasenya-llarga"},
            escriu="a",
        ),
        _r(PUBLICA, None, "POST", "/api/logout"),
    ]
)


# ------------------------------------------------------------------ entorn


def _xml(marca: str) -> bytes:
    """L'XML d'exemple amb els professors («Prof 1») dient-se «<marca> 1»."""
    return XML_EXEMPLE.read_text(encoding="utf-8").replace("Prof ", f"{marca} ").encode("utf-8")


def _prepara(client, marca: str) -> None:
    """L'horari i una mica de tot, amb la marca del centre: la configuració
    d'exàmens, substitucions i vigilàncies del dia DATA, substitucions del dia
    a purgar..."""
    peticions = [
        (
            "POST",
            "/api/files/upload-xml",
            {"files": {"file": ("horari.xml", _xml(marca), "text/xml")}, "data": {"data_inici": "2026-07-23"}},
        ),
        *[("POST", "/api/config/nivells", {"json": {"codi": nivell}}) for nivell in ("1-BAT", "2-BAT")],
        *[
            ("POST", f"/api/config/grups/{grup[:5]}", {"json": {"codi": grup}})
            for grup in ("1-BAT-A", "1-BAT-B", "2-BAT-A", "2-BAT-B")
        ],
        *[("POST", "/api/config/aules", {"json": {"codi": f"A0{i}"}}) for i in range(1, 5)],
        ("POST", "/api/config/nivells", {"json": {"codi": f"{marca}-NIVELL"}}),
        ("POST", "/api/config/aules", {"json": {"codi": f"{marca}-AULA-0"}}),
        ("POST", "/api/config/assignatures/1-BAT", {"json": {"nom": f"{marca}-ASSIGNATURA"}}),
        ("POST", "/api/config/abreviatures", {"json": {"grups_originals": "1-BAT-A,2-BAT-A", "abreviatura": marca}}),
        ("POST", "/api/cursos", {"json": {"nom": f"{marca}-CURS-0", "data_inici": "2026-09-01"}}),
        ("POST", "/api/prioritats/no-substituir", {"json": {"assignatura": f"{marca}-NO-SUBSTITUIR"}}),
        ("PUT", "/api/grups-amagats", {"json": {"grups": [f"{marca}-GRUP-AMAGAT"]}}),
        ("PUT", "/api/pdf/preferences", {"json": {"vigilancies": {"marca": marca}}}),
        ("PUT", "/api/scheduler/costos-professors", {"json": {"individuals": {f"{marca} 2": {"substitucio": 4}}}}),
        # Les hores on poden anar els exàmens de 1-BAT el dia que es genera (inventari)
        ("PUT", "/api/scheduler/config", {"json": {"alliberaments_per_nivell": alliberaments(["2026-09-28"])}}),
        (
            "POST",
            f"/api/vigilancies/{DATA}",
            {"json": {"hora": "10:00", "tipus": marca, "grups": "1-BAT-A", "aula": "A01", "nivell": "1-BAT"}},
        ),
        *[
            peticio
            for dia in (DATA, DIA_A_PURGAR)
            for peticio in (
                (
                    "PUT",
                    f"/api/substitucions/{dia}/absencies/{marca} 1",
                    {"json": {"hores_absencia": ["12:30", "15:00", "16:00"], "force": True}},
                ),
                ("POST", f"/api/substitucions/{dia}/generar", {}),
            )
        ],
        (
            "POST",
            "/api/absencies-cobertes",
            {
                "json": {
                    "professor": f"{marca} 3",
                    "data_inici": "2026-11-02",
                    "data_final": "2026-11-06",
                    "motiu": marca,
                }
            },
        ),
    ]
    for metode, url, kw in peticions:
        resp = client.request(metode, url, **kw)
        assert resp.status_code == 200, (url, resp.text)


def _centre(marca: str) -> str:
    nom = nova_institucio()
    with get_data_db_session(nom) as db:
        ConfiguracioRepository.set(db, "institucio_display_name", f"{marca} centre")
        db.commit()
    return nom


def _client():
    # Sense aixecar les excepcions: un error intern ha de sortir com a 500
    return TestClient(app_sencera(), base_url="https://testserver", raise_server_exceptions=False)


def _usuari(nom):
    with AuthSessionLocal() as db:
        return db.query(User).filter(User.username == nom).one()


@pytest.fixture(scope="module")
def entorn():
    app_sencera()
    limiter.reset()
    a, b, inactiu = _centre("MARCAA"), _centre("MARCAB"), _centre("MARCAC")
    # El centre per defecte del servidor és el B (ja mentre es preparen els centres)
    mp = pytest.MonkeyPatch()
    mp.setitem(config.global_data, "institucio", b)
    mp.setenv("APP_INSTITUCIO", b)
    try:
        ctx = {"A": a, "B": b, "M": "MARCAA", "nou": f"seg_nou_{uuid.uuid4().hex[:6]}"}
        # Els ids que la comprovació (c) recull de les respostes; abans, uns de vàlids
        ctx.update(assignacio=1, abreviatura=1, vigilancia="1", xml=1, xml_nou=1, curs=1, absencia=1, usuari=1)
        ctx.update(csv=b"assignatura;grup\n", ordre_10=[])
        noms = {}
        for clau, centre, rol in [
            ("admin_a", a, ADMIN),
            ("user_a", a, USER),
            ("admin_b", b, ADMIN),
            ("user_b", b, USER),
            ("super", a, SUPER),
            ("admin_inactiu", inactiu, ADMIN),
        ]:
            noms[clau] = f"{clau}_{uuid.uuid4().hex[:6]}"
            crea_usuari(noms[clau], centre, rol)
        ctx.update(noms)
        clients = {clau: entra(_client(), nom) for clau, nom in noms.items()}
        _prepara(clients["admin_a"], "MARCAA")
        _prepara(clients["admin_b"], "MARCAB")
        # La primera càrrega de l'horari d'avui sincronitza la taula de professors
        # (helpers.get_horari): que no ho faci la primera ruta de l'inventari que el llegeixi
        for centre in (a, b):
            invalidar_horari(centre)
            get_horari(centre, data_iso=avui())
        ctx["usuari_b"] = crea_usuari(f"MARCAB_{uuid.uuid4().hex[:6]}", b, USER)
        ctx["xml_a"] = _xml("MARCAA")
        con = sqlite3.connect(DATA_BASE_DIR / a / "gestor.db")
        with con:
            con.execute("INSERT INTO professors (nom, actiu) VALUES ('MARCAA 99', 0)")
        con.close()
        config.set_institucio_activa(inactiu, False)
        limiter.reset()
        yield {"ctx": ctx, "clients": clients, "centres": (a, b)}
    finally:
        mp.undo()


def _estat(centre: str) -> dict:
    """Totes les taules de la BD, els fitxers de la carpeta i els usuaris del centre."""
    carpeta = DATA_BASE_DIR / centre
    con = sqlite3.connect(f"file:{carpeta / 'gestor.db'}?mode=ro", uri=True)
    try:
        taules = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        bd = {t: sorted(map(repr, con.execute(f'SELECT * FROM "{t}"'))) for t in taules}
    finally:
        con.close()
    fitxers = {
        str(f.relative_to(carpeta)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in carpeta.rglob("*")
        if f.is_file() and not f.name.startswith("gestor.db")
    }
    con = sqlite3.connect(f"file:{os.environ['AUTH_DB_PATH']}?mode=ro", uri=True)
    try:
        usuaris = sorted(map(repr, con.execute("SELECT * FROM users WHERE institucio = ?", (centre,))))
    finally:
        con.close()
    return {"bd": bd, "fitxers": fitxers, "usuaris": usuaris}


def _diferencies(abans: dict, despres: dict) -> list:
    return [
        f"{part}/{clau}"
        for part in abans
        for clau in sorted(set(abans[part]) | set(despres[part]) if isinstance(abans[part], dict) else [""])
        if (abans[part].get(clau) if isinstance(abans[part], dict) else abans[part])
        != (despres[part].get(clau) if isinstance(despres[part], dict) else despres[part])
    ]


def _resol(valor, ctx):
    if callable(valor):
        return valor(ctx)
    if isinstance(valor, str):
        return valor.format(**ctx)
    if isinstance(valor, bytes):
        return valor
    if isinstance(valor, dict):
        return {_resol(k, ctx): _resol(v, ctx) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_resol(v, ctx) for v in valor]
    return valor


def _peticio(client, clau, ruta, ctx):
    metode, _ = clau
    return client.request(metode, _resol(ruta.url, ctx), **_resol(ruta.kw, ctx))


def _rutes_de_l_app():
    rutes = set()
    for ruta in app_sencera().routes:
        candidates = ruta.original_router.routes if hasattr(ruta, "original_router") else [ruta]
        for r in candidates:
            if isinstance(r, APIRoute):
                rutes |= {(m, r.path) for m in r.methods}
    return rutes


# ----------------------------------------------------------------- l'inventari


def test_totes_les_rutes_son_a_l_inventari():
    """Una ruta nova s'ha de classificar (i tenir una petició vàlida); una
    d'esborrada, treure."""
    app_rutes = _rutes_de_l_app()
    assert app_rutes - set(INVENTARI) == set(), "rutes sense classificar"
    assert set(INVENTARI) - app_rutes == set(), "rutes de l'inventari que ja no hi són"


def test_l_inventari_es_coherent():
    for clau, ruta in INVENTARI.items():
        assert ruta.grup in (PUBLICA, SESSIO, GLOBAL, CENTRE), clau
        assert (ruta.rol is None) == (ruta.grup == PUBLICA), clau
        assert set(ruta.escriu) <= {"a", "b"}, clau
        if ruta.grup in (CENTRE, SESSIO):
            # Les del centre i les del perfil només poden tocar el centre de la sessió
            assert set(ruta.escriu) <= {"a"}, clau
        if ruta.grup == GLOBAL:
            assert ruta.rol == SUPER, clau


# --------------------------------------------------------------- a) autenticació


def _testimonis_que_no_valen(ctx):
    admin_a = _usuari(ctx["admin_a"])
    return {
        "sense sessió": None,
        "signatura falsa": security.create_access_token(
            {"sub": ctx["admin_a"], "uid": admin_a.id, "institucio": ctx["A"]}
        )[:-4]
        + "AAAA",
        "testimoni d'un altre centre": security.testimoni_de_sessio(admin_a, ctx["B"]),
        "usuari inexistent": security.create_access_token(
            {"sub": "ningu", "uid": 999999, "institucio": ctx["A"], "sv": 0}
        ),
    }


def test_sense_una_sessio_valida_es_rebutja_amb_401(entorn):
    ctx = entorn["ctx"]
    abans = {c: _estat(c) for c in entorn["centres"]}
    rebutjades = []
    for nom, testimoni in _testimonis_que_no_valen(ctx).items():
        client = _client()
        if testimoni:
            client.cookies.set(security.COOKIE_NAME, testimoni)
        for clau, ruta in INVENTARI.items():
            if ruta.grup == PUBLICA:
                continue
            resp = _peticio(client, clau, ruta, ctx)
            if resp.status_code != 401:
                rebutjades.append((nom, clau, resp.status_code))
    assert rebutjades == []
    assert {c: _estat(c) for c in entorn["centres"]} == abans


def test_amb_la_sessio_d_un_centre_desactivat_es_rebutja_amb_403(entorn):
    ctx, client = entorn["ctx"], entorn["clients"]["admin_inactiu"]
    respostes = {
        clau: _peticio(client, clau, ruta, ctx).status_code for clau, ruta in INVENTARI.items() if ruta.grup != PUBLICA
    }
    assert {clau: codi for clau, codi in respostes.items() if codi != 403} == {}


def test_les_publiques_responen_sense_sessio(entorn):
    ctx = entorn["ctx"]
    for clau, ruta in INVENTARI.items():
        if ruta.grup == PUBLICA:
            assert _peticio(_client(), clau, ruta, ctx).status_code == 200, clau
    limiter.reset()


# -------------------------------------------------------------- b) autorització


def test_les_rutes_de_l_admin_i_del_superadmin_rebutgen_els_rols_inferiors(entorn):
    ctx, clients = entorn["ctx"], entorn["clients"]
    abans = {c: _estat(c) for c in entorn["centres"]}
    no_rebutjades = []
    for clau, ruta in INVENTARI.items():
        for rol in INFERIORS.get(ruta.rol, []):
            client = clients["user_a" if rol == USER else "admin_a"]
            resp = _peticio(client, clau, ruta, ctx)
            if resp.status_code != 403:
                no_rebutjades.append((clau, rol, resp.status_code))
    assert no_rebutjades == []
    assert {c: _estat(c) for c in entorn["centres"]} == abans


# ------------------------------------------------------------ c) aïllament


def _textos(resp) -> str:
    text = resp.content.decode("utf-8", errors="replace")
    if resp.content.startswith(b"%PDF"):
        text += " ".join(text_pdf(resp.content))
    return text


def test_un_usuari_del_centre_a_nomes_llegeix_i_escriu_el_centre_a(entorn):
    ctx, clients = entorn["ctx"], entorn["clients"]
    a, b = entorn["centres"]
    per_rol = {USER: clients["user_a"], ADMIN: clients["admin_a"], SUPER: clients["super"], None: _client()}
    errors = []
    for clau, ruta in INVENTARI.items():
        abans = {"a": _estat(a), "b": _estat(b)}
        client = per_rol[ruta.rol]
        resp = _peticio(client, clau, ruta, ctx)
        if resp.status_code != ruta.esperat:
            errors.append((clau, "codi", resp.status_code, resp.text[:300]))
            continue
        if ruta.grup != GLOBAL and "MARCAB" in _textos(resp):
            errors.append((clau, "la resposta porta dades del centre B"))
        despres = {"a": _estat(a), "b": _estat(b)}
        canviats = {c for c in ("a", "b") if abans[c] != despres[c]}
        if canviats != set(ruta.escriu):
            detall = {c: _diferencies(abans[c], despres[c]) for c in ("a", "b")}
            errors.append((clau, "canvia", sorted(canviats), "en lloc de", sorted(ruta.escriu), detall))
        try:
            if ruta.recull:
                ruta.recull(resp, ctx)
            if ruta.comprova:
                ruta.comprova(client, ctx)
        except (AssertionError, KeyError, IndexError, TypeError) as exc:
            errors.append((clau, "recull o comprova", repr(exc), resp.text[:300]))
        limiter.reset()
    assert errors == [], "\n".join(map(repr, errors))
