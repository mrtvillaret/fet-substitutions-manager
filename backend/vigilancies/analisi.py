"""Regla única de conflictes de vigilàncies. Només analitza, mai no desa."""

from collections import defaultdict

from config import constants
from grups.disponibilitat import sense_classe
from i18n_setup import translate as _
from substitucions.domain import DiaEscolar
from substitucions.files import FilaSubstitucio
from textos import nom_net
from vigilancies.assignacio import es_enllac
from vigilancies.files import FilaVigilancia

type _Cobertures = defaultdict[tuple[str, str], list[FilaSubstitucio]]


def selecciona_problemes(problemes: list[dict], files: list[FilaVigilancia]) -> list[dict]:
    """Analitzar sempre el dia sencer; presentar només els problemes que afecten la tria."""
    ids = {str(v.id) for v in files if v.id is not None}
    return [p for p in problemes if not p["files"] or ids.intersection(p["files"])]


def analitza_vigilancies(dia: DiaEscolar) -> list[dict]:
    """Tipus estables, gravetat i cobertura efectiva per a web, revisió i PDF."""
    resultat: list[dict] = []
    absents, classes, cobertures = _indexa_cobertures(dia)

    if dia.vigilancies and dia.horari is None:
        _afegeix(
            resultat,
            "horari_no_disponible",
            "avis",
            dia.vigilancies,
            _("⚠️ No s’ha pogut completar la comprovació de l’horari"),
        )

    per_hora: defaultdict[str, list[FilaVigilancia]] = defaultdict(list)
    efectius: defaultdict[tuple[str, str], list[FilaVigilancia]] = defaultdict(list)
    for v in dia.vigilancies:
        hora, p, aula = v.hora or "", _nom(v.vigilant), _nom(v.aula)
        per_hora[hora].append(v)
        _comprova_camps_obligatoris(resultat, v, hora, p, aula)
        if not p or not hora:
            continue
        efectiu = _resol_vigilant_efectiu(resultat, dia, absents, cobertures, v, hora, p, aula)
        if not efectiu:
            continue
        efectius[(hora, efectiu)].append(v)
        if dia.horari is None:
            continue
        if efectiu != p:
            _comprova_horari(resultat, dia, v, efectiu)
        _comprova_activitat_i_cobertura(resultat, dia, absents, classes, v, hora, efectiu)
        _comprova_jornada(resultat, dia, v, hora, efectiu)

    _detecta_repeticions(resultat, per_hora)
    _detecta_conflictes_dels_efectius(resultat, dia, efectius)
    ordre = {h: i for i, h in enumerate(dia.horari.hores)} if dia.horari is not None else {}
    return sorted(resultat, key=lambda p: (ordre.get(p["hora"], 999), p["hora"], p["files"], p["tipus"]))


def _indexa_cobertures(dia: DiaEscolar) -> tuple[defaultdict[str, set[str]], _Cobertures, _Cobertures]:
    absents = defaultdict(set, {h: set(ps) for h, ps in dia.absents_per_hora.items()})
    classes: _Cobertures = defaultdict(list)
    cobertures: _Cobertures = defaultdict(list)
    for sub in dia.files:
        clau = (sub.hora, _nom(sub.professor_absent))
        if sub.tipus_absencia == "VIGILANCIA":
            classes[clau].append(sub)
        elif sub.tipus_absencia == "VIGILANCIA_ABSENT":
            cobertures[clau].append(sub)
            absents[clau[0]].add(clau[1])
    return absents, classes, cobertures


def _nom(valor: str | None) -> str:
    return nom_net(valor) or ""


def _afegeix(
    resultat: list[dict],
    tipus: str,
    gravetat: str,
    vigs: list[FilaVigilancia],
    missatge: str,
    professor: str = "",
    grup: str | None = None,
    efectiva: str | None = None,
) -> None:
    v = vigs[0] if vigs else FilaVigilancia()
    if tipus in ("classe_coberta", "classe_sense_cobertura"):
        for anterior in resultat:
            if (anterior["tipus"], anterior["hora"], anterior["professor"], anterior["grup"]) == (
                tipus,
                v.hora or "",
                professor,
                grup,
            ):
                anterior["files"].extend(
                    str(f.id) for f in vigs if f.id is not None and str(f.id) not in anterior["files"]
                )
                return
    resultat.append(
        {
            "tipus": tipus,
            "gravetat": gravetat,
            "hora": v.hora or "",
            "files": [str(v.id) for v in vigs if v.id is not None],
            "professor": professor,
            "grup": v.grups or "" if grup is None else grup,
            "aula": v.aula or "",
            "cobertura_efectiva": efectiva,
            "missatge": missatge.removeprefix("ℹ️ "),
        }
    )


