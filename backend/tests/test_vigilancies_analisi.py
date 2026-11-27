"""Mateixa anàlisi a pantalla, revisió i documents; cobertures reals."""

import subprocess
from datetime import date
from types import SimpleNamespace

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio
from suport_noms import unic

from database import get_data_db_session
from models import Substitucio, Vigilancia
from pdf.router import router as pdf_router
from pdf.validacions import _absencies_sense_substitut, _baixes_i_substituts_no_valids, _substituts_repetits
from substitucions.domain import DiaEscolar
from substitucions.files import FilaSubstitucio
from vigilancies.analisi import analitza_vigilancies
from vigilancies.files import FilaVigilancia
from vigilancies.router import router


def dia_fals(
    vigs,
    files=(),
    activitats=None,
    absents=None,
    alliberats=None,
    horari=True,
    *,
    baixes=(),
    jornada=("09:00", "11:00"),
):
    activitats = activitats or {}
    dia = SimpleNamespace(
        vigilancies=vigs,
        files=[FilaSubstitucio(**f) for f in files],
        absents_per_hora=absents or {},
        alliberats=alliberats or {},
        baixes=set(baixes),
        nom_del_dia="Dilluns",
        horari=SimpleNamespace(hores=["09:00", "10:00", "11:00"], get_jornada_professor=lambda *_: jornada)
        if horari
        else None,
        activitat=lambda p, h: activitats.get(p, {}),
        professor_a_horari=lambda p: True if horari else None,
        vigilants_per_hora={},
    )
    dia.motius_substitut = lambda substitut, hora: DiaEscolar.motius_substitut(dia, substitut, hora)
    return dia


def missatges_de_files(dia, problemes):
    """El que afegeixen a la revisió les comprovacions de files (pdf/validacions.py)."""
    conflictes: list[str] = []
    avisos: list[str] = []
    _substituts_repetits(dia, avisos, problemes)
    _absencies_sense_substitut(dia, conflictes, problemes)
    _baixes_i_substituts_no_valids(dia, conflictes, avisos, problemes)
    return conflictes + avisos


def vig(id="1", vigilant="Prof 1", hora="10:00", aula="A1", grups="G1"):
    return FilaVigilancia(id=id, vigilant=vigilant, hora=hora, aula=aula, grups=grups, tipus="Prova")


@pytest.mark.parametrize(
    "cas",
    ["valida", "buida", "altre_grup", "absent", "baixa", "amb_classe", "vigilant", "dues_substitucions"],
)
def test_nomes_una_cobertura_valida_resol_la_classe_pendent(cas):
    from vigilancies.analisi import analitza_vigilancies

    sub = dict(
        hora="10:00",
        professor_absent="Prof 1",
        grup="G3" if cas == "altre_grup" else "G2",
        substitut="" if cas == "buida" else "Prof 2",
        tipus_absencia="VIGILANCIA",
    )
    activitats = {"Prof 1": {"assignatura": "Prova", "grup": "G2"}}
    if cas == "amb_classe":
        activitats["Prof 2"] = {"assignatura": "Prova", "grup": "G3"}
    dia = dia_fals(
        [vig(), vig("2", vigilant="Prof 2", aula="A2")] if cas == "vigilant" else [vig()],
        [sub, dict(sub, professor_absent="Prof 3")] if cas == "dues_substitucions" else [sub],
        activitats,
        absents={"10:00": {"Prof 2"}} if cas == "absent" else None,
        baixes={"Prof 2"} if cas == "baixa" else (),
    )
    ps = analitza_vigilancies(dia)
    classes = [p for p in ps if p["tipus"].startswith("classe_")]
    esperat = (
        ("classe_coberta", "informacio", "Prof 2") if cas == "valida" else ("classe_sense_cobertura", "important", None)
    )
    assert [(p["tipus"], p["gravetat"], p["cobertura_efectiva"], p["files"]) for p in classes] == [(*esperat, ["1"])]
    # Sense substitut, substitut absent, de baixa o amb classe: ja ho diu la classe sense cobertura
    repetit = ["🔄 10:00: Prof 2 assignat 2 vegades com a substitut"] if cas == "dues_substitucions" else []
    assert missatges_de_files(dia, ps) == repetit


