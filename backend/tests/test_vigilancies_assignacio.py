"""
Regles de l'assignació automàtica de vigilants (vigilancies/assignacio.py),
per l'API. Cada hora es resol sencera; prioritats: files cobertes > titular
de l'ENLLAÇ > titulars > qui tenia classe amb el grup > mateix nivell >
nivell proper > qualsevol alliberat > guàrdia; els empats, a l'atzar (aquí,
amb llavor fixa).

Dilluns 20/04/2026 a les 10:00, horari d'exemple:
  1-ESO-A Prof 30, 1-ESO-B Prof 34, 1-ESO-C Prof 49
  2-ESO-A Prof 33, 2-ESO-B Prof 38, 2-ESO-C Prof 45
  3-ESO-B Prof 41
  2-BAT-A,2-BAT-B Prof 26, 31, 35 i 47 (una sola classe dels dos grups)
  guàrdia: Prof 3, 21, 28; Prof 2, hora lliure
Els grups amb examen queden sense classe; els altres, només si es diu.
"""

import itertools
import random
import uuid

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from config.context import fixa_institucio_peticio
from database import get_data_db_session
from models import AbreviaturaGrup, CategoriaPrioritat, ConfiguracioExamen, Grup, Nivell
from prioritats.services import carrega_prioritats
from rate_limit import limiter
from repositories import GrupsAlliberatsRepository
from substitucions import router as substitucions
from vigilancies import services
from vigilancies.assignacio import assignacio_optima, grups_de, save_vigilancies_afinitats, titular_de, titulars_de
from vigilancies.router import router as vigilancies_router

APP = crea_app(vigilancies_router, substitucions.router)
DATA = "2026-04-20"  # dilluns
URL = f"/api/vigilancies/{DATA}"
NIVELLS = {
    "1-ESO": ["1-ESO-A", "1-ESO-B", "1-ESO-C"],
    "2-ESO": ["2-ESO-A", "2-ESO-B", "2-ESO-C"],
    "3-ESO": ["3-ESO-A", "3-ESO-B", "3-ESO-C"],
    "2-BAT": ["2-BAT-A", "2-BAT-B"],
}


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def llavor(monkeypatch):
    """Fixa l'atzar dels empats: llavor(n) abans d'assignar."""
    estat = {"llavor": 0}
    monkeypatch.setattr(services, "_atzar", lambda: random.Random(estat["llavor"]))

    def fixa(n):
        estat["llavor"] = n

    return fixa


def _centre(config=(), alliberats=(), absents=(), abreviatures=(), afinitats=()):
    """Un centre amb l'horari d'exemple, els nivells, la configuració
    d'exàmens [(assignatura, grup, aula, titular)], els grups sense classe de
    les 10:00, les absències de les 10:00 i les abreviatures."""
    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        for ordre, (codi, grups) in enumerate(NIVELLS.items()):
            nivell = Nivell(codi=codi, nom=codi, ordre=ordre, actiu=True)
            db.add(nivell)
            db.flush()
            for g in grups:
                db.add(Grup(codi=g, nom=g, nivell_id=nivell.id))
        for assignatura, grup, aula, titular in config:
            db.add(ConfiguracioExamen(assignatura=assignatura, grup=grup, aula=aula, titular=titular))
        for originals, abreviatura in abreviatures:
            db.add(AbreviaturaGrup(grups_originals=originals, abreviatura=abreviatura))
        if alliberats:
            GrupsAlliberatsRepository.set_for_date(db, DATA, {"10:00": list(alliberats)})
        if afinitats:
            save_vigilancies_afinitats(db, list(afinitats))
        db.commit()
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(APP), nom)
    for professor in absents:
        resp = client.put(
            f"/api/substitucions/{DATA}/absencies/{professor}", json={"hores_absencia": ["10:00"], "updated_at_map": {}}
        )
        assert resp.status_code == 200, resp.text
    return centre, client


def _crea(client, grups, tipus="Castellà", aula="A1", nivell=None):
    nivell = nivell or next(n for n, gs in NIVELLS.items() if grups in gs or grups.startswith(n))
    body = {"hora": "10:00", "tipus": tipus, "grups": grups, "aula": aula, "vigilant": "", "nivell": nivell}
    resp = client.post(URL, json=body)
    assert resp.status_code == 200, resp.text


def _vigilants(client):
    return {(v["grups"], v["aula"]): v["vigilant"] for v in client.get(URL).json()}


