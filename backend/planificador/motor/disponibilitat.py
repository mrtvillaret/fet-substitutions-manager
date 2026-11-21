"""
Disponibilitat estàtica i context de franja, amb la classificació actual.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from planificador.compartit.nivells import NivellsDelsGrups
from planificador.compartit.normalitzacio import normalitzar_dia, normalitzar_text
from planificador.motor.durades import examen_del_problema, hores_ocupades, vigilancia
from planificador.motor.model import Problema, descongela
from textos import normalitzar_hora as _normalitzar_hora


@dataclass(slots=True)
class _Context:
    """El que és igual per a tots els professors d'una sessió en una franja."""

    nivells_actius: list[str]
    nivells_dels_grups: NivellsDelsGrups
    alliberaments_per_nivell: dict | None
    data_iso: str | None
    no_substituir_norm: set[str]
    totes_hores: list[str]  # la graella, normalitzada i sense repetits
    hores_examen: list[str]  # totes les hores que dura l'examen
    hores_supervisio: set[str]  # les hores en què el titular hi ha de ser


@dataclass(slots=True)
class _Jornada:
    """Primera i última hora amb activitat d'un professor, i on són a la graella."""

    primera: str | None
    ultima: str | None
    idx_primera: int | None
    idx_ultima: int | None


def _camp(objecte: dict | Any, nom: str, defecte=None):
    """Un camp d'una sessió o d'un examen, sigui diccionari (v2) o objecte (v3)."""
    return objecte.get(nom, defecte) if isinstance(objecte, dict) else getattr(objecte, nom, defecte)


def _dedup(seq):
    vistos = set()
    resultat = []
    for item in seq:
        if item in vistos:
            continue
        vistos.add(item)
        resultat.append(item)
    return resultat


def _analisi_buida(nivells_actius: list[str]) -> dict:
    analisi = {
        "lliures": [],
        "alliberats": [],
        "abans_jornada": [],
        "despres_jornada": [],
        "no_treballa_dia": [],
        "substitucions": [],
        "altres": [],
        "zona_examen": [],  # Conflictes a la zona examen sense titular (cost=0)
    }
    for nivell in nivells_actius:
        analisi[f"classe_{nivell}"] = []
    return analisi


def _nivell_alliberat_a_slot(ctx: _Context, nivell: str, hora: str) -> bool:
    """
    Comprova si un nivell està alliberat (🟩) a la data de la sessió i una hora.
    Si no hi ha informació d'alliberaments, tots els nivells actius es
    consideren alliberats (comportament antic).
    """
    if not ctx.alliberaments_per_nivell:
        return nivell in ctx.nivells_actius

    nivell_data = ctx.alliberaments_per_nivell.get(nivell)
    if not nivell_data:
        return False

    config = nivell_data.get("config", {})
    if not config:
        return False

    # Buscar la data (format YYYY-MM-DD)
    dia_config = config.get(ctx.data_iso)
    if not dia_config:
        return False

    # Buscar l'hora (format HH:MM)
    hora_config = dia_config.get(_normalitzar_hora(hora))
    if not hora_config:
        return False

    # Comprovar si està alliberat (clau 'a')
    return hora_config.get("a", False) is True


def _hores_de_la_sessio(
    hora: str,
    totes_hores: list[str],
    durada_sessio: int,
    hores_override: list[str] | None,
    hores_supervisio: list[str] | None,
) -> tuple[list[str], list[str], set[str]] | None:
    """(graella normalitzada, hores de l'examen, hores de supervisió); None si
    l'hora d'inici no és a la graella."""
    totes_hores_norm = _dedup([_normalitzar_hora(h) for h in (totes_hores or [])])
    hora_norm = _normalitzar_hora(hora)
    if hora_norm not in totes_hores_norm:
        return None

    # Hores afectades per l'examen (finestra completa)
    if hores_override is not None:
        hores_examen = [_normalitzar_hora(h) for h in hores_override]
    else:
        idx_inici = totes_hores_norm.index(hora_norm)
        idx_final = min(idx_inici + durada_sessio, len(totes_hores_norm))
        hores_examen = totes_hores_norm[idx_inici:idx_final]

    # Zona de supervisió: hores on el titular HA d'estar present (cost real)
    # Si hores_supervisio és None → totes les hores d'examen són de supervisió
    if hores_supervisio is not None:
        hores_supervisio_set = {_normalitzar_hora(h) for h in hores_supervisio}
    else:
        hores_supervisio_set = set(hores_examen)
    return totes_hores_norm, hores_examen, hores_supervisio_set


