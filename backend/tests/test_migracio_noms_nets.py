"""
Migració de la regla dels noms (migracions/noms_nets.py) sobre una BD de
centre temporal amb l'esquema de l'aplicació.
"""

import json
import uuid
from datetime import date, datetime

import pytest

from database import get_data_db_session, get_data_dir_for_institucio
from migracions.noms_nets import main, migra
from models import (
    AssignaturaPrioritat,
    CategoriaPrioritat,
    Configuracio,
    ConfiguracioExamen,
    NoSubstituir,
    Professor,
    Substitucio,
)

ABANS, DESPRES = datetime(2026, 1, 1), datetime(2026, 2, 1)


@pytest.fixture
def centre():
    nom = f"migra_{uuid.uuid4().hex[:8]}"
    with get_data_db_session(nom) as db:
        db.add_all(
            [
                NoSubstituir(assignatura="Guàrdia", updated_at=ABANS),
                NoSubstituir(assignatura=" Guàrdia", updated_at=DESPRES),  # la més recent
                NoSubstituir(assignatura="", updated_at=ABANS),
                NoSubstituir(assignatura="   ", updated_at=DESPRES),  # només espais: el buit
                NoSubstituir(assignatura="Pares", updated_at=ABANS),
            ]
        )
        cat1 = CategoriaPrioritat(nom="Guàrdies", ordre=0, activa=True)
        cat2 = CategoriaPrioritat(nom="Altres", ordre=1, activa=True)
        db.add_all([cat1, cat2])
        db.flush()
        db.add_all(
            [
                AssignaturaPrioritat(assignatura="Guàrdia ", categoria_id=cat1.id, pes=6, updated_at=DESPRES),
                AssignaturaPrioritat(assignatura="Guàrdia", categoria_id=cat1.id, pes=3, updated_at=ABANS),
                AssignaturaPrioritat(assignatura="Guàrdia", categoria_id=cat2.id, pes=1, updated_at=ABANS),
                Professor(nom="  Prof 3"),
                ConfiguracioExamen(assignatura="Anglès ", grup="1-BAT-A", titular=" Prof 3", aula="A1 "),
                Substitucio(
                    data=date(2026, 4, 20),
                    hora="10:00",
                    professor_absent="Prof 15",
                    assignatura="Anglès ",
                    grup="1-BAT-A",
                    substitut=" Prof 21",
                ),
                Configuracio(clau="ultim_professor_subs", valor="  Prof 9 "),
                Configuracio(clau="activitats_alliberables", valor=json.dumps(["Reunió", "Reunió ", " Pati"])),
            ]
        )
        db.commit()
    return str(get_data_dir_for_institucio(nom) / "gestor.db"), nom


def _estat(nom):
    with get_data_db_session(nom) as db:
        return {
            "no_substituir": sorted((x.assignatura, x.updated_at) for x in db.query(NoSubstituir)),
            "prioritats": sorted((x.categoria_id, x.assignatura, x.pes) for x in db.query(AssignaturaPrioritat)),
            "professors": [x.nom for x in db.query(Professor)],
            "examens": [(x.assignatura, x.titular, x.aula) for x in db.query(ConfiguracioExamen)],
            "substitucions": [(x.assignatura, x.substitut) for x in db.query(Substitucio)],
            "config": {x.clau: x.valor for x in db.query(Configuracio)},
        }


def test_el_recompte_no_canvia_res_i_compta_les_fusions(centre):
    cami, nom = centre
    abans = _estat(nom)
    resum = migra(cami, aplica=False)
    assert _estat(nom) == abans
    assert resum["no_substituir: fusions"] == 2  # « Guàrdia» i «   »
    assert resum["assignatures_prioritat: fusions"] == 1  # només dins de la mateixa categoria
    assert resum["configuracio[activitats_alliberables]: fusions"] == 1


def test_aplica_fusiona_dins_de_cada_llista_i_conserva_la_mes_recent(centre):
    cami, nom = centre
    migra(cami, aplica=True)
    estat = _estat(nom)
    # «No substituir»: una Guàrdia (la més recent) i un sol buit
    assert estat["no_substituir"] == [("", DESPRES), ("Guàrdia", DESPRES), ("Pares", ABANS)]
    # Prioritats: dins la categoria 1 es queda la més recent (pes 6); la de la categoria 2 no es toca
    assert [p[1:] for p in estat["prioritats"]] == [("Guàrdia", 6), ("Guàrdia", 1)]


def test_una_activitat_a_no_substituir_i_a_les_prioritats_es_queda_a_totes_dues(centre):
    """Una Guàrdia: el professor pot anar a substituir, però si se'n va, se
    l'ha de substituir a ell. Mai es fusionen entrades de taules diferents."""
    cami, nom = centre
    migra(cami, aplica=True)
    estat = _estat(nom)
    assert "Guàrdia" in {a for a, _ in estat["no_substituir"]}
    assert "Guàrdia" in {p[1] for p in estat["prioritats"]}


def test_aplica_neteja_tambe_els_camps_que_no_son_clau_i_els_registres(centre):
    cami, nom = centre
    migra(cami, aplica=True)
    estat = _estat(nom)
    assert estat["professors"] == ["Prof 3"]
    assert estat["examens"] == [("Anglès", "Prof 3", "A1")]  # titular i aula també
    assert estat["substitucions"] == [("Anglès", "Prof 21")]
    assert estat["config"]["ultim_professor_subs"] == "Prof 9"
    assert json.loads(estat["config"]["activitats_alliberables"]) == ["Reunió", "Pati"]


def test_aplica_dos_cops_no_fa_res_el_segon(centre):
    cami, nom = centre
    migra(cami, aplica=True)
    estat = _estat(nom)
    assert all(n == 0 for n in migra(cami, aplica=True).values())
    assert _estat(nom) == estat


def test_la_linia_d_ordres_fa_copia_abans_d_aplicar_i_no_escriu_noms(centre, capsys):
    cami, _ = centre
    assert main(["--recompte", cami]) == 0
    assert main(["--aplica", cami]) == 0
    sortida = capsys.readouterr().out
    assert "bd 1" in sortida and "Guàrdia" not in sortida and "Prof" not in sortida
    copies = list(get_data_dir_for_institucio(centre[1]).glob("gestor.db.abans-noms-nets-*"))
    assert len(copies) == 1


def test_el_recompte_obre_la_bd_en_nomes_lectura(centre, monkeypatch):
    import sqlite3

    import migracions.noms_nets as m

    obertes = []
    original = sqlite3.connect
    monkeypatch.setattr(m.sqlite3, "connect", lambda *a, **k: obertes.append((a, k)) or original(*a, **k))
    migra(centre[0], aplica=False)
    assert obertes and all("mode=ro" in a[0] and k.get("uri") for a, k in obertes)