@pytest.mark.parametrize(
    "cas", ["valida", "buida", "altre_grup", "altra_aula", "substitut_absent", "substitut_exclos", "vigilant_exclos"]
)
def test_cobertura_de_l_absent_i_validacio_del_vigilant_efectiu(cas):
    from vigilancies.analisi import analitza_vigilancies

    sub = dict(
        hora="10:00",
        professor_absent="Prof 1",
        # Comportament actual (pendent de decidir): un grup o una aula diferents invaliden la cobertura.
        grup="G2" if cas == "altre_grup" else "G1",
        aula="A2" if cas == "altra_aula" else "A1",
        substitut="" if cas == "buida" else "Prof 2",
        tipus_absencia="VIGILANCIA_ABSENT",
    )
    baixes = {"vigilant_exclos": {"Prof 1"}, "substitut_exclos": {"Prof 2"}}
    dia = dia_fals(
        [vig()],
        [sub],
        {"Prof 2": {"assignatura": "Prova", "grup": "G2"}},
        absents={"10:00": {"Prof 2"}} if cas == "substitut_absent" else None,
        baixes=baixes.get(cas, ()),
    )
    if cas == "valida":
        esperats = [
            ("classe_sense_cobertura", "important", "Prof 2", None),
            ("vigilant_absent_cobert", "informacio", "Prof 1", "Prof 2"),
        ]
    else:
        tipus = "vigilant_exclos" if cas == "vigilant_exclos" else "vigilant_absent_sense_cobertura"
        esperats = [(tipus, "important", "Prof 1", None)]
    ps = analitza_vigilancies(dia)
    assert [(p["tipus"], p["gravetat"], p["professor"], p["cobertura_efectiva"]) for p in ps] == esperats
    assert all(p["files"] == ["1"] for p in ps)
    # La classe del substitut, l'anàlisi només la diu si és el vigilant efectiu; l'absència
    # o la baixa del substitut, i la fila sense substitut, ja les diu la vigilància sense cobertura
    te_classe = [] if cas in ("valida", "buida") else ["⚠️ 10:00: Substitut Prof 2 té classe (Prova, G2)"]
    assert missatges_de_files(dia, ps) == te_classe


@pytest.mark.parametrize("hora,fragment", [("09:00", "arriba abans"), ("10:00", None), ("11:00", "queda més estona")])
def test_vigilancia_fora_de_la_jornada(hora, fragment):
    from vigilancies.analisi import analitza_vigilancies

    ps = analitza_vigilancies(dia_fals([vig(hora=hora)], jornada=("10:00", "10:00")))
    if fragment is None:
        assert ps == []
    else:
        (p,) = ps
        assert (p["tipus"], p["gravetat"], p["hora"], p["files"], p["cobertura_efectiva"]) == (
            "fora_jornada",
            "avis",
            hora,
            ["1"],
            "Prof 1",
        )
        assert fragment in p["missatge"]


def test_sense_horari_absencies_per_hora_i_avis_explicit():
    from vigilancies.analisi import analitza_vigilancies

    dia = dia_fals([vig()], absents={"09:00": {"Prof 1"}}, horari=False)
    assert [p["tipus"] for p in analitza_vigilancies(dia)] == ["horari_no_disponible"]
    dia.absents_per_hora = {"10:00": {"Prof 1"}}
    assert {p["tipus"] for p in analitza_vigilancies(dia)} == {
        "horari_no_disponible",
        "vigilant_absent_sense_cobertura",
    }


