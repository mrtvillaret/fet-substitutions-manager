"""
Les taules de l'informe de direcció (pdf/informe_direccio.py), sense generar
el PDF: el text de cada cel·la.
"""

from reportlab.platypus import Table

from pdf.informe_direccio import _taula_impacte_per_grup, _taula_matriu_grups_mesos, _taula_matriu_professors_mesos


def _text_de_les_celles(elems):
    (taula,) = [e for e in elems if isinstance(e, Table)]
    return [[c.getPlainText() if hasattr(c, "getPlainText") else str(c) for c in fila] for fila in taula._cellvalues]


def test_les_absencies_per_professor_i_mes_porten_el_total_que_decideix_l_ordre():
    # L'ordre és per absències + serveis: sense el total, «0 abs / 4 serv»
    # per sobre de «3 abs» semblava desordenat
    mesos = ["Setembre 2026"]
    professors = [
        {"nom": "Prof 12", "absencies": 0, "serveis": 4, "total": 4},
        {"nom": "Prof 26", "absencies": 3, "serveis": 0, "total": 3},
    ]
    abs_ = {"Prof 12": {"Setembre 2026": 0}, "Prof 26": {"Setembre 2026": 3}}
    serv = {"Prof 12": {"Setembre 2026": 4}, "Prof 26": {"Setembre 2026": 0}}

    files = _text_de_les_celles(_taula_matriu_professors_mesos(abs_, serv, mesos, professors))

    assert files[0][-3:] == ["Abs", "Serv", "Total"]
    assert files[1][0] == "Prof 12" and files[1][-3:] == ["—", "4", "4"]
    assert files[2][0] == "Prof 26" and files[2][-3:] == ["3", "—", "3"]


def test_impacte_i_evolucio_per_grup_no_mostren_ni_agrupen_per_nivell():
    grups = [
        {"nom": "1-BAT-A", "absencies": 2, "cobertes": 1, "pendents": 1, "pct": 50},
        {"nom": "2-ESO-A", "absencies": 1, "cobertes": 1, "pendents": 0, "pct": 100},
    ]
    dades = {
        "grups_ordenats": grups,
        "per_grup_mes": {"1-BAT-A": {"Març 2026": 2}, "2-ESO-A": {"Març 2026": 1}},
        "mesos": ["Març 2026"],
    }

    impacte = _text_de_les_celles(_taula_impacte_per_grup(dades))
    evolucio = _text_de_les_celles(_taula_matriu_grups_mesos(dades))

    assert impacte[0] == ["Grup", "Absències", "Amb substitut", "Pendents", "Cobertura"]
    assert [fila[0] for fila in impacte[1:]] == ["1-BAT-A", "2-ESO-A", "TOTAL"]
    assert evolucio[0] == ["Grup", "Mar", "Tot."]
