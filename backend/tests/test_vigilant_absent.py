"""
Professor que vigila un examen i alhora és absent a la mateixa hora.

Regla: l'absència es registra sempre com a ABSENCIA (és el que diu que el
professor no hi és), i cobreix la seva classe. La VIGILANCIA (cobertura de la
classe d'un vigilant) només existeix si el vigilant NO és absent. Si és
absent, l'examen el cobreix la VIGILANCIA_ABSENT.

Abans, segons l'ordre en què es feien les coses, la classe quedava coberta
dues vegades (ABSENCIA + VIGILANCIA) o, en canviar el vigilant, l'absència
desapareixia del tot.

Dilluns 20/04/2026 a les 10:00: Prof 15 fa Anglès amb 3-ESO-A; Prof 3, 21 i
28 fan guàrdia.
"""
from test_vigilancies_api import (  # noqa: F401  (fixtures)
    URL,
    URL_SUBS,
    _absent,
    _crea,
    _limiter_net,
    _vigilancies,
    centre,
    client,
)

CLASSE = ("10:00", "Prof 15", "Anglès")


def _files(client):
    return client.get(URL_SUBS, params={"include_all": True}).json()


def _totes(client):
    # include_all amaga les ENCADENADES; aquí no n'hi ha cap que interessi.
    return [(s["hora"], s["professor_absent"], s["assignatura"], s["tipus_absencia"], s["substitut"])
            for s in _files(client)]


def _cobertures_classe(client):
    return [(t, sub) for h, p, a, t, sub in _totes(client) if (h, p, a) == CLASSE]


def _vigilancia_absent_de(client, professor):
    return [sub for h, p, a, t, sub in _totes(client) if p == professor and t == "VIGILANCIA_ABSENT"]


def _canvia_vigilant(client, nou):
    vig = _vigilancies(client)[0]
    resp = client.put(f"{URL}/{vig['id']}", json={"vigilant": nou, "updated_at": vig["updated_at"]})
    assert resp.status_code == 200


def _posa_substitut(client, tipus, substitut, professor="Prof 15"):
    fila = next(s for s in _files(client)
                if s["professor_absent"] == professor and s["hora"] == "10:00" and s["tipus_absencia"] == tipus)
    resp = client.put(f"{URL_SUBS}/10:00/{professor}",
                      json={"substitut": substitut, "updated_at": fila["updated_at"]})
    assert resp.status_code == 200, resp.text


def _treu_absencia(client, professor="Prof 15"):
    resp = client.put(f"{URL_SUBS}/absencies/{professor}", json={"hores_absencia": [], "updated_at_map": {}})
    assert resp.status_code == 200


# ------------------------------------------------ vigilant absent: estat

def test_vigilant_i_despres_absent(client):
    _crea(client, "Prof 15")
    _absent(client, "Prof 15")
    assert _cobertures_classe(client) == [("ABSENCIA", "")]
    assert _vigilancia_absent_de(client, "Prof 15") == [""]


def test_absent_i_despres_vigilant(client):
    _absent(client, "Prof 15")
    _crea(client, "Prof 15")
    assert _cobertures_classe(client) == [("ABSENCIA", "")]
    assert _vigilancia_absent_de(client, "Prof 15") == [""]


def test_nova_substitucio_d_un_vigilant(client):
    _crea(client, "Prof 15")
    resp = client.post(f"{URL_SUBS}/nova", json={"professor": "Prof 15", "hores": ["10:00"], "tipus_absencia": "ABSENCIA"})
    assert resp.status_code == 200
    assert _cobertures_classe(client) == [("ABSENCIA", "")]
    assert _vigilancia_absent_de(client, "Prof 15") == [""]


# ------------------------------------------- canvis posteriors (l'error)

def test_canviar_el_vigilant_no_fa_perdre_l_absencia(client):
    _crea(client, "Prof 15")
    _absent(client, "Prof 15")
    _canvia_vigilant(client, "Prof 21")
    assert _cobertures_classe(client) == [("ABSENCIA", "")]
    assert _vigilancia_absent_de(client, "Prof 15") == []