def test_ordre_dels_avisos_i_tria_amb_conflictes_d_altres_files():
    from vigilancies.analisi import analitza_vigilancies, selecciona_problemes

    dia = dia_fals(
        [
            vig("3", hora="", vigilant="", aula=""),
            vig("2", vigilant="Prof 2"),
            vig("10", vigilant="", aula=""),
            vig(),
            vig("4", hora="11:00", vigilant=""),
            vig("5", hora="09:00", vigilant=""),
        ],
        [
            dict(hora="10:00", professor_absent="Prof 1", substitut="Prof 2", tipus_absencia="VIGILANCIA_ABSENT"),
            dict(hora="10:00", professor_absent="Prof 3", substitut="Prof 2", tipus_absencia="ABSENCIA"),
        ],
    )
    ps = analitza_vigilancies(dia)
    assert [
        (p["hora"], p["files"], p["tipus"], p["gravetat"], p["professor"], p["cobertura_efectiva"]) for p in ps
    ] == [
        ("09:00", ["5"], "sense_vigilant", "important", "", None),
        ("10:00", ["1"], "vigilant_absent_cobert", "informacio", "Prof 1", "Prof 2"),
        ("10:00", ["10"], "sense_aula", "important", "", None),
        ("10:00", ["10"], "sense_vigilant", "important", "", None),
        ("10:00", ["2", "1"], "aula_repetida", "avis", "", None),
        ("10:00", ["2", "1"], "vigilant_efectiu_repetit", "avis", "Prof 2", "Prof 2"),
        ("10:00", ["2", "1"], "vigilant_i_substitut", "important", "Prof 2", None),
        ("11:00", ["4"], "sense_vigilant", "important", "", None),
        ("", ["3"], "sense_aula", "important", "", None),
        ("", ["3"], "sense_hora", "important", "", None),
        ("", ["3"], "sense_vigilant", "important", "", None),
    ]
    triats = selecciona_problemes(ps, [vig()])
    assert triats == [ps[1], *ps[4:7]]


