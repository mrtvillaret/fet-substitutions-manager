"""Regles de l'horari (XML de FET): què en veu cada pantalla, com es puja un
XML nou i com es gestionen les seves versions.

Les funcions de lectura reben el `Dia` (l'horari vigent a la data de treball);
sense XML, responen buit amb `xml_missing`."""

import hashlib
import logging
import os
import shutil
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import BinaryIO, Optional

import defusedxml.ElementTree as SafeET
from defusedxml import DefusedXmlException
from sqlalchemy.orm import Session

from absencia_coberta.services import absencies_cobertes_del_dia
from database import get_data_db_session, get_data_dir_for_institucio
from errors_domini import NoTrobat, NoValid
from helpers import MissingXmlError, invalidar_horari
from horari.repositories import XMLVersionRepository
from noms import nom_net
from parametres import data_iso
from repositories import ConfiguracioRepository
from serveis.dia import Dia

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- lectura


def estat(dia: Dia) -> dict:
    """Si hi ha horari i quants professors i hores té."""
    try:
        horari = dia.horari
    except MissingXmlError:
        return {
            "data_actual": datetime.now().strftime("%Y-%m-%d"),
            "horari_carregat": False,
            "num_professors": 0,
            "num_hores": 0,
            "xml_missing": True,
        }
    return {
        "data_actual": datetime.now().strftime("%Y-%m-%d"),
        "horari_carregat": True,
        "num_professors": len(horari.professors),
        "num_hores": len(horari.hores),
    }


def professors(dia: Dia) -> dict:
    """Els professors, fins a l'últim configurat, per ordre alfabètic."""
    try:
        horari = dia.horari
    except MissingXmlError:
        return {"professors": [], "xml_missing": True}
    # horari.professors ja té el límit aplicat (veure core/horari.py línia 50-62)
    return {"professors": sorted(horari.professors)}


def hores(dia: Dia) -> dict:
    """Les hores del dia en l'ordre de l'XML (no alfabètic)."""
    try:
        horari = dia.horari
    except MissingXmlError:
        return {"hores": [], "xml_missing": True}
    return {
        "hores": horari.hores  # Ja estan en l'ordre correcte de l'XML
    }


def tots_els_professors(dia: Dia) -> dict:
    """TOTS els professors de l'XML, sense el límit de l'últim professor."""
    try:
        horari = dia.horari

        # Llegir professors directament del XML sense límit
        tree = ET.parse(horari.xml_path)
        root = tree.getroot()

        # En ORDRE del document XML (és l'ordre que fa servir el límit
        # ultim_professor_subs a horari_web.py), amb el nom cru (amb els espais
        # inicials, que a FET distingeixen secundària de primària) i el net.
        professors_ordenats = []
        for teacher in root.findall("Teacher"):
            nom_cru = teacher.get("name", "")
            nom = nom_net(nom_cru)
            if nom:
                professors_ordenats.append({"nom": nom, "nom_cru": nom_cru})

        # Llista plana ordenada alfabèticament (compatibilitat: professors de baixa)
        professors = sorted(p["nom"] for p in professors_ordenats)

        return {"professors": professors, "professors_ordenats": professors_ordenats, "total": len(professors)}
    except MissingXmlError:
        return {"professors": [], "total": 0, "xml_missing": True}


def professors_del_dia(dia: Dia, data: Optional[str]) -> dict:
    """Els professors amb el límit de l'últim professor i, amb `data`, a part
    els que hi tenen una absència coberta (amb la data de fi)."""
    try:
        horari = dia.horari

        resposta = {"professors": horari.professors, "total": len(horari.professors)}
        if data:
            # Els que tenen una absència coberta aquell dia: ja no són a la llista,
            # però la pantalla els mostra a part (sense que es puguin triar)
            resposta["absencies_cobertes"] = absencies_cobertes_del_dia(dia.institucio, data, horari.absents_coberts)
        return resposta
    except MissingXmlError:
        return {"professors": [], "total": 0, "xml_missing": True}


def grups(dia: Dia) -> dict:
    """TOTS els grups de l'XML (no només els visibles), tal com hi són i amb
    les abreviatures aplicades, i la data d'inici de la versió."""
    try:
        horari = dia.horari

        # Detecció: TOTS els grups de l'XML (no només els visibles), perquè el
        # selector de configuració els pugui oferir tots.
        grups_raw = sorted(list(horari.tots_grups_raw))
        grups_abreviats = sorted(list(horari.tots_grups))

        # Versió d'XML carregada, per poder-la indicar a la configuració
        xml_data_inici = dia.versio_des_de

        return {
            "grups_raw": grups_raw,
            "grups": grups_abreviats,
            "total_raw": len(grups_raw),
            "total_abreviats": len(grups_abreviats),
            "xml_data_inici": xml_data_inici,
        }
    except MissingXmlError:
        return {"grups_raw": [], "grups": [], "total_raw": 0, "total_abreviats": 0, "xml_missing": True}