def _titulars(client):
    resp = client.post(f"{URL}/assign/titulars")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _pendents(client, disponibles=False):
    resp = client.post(f"{URL}/assign/pendents", params={"disponibles": disponibles})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ------------------------------------------------------------ 1: l'ENLLAÇ mana


def test_1_el_titular_de_l_enllac_va_a_l_enllac_encara_que_sigui_titular_d_un_grup(llavor):
    _, client = _centre(
        config=[
            ("Castellà", "1-ESO", "ENLLAÇ", "Prof 34"),
            ("Castellà", "1-ESO-A", "1-ESO-A", "Prof 30"),
            ("Castellà", "1-ESO-B", "1-ESO-B", "Prof 34"),
        ],
        alliberats=["1-ESO-C"],
    )
    _crea(client, "1-ESO", aula="ENLLAÇ")
    _crea(client, "1-ESO-A", aula="1-ESO-A")
    _crea(client, "1-ESO-B", aula="1-ESO-B")
    assert _titulars(client)["assigned_count"] == 2
    assert _vigilants(client) == {
        ("1-ESO", "ENLLAÇ"): "Prof 34",
        ("1-ESO-A", "1-ESO-A"): "Prof 30",
        ("1-ESO-B", "1-ESO-B"): "",
    }
    _pendents(client)
    # 1-ESO-B, sense el seu professor (és a l'ENLLAÇ): un alliberat del mateix nivell
    assert _vigilants(client)[("1-ESO-B", "1-ESO-B")] == "Prof 49"


def test_1b_el_cas_de_castella_el_titular_de_1_eso_b_te_classe(llavor):
    # Prof 34 tenia classe amb 1-ESO-B, però és el titular de l'ENLLAÇ; el
    # titular de 1-ESO-B, Prof 41, té classe. Cap alliberat més: la fila queda
    # pendent i, si es demanen disponibles, la vigila una guàrdia.
    _, client = _centre(
        config=[
            ("Castellà", "1-ESO", "ENLLAÇ", "Prof 34"),
            ("Castellà", "1-ESO-A", "1-ESO-A", "Prof 30"),
            ("Castellà", "1-ESO-B", "1-ESO-B", "Prof 41"),
        ]
    )
    _crea(client, "1-ESO", aula="ENLLAÇ")
    _crea(client, "1-ESO-A", aula="1-ESO-A")
    _crea(client, "1-ESO-B", aula="1-ESO-B")
    _titulars(client)
    assert _vigilants(client) == {
        ("1-ESO", "ENLLAÇ"): "Prof 34",
        ("1-ESO-A", "1-ESO-A"): "Prof 30",
        ("1-ESO-B", "1-ESO-B"): "",
    }
    _pendents(client)
    assert _vigilants(client)[("1-ESO-B", "1-ESO-B")] == ""
    _pendents(client, disponibles=True)
    assert _vigilants(client)[("1-ESO-B", "1-ESO-B")] in {"Prof 3", "Prof 21", "Prof 28"}


# ------------------------------------------------------------ 2: titular de diversos grups


def _mates(titular, grups=("2-ESO-A", "2-ESO-B")):
    aules = {"2-ESO-A": "A1", "2-ESO-B": "A2", "2-ESO-C": "A3"}
    return [("Matemàtiques", g, aules[g], titular) for g in grups]


def _crea_mates(client, grups=("2-ESO-A", "2-ESO-B")):
    aules = {"2-ESO-A": "A1", "2-ESO-B": "A2", "2-ESO-C": "A3"}
    for g in grups:
        _crea(client, g, tipus="Matemàtiques", aula=aules[g])


def _per_grup(client):
    return {g: v for (g, _), v in _vigilants(client).items()}


def test_2a_el_titular_de_diversos_grups_va_al_grup_on_tenia_classe(llavor):
    _, client = _centre(config=_mates("Prof 38"))  # Prof 38 tenia classe amb 2-ESO-B
    _crea_mates(client)
    assert _titulars(client)["assigned_count"] == 1
    assert _per_grup(client) == {"2-ESO-A": "", "2-ESO-B": "Prof 38"}
    _pendents(client)
    assert _per_grup(client) == {"2-ESO-A": "Prof 33", "2-ESO-B": "Prof 38"}