@pytest.mark.parametrize("idioma", ["ca", "es", "en", "it"])
def test_api_i_els_dos_pdf_imprimeixen_exactament_els_mateixos_avisos(idioma):

    from configuracio.repositories import ConfiguracioRepository

    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "idioma", idioma)
        db.commit()
    nom = "analisi_" + unic()
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(crea_app(router, pdf_router)), nom)
    data = "2026-04-20"
    r = client.post(
        f"/api/vigilancies/{data}",
        json={
            "hora": "10:00",
            "tipus": "Prova",
            "grups": "1-ESO-A",
            "aula": "A1",
            "vigilant": "Prof 30",
            "nivell": "1-ESO",
        },
    )
    assert r.status_code == 200
    # Una classe sense substitut, perquè els PDF tinguin també un avís de substitucions
    with get_data_db_session(centre) as db:
        db.add(
            Substitucio(
                data=date.fromisoformat(data),
                hora="11:30",
                professor_absent="Prof 15",
                grup="1-ESO-A",
                assignatura="Anglès",
                tipus_absencia="ABSENCIA",
            )
        )
        db.commit()
    ps = client.get(f"/api/vigilancies/{data}/analisi")
    assert ps.status_code == 200, ps.text
    ps = ps.json()
    validacio = client.get(f"/api/pdf/{data}/validacions").json()
    assert validacio["problemes_vigilancies"] == ps
    assert any(p["tipus"] == "classe_sense_cobertura" for p in ps)
    (sense_substitut,) = [c for c in validacio["conflicts"] if "Prof 15" in c]
    sense_substitut = sense_substitut.split(": ", 1)[1]  # el PDF no repeteix l'hora a la línia
    # La lectura i les exportacions no modifiquen les files.
    abans = client.get(f"/api/vigilancies/{data}").json()
    # ruta -> hi surten els avisos de vigilàncies, el de substitucions: cada PDF, els de les seves seccions
    for ruta, amb_avisos_de_vigilancies, amb_avis_de_substitucions in [
        (f"/api/pdf/vigilancies/{data}", True, False),
        (f"/api/pdf/complete/{data}", True, True),
        (f"/api/pdf/complete/{data}?include_vigilancies=false", False, True),
        (f"/api/pdf/complete/{data}?include_substitutions=false", True, False),
    ]:
        r = client.get(ruta)
        assert r.status_code == 200
        text = subprocess.run(["pdftotext", "-", "-"], input=r.content, capture_output=True, check=True).stdout.decode()
        text = " ".join(text.split())
        # La revisió d'abans del PDF complet porta (i demana confirmar) els avisos que imprimirà
        revisio = None
        if "/complete/" in ruta:
            revisio = client.get(f"/api/pdf/{data}/validacions?{ruta.partition('?')[2]}").json()
            revisats = revisio["conflicts"] + revisio["warnings"] + revisio["informatius"]
            assert revisio["total"] == len(revisats)
            assert revisio["has_critical"] == bool(revisio["conflicts"])
            assert any(sense_substitut in avis for avis in revisio["conflicts"]) == amb_avis_de_substitucions
        for p in ps:
            # Reportlab/Helvetica substitueix les icones que no pot imprimir.
            missatge = p["missatge"].split(" ", 1)[1]
            # La classe que deixa el vigilant és una fila de substitucions: el seu
            # avís va amb les substitucions (al PDF de vigilàncies, amb les seves files).
            esperat = amb_avisos_de_vigilancies
            if p["tipus"].startswith("classe_") and "/complete/" in ruta:
                esperat = amb_avis_de_substitucions
            assert (" ".join(missatge.split()) in text) == esperat, (ruta, p, text)
            if revisio is not None:
                assert (p["missatge"] in revisats) == (p in revisio["problemes_vigilancies"]) == esperat, (ruta, p)
        assert (sense_substitut in text) == amb_avis_de_substitucions, (ruta, text)
    assert client.get(f"/api/vigilancies/{data}").json() == abans


def test_revisio_del_pdf_de_vigilancies_amb_els_problemes_dels_nivells_triats():
    """Amb la tria de nivells, la revisió porta els problemes de les vigilàncies que
    imprimirà el PDF de vigilàncies d'aquells nivells (generacio.vigilancies_dels_nivells
    i selecciona_problemes) i la gravetat d'aquests; sense, la revisió de sempre."""
    centre = nova_institucio(amb_xml=True)
    nom = "analisi_" + unic()
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(crea_app(router, pdf_router)), nom)
    data = "2026-04-20"
    # Sense vigilant: un problema important per fila (la de sense nivell no es pot crear per l'API)
    with get_data_db_session(centre) as db:
        files = {
            nivell: Vigilancia(
                data=date.fromisoformat(data), hora="10:00", tipus="Prova", grups="", aula=aula, nivell=nivell
            )
            for nivell, aula in [("1-ESO", "A1"), ("2-ESO", "A2"), ("", "A3")]
        }
        db.add_all(files.values())
        db.commit()
        ids = {nivell: str(fila.id) for nivell, fila in files.items()}
    tots = client.get(f"/api/pdf/{data}/validacions").json()
    assert {f for p in tots["problemes_vigilancies"] for f in p["files"]} >= set(ids.values())

    for consulta, nivells in [
        ("nivells=1-ESO&inclou_sense_nivell=false", {"1-ESO"}),
        ("nivells=1-ESO,2-ESO&inclou_sense_nivell=true", {"1-ESO", "2-ESO", ""}),
        ("nivells=&inclou_sense_nivell=true", {"1-ESO", "2-ESO", ""}),
        ("inclou_sense_nivell=false", {"1-ESO", "2-ESO"}),
    ]:
        triats = {ids[n] for n in nivells}
        revisio = client.get(f"/api/pdf/{data}/validacions?{consulta}").json()
        esperats = [p for p in tots["problemes_vigilancies"] if not p["files"] or triats.intersection(p["files"])]
        assert revisio["problemes_vigilancies"] == esperats, consulta
        assert revisio["conflicts"] == [p["missatge"] for p in esperats if p["gravetat"] == "important"]
        assert revisio["warnings"] == [p["missatge"] for p in esperats if p["gravetat"] == "avis"]
        assert revisio["informatius"] == [p["missatge"] for p in esperats if p["gravetat"] == "informacio"]
        assert revisio["total"] == len(esperats)
        assert revisio["has_critical"] == bool(revisio["conflicts"])
        assert revisio["avisos_encadenades"] == []


