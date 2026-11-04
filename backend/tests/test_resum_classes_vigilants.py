from types import SimpleNamespace

from pdf.validacions import _resum_cobertures


def test_el_resum_identifica_les_classes_del_vigilant_i_conserva_els_recomptes():
    cob = SimpleNamespace(classes_de_vigilants={"09:00": {"Prof 1": "Prof 2", "Prof 3": ""}, "10:00": {"Prof 4": ""}})
    avisos = []
    _resum_cobertures(cob, avisos)
    assert avisos == [
        "ℹ️ 1 classes de vigilants amb substitut (el professor vigila un examen a aquella hora)",
        "❌ 2 classes de vigilants sense substitut (el professor vigila un examen a aquella hora)",
    ]
    avisos = []
    _resum_cobertures(SimpleNamespace(classes_de_vigilants={}), avisos)
    assert avisos == []
