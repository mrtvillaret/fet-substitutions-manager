"""El validador i el cost donen els mateixos punts a cada incidència.

Abans el validador tenia uns pesos per defecte propis (restricció dura 1000 en
lloc de 10000, violada = dura en lloc de 20000, dies diferents 500 en lloc de 0)
i el límit per professor hi valia 600 on el cost en comptava 6000. Ara tots dos
treuen els punts de `planificador/compartit/punts.py`.
"""

import pytest

from planificador.compartit.punts import punts_limit_professor, punts_restriccio
from planificador.motor.avaluador import cost_sessio
from planificador.motor.registre import ValidadorHorari
from planificador.motor.regles import calcular_penalitzacio_total_professors

PROF = "Prof 1"


def _sessio(nom: str, curs: str = "1-BAT", professor: str = PROF) -> dict:
    return {"nom": f"{nom} ({curs})", "nom_base": nom, "curs": curs, "examens": [{"titular": professor}]}


def _horari(*franges) -> dict:
    """franges: (dia, hora, [sessions])"""
    dies = {}
    for dia, hora, sessions in franges:
        dies.setdefault(dia, []).append({"hora": hora, "sessions_simultanees": sessions})
    return {"dies": [{"dia": dia, "sessions": sessions} for dia, sessions in dies.items()], "metadata": {}}


def _punts(incidencia: dict) -> int:
    return incidencia["punts"]


def _linies(restriccions: dict, horari: dict, codi: str) -> list[dict]:
    """Les incidències del validador amb aquest codi (missatges amb dades)."""
    return [m for m in ValidadorHorari(horari, restriccions, set()).validar()["logs"] if m["codi"] == codi]


def _limit(pes, max_examens=0, **pesos) -> dict:
    restr = {
        "restriccions_dures": {
            "professors_limit_dies_especifics": {
                PROF: {
                    "assignatures": ["Filosofia", "Història"],
                    "dies_restringits": ["Dilluns"],
                    "max_examens": max_examens,
                    "pes_penalitzacio": pes,
                }
            }
        }
    }
    if pesos:
        restr["pesos_optimitzacio"] = pesos
    return restr


@pytest.mark.parametrize("pes", [60, 100])
@pytest.mark.parametrize("pesos", [{}, {"restriccio_dura": 1000, "restriccio_dura_violada": 3000}])
@pytest.mark.parametrize("examens", [1, 2])
def test_limit_per_professor_val_el_mateix_al_validador_i_al_cost(pes, pesos, examens):
    sessions = [_sessio("Filosofia"), _sessio("Història")][:examens]
    horari = _horari(*[("Dilluns", hora, [s]) for hora, s in zip(("08:00", "09:00"), sessions, strict=False)])
    restr = _limit(pes, **pesos)
    [linia] = _linies(restr, horari, "inc_limit_dies_professor")
    cost = calcular_penalitzacio_total_professors({"Dilluns": sessions}, restr)
    assert _punts(linia) == cost == punts_limit_professor(restr, pes, examens)


def test_el_cas_conegut_600_contra_6000():
    # Pes 60 %, sense pesos desats: abans el validador hi posava 600
    horari = _horari(("Dilluns", "08:00", [_sessio("Filosofia")]))
    [linia] = _linies(_limit(60), horari, "inc_limit_dies_professor")
    assert _punts(linia) == 6000


def test_pesos_per_defecte_iguals_que_al_cost():
    assert punts_restriccio({}, 50) == 5000
    assert punts_restriccio({}, 100) == 10000
    assert punts_restriccio({"pesos_optimitzacio": {"restriccio_dura": 1000}}, 100) == 10000
    assert punts_restriccio({"pesos_optimitzacio": {"restriccio_dura_violada": 7}}, 100) == 7


@pytest.mark.parametrize("pes", [40, 100])
def test_no_mateix_slot_val_el_mateix_que_cada_sessio_al_cost(pes):
    a, b = _sessio("Física"), _sessio("Química", curs="2-BAT", professor="Prof 2")
    restr = {"restriccions_dures": {"no_mateix_slot": {"G": ["Física", "Química"], "_pes_G": pes}}}
    horari = _horari(("Dilluns", "08:00", [a, b]))
    # Una línia per examen, com el cost (cada examen del grup en suma)
    linia, _ = _linies(restr, horari, "inc_no_mateix_slot")
    buida = {"substitucions": [], "abans_jornada": [], "despres_jornada": [], "no_treballa_dia": []}
    cost = cost_sessio(a, "Dilluns", "08:00", buida, restr, sessions_dia=[a, b], sessions_slot=[a, b])
    assert _punts(linia) == cost["breakdown"]["no_mateix_slot"] == punts_restriccio(restr, pes)


@pytest.mark.parametrize("pes", [30, 100])
def test_no_mateix_dia_val_el_mateix_que_cada_sessio_al_cost(pes):
    a, b = _sessio("Física"), _sessio("Química")
    restr = {"restriccions_dures": {"no_mateix_dia": [{"assignatures": ["Física", "Química"], "pes": pes}]}}
    horari = _horari(("Dilluns", "08:00", [a]), ("Dilluns", "09:00", [b]))
    linia, _ = _linies(restr, horari, "inc_no_mateix_dia")
    buida = {"substitucions": [], "abans_jornada": [], "despres_jornada": [], "no_treballa_dia": []}
    cost = cost_sessio(a, "Dilluns", "08:00", buida, restr, sessions_dia=[a, b], sessions_slot=[a])
    assert _punts(linia) == cost["breakdown"]["restriccio_dura"] == punts_restriccio(restr, pes)