def _titulars_altres_sessions(sessio: dict | Any, sessions_al_slot: list[dict | Any] | None) -> set:
    """Titulars de les altres sessions de la mateixa franja (per als alliberaments)."""
    profs_altres = set()
    if not sessions_al_slot:
        return profs_altres
    sessio_nom = _camp(sessio, "nom")
    for s_info in sessions_al_slot:
        s_real = s_info.get("sessio", s_info) if isinstance(s_info, dict) else s_info
        if _camp(s_real, "nom") != sessio_nom:
            for ex in _camp(s_real, "examens", []):
                p = _camp(ex, "titular")
                if p:
                    profs_altres.add(p)
    return profs_altres


def _horari_del_dia(
    prof: str, dia_norm: str, horaris_professors: dict, horaris_professors_norm: dict | None
) -> dict | None:
    """{hora normalitzada: activitat} del professor aquell dia; None si el dia
    no surt al seu horari."""
    if horaris_professors_norm:
        return horaris_professors_norm.get(prof, {}).get(dia_norm)
    if dia_norm not in horaris_professors[prof]:
        return None
    return horari_del_dia_normalitzat(horaris_professors[prof][dia_norm])


def horari_del_dia_normalitzat(hores: dict) -> dict:
    """{hora normalitzada (HH:MM): activitat} d'un dia: si dues hores es
    normalitzen igual guanya la primera, i una hora de nom buit no hi és. És la
    mateixa normalització per als dos camins: l'horari sense normalitzar
    (aquí) i el normalitzat d'entrada pels motors (`_pre_normalitzar_horaris`)."""
    horari_dia_norm = {}
    for h_k, act in hores.items():
        h_norm = _normalitzar_hora(h_k)
        if h_norm and h_norm not in horari_dia_norm:
            horari_dia_norm[h_norm] = act
    return horari_dia_norm


def _jornada(horari_dia_norm: dict, totes_hores_norm: list[str], index_map: dict[str, int]) -> _Jornada:
    primera = None
    ultima = None
    for h in totes_hores_norm:
        if h in horari_dia_norm:
            if primera is None:
                primera = h
            ultima = h

    idx_primera = index_map.get(primera) if primera else None
    idx_ultima = index_map.get(ultima) if ultima else None
    if idx_primera is None and idx_ultima is not None:
        idx_primera = idx_ultima
    if idx_ultima is None and idx_primera is not None:
        idx_ultima = idx_primera
    return _Jornada(primera, ultima, idx_primera, idx_ultima)