def test_2b_si_no_tenia_classe_va_al_grup_que_quedaria_sense_vigilant(llavor):
    # Prof 41 (alliberat) és titular de 2-ESO-A i 2-ESO-B; el professor de
    # 2-ESO-B és absent: el titular va a 2-ESO-B, i Prof 33 al seu grup
    _, client = _centre(config=_mates("Prof 41"), alliberats=["3-ESO-B"], absents=["Prof 38"])
    _crea_mates(client)
    _titulars(client)
    assert _per_grup(client) == {"2-ESO-A": "", "2-ESO-B": "Prof 41"}
    _pendents(client)
    assert _per_grup(client) == {"2-ESO-A": "Prof 33", "2-ESO-B": "Prof 41"}


def test_2b_si_en_quedarien_diversos_sense_vigilant_un_d_ells_a_l_atzar(llavor):
    grups = ("2-ESO-A", "2-ESO-B", "2-ESO-C")
    destins = set()
    for n in range(12):
        llavor(n)
        _, client = _centre(config=_mates("Prof 41", grups), alliberats=["3-ESO-B"], absents=["Prof 38", "Prof 45"])
        _crea_mates(client, grups)
        _titulars(client)
        vigilants = _per_grup(client)
        assert vigilants["2-ESO-A"] == ""  # 2-ESO-A té el seu professor: no hi va
        destins.add(next(g for g, v in vigilants.items() if v == "Prof 41"))
    assert destins == {"2-ESO-B", "2-ESO-C"}


def test_2c_si_tots_els_grups_tenen_el_seu_professor_un_a_l_atzar(llavor):
    destins = set()
    for n in range(12):
        llavor(n)
        _, client = _centre(config=_mates("Prof 41"), alliberats=["3-ESO-B"])
        _crea_mates(client)
        _titulars(client)
        _pendents(client)
        vigilants = _per_grup(client)
        desti = next(g for g, v in vigilants.items() if v == "Prof 41")
        destins.add(desti)
        altre = ({"2-ESO-A", "2-ESO-B"} - {desti}).pop()
        assert vigilants[altre] == {"2-ESO-A": "Prof 33", "2-ESO-B": "Prof 38"}[altre]
    assert destins == {"2-ESO-A", "2-ESO-B"}


def test_l_atzar_amb_la_mateixa_llavor_dona_sempre_el_mateix(llavor):
    resultats = set()
    for _ in range(3):
        llavor(7)
        _, client = _centre(config=_mates("Prof 41"), alliberats=["3-ESO-B"])
        _crea_mates(client)
        _titulars(client)
        resultats.add(tuple(sorted(_per_grup(client).items())))
    assert len(resultats) == 1


# ------------------------------------------------------------ 3: qui tenia classe amb el grup


def test_3_compta_una_classe_de_diversos_grups_que_inclou_el_de_l_examen(llavor):
    # La classe «2-BAT-A,2-BAT-B» (Prof 26, 31, 35, 47) inclou 2-BAT-A; Prof 41
    # (3-ESO-B) també és alliberat, però no tenia classe amb el grup
    _, client = _centre(alliberats=["2-BAT-A,2-BAT-B", "3-ESO-B"])
    _crea(client, "2-BAT-A", tipus="Anglès")
    _pendents(client)
    assert _per_grup(client)["2-BAT-A"] in {"Prof 26", "Prof 31", "Prof 35", "Prof 47"}


def test_3_les_abreviatures_es_desfan_amb_la_taula(llavor):
    # «1-ESO-AB» vol dir 1-ESO-A i 1-ESO-B: hi va Prof 30 o Prof 34, no Prof 49
    # (1-ESO-C, del mateix nivell, però sense classe amb el grup)
    _, client = _centre(alliberats=["1-ESO-A", "1-ESO-B", "1-ESO-C"], abreviatures=[("1-ESO-A,1-ESO-B", "1-ESO-AB")])
    _crea(client, "1-ESO-AB", nivell="1-ESO")
    _pendents(client)
    assert _per_grup(client)["1-ESO-AB"] in {"Prof 30", "Prof 34"}


# ------------------------------------------------------------ 4: la resta, per nivell


AFINITATS = [{"base": "2-ESO", "ordre": ["2-ESO", "3-ESO"]}]


