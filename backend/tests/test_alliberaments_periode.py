"""
Alliberaments per període i activitats alliberables.

Un alliberament per període és un canvi d'estat: a partir d'un dia, cada
setmana el mateix dia i hora, un grup / professor / activitat queda alliberat
(o deixa de ser-ho) fins al canvi següent. Les activitats sense grup que es
configuren com a alliberables a Prioritats (p.ex. Reforç) surten com a files a
la taula de grups i alliberen tots els professors que les fan.

Horari d'exemple, els dilluns:
  - 09:00  Prof 18 i Prof 31 fan Reforç (sense grup); a les 11:30, Prof 12.
  - 10:00  Prof 26 fa «2.3» amb 2-BAT-A,2-BAT-B; Prof 15, Anglès amb 3-ESO-A.
Dilluns de prova: 13/04, 20/04, 27/04 i 04/05/2026.
"""

import uuid

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from absencia_coberta.router import router as absencia_coberta_router
from grups import router as grups
from prioritats.router import router as prioritats_router
from rate_limit import limiter
from routes import settings
from substitucions import router as substitucions

APP = crea_app(
    grups.router, grups.router_admin, substitucions.router, prioritats_router, absencia_coberta_router, settings.router
)
DILLUNS = ["2026-04-13", "2026-04-20", "2026-04-27", "2026-05-04"]


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def client():
    centre = nova_institucio(amb_xml=True)
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _canvi(client, tipus, clau, hores, data, alliberat=True):
    resp = client.post(
        "/api/grups/periode", json={"tipus": tipus, "clau": clau, "hores": hores, "data": data, "alliberat": alliberat}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _disponibles(client, data, hora):
    resp = client.get(f"/api/substitucions/{data}/{hora}/disponibles")
    assert resp.status_code == 200, resp.text
    return {d["professor"]: d["tipus"] for d in resp.json()["disponibles"]}


def _alliberat(client, data, hora, professor):
    return _disponibles(client, data, hora).get(professor) == "alliberat"


# ------------------------------------------------------------------ professor


def test_un_professor_alliberat_a_partir_d_un_dia_ho_esta_cada_setmana(client):
    assert _canvi(client, "professor", "Prof 26", ["10:00"], DILLUNS[1])["dia_setmana"] == "Dilluns"
    assert not _alliberat(client, DILLUNS[0], "10:00", "Prof 26")  # abans: no
    assert _alliberat(client, DILLUNS[1], "10:00", "Prof 26")
    assert _alliberat(client, DILLUNS[2], "10:00", "Prof 26")
    assert not _alliberat(client, DILLUNS[2], "11:30", "Prof 26")  # només a l'hora indicada


def test_un_canvi_posterior_el_torna_a_l_estat_normal(client):
    _canvi(client, "professor", "Prof 26", ["10:00"], DILLUNS[1])
    _canvi(client, "professor", "Prof 26", ["10:00"], DILLUNS[3], alliberat=False)
    assert _alliberat(client, DILLUNS[2], "10:00", "Prof 26")
    assert not _alliberat(client, DILLUNS[3], "10:00", "Prof 26")


def test_els_canvis_no_es_llisten_ni_s_esborren_per_l_api(client):
    # La pantalla no ho fa servir (30/10/2026): un canvi es desfà amb un altre
    # canvi posterior (test_un_canvi_posterior_el_torna_a_l_estat_normal)
    _canvi(client, "professor", "Prof 26", ["10:00"], DILLUNS[1])
    assert client.get("/api/grups/periode/canvis").status_code == 404
    assert client.delete("/api/grups/periode/1").status_code == 404
    assert _alliberat(client, DILLUNS[2], "10:00", "Prof 26")


# ------------------------------------------------------------------ grup


@pytest.mark.parametrize("tipus, clau", [("grup", "3-ESO-A"), ("activitat", "Reforç")])
def test_nomes_hi_ha_canvis_per_periode_de_professors(client, tipus, clau):
    # Decidit el 9/10/2026: cap canvi d'estat per període als grups ni a les
    # classes; només els dels professors, per als reforços
    resposta = client.post(
        "/api/grups/periode", json={"tipus": tipus, "clau": clau, "hores": ["10:00"], "data": DILLUNS[1]}
    )
    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "Tipus desconegut"


# ------------------------------------------------------------------ activitats


def _configura_reforc(client):
    resp = client.put("/api/prioritats/activitats-alliberables", json={"activitats": ["Reforç"]})
    assert resp.status_code == 200, resp.text


def test_les_activitats_es_configuren_a_prioritats(client):
    cos = client.get("/api/prioritats/activitats-alliberables").json()
    assert cos["activitats"] == []
    assert "Reforç" in cos["disponibles"]
    _configura_reforc(client)
    assert client.get("/api/prioritats/activitats-alliberables").json()["activitats"] == ["Reforç"]


def test_les_activitats_per_triar_inclouen_les_d_un_professor_amb_una_absencia_coberta(client):
    # És configuració, no un dia: «E.E.» només la fa Prof 32
    resp = client.post(
        "/api/absencies-cobertes", json={"professor": "Prof 32", "data_inici": DILLUNS[1], "data_final": DILLUNS[1]}
    )
    assert resp.status_code == 200, resp.text
    cos = client.get("/api/prioritats/activitats-alliberables", params={"data": DILLUNS[1]}).json()
    assert "E.E." in cos["disponibles"]


def test_les_activitats_per_triar_son_les_dels_professors_fins_a_l_ultim(client):
    # Prof 32 va després de Prof 31 a l'XML: amb el límit, «E.E.» no hi és
    resp = client.put("/api/settings", json={"ultim_professor_subs": "Prof 31"})
    assert resp.status_code == 200, resp.text
    cos = client.get("/api/prioritats/activitats-alliberables", params={"data": DILLUNS[1]}).json()
    assert "E.E." not in cos["disponibles"]
    assert "Reforç" in cos["disponibles"]


def test_una_activitat_configurada_surt_a_la_taula_amb_qui_la_fa(client):
    assert client.get(f"/api/grups/{DILLUNS[1]}").json()["activitats_per_hora"] == {}
    _configura_reforc(client)
    reforc = client.get(f"/api/grups/{DILLUNS[1]}").json()["activitats_per_hora"]["Reforç"]
    assert sorted(reforc["09:00"]) == ["Prof 18", "Prof 31"]


def test_alliberar_una_activitat_un_dia_allibera_qui_la_fa(client):
    _configura_reforc(client)
    assert not _alliberat(client, DILLUNS[1], "09:00", "Prof 18")
    resp = client.put(f"/api/grups/{DILLUNS[1]}", json={"activitats": {"09:00": ["Reforç"]}})
    assert resp.status_code == 200, resp.text
    assert _alliberat(client, DILLUNS[1], "09:00", "Prof 18")
    assert _alliberat(client, DILLUNS[1], "09:00", "Prof 31")
    assert client.get(f"/api/grups/{DILLUNS[1]}").json()["activitats_seleccionades_per_hora"] == {"09:00": ["Reforç"]}


def test_un_professor_d_una_activitat_es_pot_alliberar_sol(client):
    _configura_reforc(client)
    _canvi(client, "professor", "Prof 18", ["09:00"], DILLUNS[1])
    assert _alliberat(client, DILLUNS[2], "09:00", "Prof 18")
    assert not _alliberat(client, DILLUNS[2], "09:00", "Prof 31")


# ------------------------------------------------------------------ validació


@pytest.mark.parametrize(
    "cos",
    [
        {"tipus": "altre", "clau": "x", "hores": ["10:00"], "data": "2026-04-20"},
        {"tipus": "professor", "clau": "", "hores": ["10:00"], "data": "2026-04-20"},
        {"tipus": "professor", "clau": "Prof 26", "hores": [], "data": "2026-04-20"},
        {"tipus": "professor", "clau": "Prof 26", "hores": ["10:00"], "data": "20/04/2026"},
    ],
)
def test_canvis_invalids_es_rebutgen(client, cos):
    assert client.post("/api/grups/periode", json=cos).status_code == 400


# ------------------------------------------------------------------ reforços
# Activitat «alliberada fins que tingui alumnes»: qui la fa està alliberat sense
# marcar res; es marquen les franges que ja tenen alumnes (i es poden tornar a
# alliberar). Els dimecres, Prof 12 fa Reforç a les 08:00.

DIMECRES = ["2026-04-15", "2026-04-22", "2026-04-29"]


def _configura_reforc_per_defecte(client):
    resp = client.put(
        "/api/prioritats/activitats-alliberables", json={"activitats": ["Reforç"], "per_defecte": ["Reforç"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["per_defecte"] == ["Reforç"]


def _amb_alumnes(client, professor, dia, hora, data, amb_alumnes=True):
    resp = client.post(
        "/api/grups/periode",
        json={
            "tipus": "professor",
            "clau": professor,
            "hores": [hora],
            "data": data,
            "alliberat": not amb_alumnes,
            "dia_setmana": dia,
        },
    )
    assert resp.status_code == 200, resp.text


def test_un_reforc_sense_alumnes_esta_alliberat_sense_marcar_res(client):
    assert not _alliberat(client, DILLUNS[1], "09:00", "Prof 18")
    _configura_reforc_per_defecte(client)
    assert _alliberat(client, DILLUNS[1], "09:00", "Prof 18")
    assert _alliberat(client, DILLUNS[1], "09:00", "Prof 31")
    # No surt com a fila de la taula: es gestiona a part
    cos = client.get(f"/api/grups/{DILLUNS[1]}").json()
    assert cos["activitats_per_hora"] == {}
    assert cos["activitats_per_defecte"] == ["Reforç"]


def test_una_franja_amb_alumnes_deixa_d_estar_alliberada_i_es_pot_tornar_a_alliberar(client):
    _configura_reforc_per_defecte(client)
    _amb_alumnes(client, "Prof 18", "Dilluns", "09:00", DILLUNS[1])
    assert _alliberat(client, DILLUNS[0], "09:00", "Prof 18")  # abans de la data
    assert not _alliberat(client, DILLUNS[1], "09:00", "Prof 18")
    assert not _alliberat(client, DILLUNS[2], "09:00", "Prof 18")
    assert _alliberat(client, DILLUNS[2], "09:00", "Prof 31")  # els altres, igual
    _amb_alumnes(client, "Prof 18", "Dilluns", "09:00", DILLUNS[3], amb_alumnes=False)
    assert not _alliberat(client, DILLUNS[2], "09:00", "Prof 18")
    assert _alliberat(client, DILLUNS[3], "09:00", "Prof 18")


def test_es_pot_marcar_una_franja_d_un_altre_dia_de_la_setmana(client):
    _configura_reforc_per_defecte(client)
    # Des d'un dilluns es marca el reforç dels dimecres
    _amb_alumnes(client, "Prof 12", "Dimecres", "08:00", DILLUNS[1])
    assert _alliberat(client, DIMECRES[0], "08:00", "Prof 12")
    assert not _alliberat(client, DIMECRES[1], "08:00", "Prof 12")


def test_les_franges_de_reforc_de_cada_professor(client):
    _configura_reforc_per_defecte(client)
    _amb_alumnes(client, "Prof 18", "Dilluns", "09:00", DILLUNS[1])
    resp = client.get("/api/grups/reforcos/Reforç", params={"data": DILLUNS[2]})
    assert resp.status_code == 200, resp.text
    franges = resp.json()["professors"]
    sense_historial = [{k: v for k, v in f.items() if k != "historial"} for f in franges["Prof 18"]]
    assert {"dia": "Dilluns", "hora": "09:00", "amb_alumnes": True, "des_de": DILLUNS[1]} in sense_historial
    assert all(not f["amb_alumnes"] for f in franges["Prof 31"])
    # Abans de la data, encara sense alumnes
    abans = client.get("/api/grups/reforcos/Reforç", params={"data": DILLUNS[0]}).json()["professors"]
    assert not any(f["amb_alumnes"] for f in abans["Prof 18"])


def test_activitat_no_configurada_o_dia_desconegut(client):
    assert client.get("/api/grups/reforcos/Reforç", params={"data": DILLUNS[1]}).status_code == 404
    _configura_reforc_per_defecte(client)
    resp = client.post(
        "/api/grups/periode",
        json={
            "tipus": "professor",
            "clau": "Prof 18",
            "hores": ["09:00"],
            "data": DILLUNS[1],
            "alliberat": False,
            "dia_setmana": "Diumenge",
        },
    )
    assert resp.status_code == 400


def test_cada_franja_porta_el_seu_historial(client):
    _configura_reforc_per_defecte(client)
    _amb_alumnes(client, "Prof 18", "Dilluns", "09:00", DILLUNS[1])
    _amb_alumnes(client, "Prof 18", "Dilluns", "09:00", DILLUNS[3], amb_alumnes=False)
    franges = client.get("/api/grups/reforcos/Reforç", params={"data": DILLUNS[2]}).json()["professors"]["Prof 18"]
    franja = next(f for f in franges if (f["dia"], f["hora"]) == ("Dilluns", "09:00"))
    assert franja["historial"] == [
        {"des_de": DILLUNS[1], "amb_alumnes": True},
        {"des_de": DILLUNS[3], "amb_alumnes": False},
    ]


def test_un_reforc_amb_alumnes_es_pot_alliberar_nomes_un_dia(client):
    _configura_reforc_per_defecte(client)
    _amb_alumnes(client, "Prof 18", "Dilluns", "09:00", DILLUNS[1])
    cos = client.get(f"/api/grups/{DILLUNS[2]}").json()
    assert sorted((r["professor"], r["amb_alumnes"]) for r in cos["reforcs_per_hora"]["Reforç"]["09:00"]) == [
        ("Prof 18", True),
        ("Prof 31", False),
    ]
    assert not _alliberat(client, DILLUNS[2], "09:00", "Prof 18")
    # Aquell dia els alumnes no hi són: s'allibera només aquell dia
    resp = client.put(f"/api/grups/{DILLUNS[2]}", json={"professors": {"09:00": ["Prof 18"]}})
    assert resp.status_code == 200, resp.text
    assert _alliberat(client, DILLUNS[2], "09:00", "Prof 18")
    assert not _alliberat(client, DILLUNS[3], "09:00", "Prof 18")  # la setmana següent, no


def test_un_reforc_sense_alumnes_pot_estar_ocupat_un_sol_dia(client):
    _configura_reforc_per_defecte(client)
    assert _alliberat(client, DILLUNS[1], "09:00", "Prof 31")
    resp = client.put(f"/api/grups/{DILLUNS[1]}", json={"ocupats": {"09:00": ["Prof 31"]}})
    assert resp.status_code == 200, resp.text
    assert not _alliberat(client, DILLUNS[1], "09:00", "Prof 31")
    assert _alliberat(client, DILLUNS[1], "09:00", "Prof 18")  # els altres, igual
    assert _alliberat(client, DILLUNS[2], "09:00", "Prof 31")  # la setmana següent, sí
    cos = client.get(f"/api/grups/{DILLUNS[1]}").json()
    assert cos["ocupats_per_hora"] == {"09:00": ["Prof 31"]}
    assert cos["grups_seleccionats_per_hora"] == {}  # no es barreja amb els grups


def test_un_reforc_ocupat_continua_disponible_amb_la_prioritat_del_reforc():
    # Amb «Reforç» com a categoria de prioritat (darrere dels alliberats)
    centre = nova_institucio(
        amb_xml=True, prioritats=[("Alliberats", ["alliberat"]), ("Guàrdies", ["Guàrdia"]), ("Reforços", ["Reforç"])]
    )
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(APP), nom)
    _configura_reforc_per_defecte(client)
    assert _disponibles(client, DILLUNS[1], "09:00")["Prof 31"] == "alliberat"
    client.put(f"/api/grups/{DILLUNS[1]}", json={"ocupats": {"09:00": ["Prof 31"]}})
    assert _disponibles(client, DILLUNS[1], "09:00")["Prof 31"] == "Reforç"


def test_la_taula_nomes_mostra_les_hores_amb_grups_o_activitats_alliberables(client):
    # Dilluns: cap grup té classe al pati, a les 13:30, a les 14:30 ni a les 17:00
    hores = client.get(f"/api/grups/{DILLUNS[1]}").json()["hores"]
    assert hores == ["08:00", "09:00", "10:00", "11:30", "12:30", "15:00", "16:00"]
    # Si una hora que no surt ja té alguna cosa marcada, es continua mostrant
    client.put(f"/api/grups/{DILLUNS[1]}", json={"grups": {"17:00": ["1-ESO-A"]}})
    assert "17:00" in client.get(f"/api/grups/{DILLUNS[1]}").json()["hores"]


def test_ocupat_un_dia_guanya_a_un_canvi_d_estat_alliberat(client):
    # La franja s'ha marcat amb alumnes i després s'ha tornat a alliberar
    _configura_reforc_per_defecte(client)
    _amb_alumnes(client, "Prof 31", "Dilluns", "09:00", DILLUNS[0])
    _amb_alumnes(client, "Prof 31", "Dilluns", "09:00", DILLUNS[1], amb_alumnes=False)
    assert _alliberat(client, DILLUNS[2], "09:00", "Prof 31")
    client.put(f"/api/grups/{DILLUNS[2]}", json={"ocupats": {"09:00": ["Prof 31"]}})
    assert not _alliberat(client, DILLUNS[2], "09:00", "Prof 31")


def test_un_error_llegint_els_canvis_per_periode_no_es_calla():
    # La taula es crea sempre en obrir la BD (database.create_data_tables):
    # abans, qualsevol error es convertia en «cap canvi» i deixava professors
    # sense alliberar sense que ningú se n'adonés
    from grups.repositories import AlliberamentsPeriodeRepository

    class SessioQueFalla:
        def query(self, *_args, **_kwargs):
            raise RuntimeError("error simulat llegint la BD")

        def rollback(self):
            pass

    with pytest.raises(RuntimeError):
        AlliberamentsPeriodeRepository.darrers(SessioQueFalla(), DILLUNS[1])