def assignatures(dia: Dia) -> dict:
    """Totes les assignatures de l'XML, si hi ha hores sense assignatura
    (`te_buits`), les que tenen grup en alguna hora i la data d'inici de la
    versió."""
    try:
        horari = dia.horari

        # Obtenir totes les assignatures úniques
        assignatures = horari.get_all_subjects()

        # Detectar si hi ha hores amb Subject buit (hores lliures): en aquest cas
        # la config de "no substituir" ha de poder seleccionar l'opció buida.
        te_buits = any(
            not (dades.get("assignatura") or "").strip()
            for dia_hores in horari.horari.values()
            for hora_profs in dia_hores.values()
            for dades in hora_profs.values()
        )

        # Les activitats que tenen grup en alguna hora: a Prioritats, posar-ne
        # una a «No substituir» deixa aquell grup sense professor quan qui la
        # fa falti (l'hora no surt a Substitucions), i la pantalla ho avisa
        amb_grup = {
            (dades.get("assignatura") or "").strip()
            for dia_hores in horari.horari.values()
            for hora_profs in dia_hores.values()
            for dades in hora_profs.values()
            if (dades.get("grup") or "").strip()
        }

        # Versió d'XML carregada, per poder-la indicar a la configuració
        xml_data_inici = dia.versio_des_de

        return {
            "assignatures": sorted(list(assignatures)),
            "total": len(assignatures),
            "te_buits": te_buits,
            "amb_grup": sorted(amb_grup),
            "xml_data_inici": xml_data_inici,
        }
    except MissingXmlError:
        return {"assignatures": [], "total": 0, "xml_missing": True}


# ---------------------------------------------------------------- pujada


