"""
Publicar l'horari d'exàmens del planificador (POST /api/scheduler/publicar):
per a cada data, les vigilàncies dels exàmens (conservant el vigilant i els
comentaris de les que ja hi eren), els grups que queden sense classe i,
opcionalment, els titulars com a vigilants.

- Cada examen té vigilància a totes les seves hores (la durada de l'examen per
  a l'alumnat); el titular s'hi assigna a les hores que està disponible.
- Queden sense classe els grups dels nivells seleccionats al planificador a
  les hores marcades aquell dia, tinguin examen o no a aquella hora.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import cast

from configuracio_examens.repositories import MasterConfigRepository
from database import get_data_db_session
from errors_domini import NoValid
from errors_servidor import registra_excepcio
from grups.repositories import GrupsAlliberatsRepository
from horari.domain import Dia
from planificador.config import ConfigPlanificador, llegeix_config
from planificador.schemas import DiaHorari, SchedulerPublicarRequest
from planificador.services import cursos_anteriors
from substitucions import cobertures
from substitucions.reconciliacio import treu_substituts_no_valids
from substitucions.repositories import SubstitucioRepository
from textos import normalitzar_hora
from vigilancies.assignacio import titulars_de
from vigilancies.domain import nivell_obligatori
from vigilancies.repositories import VigilanciaRepository
from vigilancies.services import (
    calcula_assignacio,
    completa_ordre,
    files_configuracio,
    ordena_automaticament,
    taules_de_grups,
    te_ordre_manual,
)

log = logging.getLogger(__name__)


def error_intern(missatge: str) -> str:
    """Un error intern durant la publicació: el detall (amb la traça) va al
    registre amb una referència; la resposta només en porta el missatge i la
    referència. Es crida des d'un `except`."""
    return f"{missatge} (error intern, ref {registra_excepcio(missatge)})"


def data_del_dia(dia: DiaHorari, setmanes: list[dict[str, date]]) -> date | None:
    """La data del dia o la de la primera setmana que conté el seu nom."""
    return dia.data or next((setmana[dia.dia] for setmana in setmanes if dia.dia in setmana), None)


def primera_data(dies: list[DiaHorari], setmanes: list[dict[str, date]]) -> date | None:
    """La primera data de l’horari, per saber-ne les hores lectives."""
    for dia in dies:
        if dia.data:
            return dia.data
    for setmana in setmanes:
        for dia in dies:
            if data := setmana.get(dia.dia):
                return data
    return None


@dataclass
class ResumPublicacio:
    dates: list[date] = field(default_factory=list)
    creades: int = 0
    actualitzades: int = 0
    sense_canvis: int = 0
    eliminades: int = 0
    grups_alliberats: int = 0
    titulars: int = 0
    errors: list = field(default_factory=list)
    # Avisos per a l'usuari, amb codi i paràmetres (els tradueix la pantalla):
    # p.ex. un titular amb una absència coberta, la vigilància del qual queda sense vigilant
    avisos: list = field(default_factory=list)
    # (data, hora) on s'ha esborrat alguna vigilància: cal refrescar-ne les
    # cobertures de classe dels vigilants (com fa esborrar-la a Vigilàncies)
    hores_esborrades: set[tuple[date, str]] = field(default_factory=set)


