"""
El diagnòstic de per què un horari d'exàmens no és viable
(scheduler_engine/core/diagnostic.InfeasibilityDiagnostic), cridat
directament amb exàmens simulats. Ha de dir el que realment impedeix
col·locar-los i no donar com a causa una restricció que es pot complir.

Calendari: dilluns i dimarts, a les 09:00 i a les 11:30 (4 hores).
"""

from scheduler_engine.core.diagnostic import InfeasibilityDiagnostic
from scheduler_engine.core.missatges import missatge

DIES = [("Dilluns", "2026-04-20"), ("Dimarts", "2026-04-21")]
HORES = ["09:00", "11:30"]


def _examen(nom, nivell):
    return {"nom": nom, "curs": nivell, "sessions": [{"nom": nom, "curs": nivell, "examens": []}]}


def _diagnostic(examens, **dures):
    restriccions = {"restriccions_dures": dures, "preferencies": {}}
    nivells = sorted({e["curs"] for e in examens})
    return InfeasibilityDiagnostic(restriccions, DIES, HORES, nivells).run(examens)


def _incompatibles(*noms):
    return {"G": list(noms), "_pes_G": 100}


# Un examen de cada nivell: la capacitat per nivell no hi intervé
FIL1, FIL2, FIL3 = _examen("Fil (1-BAT)", "1-BAT"), _examen("Fil (2-BAT)", "2-BAT"), _examen("Fil (3-BAT)", "3-BAT")


def test_tres_incompatibles_limitats_a_dues_hores_no_hi_caben():
    # Hi ha 4 hores al calendari, però els tres només poden anar dilluns
    msgs = _diagnostic(
        [FIL1, FIL2, FIL3],
        no_mateix_slot=_incompatibles("Fil (1-BAT)", "Fil (2-BAT)", "Fil (3-BAT)"),
        assignatures_dia_fix={"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns", "Fil (3-BAT)": "Dilluns"},
    )
    assert len(msgs) == 1
    assert msgs[0] == missatge(
        "hores_insuficients", grup="G", assignatures=["Fil (1-BAT)", "Fil (2-BAT)", "Fil (3-BAT)"], count=3, hores=2
    )


def test_dos_incompatibles_amb_les_mateixes_dues_hores_hi_caben():
    # Abans es donava com a conflicte qualsevol parella amb les mateixes hores
    msgs = _diagnostic(
        [FIL1, FIL2],
        no_mateix_slot=_incompatibles("Fil (1-BAT)", "Fil (2-BAT)"),
        assignatures_dia_fix={"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"},
    )
    assert msgs == []


def test_dos_incompatibles_fixats_a_la_mateixa_hora():
    msgs = _diagnostic(
        [FIL1, FIL2],
        no_mateix_slot=_incompatibles("Fil (1-BAT)", "Fil (2-BAT)"),
        assignatures_dia_fix={"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"},
        assignatures_hora_fix={"Fil (1-BAT)": "09:00", "Fil (2-BAT)": "09:00"},
    )
    assert len(msgs) == 1
    assert msgs[0] == missatge(
        "parella_mateixa_hora",
        grup="G",
        assignatures=["Fil (1-BAT)", "Fil (2-BAT)"],
        nom="Fil (1-BAT)",
        altre="Fil (2-BAT)",
    )


def test_cinc_incompatibles_en_quatre_hores():
    examens = [_examen(f"Ex{i} ({i}-N)", f"{i}-N") for i in range(5)]
    msgs = _diagnostic(examens, no_mateix_slot=_incompatibles(*(e["nom"] for e in examens)))
    assert len(msgs) == 1
    assert msgs[0] == missatge(
        "hores_insuficients", grup="G", assignatures=[e["nom"] for e in examens], count=5, hores=4
    )


def test_quatre_incompatibles_en_quatre_hores_hi_caben():
    examens = [_examen(f"Ex{i} ({i}-N)", f"{i}-N") for i in range(4)]
    assert _diagnostic(examens, no_mateix_slot=_incompatibles(*(e["nom"] for e in examens))) == []


def _examens_1bat(n):
    return [_examen(f"Ex{i} (1-BAT)", "1-BAT") for i in range(n)]