def _comprova_camps_obligatoris(resultat: list[dict], v: FilaVigilancia, hora: str, p: str, aula: str) -> None:
    if hora and p and aula:
        return

    tipus = _("VIGILÀNCIA") if v.tipus == "VIGILÀNCIA" else v.tipus or ""
    if not hora:
        _afegeix(
            resultat,
            "sense_hora",
            "important",
            [v],
            _("❌ Vigilància sense hora ({tipus}, {grup})").format(
                tipus=tipus,
                grup=v.grups or "",
            ),
        )
    if not p:
        _afegeix(
            resultat,
            "sense_vigilant",
            "important",
            [v],
            _("❌ {hora}: {tipus} sense vigilant assignat").format(hora=hora, tipus=tipus),
        )
    if not aula:
        _afegeix(
            resultat,
            "sense_aula",
            "important",
            [v],
            _("🏫 {hora}: {tipus} sense aula assignada").format(hora=hora, tipus=tipus),
        )


def _comprova_horari(resultat: list[dict], dia: DiaEscolar, v: FilaVigilancia, professor: str) -> None:
    if dia.professor_a_horari(professor) is False:
        _afegeix(
            resultat,
            "vigilant_fora_horari",
            "important",
            [v],
            _("❌ {hora}: {vigilant} no és a l’horari d’aquell dia").format(hora=v.hora or "", vigilant=professor),
            professor,
        )


def _present(dia: DiaEscolar, absents: defaultdict[str, set[str]], professor: str, hora: str) -> bool:
    return bool(professor and professor not in absents[hora] and professor not in dia.baixes)


def _resol_vigilant_efectiu(
    resultat: list[dict],
    dia: DiaEscolar,
    absents: defaultdict[str, set[str]],
    cobertures: _Cobertures,
    v: FilaVigilancia,
    hora: str,
    p: str,
    aula: str,
) -> str | None:
    _comprova_horari(resultat, dia, v, p)
    if p in dia.baixes:
        _afegeix(
            resultat,
            "vigilant_exclos",
            "important",
            [v],
            _("🔄 {hora}: {vigilant} té una absència coberta però és assignat com a vigilant").format(
                hora=hora, vigilant=p
            ),
            p,
        )
        return None
    efectiu: str | None = p
    if p in absents[hora]:
        compatibles = [
            s for s in cobertures[(hora, p)] if (not s.grup or s.grup == v.grups) and (not s.aula or s.aula == aula)
        ]
        efectiu = next(
            (_nom(s.substitut) for s in compatibles if _present(dia, absents, _nom(s.substitut), hora)), None
        )
        if not efectiu:
            _afegeix(
                resultat,
                "vigilant_absent_sense_cobertura",
                "important",
                [v],
                _("⚠️ {hora}: Vigilant {vigilant} absent sense cobertura").format(hora=hora, vigilant=p),
                p,
            )
            return None
        _afegeix(
            resultat,
            "vigilant_absent_cobert",
            "informacio",
            [v],
            _("ℹ️ {hora}: Vigilant {vigilant} absent (cobert per {substitut})").format(
                hora=hora, vigilant=p, substitut=efectiu
            ),
            p,
            efectiva=efectiu,
        )
    return efectiu


def _classe_pendent(dia: DiaEscolar, p: str, hora: str) -> bool:
    a = dia.activitat(p, hora)
    return bool(a.get("assignatura") and a.get("grup") and not sense_classe(p, a["grup"], dia.alliberats.get(hora, [])))


def _cobertura_classe(
    dia: DiaEscolar, absents: defaultdict[str, set[str]], classes: _Cobertures, p: str, hora: str
) -> str | None:
    a = dia.activitat(p, hora)
    for sub in classes[(hora, p)]:
        if (sub.grup or "") != (a.get("grup") or ""):
            continue
        q = _nom(sub.substitut)
        if not _present(dia, absents, q, hora) or _classe_pendent(dia, q, hora):
            continue
        if any(_nom(v.vigilant) == q and v.hora == hora for v in dia.vigilancies):
            continue
        if sum(1 for s in dia.files if s.hora == hora and _nom(s.substitut) == q) != 1:
            continue
        return q
    return None