@pytest.mark.parametrize("tipus,base", [("dies_diferents", 100), ("mateix_dia", 100)])
@pytest.mark.parametrize(
    "noms",
    [["Física (1-BAT)", "Química (1-BAT)"], ["Física", "Química"], ["Física", "Química (1-BAT)"]],
)
def test_preferencies_de_dia_simetriques_amb_noms_sense_nivell(tipus, base, noms):
    """La companya es troba pel nom complet o sense nivell, com la sessió pròpia. Abans, amb
    noms sense nivell no puntuava, i barrejats només ho feia una de les dues sessions."""
    a, b = _sessio("Física"), _sessio("Química")
    restr = {
        "preferencies": {tipus: [{"assignatures": noms, "pes": 90}]},
        "pesos_optimitzacio": {f"preferencia_{tipus}": base},
    }
    buida = {"substitucions": [], "abans_jornada": [], "despres_jornada": [], "no_treballa_dia": []}
    punts = [
        cost_sessio(s, "Dilluns", hora, buida, restr, sessions_dia=[a, b], sessions_slot=[s])["breakdown"][
            "preferencies"
        ]
        for s, hora in ((a, "08:00"), (b, "09:00"))
    ]
    assert punts == [90, 90] if tipus == "dies_diferents" else punts == [-90, -90]


@pytest.mark.parametrize("pes", [100, 90])
def test_mateixa_data_obligatoria_trencada_a_ma_suma_la_regla_incomplerta(pes):
    """Una «mateixa data» obligatòria amb els exàmens en dates diferents (només editant a
    mà) suma «Obligatòria incomplerta» un cop, amb la seva línia al registre; per sota del
    100 % no és obligatòria i no en suma."""
    from planificador.motor.avaluador import incidencies_restriccions

    a, b = _sessio("Física"), _sessio("Química")
    restr = {"preferencies": {"mateix_dia": [{"assignatures": ["Física", "Química"], "pes": pes}]}}
    horari = {
        "dies": [
            {"dia": "Dilluns", "data": "2027-03-01", "sessions": [{"hora": "08:00", "sessions_simultanees": [a]}]},
            {"dia": "Dimarts", "data": "2027-03-02", "sessions": [{"hora": "08:00", "sessions_simultanees": [b]}]},
        ],
        "metadata": {},
    }
    incidencies = [i for i in incidencies_restriccions(horari, restr) if i.concepte == "mateix_dia_obligatori"]
    linies = _linies(restr, horari, "inc_mateix_dia_obligatori")
    if pes < 100:
        assert incidencies == [] and linies == []
    else:
        assert [i.punts for i in incidencies] == [10000]
        assert linies == [
            {
                "codi": "inc_mateix_dia_obligatori",
                "params": {"nom": "Física (1-BAT), Química (1-BAT)", "dates": ["2027-03-01", "2027-03-02"]},
                "punts": 10000,
            }
        ]


@pytest.mark.parametrize(
    "dies,incidencia",
    [
        (["Dilluns"], True),  # un nom de dia: tots els dilluns junts (2 > 1)
        (["2027-03-01"], False),  # una data: només aquell dilluns (1)
        (["2027-03-01", "2027-03-08"], True),  # les dues dates en una fila: 2 > 1
        (["2027-3-8"], False),  # sense zeros, es normalitza
    ],
)
def test_limit_per_professor_amb_dates_o_noms_de_dia(dies, incidencia):
    """Amb dues setmanes, una fila del límit amb dates compta només aquelles dates; amb un
    nom de dia, tots els dies de la planificació amb aquell nom."""
    from planificador.motor.avaluador import incidencies_restriccions
    from planificador.schemas import LimitDiesProfessor

    a, b = _sessio("Filosofia"), _sessio("Història")
    limit = LimitDiesProfessor.model_validate(
        {"assignatures": ["Filosofia", "Història"], "dies_restringits": dies, "max_examens": 1, "pes_penalitzacio": 60}
    ).model_dump()
    restr = {"restriccions_dures": {"professors_limit_dies_especifics": {PROF: limit}}}
    horari = {
        "dies": [
            {"dia": "Dilluns", "data": "2027-03-01", "sessions": [{"hora": "08:00", "sessions_simultanees": [a]}]},
            {"dia": "Dilluns", "data": "2027-03-08", "sessions": [{"hora": "08:00", "sessions_simultanees": [b]}]},
        ],
        "metadata": {},
    }
    limits = [i for i in incidencies_restriccions(horari, restr) if i.concepte == "limit_dies_professor"]
    assert bool(limits) is incidencia
    assert bool(_linies(restr, horari, "inc_limit_dies_professor")) is incidencia


@pytest.mark.parametrize(
    "dies,data,viola",
    [
        (["Dilluns"], "2027-03-08", True),
        (["2027-03-01"], "2027-03-08", False),
        (["2027-03-08"], "2027-03-08", False),
        (["2027-03-01"], "2027-03-01", True),  # el mateix dilluns de la regla: 2 > 1
    ],
)
def test_limit_obligatori_per_data_als_motors(dies, data, viola):
    """La versió dura que fan servir els motors: amb una data, un examen d'un altre dilluns
    no hi compta; amb el nom del dia, sí (el segon dilluns supera el màxim d'1)."""
    from planificador.motor.regles import viola_limit_dies_professor_obligatori

    a, b = _sessio("Filosofia"), _sessio("Història")
    restr = {
        "restriccions_dures": {
            "professors_limit_dies_especifics": {
                PROF: {
                    "assignatures": ["Filosofia", "Història"],
                    "dies_restringits": dies,
                    "max_examens": 1,
                    "pes_penalitzacio": 100,
                }
            }
        }
    }
    col_locades = {"2027-03-01": [a]}
    assert viola_limit_dies_professor_obligatori(b, data, col_locades, restr) is viola