def test_tres_examens_d_un_nivell_amb_una_sola_hora_possible():
    # Abans comptava «dates amb alguna hora × totes les hores»: 1 × 2 = 2
    msgs = _diagnostic(_examens_1bat(3), slots_valids_per_nivell={"1-BAT": {"Dilluns": ["09:00"], "Dimarts": []}})
    assert msgs == [missatge("capacitat_nivell_dates", nivell="1-BAT", count=3, hores=1, dies=1)]


def test_tres_examens_d_un_nivell_amb_una_hora_cada_dia():
    # 2 hores possibles en 2 dates; abans en comptava 2 × 2 = 4 i no ho detectava
    msgs = _diagnostic(
        _examens_1bat(3), slots_valids_per_nivell={"1-BAT": {"Dilluns": ["09:00"], "Dimarts": ["11:30"]}}
    )
    assert msgs == [missatge("capacitat_nivell_dates", nivell="1-BAT", count=3, hores=2, dies=2)]


def test_dos_examens_d_un_nivell_amb_una_hora_cada_dia_hi_caben():
    assert (
        _diagnostic(_examens_1bat(2), slots_valids_per_nivell={"1-BAT": {"Dilluns": ["09:00"], "Dimarts": ["11:30"]}})
        == []
    )


# ------------------------------------------- tres causes de «dia_hora_fix»


def test_fixat_a_hora_sense_inici_diu_l_hora_i_el_nivell():
    # Revisió B1: bloquejat a totes les altres franges per «fixat» i a la seva
    # per «nivell sense inici»; abans sortia la més freqüent, «Dia/hora fixat»
    msgs = _diagnostic(
        [FIL1],
        assignatures_dia_fix={"Fil (1-BAT)": "Dilluns"},
        assignatures_hora_fix={"Fil (1-BAT)": "11:30"},
        slots_valids_per_nivell={"1-BAT": {"Dilluns": ["09:00"], "Dimarts": ["09:00", "11:30"]}},
    )
    assert msgs == [
        missatge("fixat_a_hora_sense_inici", nom="Fil (1-BAT)", dia="Dilluns", hora="11:30", nivell="1-BAT")
    ]


def test_fixat_a_un_dia_fora_de_les_dates():
    msgs = _diagnostic([FIL1], assignatures_dia_fix={"Fil (1-BAT)": "Dijous"})
    assert msgs == [missatge("fixat_fora_de_dates", nom="Fil (1-BAT)", dia="Dijous", hora="")]


def test_fixat_a_una_hora_que_no_es_d_examen():
    msgs = _diagnostic([FIL1], assignatures_hora_fix={"Fil (1-BAT)": "10:00"})
    assert msgs == [missatge("fixat_fora_de_dates", nom="Fil (1-BAT)", dia="", hora="10:00")]


def test_fixat_a_una_franja_prohibida():
    msgs = _diagnostic(
        [FIL1],
        assignatures_dia_fix={"Fil (1-BAT)": "2026-04-21"},
        assignatures_slot_prohibit=[{"assignatures": ["Fil (1-BAT)"], "dia": "Dimarts"}],
    )
    assert msgs == [missatge("fixat_a_franja_prohibida", nom="Fil (1-BAT)", dia="2026-04-21", hora="")]


def test_sense_pin_i_cap_hora_d_inici_la_causa_es_el_nivell():
    msgs = _diagnostic([FIL1], slots_valids_per_nivell={"1-BAT": {"Dilluns": [], "Dimarts": []}})
    assert msgs == [missatge("examen_sense_hora_causa", nom="Fil (1-BAT)", causa="nivell_sense_inici")]


def test_sense_pin_i_franges_prohibides():
    msgs = _diagnostic([FIL1], assignatures_slot_prohibit=[{"assignatures": ["Fil (1-BAT)"]}])
    assert msgs == [missatge("examen_sense_hora_causa", nom="Fil (1-BAT)", causa="franja_prohibida")]


# ------------------------------------------- límit d'exàmens per professor


def _del_professor(nom, nivell, professor="P"):
    return {"nom": nom, "curs": nivell, "sessions": [{"nom": nom, "curs": nivell, "examens": [{"titular": professor}]}]}


def _limit(dies, maxim, pes=100, assignatures=("Fil (1-BAT)", "Fil (2-BAT)")):
    return {
        "P": {
            "assignatures": list(assignatures),
            "dies_restringits": dies,
            "max_examens": maxim,
            "pes_penalitzacio": pes,
        }
    }