def _classifica_classe(analisi: dict, ctx: _Context, prof: str, ex, act: dict, h: str) -> str:
    """Apunta l'activitat que el professor té a l'hora h de l'examen i diu què
    és: «zona_examen» (fora de la supervisió: informatiu, cap cost),
    «alliberat», «altres» o «substitucio»."""
    grup = act.get("grup", "") or ""
    assig = act.get("assignatura", "") or ""
    # El nivell de la classe, amb les taules (un dels actius o cap)
    nivell_del_grup = ctx.nivells_dels_grups.nivell(grup, entre=ctx.nivells_actius)

    def no_es_cobreix() -> bool:
        """Sense grup (guàrdies, CD...) o assignatura de «No substituir»."""
        return not grup.strip() or normalitzar_text(assig) in ctx.no_substituir_norm

    if h not in ctx.hores_supervisio:
        # Zona examen: el titular ja no ha d'estar present → no cost real
        # Registrem el conflicte com a informatiu (zona_examen) si és classe real
        es_alliberat_zona = nivell_del_grup and _nivell_alliberat_a_slot(ctx, nivell_del_grup, h)
        if not es_alliberat_zona and not no_es_cobreix():
            analisi["zona_examen"].append({"professor": prof, "examen": ex, "activitat": act, "hora": h})
        return "zona_examen"

    # Zona supervisió: el titular HA d'estar → cost real
    # Cas 1: Alliberat perquè els seus alumnes estan alliberats (no tenen classe)
    if nivell_del_grup and _nivell_alliberat_a_slot(ctx, nivell_del_grup, h):
        return "alliberat"

    # Cas 2: Altres activitats (guàrdies, CD, etc.) o assignatures No Substituir
    if no_es_cobreix():
        analisi["altres"].append({"professor": prof, "examen": ex, "activitat": act, "hora": h})
        return "altres"

    # Cas 3: Substitució real
    detall = {"professor": prof, "examen": ex, "activitat": act, "hora": h}
    analisi[f"classe_{nivell_del_grup}" if nivell_del_grup else "altres"].append(detall)
    analisi["substitucions"].append(detall)
    return "substitucio"


def _classifica_hora_lliure(
    analisi: dict,
    ctx: _Context,
    prof: str,
    ex,
    h: str,
    jornada: _Jornada,
    index_map: dict[str, int],
    abans_vistes: set[str],
    despres_vistes: set[str],
) -> str | None:
    """Una hora de supervisió sense activitat: «dins» de la jornada, o «fora»
    (apunta cada hora que ha d'esperar abans de la primera classe o després de
    l'última, pati inclòs i una sola vegada); None si l'hora no és a la graella."""
    if jornada.idx_primera is None or jornada.idx_ultima is None:
        return "dins"
    idx_h = index_map.get(h)
    if idx_h is None:
        return None
    if idx_h < jornada.idx_primera:
        # De l'hora de l'examen fins a la primera classe
        for h_espera in ctx.totes_hores[idx_h : jornada.idx_primera]:
            if h_espera not in abans_vistes:
                abans_vistes.add(h_espera)
                analisi["abans_jornada"].append(
                    {"professor": prof, "examen": ex, "primera_hora": jornada.primera, "hora": h_espera}
                )
        return "fora"
    if idx_h > jornada.idx_ultima:
        # De després de l'última classe fins a l'hora de l'examen
        for h_espera in ctx.totes_hores[jornada.idx_ultima + 1 : idx_h + 1]:
            if h_espera not in despres_vistes:
                despres_vistes.add(h_espera)
                analisi["despres_jornada"].append(
                    {"professor": prof, "examen": ex, "ultima_hora": jornada.ultima, "hora": h_espera}
                )
        return "fora"
    return "dins"


def _analitza_professor(
    analisi: dict, ctx: _Context, prof: str, ex, horari_dia_norm: dict, es_en_altres: bool
) -> tuple[bool, bool]:
    """Classifica cada hora de l'examen d'un professor que treballa aquell dia."""
    index_map = {h: i for i, h in enumerate(ctx.totes_hores)}
    jornada = _jornada(horari_dia_norm, ctx.totes_hores, index_map)

    classes = set()  # què ha sortit a les hores de supervisió amb activitat
    lliures = set()  # i a les hores de supervisió sense
    abans_vistes, despres_vistes = set(), set()
    for h in ctx.hores_examen:
        act = horari_dia_norm.get(h)
        if act:
            classes.add(_classifica_classe(analisi, ctx, prof, ex, act, h))
        elif h in ctx.hores_supervisio:  # a la zona d'examen no hi ha abans ni després
            lliures.add(
                _classifica_hora_lliure(analisi, ctx, prof, ex, h, jornada, index_map, abans_vistes, despres_vistes)
            )

    te_activitat_supervisio = bool(classes - {"zona_examen"})
    if not te_activitat_supervisio and "fora" not in lliures and "dins" in lliures:
        analisi["lliures"].append({"professor": prof, "examen": ex})

    if te_activitat_supervisio and "substitucio" not in classes and ("alliberat" in classes or es_en_altres):
        analisi["alliberats"].append({"professor": prof, "examen": ex})

    return te_activitat_supervisio and "substitucio" not in classes, "alliberat" in classes