class PublicacioExamens:
    def __init__(
        self, db, cfg: ConfigPlanificador, totes_hores: list, grups_sense_classe: list, netejar_existents: bool
    ):
        """`cfg`: la configuració del planificador (planificador.config.ConfigPlanificador)."""
        self.db = db
        self.cfg = cfg
        self.alliberaments = cfg.alliberaments if isinstance(cfg.alliberaments, dict) else {}
        self.nivells_seleccionats = cfg.nivells_actius()
        self.totes_hores = totes_hores
        self.grups_sense_classe = grups_sense_classe
        self.netejar_existents = netejar_existents
        self.resum = ResumPublicacio()
        # (data, hora, nivell, grup, aula) de les vigilàncies dels exàmens publicats
        self._publicades: set[tuple[date, str, str, str, str]] = set()

    # ------------------------------------------------------------ per dia

    def publica_dia(self, dia_info: dict, data: date) -> None:
        if self.netejar_existents:
            self._esborra_el_dia(data)
        nivells_dia = {
            s["curs"]
            for slot in dia_info.get("sessions", [])
            for s in slot.get("sessions_simultanees", [])
            if s.get("curs")
        }
        manual = te_ordre_manual(VigilanciaRepository.del_dia(self.db, data))
        self._sincronitza_vigilancies(dia_info, data, nivells_dia)
        self.db.flush()
        # Un dia sense ordre fet a mà surt ordenat automàticament; si n'hi
        # havia, les files noves van al final del bloc de la seva hora
        vigs = VigilanciaRepository.del_dia(self.db, data)
        if manual:
            completa_ordre(vigs)
        else:
            ordena_automaticament(vigs)
        self._allibera_grups(data)
        self.db.flush()
        treu_substituts_no_valids(self.db, data)

    def _esborra_el_dia(self, data: date) -> None:
        """Mode forçat (opció d'emergència): esborra tot el dia i es recrea."""
        db = self.db
        for hora in VigilanciaRepository.hores_del_dia(db, data):
            self.resum.hores_esborrades.add((data, hora))
        self.resum.eliminades += VigilanciaRepository.esborra_del_dia(db, data)
        GrupsAlliberatsRepository.esborra_del_dia(db, data)
        SubstitucioRepository.esborra_vigilancies_del_dia(db, data)
        db.flush()

    def _hores_seguents(self, hora_inici: str, durada: int) -> list:
        """`durada` hores de l'horari del centre a partir de `hora_inici`."""
        if durada > 1 and self.totes_hores and hora_inici in self.totes_hores:
            idx = self.totes_hores.index(hora_inici)
            return self.totes_hores[idx : idx + durada]
        return [hora_inici]

    def _sincronitza_vigilancies(self, dia_info: dict, data: date, nivells_dia: set) -> None:
        """Les vigilàncies dels nivells de l'horari en aquell dia, per (hora,
        nivell, grup, aula): les que ja hi eren es conserven (vigilant i
        comentaris), les noves es creen i les que ja no hi són s'esborren.
        Els nivells que l'horari no toca no es modifiquen."""
        db = self.db
        existents = {
            cast(tuple[str, str, str, str], (v.hora, v.nivell or "", v.grups or "", v.aula or "")): v
            for v in VigilanciaRepository.del_dia_dels_nivells(db, data, nivells_dia)
        }
        noves: dict[tuple[str, str, str, str], str] = {}  # clau → tipus de la primera sessió que l'ocupa
        for slot in dia_info.get("sessions", []):
            hora_inici = slot.get("hora", "")
            if not hora_inici:
                continue
            for sessio in slot.get("sessions_simultanees", []):
                curs = sessio.get("curs", "")
                nom = sessio.get("nom", "")
                hores = self._hores_seguents(hora_inici, self.cfg.durada_examen_de(nom))
                for examen in sessio.get("examens", []):
                    grup = examen.get("grup", "")
                    aula = examen.get("aula", "") or ""
                    tipus = examen.get("assignatura") or sessio.get("nom_base") or sessio.get("nom", "")
                    for hora in hores:
                        clau = (hora, curs, grup, aula)
                        if clau in noves:
                            # Repetida a la mateixa petició: una sola fila. Si és un altre
                            # examen (dos a la mateixa aula i hora), l'usuari ho ha de saber.
                            if noves[clau] != tipus:
                                self._avisa_aula_ocupada(data, clau, noves[clau], tipus)
                            continue
                        self._publicades.add((data, *clau))
                        noves[clau] = tipus
                        if clau not in existents:
                            VigilanciaRepository.afegeix(
                                db,
                                data=data,
                                hora=hora,
                                tipus=tipus,
                                grups=grup,
                                aula=aula,
                                vigilant=None,
                                comentaris="",
                                nivell=nivell_obligatori(curs),
                            )
                            self.resum.creades += 1
                        elif (existents[clau].tipus or "") != tipus:
                            existents[clau].tipus = tipus
                            self.resum.actualitzades += 1
                        else:
                            self.resum.sense_canvis += 1
        for clau, v in existents.items():
            if clau not in noves:
                self.resum.hores_esborrades.add((data, clau[0]))
                VigilanciaRepository.esborra(db, v)
                self.resum.eliminades += 1

    def _avisa_aula_ocupada(self, data: date, clau: tuple, primer: str, segon: str) -> None:
        hora, _, grup, aula = clau
        avis = {
            "codi": "examens_mateixa_aula_i_hora",
            "params": {
                "data": data,
                "hora": hora,
                "grups": grup,
                "aula": aula,
                "assignatura": primer,
                "altra": segon,
            },
        }
        if avis not in self.resum.avisos:
            self.resum.avisos.append(avis)

    def _nivells_marcats(self, data: date) -> list:
        """Nivells seleccionats al planificador amb alguna hora marcada sense classe aquell dia."""
        return [
            niv
            for niv in self.nivells_seleccionats
            if any(
                isinstance(flags, dict) and flags.get("a")
                for flags in (((self.alliberaments.get(niv) or {}).get("config") or {}).get(data) or {}).values()
            )
        ]

    def _allibera_grups(self, data: date) -> None:
        """Els grups dels nivells seleccionats queden sense classe a les hores
        marcades d'aquell dia, tinguin examen o no (sense repetir els que ja hi són)."""
        db = self.db
        marcats = self._nivells_marcats(data)
        grups = (
            [g for g in self.grups_sense_classe if self._nivell_del_grup(g) in marcats]
            if self.grups_sense_classe
            else [g for niv in marcats for g in MasterConfigRepository.grups_actius_del_nivell(db, niv)]
        )
        existents = {(ga.hora, ga.grups or "") for ga in GrupsAlliberatsRepository.files_del_dia(db, data)}
        for grup in grups:
            nivell = self._nivell_del_grup(grup)
            if not nivell:
                continue
            for hora in self._hores_alliberades(nivell, data):
                if (hora, grup) not in existents:
                    GrupsAlliberatsRepository.afegeix(db, data, hora, grup)
                    self.resum.grups_alliberats += 1

    def _nivell_del_grup(self, grup: str) -> str | None:
        """El nivell d'un grup (p. ex. «1-BAT-A» → «1-BAT»), amb les taules de la configuració d'exàmens."""
        return self.cfg.nivells_dels_grups.nivell(grup)

    def _hores_alliberades(self, nivell: str, data: date) -> list:
        """Les hores sense classe (marca «a») d'un nivell aquell dia, en l'ordre de l'horari."""
        dia_cfg = ((self.alliberaments.get(nivell, {}).get("config")) or {}).get(data, {})
        hores = [
            normalitzar_hora(h) for h, flags in (dia_cfg or {}).items() if isinstance(flags, dict) and flags.get("a")
        ]
        if self.totes_hores:
            ordre = {h: i for i, h in enumerate(self.totes_hores)}
            return sorted(set(hores), key=lambda h: ordre.get(h, 10**9))
        return sorted(set(hores))

    # ------------------------------------------------------------ titulars

    def _avisa_titulars_absents(self, db, vigilancies: list, institucio: str, data: date) -> None:
        """Un titular amb una absència coberta aquell dia no és a l'horari del
        dia (Dia) i, per tant, no s'assigna: la vigilància queda sense vigilant
        i cal que l'usuari ho sàpiga per assignar-la."""
        absents = Dia(data, institucio).horari.absents_coberts
        if not absents:
            return
        config = files_configuracio(db)
        _, abreviatures, nivells = taules_de_grups(db)
        for v in vigilancies:
            if v.vigilant:
                continue
            possibles, _ = titulars_de(config, v.tipus, v.grups, v.aula, abreviatures, nivells)
            # Si tots els titulars possibles hi són (n'hi pot haver diversos)
            if possibles and possibles <= absents:
                titular = ", ".join(sorted(possibles))
                self.resum.avisos.append(
                    {
                        "codi": "titular_amb_absencia_coberta",
                        "params": {
                            "data": data,
                            "hora": v.hora,
                            "titular": titular,
                            "assignatura": v.tipus,
                            "grups": v.grups,
                        },
                    }
                )

    def assigna_titulars(self, institucio: str) -> None:
        """Cada examen, amb el seu titular com a vigilant si està lliure."""
        db = self.db
        for data in sorted(set(self.resum.dates)):
            db.flush()
            # Les vigilàncies dels exàmens publicats (no les d'altres nivells);
            # el titular s'hi posa a les hores que està disponible o alliberat
            vigilancies = [
                v
                for vigs in VigilanciaRepository.get_by_date(db, data).values()
                for v in vigs
                if (data, v.hora, v.nivell or "", v.grups or "", v.aula or "") in self._publicades
            ]
            if not vigilancies:
                continue
            try:
                # L'assignació sencera de cada hora (com «Assigna titulars»):
                # se'n desen només els titulars de les files publicades
                calcul = calcula_assignacio(db, Dia(data, institucio), data, amb_guardia=False)
                publicades = {str(v.id) for v in vigilancies}
                self._avisa_titulars_absents(db, vigilancies, institucio, data)
                for vig_id, professor in calcul["vigilants"].items():
                    if vig_id not in publicades or professor not in calcul["titulars"].get(vig_id, ()):
                        continue
                    vig = VigilanciaRepository.per_id(db, int(vig_id))
                    if vig and not vig.vigilant:
                        vig.vigilant = professor
                        self.resum.titulars += 1
            except Exception:
                self.resum.errors.append(error_intern(f"{data}: no s'han pogut assignar els titulars"))