@pytest.mark.parametrize(
    "tipus,grup,problemes_esperats,avisos_esperats",
    [
        # L'anàlisi només diu que la classe de Prof 1 queda sense cobertura, no que Prof 2 en té dues
        ("ABSENCIA", "G2", ["classe_sense_cobertura"], ["🔄 10:00: Prof 2 assignat 2 vegades com a substitut"]),
        ("VIGILANCIA", "G2", ["classe_sense_cobertura"], ["🔄 10:00: Prof 2 assignat 2 vegades com a substitut"]),
        # Prof 2 vigila per Prof 1 (absent): «vigilant i substitut alhora» ja ho diu
        ("VIGILANCIA_ABSENT", "", ["vigilant_absent_cobert", "vigilant_i_substitut"], []),
    ],
)
def test_un_substitut_de_dues_files_a_la_mateixa_hora_es_avisa(tipus, grup, problemes_esperats, avisos_esperats):
    # Prof 2 cobreix la classe (o la vigilància) de Prof 1, que vigila, i la classe de Prof 3
    dia = dia_fals(
        [vig()],
        [
            dict(hora="10:00", professor_absent="Prof 1", grup=grup, substitut="Prof 2", tipus_absencia=tipus),
            dict(hora="10:00", professor_absent="Prof 3", grup="G3", substitut="Prof 2", tipus_absencia="ABSENCIA"),
        ],
        {"Prof 1": {"assignatura": "Prova", "grup": "G2"}},
    )
    problemes = analitza_vigilancies(dia)
    avisos: list[str] = []
    _substituts_repetits(dia, avisos, problemes)
    assert [p["tipus"] for p in problemes] == problemes_esperats
    assert avisos == avisos_esperats


def test_una_classe_pendent_es_un_sol_problema_encara_que_vigili_dues_files():
    from vigilancies.analisi import analitza_vigilancies

    dia = dia_fals([vig(), vig("2")], activitats={"Prof 1": {"assignatura": "Prova", "grup": "G2"}})
    classes = [p for p in analitza_vigilancies(dia) if p["tipus"] == "classe_sense_cobertura"]
    assert len(classes) == 1
    assert classes[0]["files"] == ["1", "2"]


def test_avisos_amb_text_d_usuari_no_s_interpreten_com_html():

    centre = nova_institucio(amb_xml=True)
    nom = "text_" + unic()
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(crea_app(router, pdf_router)), nom)
    data = "2026-04-20"
    assert (
        client.post(
            f"/api/vigilancies/{data}",
            json={
                "hora": "10:00",
                "tipus": "Prova <font",
                "grups": "G1",
                "aula": "",
                "vigilant": "",
                "nivell": "N1",
            },
        ).status_code
        == 200
    )
    for ruta in [
        f"/api/pdf/vigilancies/{data}",
        f"/api/pdf/complete/{data}",
        f"/api/pdf/vigilancies/interval?data_inici={data}&data_final={data}",
    ]:
        r = client.get(ruta)
        assert r.status_code == 200, r.text[:200]
        text = subprocess.run(["pdftotext", "-", "-"], input=r.content, capture_output=True, check=True).stdout.decode()
        assert "Prova <font" in text


