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

from helpers import assign_phase1_titulars
from models import Grup, GrupAlliberat, Nivell, Substitucio, Vigilancia
from repositories import ConfiguracioExamenRepository, VigilanciaRepository, parse_date
from scheduler_engine.core.constraints import detectar_nivell_grup
from serveis.dia import Dia
from utils.hores import normalitzar_hora

log = logging.getLogger(__name__)


def data_del_dia(dia_info: dict, setmanes: list) -> str | None:
    """La data d'un dia de l'horari: la seva o, si no en té, la que li toca
    pel nom («Dilluns») a la primera setmana que el tingui."""
    if dia_info.get("data"):
        return dia_info["data"]
    dia_nom = dia_info.get("dia", "")
    return next((setmana[dia_nom] for setmana in setmanes if setmana.get(dia_nom)), None)


def primera_data(horari: dict, setmanes: list) -> str | None:
    """La primera data de l'horari, per saber-ne les hores lectives."""
    for dia_info in horari.get("dies", []):
        if isinstance(dia_info, dict) and dia_info.get("data"):
            return dia_info["data"]
    for setmana in setmanes:
        for dia_info in horari.get("dies", []):
            d = setmana.get(dia_info.get("dia", "")) if isinstance(dia_info, dict) else setmana.get(dia_info, "")
            if d:
                return d
    return None


@dataclass
class ResumPublicacio:
    dates: list = field(default_factory=list)
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
    hores_esborrades: set = field(default_factory=set)


