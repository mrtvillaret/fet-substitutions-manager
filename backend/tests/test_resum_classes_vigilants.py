"""Les cobertures es mostren per classe, amb gravetat i substitut efectiu."""

from test_vigilancies_analisi import dia_fals, vig

from vigilancies.analisi import analitza_vigilancies


def test_identifica_cada_classe_en_lloc_d_un_resum_que_pot_duplicar_problemes():
    files = [dict(hora="10:00", professor_absent="Prof 1", grup="G2", substitut="Prof 2", tipus_absencia="VIGILANCIA")]
    dia = dia_fals(
        [vig(), vig("2", vigilant="Prof 3")],
        files,
        {
            "Prof 1": {"assignatura": "Prova 1", "grup": "G2"},
            "Prof 3": {"assignatura": "Prova 3", "grup": "G3"},
        },
    )
    problemes = analitza_vigilancies(dia)
    cobertes = [p for p in problemes if p["tipus"] == "classe_coberta"]
    pendents = [p for p in problemes if p["tipus"] == "classe_sense_cobertura"]
    assert len(cobertes) == len(pendents) == 1
    assert cobertes[0]["cobertura_efectiva"] == "Prof 2"
    assert pendents[0]["gravetat"] == "important"
    assert "Prova 1" in cobertes[0]["missatge"] and "G2" in cobertes[0]["missatge"]
    assert "Prova 3" in pendents[0]["missatge"] and "G3" in pendents[0]["missatge"]
    assert analitza_vigilancies(dia_fals([])) == []