def analitzar_disponibilitat_sessio(
    sessio: dict | Any,
    dia: str,
    hora: str,
    horaris_professors: dict,
    totes_hores: list[str],
    nivells_actius: list[str],
    durada_titular: int = 1,
    no_substituir_norm: set[str] = None,
    sessions_al_slot: list[dict | Any] = None,
    hores_override: list[str] | None = None,
    alliberaments_per_nivell: dict | None = None,
    data_iso: str | None = None,
    hores_supervisio: list[str] | None = None,
    horaris_professors_norm: dict | None = None,
    nivells_dels_grups: NivellsDelsGrups | None = None,
    *,
    candidats_context: list | None = None,
) -> dict:
    """
    Analitza la disponibilitat dels professors d'una sessió en un slot determinat.

    Paràmetres:
    - alliberaments_per_nivell: Dict amb estructura { nivell: { config: { "YYYY-MM-DD": { "HH:MM": { a: bool } } } } }
      On 'a' indica si el nivell està alliberat a aquella data/hora.
    - data_iso: Data en format ISO (YYYY-MM-DD) per consultar els alliberaments.
    - nivells_dels_grups: el nivell de cada grup de les classes, amb les taules
      de la configuració d'exàmens; sense, cap classe és d'un nivell.

    Retorna un diccionari amb les categories de professors:
    - lliures: sense classe ni obligacions
    - alliberats: tindrien classe però els seus alumnes estan alliberats (no tenen classe)
    - substitucions: necessiten algú que els cobreixi la classe
    - abans_jornada: haurien d'arribar abans de la seva primera classe
    - despres_jornada: haurien de marxar després de la seva última classe
    - no_treballa_dia: el professor no té cap activitat aquest dia
    - classe_{nivell}: detall de quina classe tenen (per a estadístiques)
    - altres: activitats sense grup o assignatures que no es substitueixen
    """
    analisi = _analisi_buida(nivells_actius)
    dia_norm = normalitzar_dia(dia)
    # durada_titular: exactament la que rep la funció (ja resolta pel camí de càlcul)
    hores = _hores_de_la_sessio(hora, totes_hores, durada_titular, hores_override, hores_supervisio)
    if hores is None:
        return analisi
    totes_hores_norm, hores_examen, hores_supervisio_set = hores
    ctx = _Context(
        nivells_actius=nivells_actius,
        nivells_dels_grups=nivells_dels_grups or NivellsDelsGrups(),
        alliberaments_per_nivell=alliberaments_per_nivell,
        data_iso=data_iso,
        no_substituir_norm=set() if no_substituir_norm is None else no_substituir_norm,
        totes_hores=totes_hores_norm,
        hores_examen=hores_examen,
        hores_supervisio=hores_supervisio_set,
    )
    profs_altres = _titulars_altres_sessions(sessio, sessions_al_slot)

    for ex in _camp(sessio, "examens", []):
        prof = _camp(ex, "titular")
        if not prof:
            continue

        if prof not in horaris_professors:
            analisi["lliures"].append({"professor": prof, "examen": ex})
            continue

        horari_dia_norm = _horari_del_dia(prof, dia_norm, horaris_professors, horaris_professors_norm)
        # Un dia sense cap activitat és un dia que no treballa, encara que surti a
        # l'XML amb les franges buides (FET hi posa tots els dies de cada professor)
        if not horari_dia_norm:
            for h in hores_examen:
                if h in hores_supervisio_set:
                    analisi["no_treballa_dia"].append({"professor": prof, "examen": ex, "dia": dia_norm, "hora": h})
            continue

        candidat, alliberat = _analitza_professor(analisi, ctx, prof, ex, horari_dia_norm, prof in profs_altres)
        if candidat and candidats_context is not None:
            candidats_context.append((alliberat, {"professor": prof, "examen": ex}))

    return analisi