A, B = _del_professor("Fil (1-BAT)", "1-BAT"), _del_professor("Fil (2-BAT)", "2-BAT")


def test_limit_de_professor_amb_mes_examens_forcats_que_el_maxim():
    msgs = _diagnostic(
        [A, B],
        professors_limit_dies_especifics=_limit(["Dilluns"], 1),
        assignatures_dia_fix={"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"},
    )
    assert msgs == [
        missatge(
            "limit_professor_insuficient",
            professor="P",
            max=1,
            count=2,
            noms=["Fil (1-BAT)", "Fil (2-BAT)"],
            dies="Dilluns",
        )
    ]


def test_limit_zero_i_tots_els_dies_restringits():
    msgs = _diagnostic([A], professors_limit_dies_especifics=_limit(["Dilluns", "Dimarts"], 0))
    assert msgs == [
        missatge(
            "limit_professor_insuficient", professor="P", max=0, count=1, noms=["Fil (1-BAT)"], dies="Dilluns, Dimarts"
        )
    ]


def test_limit_amb_una_altra_data_possible_no_diu_res():
    # Sense fixar, tots dos poden anar dimarts
    assert _diagnostic([A, B], professors_limit_dies_especifics=_limit(["Dilluns"], 1)) == []


def test_limit_que_hi_cap_no_diu_res():
    dures = {"assignatures_dia_fix": {"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"}}
    assert _diagnostic([A, B], professors_limit_dies_especifics=_limit(["Dilluns"], 2), **dures) == []


def test_limit_tou_no_es_comprova():
    dures = {"assignatures_dia_fix": {"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"}}
    assert _diagnostic([A, B], professors_limit_dies_especifics=_limit(["Dilluns"], 1, pes=60), **dures) == []


def test_limit_nomes_compta_les_assignatures_i_el_professor_del_limit():
    altre = _del_professor("Fil (2-BAT)", "2-BAT", professor="Q")
    dures = {"assignatures_dia_fix": {"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"}}
    assert _diagnostic([A, altre], professors_limit_dies_especifics=_limit(["Dilluns"], 1), **dures) == []
    limit = _limit(["Dilluns"], 1, assignatures=("Fil (1-BAT)",))
    assert _diagnostic([A, B], professors_limit_dies_especifics=limit, **dures) == []


# ------------------------------- exclosos per examen i horari estricte


def test_dos_examens_amb_el_mateix_nom_el_que_queda_fora_te_missatge():
    # Abans les dates es desaven per nom: el segon (viable) trepitjava el
    # primer i el que no té cap hora no sortia
    sense_inici = _examen("Fil", "2-BAT")
    amb_inici = _examen("Fil", "1-BAT")
    msgs = _diagnostic([sense_inici, amb_inici], slots_valids_per_nivell={"2-BAT": {"Dilluns": [], "Dimarts": []}})
    assert msgs == [missatge("examen_sense_hora_causa", nom="Fil", causa="nivell_sense_inici")]


def _amb_estrictes(examens, analitza):
    restriccions = {"restriccions_dures": {"professors_horari_estricte": ["P"]}, "preferencies": {}}
    return InfeasibilityDiagnostic(restriccions, DIES, HORES, ["1-BAT"], analitza=analitza).run(examens)


def test_horari_estricte_es_comprova_amb_l_analisi():
    crides = []

    def analitza(sessio, dia, hora, data_iso):
        crides.append((sessio["nom"], dia, hora, data_iso))
        return {"abans_jornada": [{"professor": "P"}]}  # P hauria d'arribar abans a totes les franges

    assert _amb_estrictes([FIL1], analitza) == [
        missatge("examen_sense_hora_causa", nom="Fil (1-BAT)", causa="professors_estrictes")
    ]
    assert ("Fil (1-BAT)", "Dilluns", "09:00", "2026-04-20") in crides


def test_horari_estricte_sense_analisi_o_sense_estrictes_com_abans():
    assert _amb_estrictes([FIL1], None) == []
    crides = []
    diag = InfeasibilityDiagnostic({"restriccions_dures": {}}, DIES, HORES, ["1-BAT"], analitza=crides.append)
    assert diag.run([FIL1]) == [] and crides == []  # sense estrictes no s'analitza res