@pytest.mark.parametrize(
    "alliberats, esperat",
    [
        (["2-ESO-A", "3-ESO-B", "1-ESO-A"], "Prof 33"),  # mateix nivell
        (["3-ESO-B", "1-ESO-A"], "Prof 41"),  # nivell proper
        (["1-ESO-A"], "Prof 30"),  # qualsevol alliberat
    ],
    ids=["mateix nivell", "nivell proper", "qualsevol alliberat"],
)
def test_4_sense_el_professor_del_grup_mana_el_nivell(llavor, alliberats, esperat):
    _, client = _centre(alliberats=alliberats, absents=["Prof 45"], afinitats=AFINITATS)
    _crea(client, "2-ESO-C", tipus="Socials")
    _pendents(client)
    assert _per_grup(client)["2-ESO-C"] == esperat


def test_4_la_guardia_nomes_si_es_demanen_disponibles_i_al_final(llavor):
    _, client = _centre(absents=["Prof 45"])
    _crea(client, "2-ESO-C", tipus="Socials")
    assert _pendents(client)["assigned_count"] == 0
    _pendents(client, disponibles=True)
    assert _per_grup(client)["2-ESO-C"] in {"Prof 3", "Prof 21", "Prof 28"}


# ------------------------------------------------------------ titulars: hora lliure i categories


def test_el_titular_amb_l_hora_lliure_no_s_assigna_i_es_retorna(llavor):
    _, client = _centre(config=[("Socials", "2-ESO-C", "A1", "Prof 2")])
    _crea(client, "2-ESO-C", tipus="Socials")
    resposta = _titulars(client)
    assert resposta["assigned_count"] == 0
    assert [(t["hora"], t["grups"], t["tipus"], t["titular"]) for t in resposta["titulars_hora_lliure"]] == [
        ("10:00", "2-ESO-C", "Socials", "Prof 2")
    ]
    assert _per_grup(client) == {"2-ESO-C": ""}


def test_la_categoria_no_compta_per_al_titular_pero_si_per_als_pendents(llavor):
    # Prof 3 fa guàrdia, d'una categoria inactiva: com a titular de 2-ESO-C s'hi
    # posa igualment. 2-ESO-B, sense cap alliberat (Prof 38 i 45 absents), queda
    # pendent: les guàrdies, d'aquesta categoria, no s'hi posen
    centre, client = _centre(config=[("Socials", "2-ESO-C", "A1", "Prof 3")], absents=["Prof 38", "Prof 45"])
    with get_data_db_session(centre) as db:
        db.query(CategoriaPrioritat).filter(CategoriaPrioritat.nom == "Guàrdies").update({"activa": False})
        db.commit()
        fixa_institucio_peticio(centre)  # carrega_prioritats és per a la institució de la petició
        carrega_prioritats(db)  # com en desar-les des de la pantalla
        fixa_institucio_peticio(None)
    _crea(client, "2-ESO-C", tipus="Socials")
    _crea(client, "2-ESO-B", tipus="Castellà")
    assert _titulars(client)["assigned_count"] == 1
    _pendents(client, disponibles=True)
    assert _per_grup(client) == {"2-ESO-C": "Prof 3", "2-ESO-B": ""}


def test_el_titular_absent_no_s_assigna(llavor):
    _, client = _centre(config=[("Socials", "2-ESO-C", "A1", "Prof 3")], absents=["Prof 3"])
    _crea(client, "2-ESO-C", tipus="Socials")
    resposta = _titulars(client)
    assert resposta["assigned_count"] == 0
    assert resposta["titulars_hora_lliure"] == []


def test_el_titular_de_guardia_s_assigna_encara_que_no_es_demanin_disponibles(llavor):
    _, client = _centre(config=[("Socials", "2-ESO-C", "A1", "Prof 3")])
    _crea(client, "2-ESO-C", tipus="Socials")
    assert _titulars(client)["assigned_count"] == 1
    assert _per_grup(client) == {"2-ESO-C": "Prof 3"}


# ------------------------------------------------------------ diversos titulars possibles (anglès per nivells)

ANGLES_3ESO = [("Anglès", "3-ESO-A", "", "Prof 15"), ("Anglès", "3-ESO-B", "", "Prof 41")]


def test_abreviatura_desfeta_per_trobar_el_titular(llavor):
    # L'examen és de «3-ESO-AB» (abreviatura); la configuració té les files de
    # 3-ESO-A i 3-ESO-B, totes amb el mateix titular: aquell és el titular
    _, client = _centre(
        config=[("Anglès", "3-ESO-A", "", "Prof 3"), ("Anglès", "3-ESO-B", "", "Prof 3")],
        abreviatures=[("3-ESO-A,3-ESO-B", "3-ESO-AB")],
    )
    _crea(client, "3-ESO-AB", tipus="Anglès", nivell="3-ESO")
    resposta = _titulars(client)
    assert _per_grup(client) == {"3-ESO-AB": "Prof 3"}
    assert resposta["vigilancies_sense_titular"] == []