class Disponibilitat:
    """Memòria cau d'una petició: el context simultani s'aplica després.

    La clau conserva la identitat de la sessió i les dues finestres horàries.
    No barreja el cost mostrat (només vigilància) amb els avisos de l'editor
    (examen i vigilància). Els resultats retornats són còpies pròpies.
    """

    def __init__(self, problema: Problema):
        self.problema = problema
        self._horaris = descongela(problema.horaris_professors)
        self._horaris_norm = {
            professor: {dia: horari_del_dia_normalitzat(hores) for dia, hores in dies.items()}
            for professor, dies in self._horaris.items()
        }
        self._alliberaments = descongela(problema.alliberaments)
        self._taules = problema.nivells_dels_grups()
        self._no_substituir = {normalitzar_text(a) for a in problema.no_substituir if a}
        self._estatica = {}

    def analitza(self, sessio: dict, dia: str, hora: str, data_iso, hores_examen, hores_supervisio, altres=()) -> dict:
        return deepcopy(self.consulta(sessio, dia, hora, data_iso, hores_examen, hores_supervisio, altres))

    def consulta(self, sessio: dict, dia: str, hora: str, data_iso, hores_examen, hores_supervisio, altres=()) -> dict:
        """Vista prestada per puntuar: cap consumidor no n'ha de modificar el contingut.

        `analitza` conserva la còpia profunda per a les sortides editables.
        El context només substitueix la llista d'alliberats de la vista.
        """
        clau = (id(sessio), dia, hora, data_iso, tuple(hores_examen), tuple(hores_supervisio))
        if clau not in self._estatica:
            candidats = []
            analisi = analitzar_disponibilitat_sessio(
                sessio,
                dia,
                hora,
                self._horaris,
                list(self.problema.graella),
                list(self.problema.nivells),
                no_substituir_norm=self._no_substituir,
                hores_override=hores_examen,
                hores_supervisio=hores_supervisio,
                alliberaments_per_nivell=self._alliberaments,
                data_iso=data_iso,
                nivells_dels_grups=self._taules,
                horaris_professors_norm=self._horaris_norm,
                candidats_context=candidats,
            )
            # Conservar la sessió impedeix reutilitzar-ne id dins de la petició.
            self._estatica[clau] = (sessio, analisi, candidats)
        _, base, candidats = self._estatica[clau]
        resultat = base.copy()
        titulars_altres = _titulars_altres_sessions(sessio, list(altres))
        # Els candidats són en l'ordre de les assignacions, també els duplicats.
        resultat["alliberats"] = [
            entrada for ja_alliberat, entrada in candidats if ja_alliberat or entrada["professor"] in titulars_altres
        ]
        return resultat


def analitza_motor(
    problema: Problema, disponible: Disponibilitat, sessio: dict, franja, altres=(), *, copia=True
) -> dict:
    """Finestra de cerca i sortida: examen propi i vigilància independents.

    Es conserva la graella crua del motor, també per decidir si hi és l'inici.
    La normalització interna de l'anàlisi es fa després de tallar la finestra.
    """
    nom = sessio.get("nom")
    supervisio = vigilancia(nom, problema.durades_vigilancia, problema.durada_titular)
    durada = examen_del_problema(nom, problema)
    data_iso = franja.data_iso
    if data_iso is None:
        dates = problema.mapa_dies.get(normalitzar_dia(franja.dia))
        data_iso = dates[0] if isinstance(dates, (list, tuple)) and dates else dates
    consulta = disponible.analitza if copia else disponible.consulta
    return consulta(
        sessio,
        franja.dia,
        franja.hora,
        data_iso,
        hores_ocupades(franja.hora, problema.graella, durada),
        hores_ocupades(franja.hora, problema.graella, supervisio),
        altres,
    )
