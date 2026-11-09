"""La pujada només informa: comprova l'XML nou i conserva les files desades."""

import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime

import pytest
from suport_api import XML_EXEMPLE, nova_institucio
from test_files_api import _puja, _usuari_de

from database import get_data_db_session, get_data_dir_for_institucio
from horari.domain import Dia
from models import Substitucio, Vigilancia
from rate_limit import limiter
from substitucions.domain import DiaEscolar, substituts_no_valids
from substitucions.repositories import SubstitucioRepository
from vigilancies.analisi import analitza_vigilancies
from vigilancies.repositories import VigilanciaRepository


@pytest.fixture
def centre():
    limiter.reset()
    return nova_institucio(amb_xml=True)


def xml_nou():
    arrel = ET.parse(XML_EXEMPLE).getroot()
    for professor in arrel.findall("Teacher"):
        if professor.get("name", "").strip() == "Prof 21":
            arrel.remove(professor)
        if professor.get("name", "").strip() == "Prof 22":
            hora = professor.find("Day[@name='Dilluns']/Hour[@name='10:00']")
            hora.clear()
            hora.set("name", "10:00")
            ET.SubElement(hora, "Subject", name="Matèria nova")
            ET.SubElement(hora, "Students", name="Grup nou")
    return ET.tostring(arrel, encoding="utf-8")


def desa_files(centre, dates):
    with get_data_db_session(centre) as db:
        for data in dates:
            for professor in ("Prof 21", "Prof 22"):
                db.add(
                    Substitucio(
                        data=date.fromisoformat(data), hora="10:00", professor_absent="Prof 15", substitut=professor
                    )
                )
                db.add(
                    Vigilancia(
                        data=date.fromisoformat(data),
                        hora="11:30" if professor == "Prof 21" else "10:00",
                        tipus="Prova",
                        grups="G1",
                        aula=professor,
                        vigilant=professor,
                        nivell="N1",
                    )
                )
        db.commit()


def instantania(centre, dates):
    with get_data_db_session(centre) as db:
        return [(SubstitucioRepository.get_by_date(db, d), VigilanciaRepository.get_by_date(db, d)) for d in dates]


@pytest.mark.parametrize(
    "inici,avui,esperats",
    [
        ("2026-11-02", "2026-11-09", ["2026-11-09", "2026-11-16"]),
        ("2026-11-09", "2026-11-02", ["2026-11-09", "2026-11-16"]),
        ("2026-11-02", "2026-11-02", ["2026-11-02", "2026-11-09", "2026-11-16"]),
    ],
)
def test_pujada_revisa_nomes_dies_desats_des_de_validesa_o_avui(centre, rellotge_fix, inici, avui, esperats):
    dates = ["2026-10-26", "2026-11-02", "2026-11-09", "2026-11-16"]
    desa_files(centre, dates)
    abans = instantania(centre, dates)
    rellotge_fix.moment = datetime.fromisoformat(avui).replace(tzinfo=UTC)
    client = _usuari_de(centre)
    resposta = _puja(client, contingut=xml_nou(), data_inici=inici)
    assert resposta.status_code == 200, resposta.text
    cos = resposta.json()
    assert sorted({a["data"] for a in cos["avisos"]}) == esperats
    for data in esperats:
        avisos = [a for a in cos["avisos"] if a["data"] == data]
        assert any(a.get("motiu") == "fora_horari" and a["professor"] == "Prof 21" for a in avisos)
        assert any(a.get("motiu") == "vigilancia" and a["professor"] == "Prof 22" for a in avisos)
        assert any(a.get("tipus") == "vigilant_fora_horari" and a["hora"] == "11:30" for a in avisos)
        assert any(a.get("tipus") == "classe_sense_cobertura" and a["professor"] == "Prof 22" for a in avisos)
    assert cos["recomptes"] == {
        "dies": len(esperats),
        "substitucions": 2 * len(esperats),
        "vigilancies": 3 * len(esperats),
    }
    assert instantania(centre, dates) == abans
    assert (get_data_dir_for_institucio(centre) / cos["path"]).read_bytes() == xml_nou()