def _sha256(cami) -> str:
    sha = hashlib.sha256()
    with open(cami, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _relatiu(cami: Path, data_dir: str) -> str:
    try:
        return str(cami.relative_to(Path(data_dir)))
    except ValueError:
        return str(cami)


def puja_xml(institucio: str, nom_fitxer: str, fitxer: BinaryIO, data_inici: Optional[str]) -> dict:
    """
    Desa un XML de FET i el versiona a partir d'una data de vigència.

    `data_inici` (YYYY-MM-DD, per defecte avui) permet **preparar** l'horari d'un curs
    futur sense que passi a ser vigent immediatament: la versió anterior es tanca el dia
    abans, i el punter "actual" (`xml_horari_path`) només es mou si la nova versió ja és
    vigent avui.
    """
    # El nom que envia el navegador només es fa servir per mostrar-lo: el fitxer
    # es desa amb un nom propi. Un nom com "../altra_institucio/teachers.xml"
    # escriuria fora de la carpeta de la institució, i un de coincident amb
    # l'XML actual el sobreescriuria abans d'haver-lo desat a l'històric.
    nom_original = os.path.basename(nom_fitxer or "")
    file_path = None
    try:
        # Validar que és un fitxer XML
        if not nom_original.endswith(".xml"):
            raise NoValid("El fitxer ha de ser XML", codi="xml_extensio")

        # Data de vigència de la nova versió
        if data_inici:
            vigent_des_de = data_iso(data_inici)
        else:
            vigent_des_de = date.today()

        data_dir = str(get_data_dir_for_institucio(institucio))
        os.makedirs(data_dir, exist_ok=True)

        # Guardar fitxer (temporalment, fins que se'n fa la còpia a l'històric)
        file_path = os.path.join(data_dir, f".pujada_{uuid.uuid4().hex}.xml")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(fitxer, buffer)

        # Ha de ser un XML ben format i sense entitats ni referències externes:
        # la resta de l'aplicació el llegeix amb xml.etree, que no es protegeix
        # de tot. Un horari de FET no en fa servir mai.
        try:
            SafeET.parse(file_path)
        except (SafeET.ParseError, DefusedXmlException):
            raise NoValid("El fitxer no és un XML d'horari vàlid", codi="xml_no_valid") from None

        # Actualitzar configuració amb el nou path i versionar XML
        with get_data_db_session(institucio) as db:
            hash_contingut = _sha256(file_path)

            # Preparar directori d'històric
            history_dir = Path(data_dir) / "xml_history"
            history_dir.mkdir(parents=True, exist_ok=True)

            # Informació de l'XML actual (si existeix)
            current_version = XMLVersionRepository.get_current(db)

            # La cadena de versions ha de ser creixent: no es pot inserir una versió
            # que comenci abans (o el mateix dia) que la vigent.
            if current_version and vigent_des_de <= current_version.data_inici:
                raise NoValid(
                    f"La data de vigència ({vigent_des_de.isoformat()}) ha de ser posterior "
                    f"a la de la versió actual ({current_version.data_inici.isoformat()})",
                    codi="xml_data_no_posterior",
                )

            previous_path = ConfiguracioRepository.get(db, "xml_horari_path")

            if previous_path and not os.path.isabs(previous_path):
                previous_path = os.path.join(str(data_dir), previous_path)

            previous_hash = None
            if previous_path and os.path.exists(previous_path):
                previous_hash = _sha256(previous_path)

            # Si és el mateix XML que l'actual, no crear nova versió
            if current_version and current_version.hash_contingut == hash_contingut:
                XMLVersionRepository.encadena(db)
                db.commit()
                return {
                    "success": True,
                    "filename": nom_original,
                    "path": current_version.path,
                    "message": "XML idèntic a l'actual; no s'ha creat nova versió",
                }

            # Si no hi ha versions prèvies, crear versió inicial amb l'XML anterior (si existeix)
            if not current_version and previous_path and previous_hash:
                timestamp_prev = datetime.now().strftime("%Y%m%d_%H%M%S")
                history_prev_path = history_dir / f"horari_inicial_{timestamp_prev}_{uuid.uuid4().hex[:8]}.xml"
                shutil.copy2(previous_path, history_prev_path)
                stored_prev_path = _relatiu(history_prev_path, data_dir)

                XMLVersionRepository.create(
                    db, path=stored_prev_path, data_inici=date(2000, 1, 1), hash_contingut=previous_hash
                )
                if previous_hash == hash_contingut:
                    XMLVersionRepository.encadena(db)
                    db.commit()

                    return {
                        "success": True,
                        "filename": nom_original,
                        "path": stored_prev_path,
                        "message": "XML idèntic a l'anterior; s'ha creat la versió inicial",
                    }

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # El moment per llegir-lo; el sufix, perquè dues pujades del mateix
            # segon no es trepitgin
            history_path = history_dir / f"horari_{timestamp}_{uuid.uuid4().hex[:8]}.xml"
            shutil.copy2(file_path, history_path)
            stored_path = _relatiu(history_path, data_dir)

            XMLVersionRepository.create(db, path=stored_path, data_inici=vigent_des_de, hash_contingut=hash_contingut)
            # L'anterior es tanca el dia abans que entri en vigor la nova; el
            # punter "actual" només es mou si la nova ja és vigent avui
            XMLVersionRepository.encadena(db)
            db.commit()
            es_vigent_avui = vigent_des_de <= date.today()

        # Invalidar cache del horari per forçar recàrrega del nou XML
        invalidar_horari(institucio)
        log.debug(f"✅ Cache del horari invalidada - nou XML carregat: {stored_path}")

        return {
            "success": True,
            "filename": nom_original,
            "path": stored_path,
            "data_inici": vigent_des_de.isoformat(),
            "vigent_avui": es_vigent_avui,
            "message": f"Fitxer '{nom_original}' pujat correctament",
        }

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


# ---------------------------------------------------------------- versions


def llista_versions(db: Session) -> dict:
    """L'històric d'XMLs del centre, per data d'inici."""
    return {
        "versions": [
            {
                "id": v.id,
                "path": v.path,
                "data_inici": v.data_inici.isoformat(),
                "data_fi": v.data_fi.isoformat() if v.data_fi else None,
                "hash_contingut": v.hash_contingut,
            }
            for v in XMLVersionRepository.list_all(db)
        ]
    }


def _versio(db: Session, version_id: int):
    versio = XMLVersionRepository.get(db, version_id)
    if not versio:
        raise NoTrobat("Versió XML no trobada", codi="versio_xml_no_trobada")
    return versio


def canvia_inici(db: Session, version_id: int, data_inici: Optional[str]) -> None:
    """Canvia quan comença una versió; les dates de fi es recalculen totes (el
    dia abans que comenci la següent): no es poden posar a mà."""
    versio = _versio(db, version_id)
    if not data_inici:
        return

    nova = data_iso(data_inici)
    if XMLVersionRepository.comenca_el(db, nova, excepte=version_id):
        raise NoValid("Ja hi ha una altra versió d'XML que comença aquest dia", codi="versio_xml_mateix_dia")

    versio.data_inici = nova
    XMLVersionRepository.encadena(db)
    db.commit()


def esborra_versio(db: Session, institucio: str, version_id: int) -> None:
    """Esborra una versió i el seu fitxer; les altres s'encadenen de nou
    (sense forats)."""
    versio = _versio(db, version_id)
    path = versio.path
    XMLVersionRepository.delete(db, versio)
    XMLVersionRepository.encadena(db)
    db.commit()
    # Després del commit: si fallés, la versió hi seria i el fitxer també
    if path and not XMLVersionRepository.fa_servir(db, path):
        _esborra_fitxer_del_centre(institucio, path)


def _esborra_fitxer_del_centre(institucio: str, path: str) -> None:
    """Només un fitxer de dins de la carpeta del centre (com
    helpers._resolve_xml_path); el que no hi és, no es toca."""
    carpeta = get_data_dir_for_institucio(institucio).resolve()
    fitxer = (carpeta / path).resolve()
    if not fitxer.is_relative_to(carpeta):
        log.warning("Versió de l'XML amb el fitxer fora de la carpeta del centre: no s'esborra")
        return
    try:
        fitxer.unlink(missing_ok=True)
    except OSError:
        log.warning("No s'ha pogut esborrar el fitxer d'una versió de l'XML", exc_info=True)
