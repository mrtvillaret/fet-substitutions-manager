"""El diagnòstic de per què un horari no és viable, cridat directament amb
exàmens simulats i sense rellotge real.

Calendari: dilluns i dimarts, a les 09:00 i a les 11:30 (4 hores).
"""

from types import SimpleNamespace

import pytest
from suport_motor import config_inventada as config_inventada
from suport_motor import xml_inventat as xml_inventat
from test_planificador_greedy import problema_de

from planificador.compartit.missatges import missatge
from planificador.motor.compatibilitat import GREEDY
from planificador.motor.diagnostic import (
    Diagnostic,
    DiagnosticIncompatibilitats,
    construir_dies_efectius,
    identifica_sessions_no_collocades,
)

DIES = [("Dilluns", "2026-04-20"), ("Dimarts", "2026-04-21")]
HORES = ["09:00", "11:30"]


def _examen(nom, nivell):
    return {"nom": nom, "curs": nivell, "sessions": [{"nom": nom, "curs": nivell, "examens": []}]}


def _diagnostic(examens, **dures):
    restriccions = {"restriccions_dures": dures, "preferencies": {}}
    nivells = sorted({e["curs"] for e in examens})
    return DiagnosticIncompatibilitats(restriccions, DIES, HORES, nivells).executa(examens)


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


@pytest.mark.parametrize("pes", [90, 0])
def test_incompatibles_tous_no_fan_inviable_res(pes):
    """Un «no a la mateixa data i hora» per sota del 100% només costa punts."""
    examens = [_examen(f"Ex{i} ({i}-N)", f"{i}-N") for i in range(5)]
    grup = {**_incompatibles(*(e["nom"] for e in examens)), "_pes_G": pes}
    assert _diagnostic(examens, no_mateix_slot=grup) == []
    fixats = _diagnostic(
        [FIL1, FIL2],
        no_mateix_slot={**_incompatibles("Fil (1-BAT)", "Fil (2-BAT)"), "_pes_G": pes},
        assignatures_dia_fix={"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"},
        assignatures_hora_fix={"Fil (1-BAT)": "09:00", "Fil (2-BAT)": "09:00"},
    )
    assert fixats == []


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
    # Bloquejat a totes les altres franges per «fixat» i a la seva
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
    return DiagnosticIncompatibilitats(restriccions, DIES, HORES, ["1-BAT"], analitza=analitza).executa(examens)


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
    diag = DiagnosticIncompatibilitats({"restriccions_dures": {}}, DIES, HORES, ["1-BAT"], analitza=crides.append)
    assert diag.executa([FIL1]) == [] and crides == []  # sense estrictes no s'analitza res


@pytest.mark.parametrize("motiu", [None, "temps", "nodes"])
def test_aturada_i_indicis_mantenen_el_text_i_l_ordre(monkeypatch, config_inventada, xml_inventat, motiu):
    diagnostic = Diagnostic(problema_de(config_inventada, xml_inventat), GREEDY)
    indici = missatge("dates_insuficients_examens", index=1, assignatures=["A", "B"], noms=["A", "B"], dies="Dilluns")
    monkeypatch.setattr(diagnostic, "incompatibilitats", lambda _: [indici])
    error = missatge("cerca_tallada_nodes", nodes=0) if motiu else missatge("examens_pendents")
    meta = {"viable": False, "error": error, "logs": ["registre"]}
    if motiu:
        meta["motiu_aturada"] = motiu
    horari = {"dies": [], "metadata": meta}
    pla = SimpleNamespace(cfg=config_inventada, nivells=["N1"])
    diagnostic.explica_no_viable(horari, pla, [indici], False)
    assert meta["incompatibilitats"] == ([error, indici] if motiu else [indici])
    assert meta["viable"] is False
    assert meta["logs"][-1] == error


def test_pendents_no_es_contaminen_entre_nivells_i_conserven_fallback():
    def sessio(curs):
        return {"nom": "A", "curs": curs}

    horari = {"dies": [{"sessions": [{"sessions_simultanees": [sessio("N1")]}]}]}
    assert identifica_sessions_no_collocades(horari, {"N1": [sessio("N1")], "N2": [sessio("N2")]}) == [
        missatge("examen_pendent", nom="A", nivell="N2")
    ]
    horari = {"dies": [], "metadata": {"recompte_nivells": {"N1": {"pendents": 2, "esperats": 2, "collocats": 0}}}}
    assert identifica_sessions_no_collocades(horari, {}) == [missatge("nivell_cap_collocat", nivell="N1", count=2)]