def test_classe_nova_en_una_substitucio_i_dia_amb_nomes_vigilancies(centre):
    desa_files(centre, ["2026-11-09"])
    with get_data_db_session(centre) as db:
        db.query(Vigilancia).filter(Vigilancia.vigilant == "Prof 22").update({"data": date(2026, 11, 16)})
        db.commit()
    cos = _puja(_usuari_de(centre), contingut=xml_nou(), data_inici="2026-11-09").json()
    assert any(a.get("motiu") == "classe" and a["data"] == "2026-11-09" for a in cos["avisos"])
    assert any(a.get("tipus") == "classe_sense_cobertura" and a["data"] == "2026-11-16" for a in cos["avisos"])


def test_avisa_de_tots_els_motius_existents_i_nomes_problemes_importants(centre):
    # Els problemes previs també s'informen: no és una comparació d'XMLs.
    from models import AbsenciaCoberta

    desa_files(centre, ["2026-11-09"])
    with get_data_db_session(centre) as db:
        db.add(AbsenciaCoberta(professor="Prof 23", data_inici=date(2026, 11, 9), data_final=date(2026, 11, 9)))
        for professor in ("Prof 15", "Prof 23", "Prof 1"):
            db.add(
                Substitucio(
                    data=date(2026, 11, 9),
                    hora="10:00",
                    professor_absent="Prof 15",
                    substitut=professor,
                    tipus_absencia="ABSENCIA",
                )
            )
        db.commit()
    dates = ["2026-11-09"]
    abans = instantania(centre, dates)
    cos = _puja(_usuari_de(centre), contingut=xml_nou(), data_inici=dates[0]).json()
    assert {a["motiu"] for a in cos["avisos"] if a.get("motiu")} == {
        "fora_horari",
        "classe",
        "vigilancia",
        "absent",
        "baixa",
    }
    with get_data_db_session(centre) as db:
        dia = DiaEscolar(db, Dia.de_text(dates[0], centre), estricte=True)
        assert sum(bool(a.get("motiu")) for a in cos["avisos"]) == len(substituts_no_valids(db, dates[0], dia))
        assert [a["tipus"] for a in cos["avisos"] if a.get("tipus")] == [
            p["tipus"] for p in analitza_vigilancies(dia) if p["gravetat"] == "important"
        ]
    assert instantania(centre, dates) == abans


@pytest.mark.parametrize("repetit", [False, True])
def test_sense_dades_o_xml_identic_retorna_llista_i_recomptes_buits(centre, repetit):
    client = _usuari_de(centre)
    if repetit:
        _puja(client, contingut=xml_nou(), data_inici="2026-11-09")
        desa_files(centre, ["2026-11-16"])
    cos = _puja(client, contingut=xml_nou(), data_inici="2026-11-16").json()
    assert cos["avisos"] == []
    assert cos["recomptes"] == {"dies": 0, "substitucions": 0, "vigilancies": 0}


def test_el_dia_abans_de_la_versio_seguent_es_el_darrer_que_es_revisa(centre):
    # La pujada actual afegeix al final; fixem també el límit d'una versió
    # intermèdia sense canviar aquesta política d'inserció.
    from horari.repositories import XMLVersionRepository
    from horari.services import _avisos_xml

    client = _usuari_de(centre)
    cos = _puja(client, contingut=xml_nou(), data_inici="2026-11-09").json()
    desa_files(centre, ["2026-11-09", "2026-11-16"])
    with get_data_db_session(centre) as db:
        XMLVersionRepository.create(db, path="teachers.xml", data_inici=date(2026, 11, 10))
        XMLVersionRepository.encadena(db)
        db.commit()
        versio = next(v for v in XMLVersionRepository.list_all(db) if v.path == cos["path"])
        resultat = _avisos_xml(centre, versio)
    assert {a["data"] for a in resultat["avisos"]} == {"2026-11-09"}
    assert resultat["recomptes"]["dies"] == 1


def test_dies_amb_files_sense_problemes_no_sumen_avisos(centre):
    with get_data_db_session(centre) as db:
        db.add(Substitucio(data=date(2026, 11, 9), hora="10:00", professor_absent="Prof 15"))
        db.commit()
    cos = _puja(_usuari_de(centre), contingut=xml_nou(), data_inici="2026-11-09").json()
    assert cos["avisos"] == []
    assert cos["recomptes"] == {"dies": 0, "substitucions": 0, "vigilancies": 0}
