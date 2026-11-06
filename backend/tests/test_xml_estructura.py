"""Un XML ben format no és necessàriament un horari que el lector entengui."""

import pytest
from test_files_api import _fitxers, _puja, _versions, _xml_actual, centre, client  # noqa: F401

from configuracio.repositories import ConfiguracioRepository
from database import get_data_db_session

TEXTOS = {
    "ca": "L'XML d'horari ha de contenir almenys un professor, un dia i una hora",
    "es": "El XML de horario debe contener al menos un profesor, un día y una hora",
    "en": "The timetable XML must contain at least one teacher, one day and one hour",
    "it": "L'XML dell'orario deve contenere almeno un docente, un giorno e un'ora",
}


@pytest.mark.parametrize(
    "xml",
    [
        b"<document/>",
        b'<Teachers_Timetable><Teacher name="Prof prova"/></Teachers_Timetable>',
        b'<Teachers_Timetable><Teacher name="Prof prova"><Day name="Dilluns"/></Teacher></Teachers_Timetable>',
        b'<Teachers_Timetable><Teacher name=" "><Day name="Dilluns"><Hour name="09:00"/></Day></Teacher></Teachers_Timetable>',
    ],
)
@pytest.mark.parametrize("idioma", TEXTOS)
def test_xml_sense_estructura_es_rebutja_sense_desar_cap_versio(client, centre, idioma, xml):
    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "idioma", idioma)
    resposta = _puja(client, contingut=xml)
    assert resposta.status_code == 400, resposta.text
    assert resposta.json()["detail"] == TEXTOS[idioma]
    assert _versions(centre) == []
    assert _xml_actual(centre) is None
    assert _fitxers(centre) == []


def test_un_xml_invalid_no_substitueix_el_vigent(client, centre):
    assert _puja(client).status_code == 200  # l'XML d'exemple complet
    abans = _versions(centre), _xml_actual(centre), _fitxers(centre)
    assert _puja(client, contingut=b"<document/>", data_inici="2027-09-01").status_code == 400
    assert (_versions(centre), _xml_actual(centre), _fitxers(centre)) == abans
