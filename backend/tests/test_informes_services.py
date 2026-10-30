"""
Els càlculs dels informes (pdf/services.py), sense BD ni PDF: cada apartat
de l'informe de direcció a partir d'una llista de substitucions.
"""

from pdf import services

MESOS_CA = services.MESOS["ca"]


def _sub(data, tipus="ABSENCIA", absent="Prof 1", substitut="", grup="1-ESO-A", hora="08:00", assignatura="Català"):
    return {
        "data": data,
        "hora": hora,
        "professor_absent": absent,
        "substitut": substitut,
        "grup": grup,
        "assignatura": assignatura,
        "tipus_absencia": tipus,
    }


def test_compten_les_absencies_i_els_serveis_que_s_havien_de_cobrir():
    alliberats = {"2026-03-02": {"08:00": ["1-ESO-B", "professor:Prof 9"]}}
    no_sub = {"Guàrdia"}

    def real(**camps):
        return services.es_substitucio_real(_sub("2026-03-02", **camps), no_sub, alliberats)

    assert real()
    assert real(tipus="SERVEI")
    assert real(tipus="VIGILANCIA_ABSENT")
    assert not real(tipus="ENCADENADA")
    assert not real(tipus="VIGILANCIA")
    assert not real(assignatura="Guàrdia")
    assert not real(assignatura=" ")
    assert not real(grup="1-ESO-B")  # el grup no tenia classe
    assert not real(absent="Prof 9")  # el professor estava alliberat
    assert real(hora="09:00", grup="1-ESO-B")


def test_els_informes_nomes_compten_absencies_i_serveis():
    tipus = ["ABSENCIA", "SERVEI", "VIGILANCIA_ABSENT", "VIGILANCIA", "ENCADENADA"]
    subs = [_sub("2026-03-02", tipus=t, substitut="Prof 5") for t in tipus]

    assert [s["tipus_absencia"] for s in services.compta_als_informes(subs)] == ["ABSENCIA", "SERVEI"]


def test_resum():
    subs = [
        _sub("2026-03-02", substitut="Prof 5"),
        _sub("2026-03-02", tipus="SERVEI"),
        _sub("2026-03-03", tipus="SERVEI", substitut="Prof 6"),
    ]

    assert services.resum(subs, total_baixes=2) == {
        "total_absencies": 1,
        "total_serveis": 2,
        "total_baixes": 2,
        "total_substitucions": 2,
        "total_necessiten": 3,
        "cobertura_pct": 2 / 3 * 100,
        "dies_actius": 2,
    }
    assert services.resum([], total_baixes=0)["cobertura_pct"] == 0


def test_per_mes_per_ordre():
    subs = [
        _sub("2026-03-02", substitut="Prof 5"),
        _sub("2026-02-27", tipus="SERVEI"),
    ]

    assert services.per_mes(subs, MESOS_CA) == [
        {"mes": "Febrer 2026", "absencies": 0, "serveis": 1, "substitucions": 0, "cobertura": 0},
        {"mes": "Març 2026", "absencies": 1, "serveis": 0, "substitucions": 1, "cobertura": 100.0},
    ]


def test_la_cobertura_de_cada_mes_es_com_la_global():
    subs = [
        _sub("2026-03-02", substitut="Prof 5"),
        _sub("2026-03-03", tipus="SERVEI", substitut="Prof 6"),
        _sub("2026-03-04"),
        _sub("2026-03-05", tipus="SERVEI"),
    ]

    (marc,) = services.per_mes(subs, MESOS_CA)

    assert marc["substitucions"] == 2
    assert marc["cobertura"] == 2 / 4 * 100 == services.resum(subs, total_baixes=0)["cobertura_pct"]


def test_professors_de_mes_a_menys_i_els_empats_en_l_ordre_en_que_surten():
    subs = [
        _sub("2026-03-02", absent="Prof 2", substitut="Prof 7"),
        _sub("2026-03-02", absent="Prof 1", tipus="SERVEI", substitut="Prof 8"),
        _sub("2026-03-03", absent="Prof 1", substitut=" Prof 8 "),
        _sub("2026-03-04", absent=""),
    ]

    assert services.professors_absencies(subs) == [
        {"nom": "Prof 1", "absencies": 1, "serveis": 1, "total": 2},
        {"nom": "Prof 2", "absencies": 1, "serveis": 0, "total": 1},
    ]
    assert services.professors_substitucions(subs) == [{"nom": "Prof 8", "total": 2}, {"nom": "Prof 7", "total": 1}]


def test_per_dia_i_hora_amb_l_hora_normalitzada():
    subs = [
        _sub("2026-03-02", hora="9:00", substitut="Prof 5"),  # dilluns
        _sub("2026-03-02", hora="09:00"),
        _sub("2026-03-04", hora=""),  # dimecres
    ]

    per_hora, per_dia_hora = services.per_dia_i_hora(subs)

    assert per_hora == {
        "09:00": {"absencies": 2, "substitucions": 1},
        "Desconeguda": {"absencies": 1, "substitucions": 0},
    }
    assert per_dia_hora == {
        (0, "09:00"): {"absencies": 2, "substitucions": 1},
        (2, "Desconeguda"): {"absencies": 1, "substitucions": 0},
    }


def test_per_grup_i_nivell():
    subs = [
        _sub("2026-03-02", grup="1-ESO-A", substitut="Prof 5"),
        _sub("2026-03-02", grup="1-ESO-B"),
        _sub("2026-03-02", grup="ALTRE"),
        _sub("2026-03-02", grup="-"),
        _sub("2026-04-01", grup="1-ESO-A"),  # abril no és als mesos: no hi surt per mes
    ]
    mesos = ["Març 2026"]

    grups = services.per_grup_i_nivell(
        subs, ["1-ESO", "Altres"], {"1-ESO-A": "1-ESO", "1-ESO-B": "1-ESO"}, mesos, MESOS_CA
    )

    assert grups["per_nivell"] == {
        "1-ESO": {"absencies": 3, "cobertes": 1, "pendents": 2, "pct": 33, "n_grups": 2},
        "Altres": {"absencies": 1, "cobertes": 0, "pendents": 1, "pct": 0, "n_grups": 1},
    }
    assert grups["per_grup_mes"] == {
        "1-ESO-A": {"Març 2026": 1},
        "1-ESO-B": {"Març 2026": 1},
        "ALTRE": {"Març 2026": 1},
    }
    assert [g["nom"] for g in grups["grups_ordenats"]] == ["1-ESO-A", "1-ESO-B", "ALTRE"]
