"""
Centres de prova amb diverses versions de l'horari (XML): "actual.xml" és
l'horari d'exemple i "futur.xml" el mateix sense el primer professor.
"""

import xml.etree.ElementTree as ET
from datetime import date, timedelta

from suport_api import XML_EXEMPLE, nova_institucio

from database import get_data_db_session, get_data_dir_for_institucio
from models import XMLVersion
from repositories import ConfiguracioRepository

# Es calcula un sol cop, en importar-se: si la suite creua la mitjanit, les
# rutes que fan servir «avui» han de veure aquesta data (fixa_avui).
AVUI = date.today()


def dia(dies):
    return AVUI + timedelta(days=dies)


class _AvuiFix(date):
    @classmethod
    def today(cls):
        return AVUI


def fixa_avui(monkeypatch, *moduls):
    """Fa que date.today() dels mòduls donats retorni AVUI."""
    for modul in moduls:
        monkeypatch.setattr(modul, "date", _AvuiFix)


def professor_que_plega():
    return ET.parse(XML_EXEMPLE).getroot().find("Teacher").get("name").strip()


def amb_versions(*versions):
    """Centre amb versions (fitxer, inici, fi). El fitxer "futur.xml" és
    l'horari d'exemple sense el primer professor."""
    centre = nova_institucio()
    carpeta = get_data_dir_for_institucio(centre)
    arbre = ET.parse(XML_EXEMPLE)
    arbre.write(carpeta / "actual.xml", encoding="utf-8")
    arrel = arbre.getroot()
    arrel.remove(arrel.find("Teacher"))
    arbre.write(carpeta / "futur.xml", encoding="utf-8")
    with get_data_db_session(centre) as db:
        for fitxer, inici, fi in versions:
            db.add(XMLVersion(path=fitxer, data_inici=inici, data_fi=fi))
        ConfiguracioRepository.set(db, "xml_horari_path", "actual.xml")
        db.commit()
    return centre


def amb_horari_futur():
    """L'horari actual fins d'aquí a 2 dies i el futur a partir de 3 dies."""
    return amb_versions(("actual.xml", dia(-30), dia(2)), ("futur.xml", dia(3), None))