def publica(payload: SchedulerPublicarRequest, institucio: str, avui: date) -> dict:
    """Publica l'horari generat com a vigilàncies (i grups sense classe) de
    cada data; opcionalment hi posa els titulars. En prova (`dry_run`) o si
    falla algun dia, no desa res."""
    dies = payload.horari.dies
    setmanes = payload.setmanes
    grups_sense_classe = payload.grups_sense_classe or []
    opcions = payload.opcions
    dry_run = payload.dry_run

    if not dies:
        raise NoValid("L'horari no conté dies", codi="horari_sense_dies")
    if not setmanes:
        raise NoValid("Cal indicar almenys una setmana amb dates", codi="publicacio_sense_setmanes")

    dates_horari = [dia.data for dia in dies if dia.data is not None]
    dates_horari += [v for setmana in setmanes for v in setmana.values()]
    with get_data_db_session(institucio, lectura=True) as db:
        anterior = cursos_anteriors(db, dates_horari, avui)
    if anterior:
        raise NoValid(
            f"Les dates són del curs {', '.join(anterior['cursos'])}, anterior a l'actual "
            f"({anterior['curs_actual']}). El planificador fa servir la configuració d'exàmens del "
            "curs actual; les vigilàncies de cursos anteriors es consulten a Vigilàncies.",
            codi="publicacio_curs_anterior",
            params=anterior,
        )

    # Hores lectives del centre (per allargar els exàmens de més d'una hora)
    totes_hores = []
    data_hores = primera_data(dies, setmanes)
    if data_hores:
        totes_hores = Dia(data_hores, institucio).horari.hores or []

    with get_data_db_session(institucio) as db:
        publicacio = PublicacioExamens(
            db, llegeix_config(institucio), totes_hores, grups_sense_classe, opcions.netejar_existents
        )
        resum = publicacio.resum
        for dia in dies:
            data = data_del_dia(dia, setmanes)
            if not data:
                continue
            resum.dates.append(data)
            try:
                publicacio.publica_dia(dia.model_dump(exclude_unset=True, by_alias=True), data)
            except Exception:
                resum.errors.append(error_intern(f"{data}: no s'ha pogut publicar aquest dia"))

        if opcions.auto_assign_titulars and not resum.errors and not dry_run:
            publicacio.assigna_titulars(institucio)

        if dry_run or resum.errors:
            db.rollback()
        else:
            db.flush()

            try:
                for data, hora in sorted(resum.hores_esborrades):
                    cobertures.refresca_cobertures(data, hora, db)
            except Exception:
                # Un error en refrescar les cobertures no desa res (abans, un 500 a mitges)
                db.rollback()
                resum.errors.append(error_intern("no s'han pogut actualitzar les cobertures de classe"))
            else:
                db.commit()

    return {
        "success": len(resum.errors) == 0,
        "dry_run": dry_run,
        "dates_processades": sorted(set(resum.dates)),
        "vigilancies_creades": resum.creades,
        "vigilancies_actualitzades": resum.actualitzades,
        "vigilancies_sense_canvis": resum.sense_canvis,
        "vigilancies_eliminades": resum.eliminades,
        "grups_alliberats_creats": resum.grups_alliberats,
        "titulars_assignats": resum.titulars,
        "errors": resum.errors or None,
        "avisos": resum.avisos or None,
    }
