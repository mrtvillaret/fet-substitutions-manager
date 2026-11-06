"""Mateixa anàlisi a pantalla, revisió i documents; cobertures reals."""

import subprocess
from datetime import date
from types import SimpleNamespace

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from database import get_data_db_session
from pdf.router import router as pdf_router
from vigilancies.router import router


def dia_fals(vigs, files=(), activitats=None, absents=None, alliberats=None, horari=True):
    activitats = activitats or {}
    return SimpleNamespace(
        vigilancies=vigs,
        files=list(files),
        absents_per_hora=absents or {},
        alliberats=alliberats or {},
        baixes=set(),
        nom_del_dia="Dilluns",
        horari=SimpleNamespace(hores=["09:00", "10:00", "11:00"], get_jornada_professor=lambda *_: ("09:00", "11:00"))
        if horari
        else None,
        activitat=lambda p, h: activitats.get(p, {}),
    )


def vig(id="1", vigilant="Prof 1", hora="10:00", aula="A1", grups="G1"):
    return dict(id=id, vigilant=vigilant, hora=hora, aula=aula, grups=grups, tipus="Prova")


def test_cobertura_buida_no_amaga_classe_i_una_cobertura_real_la_resol():
    from vigilancies.analisi import analitza_vigilancies

    sub = dict(hora="10:00", professor_absent="Prof 1", grup="G2", substitut="", tipus_absencia="VIGILANCIA")
    dia = dia_fals([vig()], [sub], {"Prof 1": {"assignatura": "Prova", "grup": "G2"}})
    assert [(p["tipus"], p["gravetat"]) for p in analitza_vigilancies(dia)] == [("classe_sense_cobertura", "important")]
    sub["substitut"] = "Prof 2"
    p = analitza_vigilancies(dia)[0]
    assert (p["tipus"], p["gravetat"], p["cobertura_efectiva"], p["files"]) == (
        "classe_coberta",
        "informacio",
        "Prof 2",
        ["1"],
    )
    dia.absents_per_hora = {"10:00": {"Prof 2"}}
    assert analitza_vigilancies(dia)[0]["tipus"] == "classe_sense_cobertura"


def test_absent_cobert_comprova_tambe_el_vigilant_efectiu_sense_doble_feina_falsa():
    from vigilancies.analisi import analitza_vigilancies

    sub = dict(
        hora="10:00",
        professor_absent="Prof 1",
        grup="G1",
        aula="A1",
        substitut="Prof 2",
        tipus_absencia="VIGILANCIA_ABSENT",
    )
    dia = dia_fals([vig()], [sub], {"Prof 2": {"assignatura": "Prova", "grup": "G2"}})
    ps = analitza_vigilancies(dia)
    assert {p["tipus"] for p in ps} == {"vigilant_absent_cobert", "classe_sense_cobertura"}
    assert next(p for p in ps if p["tipus"] == "classe_sense_cobertura")["professor"] == "Prof 2"
    sub["substitut"] = ""
    assert [p["tipus"] for p in analitza_vigilancies(dia)] == ["vigilant_absent_sense_cobertura"]


def test_sense_horari_absencies_per_hora_i_avis_explicit():
    from vigilancies.analisi import analitza_vigilancies

    dia = dia_fals([vig()], absents={"09:00": {"Prof 1"}}, horari=False)
    assert [p["tipus"] for p in analitza_vigilancies(dia)] == ["horari_no_disponible"]
    dia.absents_per_hora = {"10:00": {"Prof 1"}}
    assert {p["tipus"] for p in analitza_vigilancies(dia)} == {
        "horari_no_disponible",
        "vigilant_absent_sense_cobertura",
    }


def test_fila_antiga_sense_hora_te_avis_i_la_tria_conserva_conflictes_amb_altres_nivells():
    from vigilancies.analisi import analitza_vigilancies, selecciona_problemes

    dia = dia_fals([vig(), vig("2"), vig("3", hora="")])
    ps = analitza_vigilancies(dia)
    assert any(p["tipus"] == "sense_hora" for p in ps)
    triats = selecciona_problemes(ps, [vig()])
    assert {p["tipus"] for p in triats} == {"vigilant_repetit", "aula_repetida"}
    assert all(p["files"] == ["1", "2"] for p in triats)


@pytest.mark.parametrize("idioma", ["ca", "es", "en", "it"])
def test_api_i_els_dos_pdf_imprimeixen_exactament_els_mateixos_avisos(idioma):
    import uuid

    from configuracio.repositories import ConfiguracioRepository

    centre = nova_institucio(amb_xml=True)
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "idioma", idioma)
        db.commit()
    nom = "analisi_" + uuid.uuid4().hex[:8]
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
    ps = client.get(f"/api/vigilancies/{data}/analisi")
    assert ps.status_code == 200, ps.text
    ps = ps.json()
    validacio = client.get(f"/api/pdf/{data}/validacions").json()
    assert validacio["problemes_vigilancies"] == ps
    assert any(p["tipus"] == "classe_sense_cobertura" for p in ps)
    # La lectura i les exportacions no modifiquen les files.
    abans = client.get(f"/api/vigilancies/{data}").json()
    for ruta in [f"/api/pdf/vigilancies/{data}", f"/api/pdf/complete/{data}"]:
        r = client.get(ruta)
        assert r.status_code == 200
        text = subprocess.run(["pdftotext", "-", "-"], input=r.content, capture_output=True, check=True).stdout.decode()
        text = " ".join(text.split())
        for p in ps:
            # Reportlab/Helvetica substitueix les icones que no pot imprimir.
            missatge = p["missatge"].split(" ", 1)[1]
            assert " ".join(missatge.split()) in text, (ruta, p, text)
    assert client.get(f"/api/vigilancies/{data}").json() == abans


def test_una_classe_pendent_es_un_sol_problema_encara_que_vigili_dues_files():
    from vigilancies.analisi import analitza_vigilancies

    dia = dia_fals([vig(), vig("2")], activitats={"Prof 1": {"assignatura": "Prova", "grup": "G2"}})
    classes = [p for p in analitza_vigilancies(dia) if p["tipus"] == "classe_sense_cobertura"]
    assert len(classes) == 1
    assert classes[0]["files"] == ["1", "2"]


def test_avisos_amb_text_d_usuari_no_s_interpreten_com_html():
    import uuid

    centre = nova_institucio(amb_xml=True)
    nom = "text_" + uuid.uuid4().hex[:8]
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
    import uuid

    from models import Substitucio

    centre = nova_institucio(amb_xml=True)
    nom = "info_" + uuid.uuid4().hex[:8]
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
        GrupsAlliberatsRepository.set_for_date(db, data, {"10:00": ["professor:Prof 15"]})
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
    assert client.get(f"/api/pdf/{data}/validacions").json()["problemes_vigilancies"] == ps
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