def test_diversos_titulars_sense_aula_tots_candidats_i_un_per_fila(llavor):
    # Anglès per nivells: dues aules del nivell 3-ESO, i dos professors sense
    # aula a la configuració. Cada fila té un dels dos, i se n'avisa
    _, client = _centre(config=ANGLES_3ESO, alliberats=["3-ESO-A", "3-ESO-B"])
    _crea(client, "3-ESO", tipus="Anglès", aula="A1")
    _crea(client, "3-ESO", tipus="Anglès", aula="A2")
    resposta = _titulars(client)
    assert resposta["assigned_count"] == 2
    assert sorted(_vigilants(client).values()) == ["Prof 15", "Prof 41"]
    assert sorted((a["grups"], a["motiu"]) for a in resposta["vigilancies_sense_titular"]) == [
        ("3-ESO", "diversos_titulars"),
        ("3-ESO", "diversos_titulars"),
    ]


def test_diversos_titulars_amb_l_aula_de_cada_professor_l_aula_tria(llavor):
    _, client = _centre(
        config=[("Anglès", "3-ESO-A", "A2", "Prof 15"), ("Anglès", "3-ESO-B", "A1", "Prof 41")],
        alliberats=["3-ESO-A", "3-ESO-B"],
    )
    _crea(client, "3-ESO", tipus="Anglès", aula="A1")
    _crea(client, "3-ESO", tipus="Anglès", aula="A2")
    resposta = _titulars(client)
    assert _vigilants(client) == {("3-ESO", "A1"): "Prof 41", ("3-ESO", "A2"): "Prof 15"}
    assert resposta["vigilancies_sense_titular"] == []


def test_diversos_titulars_per_a_una_fila_primer_qui_tenia_classe_amb_un_dels_grups(llavor):
    # Una sola fila de 3-ESO; titulars possibles: Prof 3 (guàrdia) i Prof 41
    # (tenia classe amb 3-ESO-B, que és sense classe): hi va Prof 41
    _, client = _centre(
        config=[("Anglès", "3-ESO-A", "", "Prof 3"), ("Anglès", "3-ESO-B", "", "Prof 41")], alliberats=["3-ESO-B"]
    )
    _crea(client, "3-ESO", tipus="Anglès", aula="A1")
    _titulars(client)
    assert _per_grup(client) == {"3-ESO": "Prof 41"}


def test_cap_fila_per_al_grup_s_avisa(llavor):
    _, client = _centre(config=ANGLES_3ESO)
    _crea(client, "2-ESO-C", tipus="Anglès")
    _crea(client, "2-ESO-B", tipus="Química")  # sense cap fila de l'assignatura: no s'avisa
    resposta = _titulars(client)
    assert [(a["grups"], a["motiu"]) for a in resposta["vigilancies_sense_titular"]] == [("2-ESO-C", "cap_fila_grup")]


@pytest.mark.parametrize(
    "files, grups, aula, esperat",
    [
        (ANGLES_3ESO, "3-ESO", "A1", ({"Prof 15", "Prof 41"}, "diversos_titulars")),
        (ANGLES_3ESO, "3-ESO-ABC", "A1", ({"Prof 15", "Prof 41"}, "diversos_titulars")),
        (ANGLES_3ESO, "3-ESO-A", "A1", ({"Prof 15"}, None)),  # el grup exacte
        (ANGLES_3ESO, "2-ESO-A", "A1", (set(), "cap_fila_grup")),
        ([("Anglès", "3-ESO", "", "Prof 9")], "3-ESO-ABC", "", ({"Prof 9"}, None)),  # fila del nivell
        (
            [("Anglès", "3-ESO-A", "A1", "Prof 15"), ("Anglès", "3-ESO-B", "A2", "Prof 41")],
            "3-ESO",
            "A2",
            ({"Prof 41"}, None),
        ),
        ([("Química", "3-ESO-A", "", "Prof 1")], "3-ESO-A", "", (set(), None)),  # assignatura sense files: sense avís
    ],
)
def test_titulars_de(files, grups, aula, esperat):
    config = [{"assignatura": a, "grup": g, "aula": au, "titular": t} for a, g, au, t in files]
    abreviatures = {"3-ESO-ABC": ["3-ESO-A", "3-ESO-B", "3-ESO-C"]}
    titulars, motiu = titulars_de(config, "Anglès", grups, aula, abreviatures, NIVELLS)
    assert (set(titulars), motiu) == esperat


