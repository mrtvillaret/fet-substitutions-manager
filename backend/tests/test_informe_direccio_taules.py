"""
Les taules de l'informe de direcció (pdf/informe_direccio.py), sense generar
el PDF: el text de cada cel·la.
"""

from reportlab.platypus import Table

from pdf.informe_direccio import _taula_matriu_professors_mesos


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