def test_treure_el_vigilant_no_fa_perdre_l_absencia(client):
    _crea(client, "Prof 15")
    _absent(client, "Prof 15")
    _canvia_vigilant(client, "")
    assert _cobertures_classe(client) == [("ABSENCIA", "")]
    assert _vigilancia_absent_de(client, "Prof 15") == []


def test_treure_l_absencia_d_un_vigilant_torna_a_cobrir_la_classe_per_la_vigilancia(client):
    _crea(client, "Prof 15")
    _absent(client, "Prof 15")
    _treu_absencia(client)
    assert _cobertures_classe(client) == [("VIGILANCIA", "")]
    assert _vigilancia_absent_de(client, "Prof 15") == []


# --------------------------------------- es conserven els substituts

def test_el_substitut_de_la_classe_es_conserva_en_marcar_l_absencia(client):
    _crea(client, "Prof 15")
    _posa_substitut(client, "VIGILANCIA", "Prof 3")
    _absent(client, "Prof 15")
    assert _cobertures_classe(client) == [("ABSENCIA", "Prof 3")]


def test_el_substitut_de_la_classe_es_conserva_en_treure_l_absencia(client):
    _crea(client, "Prof 15")
    _absent(client, "Prof 15")
    _posa_substitut(client, "ABSENCIA", "Prof 3")
    _treu_absencia(client)
    assert _cobertures_classe(client) == [("VIGILANCIA", "Prof 3")]


def test_el_substitut_de_la_classe_es_conserva_en_canviar_el_vigilant(client):
    _crea(client, "Prof 15")
    _absent(client, "Prof 15")
    _posa_substitut(client, "ABSENCIA", "Prof 3")
    _canvia_vigilant(client, "Prof 21")
    assert _cobertures_classe(client) == [("ABSENCIA", "Prof 3")]


# ----------------------------------------------------------- generar

def test_generar_no_duplica_la_classe_d_un_vigilant_absent(client):
    _crea(client, "Prof 15")
    _absent(client, "Prof 15")
    for regenerar_tot in (False, True):
        resp = client.post(f"{URL_SUBS}/generar", params={"regenerar_tot": regenerar_tot})
        assert resp.status_code == 200
        tipus = [t for t, _ in _cobertures_classe(client)]
        assert tipus == ["ABSENCIA"], (regenerar_tot, tipus)
        assert len(_vigilancia_absent_de(client, "Prof 15")) == 1


# --------------------------------------------- el que no ha de canviar

def test_un_vigilant_que_no_es_absent_continua_tenint_la_classe_coberta_per_la_vigilancia(client):
    _crea(client, "Prof 15")
    assert _cobertures_classe(client) == [("VIGILANCIA", "")]
    assert _vigilancia_absent_de(client, "Prof 15") == []


def test_un_absent_que_no_vigila_continua_amb_la_seva_absencia(client):
    _absent(client, "Prof 15")
    assert _cobertures_classe(client) == [("ABSENCIA", "")]
    assert _vigilancia_absent_de(client, "Prof 15") == []


def test_nova_substitucio_no_toca_la_cobertura_d_examen_d_altres_hores(client):
    # Prof 15 vigila a les 10:00 i a les 11:30 i ja és absent a les 11:30.
    # Afegir-lo absent a les 10:00 per "nova" no pot esborrar la de les 11:30.
    _crea(client, "Prof 15")
    _crea(client, "Prof 15", hora="11:30")
    _absent(client, "Prof 15", hores=("11:30",))
    assert [h for h, p, a, t, sub in _totes(client) if p == "Prof 15" and t == "VIGILANCIA_ABSENT"] == ["11:30"]

    client.post(f"{URL_SUBS}/nova", json={"professor": "Prof 15", "hores": ["10:00"], "tipus_absencia": "ABSENCIA"})
    hores = sorted(h for h, p, a, t, sub in _totes(client) if p == "Prof 15" and t == "VIGILANCIA_ABSENT")
    assert hores == ["10:00", "11:30"]