# ------------------------------------------------------------ peces


FILES_CASTELLA = [
    {"assignatura": "Castellà", "grup": "1-ESO", "aula": "ENLLAÇ", "titular": "Prof 1"},
    {"assignatura": "Castellà", "grup": "1-ESO-A", "aula": "1-ESO-A", "titular": "Prof 2"},
    {"assignatura": "Anglès", "grup": "1-ESO-B", "aula": "A1", "titular": "Prof 3"},
    {"assignatura": "Anglès", "grup": "1-ESO-B", "aula": "A2", "titular": "Prof 4"},
    {"assignatura": "Anglès", "grup": "1-ESO-C", "aula": "A1", "titular": "Prof 5"},
    {"assignatura": "Anglès", "grup": "1-ESO-C", "aula": "A1", "titular": "Prof 6"},
]


@pytest.mark.parametrize(
    "tipus, grups, aula, esperat",
    [
        ("Castellà", "1-ESO", "ENLLAÇ", "Prof 1"),  # l'ENLLAÇ, per grup (i aula)
        ("Castellà", "1-ESO-A", "una altra", "Prof 2"),  # una sola fila: l'aula no cal
        ("Anglès", "1-ESO-B", "A2", "Prof 4"),  # desdoblament: l'aula desfà
        ("Anglès", "1-ESO-B", "A9", None),  # desdoblament sense l'aula: cap
        ("Anglès", "1-ESO-C", "A1", None),  # dues files iguals: no es pot decidir
        ("Castellà", "1-ESO-B", "1-ESO-A", None),  # mateixa aula, un altre grup: no
        ("Castellà", "1-ESO-B", "", None),  # cap fila del grup: no hi ha «el primer»
        ("Castellà", "1-ESO-B", "ENLLAÇ", None),  # l'ENLLAÇ de «1-ESO» no casa amb 1-ESO-B per tros de nom
        ("Química", "1-ESO-A", "", None),  # assignatura sense configuració
    ],
)
def test_titular_de(tipus, grups, aula, esperat):
    assert titular_de(FILES_CASTELLA, tipus, grups, aula) == esperat


def test_titular_de_sense_configuracio():
    assert titular_de([], "Castellà", "1-ESO-A", "1-ESO-A") is None


def test_grups_de_desfa_comes_i_abreviatures_sense_trossos_de_text():
    abreviatures = {"1-ESO-AB": ["1-ESO-A", "1-ESO-B"]}
    assert grups_de("1-ESO-AB", abreviatures) == {"1-ESO-A", "1-ESO-B"}
    assert grups_de("2-BAT-A, 2-BAT-B", abreviatures) == {"2-BAT-A", "2-BAT-B"}
    assert grups_de("1-ESO", abreviatures) == {"1-ESO"}  # sense la taula de nivells, el text tal qual
    assert grups_de("1-ESO", abreviatures, NIVELLS) == {"1-ESO-A", "1-ESO-B", "1-ESO-C"}
    assert grups_de("1-ES", abreviatures, NIVELLS) == {"1-ES"}  # mai per tros de text
    assert grups_de("", abreviatures) == set()


def _forca_bruta(pesos):
    n, m = len(pesos), len(pesos[0])
    millor = 0
    for perm in itertools.permutations(range(m + n), n):
        millor = max(millor, sum(pesos[i][perm[i]] for i in range(n) if perm[i] < m))
    return millor


def test_assignacio_optima_dona_el_maxim_de_la_força_bruta():
    rng = random.Random(1)
    for _ in range(200):
        n, m = rng.randint(1, 4), rng.randint(1, 4)
        pesos = [[rng.choice([0, 0, rng.randint(1, 50)]) for _ in range(m)] for _ in range(n)]
        triats = assignacio_optima(pesos)
        assert len(set(triats.values())) == len(triats)
        assert all(pesos[i][j] > 0 for i, j in triats.items())
        assert sum(pesos[i][j] for i, j in triats.items()) == _forca_bruta(pesos)


def test_assignacio_optima_casos_limit():
    assert assignacio_optima([]) == {}
    assert assignacio_optima([[0, 0]]) == {}
    assert assignacio_optima([[5], [7]]) == {1: 0}
