"""
Regla dels noms en llegir l'XML de FET: els noms de professors, assignatures,
aules i etiquetes es netegen en un sol punt (noms.nom_net), però l'ordre
continua sent el de l'XML i el filtre de l'«últim professor» talla pel mateix
lloc. Els espais del davant dels professors (que FET fa servir per ordenar-los
per nivells) no formen part del nom.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from suport_api import XML_EXEMPLE

from horari_web import GestorHorariWeb
from scheduler_engine.core.horaris_xml import horaris_professors

BACKEND = Path(__file__).resolve().parent.parent

# Elements de l'XML el «name» dels quals és un nom (cal nom_net) i els que no
# ho són (dies, hores i grups tenen les seves pròpies normalitzacions)
NOMS = {"teacher", "subject_elem", "room_elem", "tag", "sub"}
NO_NOMS = {"day", "hour", "elem", "students", "students_elements[0]"}


def test_cap_lector_no_llegeix_un_nom_de_l_xml_sense_nom_net():
    """Guardià: tot .get("name") d'un element de l'XML que és un nom ha de
    passar per nom_net. Un element nou que no és a cap de les dues llistes fa
    fallar el test perquè algú decideixi si és un nom."""
    errors = []
    for fitxer in BACKEND.rglob("*.py"):
        parts = fitxer.relative_to(BACKEND).parts
        if parts[0].startswith("venv") or "tests" in parts:
            continue
        for n, linia in enumerate(fitxer.read_text(encoding="utf-8").splitlines(), 1):
            for element in re.findall(r"([\w\[\]0-9]+)\.get\(\"name\"", linia):
                lloc = f"{fitxer.relative_to(BACKEND)}:{n}"
                # nom_cru: el nom tal com és a l'XML, a propòsit (horari/router.py, per
                # sagnar el selector de l'últim professor); no fa d'identitat
                if element in NOMS and "nom_net(" not in linia and "nom_cru" not in linia:
                    errors.append(f"{lloc}: {element} sense nom_net")
                elif element not in NOMS | NO_NOMS:
                    errors.append(f"{lloc}: element nou ({element}): és un nom?")
    assert errors == []


def _xml_amb_espais(tmp_path):
    """L'XML d'exemple amb els espais que hi posa FET o qui l'edita: tres
    professors amb espais al davant (ordenació per nivells), una assignatura i
    una aula amb un espai al darrere."""
    arbre = ET.parse(XML_EXEMPLE)
    arrel = arbre.getroot()
    for teacher in arrel.findall("Teacher")[:3]:
        teacher.set("name", "   " + teacher.get("name"))
    assignatura = next(arrel.iter("Subject")).get("name")
    for subject in arrel.iter("Subject"):
        if subject.get("name") == assignatura:
            subject.set("name", assignatura + " ")
    aula = next(arrel.iter("Room")).get("name")
    for room in arrel.iter("Room"):
        if room.get("name") == aula:
            room.set("name", aula + " ")
    cami = tmp_path / "amb_espais.xml"
    arbre.write(cami, encoding="utf-8")
    return cami, assignatura, aula


@pytest.fixture
def xmls(tmp_path):
    cami, assignatura, aula = _xml_amb_espais(tmp_path)
    return {"net": str(XML_EXEMPLE), "espais": str(cami), "assignatura": assignatura, "aula": aula}


def _professors_xml(cami):
    return [t.get("name").strip() for t in ET.parse(cami).getroot().findall("Teacher")]


def test_els_professors_surten_nets_i_en_l_ordre_de_l_xml(xmls):
    assert GestorHorariWeb(xmls["espais"]).professors == _professors_xml(xmls["net"])
    assert list(horaris_professors(ET.parse(xmls["espais"]).getroot())) == _professors_xml(xmls["net"])


@pytest.mark.parametrize("ultim", ["{}", "  {} ", "{}  "])
def test_el_filtre_de_l_ultim_professor_talla_pel_mateix_lloc(xmls, ultim):
    # El segon professor de l'XML (un dels que hi tenen espais al davant)
    segon = _professors_xml(xmls["net"])[1]
    esperat = _professors_xml(xmls["net"])[:2]
    assert GestorHorariWeb(xmls["espais"], ultim.format(segon)).professors == esperat
    assert GestorHorariWeb(xmls["net"], ultim.format(segon)).professors == esperat
    assert list(horaris_professors(ET.parse(xmls["espais"]).getroot(), ultim.format(segon))) == esperat


def test_les_assignatures_i_les_aules_surten_netes(xmls):
    horari = GestorHorariWeb(xmls["espais"])
    activitats = [a for dia in horari.horari.values() for hora in dia.values() for a in hora.values()]
    assert xmls["assignatura"] in {a["assignatura"] for a in activitats}
    assert all(a["assignatura"] == a["assignatura"].strip() and a["aula"] == a["aula"].strip() for a in activitats)
    assert xmls["aula"] in {a["aula"] for a in activitats}
    planificador = horaris_professors(ET.parse(xmls["espais"]).getroot())
    assignatures = {
        h["assignatura"] for dies in planificador.values() for hores in dies.values() for h in hores.values()
    }
    assert xmls["assignatura"] in assignatures and xmls["assignatura"] + " " not in assignatures