@pytest.mark.parametrize("grup,marca", [("G2", "G2"), ("G2", "professor:Prof 1"), ("", "professor:Prof 1")])
def test_alliberat_no_es_un_problema(grup, marca):
    from vigilancies.analisi import analitza_vigilancies

    dia = dia_fals(
        [vig()], activitats={"Prof 1": {"assignatura": "Activitat", "grup": grup}}, alliberats={"10:00": [marca]}
    )
    assert analitza_vigilancies(dia) == []


@pytest.mark.parametrize("tipus_info,professor", [("classe_coberta", "Prof 30"), ("activitat_sense_grup", "Prof 22")])
def test_informatius_es_conserven_a_la_revisio_pero_no_als_tres_pdf(tipus_info, professor):

    from models import Substitucio

    centre = nova_institucio(amb_xml=True)
    nom = "info_" + unic()
    crea_usuari(nom, centre, "admin")
    client = entra(client_per(crea_app(router, pdf_router)), nom)
    data = "2026-04-20"
    assert (
        client.post(
            f"/api/vigilancies/{data}",
            json={
                "hora": "10:00",
                "tipus": "Prova",
                "grups": "1-ESO-A",
                "aula": "A1",
                "vigilant": professor,
                "nivell": "1-ESO",
            },
        ).status_code
        == 200
    )
    ps = client.get(f"/api/vigilancies/{data}/analisi").json()
    classe = next((p for p in ps if p["tipus"] == "classe_sense_cobertura"), None)
    # Una segona fila garanteix que els avisos segueixen impresos.
    assert (
        client.post(
            f"/api/vigilancies/{data}",
            json={
                "hora": "10:00",
                "tipus": "Prova",
                "grups": "1-ESO-B",
                "aula": "A1",
                "vigilant": "",
                "nivell": "1-ESO",
            },
        ).status_code
        == 200
    )
    from grups.repositories import GrupsAlliberatsRepository

    with get_data_db_session(centre) as db:
        GrupsAlliberatsRepository.set_for_date(db, date.fromisoformat(data), {"10:00": ["professor:Prof 15"]})
        db.commit()
    if classe:
        with get_data_db_session(centre) as db:
            db.add(
                Substitucio(
                    data=date.fromisoformat(data),
                    hora="10:00",
                    professor_absent="Prof 30",
                    grup=classe["grup"],
                    substitut="Prof 15",
                    tipus_absencia="VIGILANCIA",
                )
            )
            db.commit()
    ps = client.get(f"/api/vigilancies/{data}/analisi").json()
    infos = [p for p in ps if p["gravetat"] == "informacio"]
    assert any(p["tipus"] == tipus_info for p in infos), ps
    assert any(p["gravetat"] == "avis" for p in ps), ps
    revisio = client.get(f"/api/pdf/{data}/validacions").json()
    assert revisio["problemes_vigilancies"] == ps
    # Els informatius, a part (la revisió els mostra plegats); mai entre els avisos
    assert revisio["informatius"] == [p["missatge"] for p in infos]
    assert not set(revisio["informatius"]) & set(revisio["warnings"] + revisio["conflicts"])
    for ruta in [
        f"/api/pdf/vigilancies/{data}",
        f"/api/pdf/complete/{data}",
        f"/api/pdf/vigilancies/interval?data_inici={data}&data_final={data}",
    ]:
        r = client.get(ruta)
        assert r.status_code == 200, r.text
        text = subprocess.run(["pdftotext", "-", "-"], input=r.content, capture_output=True, check=True).stdout.decode()
        text = " ".join(text.split())
        for p in ps:
            missatge = p["missatge"]
            if p["gravetat"] != "informacio":
                missatge = missatge.split(" ", 1)[1]
            assert (" ".join(missatge.removeprefix("10:00: ").split()) in text) == (p["gravetat"] != "informacio"), (
                ruta,
                p,
                text,
            )
