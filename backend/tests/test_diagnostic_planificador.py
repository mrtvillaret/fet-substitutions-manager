"""
El diagnòstic de per què un horari d'exàmens no és viable
(scheduler_engine/core/diagnostic.InfeasibilityDiagnostic), cridat
directament amb exàmens simulats. Ha de dir el que realment impedeix
col·locar-los i no donar com a causa una restricció que es pot complir.

Calendari: dilluns i dimarts, a les 09:00 i a les 11:30 (4 hores).
"""
from scheduler_engine.core.diagnostic import InfeasibilityDiagnostic

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
    msgs = _diagnostic([FIL1, FIL2, FIL3],
                       no_mateix_slot=_incompatibles("Fil (1-BAT)", "Fil (2-BAT)", "Fil (3-BAT)"),
                       assignatures_dia_fix={"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns",
                                             "Fil (3-BAT)": "Dilluns"})
    assert len(msgs) == 1
    assert "3 exàmens no poden coincidir" in msgs[0]
    assert "només tenen 2 hores possibles" in msgs[0]


def test_dos_incompatibles_amb_les_mateixes_dues_hores_hi_caben():
    # Abans es donava com a conflicte qualsevol parella amb les mateixes hores
    msgs = _diagnostic([FIL1, FIL2],
                       no_mateix_slot=_incompatibles("Fil (1-BAT)", "Fil (2-BAT)"),
                       assignatures_dia_fix={"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"})
    assert msgs == []


def test_dos_incompatibles_fixats_a_la_mateixa_hora():
    msgs = _diagnostic([FIL1, FIL2],
                       no_mateix_slot=_incompatibles("Fil (1-BAT)", "Fil (2-BAT)"),
                       assignatures_dia_fix={"Fil (1-BAT)": "Dilluns", "Fil (2-BAT)": "Dilluns"},
                       assignatures_hora_fix={"Fil (1-BAT)": "09:00", "Fil (2-BAT)": "09:00"})
    assert len(msgs) == 1
    assert "'Fil (1-BAT)' i 'Fil (2-BAT)' no poden coincidir" in msgs[0]


def test_cinc_incompatibles_en_quatre_hores():
    examens = [_examen(f"Ex{i} ({i}-N)", f"{i}-N") for i in range(5)]
    msgs = _diagnostic(examens, no_mateix_slot=_incompatibles(*(e["nom"] for e in examens)))
    assert len(msgs) == 1
    assert "5 exàmens no poden coincidir" in msgs[0]
    assert "només tenen 4 hores possibles" in msgs[0]


def test_quatre_incompatibles_en_quatre_hores_hi_caben():
    examens = [_examen(f"Ex{i} ({i}-N)", f"{i}-N") for i in range(4)]
    assert _diagnostic(examens, no_mateix_slot=_incompatibles(*(e["nom"] for e in examens))) == []


def _examens_1bat(n):
    return [_examen(f"Ex{i} (1-BAT)", "1-BAT") for i in range(n)]


def test_tres_examens_d_un_nivell_amb_una_sola_hora_possible():
    # Abans comptava «dates amb alguna hora × totes les hores»: 1 × 2 = 2
    msgs = _diagnostic(_examens_1bat(3), slots_valids_per_nivell={"1-BAT": {"Dilluns": ["09:00"], "Dimarts": []}})
    assert msgs == ["1-BAT: 3 ítems > 1 slots disponibles en 1 dates"]


def test_tres_examens_d_un_nivell_amb_una_hora_cada_dia():
    # 2 hores possibles en 2 dates; abans en comptava 2 × 2 = 4 i no ho detectava
    msgs = _diagnostic(_examens_1bat(3),
                       slots_valids_per_nivell={"1-BAT": {"Dilluns": ["09:00"], "Dimarts": ["11:30"]}})
    assert msgs == ["1-BAT: 3 ítems > 2 slots disponibles en 2 dates"]


def test_dos_examens_d_un_nivell_amb_una_hora_cada_dia_hi_caben():
    assert _diagnostic(_examens_1bat(2),
                       slots_valids_per_nivell={"1-BAT": {"Dilluns": ["09:00"], "Dimarts": ["11:30"]}}) == []