class PublicacioExamens:
    def __init__(self, db, cfg, totes_hores: list, grups_sense_classe: list, netejar_existents: bool):
        """`cfg`: la configuració del planificador (routes.scheduler_config.ConfigPlanificador)."""
        self.db = db
        self.cfg = cfg
        self.alliberaments = cfg.alliberaments if isinstance(cfg.alliberaments, dict) else {}
        self.nivells = list(self.alliberaments.keys())
        self.nivells_seleccionats = cfg.nivells_actius()
        self.totes_hores = totes_hores
        self.grups_sense_classe = grups_sense_classe
        self.netejar_existents = netejar_existents
        self.resum = ResumPublicacio()
        # (data, hora, nivell, grup, aula) de les vigilàncies dels exàmens publicats
        self._publicades = set()

    # ------------------------------------------------------------ per dia

    def publica_dia(self, dia_info: dict, data_iso: str) -> None:
        data = parse_date(data_iso)
        if self.netejar_existents:
            self._esborra_el_dia(data, data_iso)
        nivells_dia = {
            s["curs"]
            for slot in dia_info.get("sessions", [])
            for s in slot.get("sessions_simultanees", [])
            if s.get("curs")
        }
        self._sincronitza_vigilancies(dia_info, data, data_iso, nivells_dia)
        self._allibera_grups(data, data_iso)
        self.db.flush()

    def _esborra_el_dia(self, data, data_iso: str) -> None:
        """Mode forçat (opció d'emergència): esborra tot el dia i es recrea."""
        db = self.db
        for (hora,) in db.query(Vigilancia.hora).filter(Vigilancia.data == data).distinct():
            self.resum.hores_esborrades.add((data_iso, hora))
        self.resum.eliminades += db.query(Vigilancia).filter(Vigilancia.data == data).delete(synchronize_session=False)
        db.query(GrupAlliberat).filter(GrupAlliberat.data == data).delete(synchronize_session=False)
        db.query(Substitucio).filter(Substitucio.data == data, Substitucio.tipus_absencia == "VIGILANCIA").delete(
            synchronize_session=False
        )
        db.flush()

    def _hores_seguents(self, hora_inici: str, durada: int) -> list:
        """`durada` hores de l'horari del centre a partir de `hora_inici`."""
        if durada > 1 and self.totes_hores and hora_inici in self.totes_hores:
            idx = self.totes_hores.index(hora_inici)
            return self.totes_hores[idx : idx + durada]
        return [hora_inici]

    def _sincronitza_vigilancies(self, dia_info: dict, data, data_iso: str, nivells_dia: set) -> None:
        """Les vigilàncies dels nivells de l'horari en aquell dia, per (hora,
        nivell, grup, aula): les que ja hi eren es conserven (vigilant i
        comentaris), les noves es creen i les que ja no hi són s'esborren.
        Els nivells que l'horari no toca no es modifiquen."""
        db = self.db
        existents = {
            (v.hora, v.nivell or "", v.grups or "", v.aula or ""): v
            for v in db.query(Vigilancia)
            .filter(Vigilancia.data == data, Vigilancia.nivell.in_(list(nivells_dia)) if nivells_dia else False)
            .all()
        }
        noves = set()
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
                        self._publicades.add((data_iso, *clau))
                        noves.add(clau)
                        if clau not in existents:
                            db.add(
                                Vigilancia(
                                    data=data,
                                    hora=hora,
                                    tipus=tipus,
                                    grups=grup,
                                    aula=aula,
                                    vigilant=None,
                                    comentaris="",
                                    nivell=curs,
                                )
                            )
                            self.resum.creades += 1
                        elif (existents[clau].tipus or "") != tipus:
                            existents[clau].tipus = tipus
                            self.resum.actualitzades += 1
                        else:
                            self.resum.sense_canvis += 1
        for clau, v in existents.items():
            if clau not in noves:
                self.resum.hores_esborrades.add((data_iso, v.hora))
                db.delete(v)
                self.resum.eliminades += 1

    def _nivells_marcats(self, data_iso: str) -> list:
        """Nivells seleccionats al planificador amb alguna hora marcada sense classe aquell dia."""
        return [
            niv
            for niv in self.nivells_seleccionats
            if any(
                isinstance(flags, dict) and flags.get("a")
                for flags in (((self.alliberaments.get(niv) or {}).get("config") or {}).get(data_iso) or {}).values()
            )
        ]

    def _allibera_grups(self, data, data_iso: str) -> None:
        """Els grups dels nivells seleccionats queden sense classe a les hores
        marcades d'aquell dia, tinguin examen o no (sense repetir els que ja hi són)."""
        db = self.db
        marcats = self._nivells_marcats(data_iso)
        grups = (
            [g for g in self.grups_sense_classe if self._nivell_del_grup(g) in marcats]
            if self.grups_sense_classe
            else [
                g.codi
                for niv in marcats
                for nivell_obj in [db.query(Nivell).filter(Nivell.codi == niv).first()]
                if nivell_obj
                for g in db.query(Grup).filter(Grup.nivell_id == nivell_obj.id, Grup.actiu == True).all()  # noqa: E712
            ]
        )
        existents = {
            (ga.hora, ga.grups or "") for ga in db.query(GrupAlliberat).filter(GrupAlliberat.data == data).all()
        }
        for grup in grups:
            nivell = self._nivell_del_grup(grup)
            if not nivell:
                continue
            for hora in self._hores_alliberades(nivell, data_iso):
                if (hora, grup) not in existents:
                    db.add(GrupAlliberat(data=data, hora=hora, grups=grup))
                    self.resum.grups_alliberats += 1

    def _nivell_del_grup(self, grup: str) -> str | None:
        """El nivell dels alliberaments al qual pertany un grup (p. ex. «1-BAT-A» → «1-BAT»)."""
        if not grup:
            return None
        for nivell in self.nivells:
            if nivell and nivell in grup:
                return nivell
        try:
            nivell = detectar_nivell_grup(grup, self.nivells)
            return None if nivell == "altres" else nivell
        except Exception:
            log.warning("No s'ha pogut detectar el nivell d'un grup", exc_info=True)
            return None

    def _hores_alliberades(self, nivell: str, data_iso: str) -> list:
        """Les hores sense classe (marca «a») d'un nivell aquell dia, en l'ordre de l'horari."""
        dia_cfg = ((self.alliberaments.get(nivell, {}).get("config")) or {}).get(data_iso, {})
        hores = [
            normalitzar_hora(h) for h, flags in (dia_cfg or {}).items() if isinstance(flags, dict) and flags.get("a")
        ]
        if self.totes_hores:
            ordre = {h: i for i, h in enumerate(self.totes_hores)}
            return sorted(set(hores), key=lambda h: ordre.get(h, 10**9))
        return sorted(set(hores))

    # ------------------------------------------------------------ titulars

    def _avisa_titulars_absents(self, db, vigilancies: list, institucio: str, data_iso: str) -> None:
        """Un titular amb una absència coberta aquell dia no és a l'horari del
        dia (Dia) i, per tant, no s'assigna: la vigilància queda sense vigilant
        i cal que l'usuari ho sàpiga per assignar-la."""
        absents = Dia.de_text(data_iso, institucio).horari.absents_coberts
        if not absents:
            return
        for v in vigilancies:
            if v.get("vigilant"):
                continue
            titular = ConfiguracioExamenRepository.buscar_titular(
                db, v.get("tipus", ""), v.get("grups", ""), v.get("aula", "")
            )
            if titular in absents:
                self.resum.avisos.append(
                    {
                        "codi": "titular_amb_absencia_coberta",
                        "params": {
                            "data": data_iso,
                            "hora": v.get("hora", ""),
                            "titular": titular,
                            "assignatura": v.get("tipus", ""),
                            "grups": v.get("grups", ""),
                        },
                    }
                )

    def assigna_titulars(self, institucio: str) -> None:
        """Cada examen, amb el seu titular com a vigilant si està lliure."""
        db = self.db
        for data_iso in sorted(set(self.resum.dates)):
            db.flush()
            # Les vigilàncies dels exàmens publicats (no les d'altres nivells);
            # el titular s'hi posa a les hores que està disponible o alliberat
            vigilancies = [
                v
                for vigs in VigilanciaRepository.get_by_date(db, data_iso).values()
                for v in vigs
                if (data_iso, v.get("hora"), v.get("nivell") or "", v.get("grups") or "", v.get("aula") or "")
                in self._publicades
            ]
            if not vigilancies:
                continue
            try:
                core = Dia.de_text(data_iso, institucio).vigilancia_core(db)
                vigilants = {}
                for v in vigilancies:
                    hora = v.get("hora", "")
                    vigilants.setdefault(hora, set())
                    if v.get("vigilant"):
                        vigilants[hora].add(v["vigilant"])
                assign_phase1_titulars(vigilancies, core, vigilants, db)
                self._avisa_titulars_absents(db, vigilancies, institucio, data_iso)
                for v in vigilancies:
                    db_id = v.get("db_id") or v.get("id")
                    if v.get("vigilant") and db_id:
                        vig = db.query(Vigilancia).filter(Vigilancia.id == int(db_id)).first()
                        if vig and not vig.vigilant:
                            vig.vigilant = v["vigilant"]
                            self.resum.titulars += 1
            except Exception as e:
                self.resum.errors.append(f"Auto-assignació {data_iso}: {str(e)}")