def test_diagnostic_expandeix_dates_sense_perdre_ordre_ni_repeticions():
    assert construir_dies_efectius(
        ["Dilluns", "2027-03-02"], {"dilluns": ["2027-03-01", "2027-03-08", "2027-03-01"]}
    ) == [("Dilluns", "2027-03-01"), ("Dilluns", "2027-03-08"), ("Dilluns", "2027-03-01"), ("Dimarts", "2027-03-02")]


def test_dos_examens_amb_les_mateixes_dues_dates_no_son_cap_causa(config_inventada, xml_inventat):
    """Poden anar en dates diferents; abans el diagnòstic deia que estaven «limitats a les
    mateixes dates» i enviava a mirar on no tocava."""
    examens = [_examen("A", "N1"), _examen("B", "N2")]
    assert _diagnostic(examens, no_mateix_dia=[{"assignatures": ["A", "B"], "pes": 100}]) == []

    config_inventada.restriccions = {
        "restriccions_dures": {"no_mateix_dia": [{"assignatures": ["A", "B"], "pes": 100}]}
    }
    config_inventada.durada_examen = 1  # exàmens d'una hora: hi caben a totes les franges
    diagnostic = Diagnostic(problema_de(config_inventada, xml_inventat), GREEDY)
    pla = SimpleNamespace(dies=["Dilluns", "Dimarts"], nivells=["N1"], dates=["2027-03-01", "2027-03-02"])
    assert diagnostic.precheck(pla) == []


@pytest.mark.parametrize("del_precheck", [True, False])
def test_error_del_diagnostic_conserva_les_causes_i_la_referencia(
    monkeypatch, config_inventada, xml_inventat, del_precheck
):
    from planificador.motor import diagnostic as modul

    diagnostic = Diagnostic(problema_de(config_inventada, xml_inventat), GREEDY)

    def falla(_):
        raise RuntimeError("error inventat")

    monkeypatch.setattr(diagnostic, "incompatibilitats", falla)
    monkeypatch.setattr(modul, "registra_excepcio", lambda _: "01234567")
    causa = missatge("examen_sense_hora", nom="A", nivell="N1")
    horari = {"dies": [], "metadata": {"viable": False, "error": missatge("examens_pendents")}}
    diagnostic.explica_no_viable(horari, SimpleNamespace(cfg=config_inventada, nivells=["N1"]), [causa], del_precheck)
    assert horari["metadata"]["explicacio_no_disponible"] == {"ref": "01234567"}
    assert horari["metadata"]["incompatibilitats"] == [causa]


@pytest.mark.parametrize("ordre", [False, True])
def test_un_examen_fixat_i_un_de_lliure_es_poden_repartir(ordre):
    """A només pot anar dilluns, però B té el dimarts; abans sortia «només pot anar a
    2026-04-20, que coincideix amb B»."""
    examens = [_examen("A", "N1"), _examen("B", "N2")]
    if ordre:
        examens.reverse()
    assert (
        _diagnostic(
            examens,
            no_mateix_dia=[{"assignatures": ["A", "B"], "pes": 100}],
            assignatures_dia_fix={"A": "Dilluns"},
        )
        == []
    )


def test_examens_sense_prou_dates_troba_el_conjunt_bloquejat():
    from planificador.motor.diagnostic import _examens_sense_prou_dates  # noqa: PLC0415

    d1, d2, d3 = "2026-04-20", "2026-04-21", "2026-04-22"
    # A, B i C només tenen dues dates entre tots; D (la tercera) no hi té res a veure
    items = [("D", {d3}), ("A", {d1, d2}), ("B", {d1, d2}), ("C", {d1, d2})]
    assert _examens_sense_prou_dates(items) == (["A", "B", "C"], [d1, d2])
    # Amb una data més per a C ja es poden repartir
    assert _examens_sense_prou_dates([("A", {d1, d2}), ("B", {d1, d2}), ("C", {d1, d2, d3})]) is None
    # Un examen sense cap data s'explica per una altra causa
    assert _examens_sense_prou_dates([("A", set()), ("B", {d1})]) is None


def test_dos_fixats_el_mateix_dia_conserven_les_dues_explicacions():
    examens = [_examen("A", "N1"), _examen("B", "N2")]
    assert _diagnostic(
        examens,
        no_mateix_dia=[{"assignatures": ["A", "B"], "pes": 100}],
        assignatures_dia_fix={"A": "Dilluns", "B": "Dilluns"},
    ) == [
        missatge("fixats_mateix_dia", index=1, assignatures=["A", "B"], noms=["A", "B"], dia="Dilluns"),
        missatge("dates_insuficients_examens", index=1, assignatures=["A", "B"], noms=["A", "B"], dies="2026-04-20"),
    ]