def _comprova_activitat_i_cobertura(
    resultat: list[dict],
    dia: DiaEscolar,
    absents: defaultdict[str, set[str]],
    classes: _Cobertures,
    v: FilaVigilancia,
    hora: str,
    efectiu: str,
) -> None:
    a = dia.activitat(efectiu, hora)
    assig, grup = a.get("assignatura") or "", a.get("grup") or ""
    if _classe_pendent(dia, efectiu, hora):
        substitut = _cobertura_classe(dia, absents, classes, efectiu, hora)
        if substitut:
            _afegeix(
                resultat,
                "classe_coberta",
                "informacio",
                [v],
                _("ℹ️ {hora}: {vigilant} vigila; {assignatura} de {grup} coberta per {substitut}").format(
                    hora=hora, vigilant=efectiu, assignatura=assig, grup=grup, substitut=substitut
                ),
                efectiu,
                grup,
                efectiva=substitut,
            )
        else:
            _afegeix(
                resultat,
                "classe_sense_cobertura",
                "important",
                [v],
                _("❌ {hora}: {vigilant} vigila; {assignatura} de {grup} queda sense substitut").format(
                    hora=hora, vigilant=efectiu, assignatura=assig, grup=grup
                ),
                efectiu,
                grup,
            )
    elif assig and not grup and not sense_classe(efectiu, grup, dia.alliberats.get(hora, [])):
        if assig not in constants.PRIORITATS:
            _afegeix(
                resultat,
                "activitat_sense_grup",
                "informacio",
                [v],
                _("ℹ️ {hora}: Vigilant {vigilant} té una activitat sense grup ({assignatura})").format(
                    hora=hora, vigilant=efectiu, assignatura=assig
                ),
                efectiu,
                grup,
                efectiva=efectiu,
            )


def _comprova_jornada(resultat: list[dict], dia: DiaEscolar, v: FilaVigilancia, hora: str, efectiu: str) -> None:
    # La mateixa comprovació de jornada a totes les presentacions.
    hores = dia.horari.hores
    primera, ultima = dia.horari.get_jornada_professor(dia.nom_del_dia, efectiu)
    if hora in hores and primera in hores and ultima in hores:
        if hores.index(hora) < hores.index(primera):
            _afegeix(
                resultat,
                "fora_jornada",
                "avis",
                [v],
                _("🕐 {hora}: {professor} arriba abans (primera hora: {primera})").format(
                    professor=efectiu, hora=hora, primera=primera
                ),
                efectiu,
                efectiva=efectiu,
            )
        elif hores.index(hora) > hores.index(ultima):
            _afegeix(
                resultat,
                "fora_jornada",
                "avis",
                [v],
                _("🕐 {hora}: {professor} es queda més estona (última hora: {ultima})").format(
                    professor=efectiu, hora=hora, ultima=ultima
                ),
                efectiu,
                efectiva=efectiu,
            )


def _missatge_vigilant_repetit(hora: str, professor: str, count: int) -> str:
    return _("🔄 {hora}: {vigilant} assignat {count} vegades com a vigilant").format(
        hora=hora, vigilant=professor, count=count
    )


def _detecta_repeticions(resultat: list[dict], per_hora: dict[str, list[FilaVigilancia]]) -> None:
    for hora, vigs in per_hora.items():
        if not hora:
            continue
        for camp, tipus in [("vigilant", "vigilant_repetit"), ("aula", "aula_repetida")]:
            grups = defaultdict(list)
            for v in vigs:
                valor = _nom(getattr(v, camp))
                if valor and not (camp == "aula" and es_enllac(valor)):
                    grups[valor].append(v)
            for valor, files in grups.items():
                if len(files) > 1:
                    missatge = (
                        _missatge_vigilant_repetit(hora, valor, len(files))
                        if camp == "vigilant"
                        else _("🏫 {hora}: Aula {aula} duplicada").format(hora=hora, aula=valor)
                    )
                    _afegeix(resultat, tipus, "avis", files, missatge, valor if camp == "vigilant" else "")


def _detecta_conflictes_dels_efectius(
    resultat: list[dict], dia: DiaEscolar, efectius: dict[tuple[str, str], list[FilaVigilancia]]
) -> None:
    for (hora, p), vigs in efectius.items():
        # Una cobertura de vigilant absent és la seva vigilància, no una segona feina.
        altres = [
            s
            for s in dia.files
            if s.hora == hora and _nom(s.substitut) == p and s.tipus_absencia != "VIGILANCIA_ABSENT"
        ]
        if altres:
            _afegeix(
                resultat,
                "vigilant_i_substitut",
                "important",
                vigs,
                _("⚠️ {hora}: {professor} és vigilant i substitut alhora").format(hora=hora, professor=p),
                p,
            )
        # Si dues cobertures acaben en el mateix vigilant també hi ha doble feina.
        originals = {_nom(v.vigilant) for v in vigs}
        if len(vigs) > 1 and len(originals) > 1:
            _afegeix(
                resultat,
                "vigilant_efectiu_repetit",
                "avis",
                vigs,
                _missatge_vigilant_repetit(hora, p, len(vigs)),
                p,
                efectiva=p,
            )
