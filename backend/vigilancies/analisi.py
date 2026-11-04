"""Regla única de conflictes de vigilàncies. Només analitza, mai no desa."""

from collections import defaultdict

from core.alliberats import sense_classe
from i18n_setup import translate as _
from substitucions.domain import DiaEscolar


def selecciona_problemes(problemes: list[dict], files: list[dict]) -> list[dict]:
    """Analitzar sempre el dia sencer; presentar només els problemes que afecten la tria."""
    ids = {str(v["id"]) for v in files if v.get("id") is not None}
    return [p for p in problemes if not p["files"] or ids.intersection(p["files"])]


def analitza_vigilancies(dia: DiaEscolar) -> list[dict]:
    """Tipus estables, gravetat i cobertura efectiva per a web, revisió i PDF.

    Les absències són per hora. Una cobertura buida, absent, exclosa de
    l'horari, amb classe o ocupada en una altra feina no resol una classe.
    El professor absent es reemplaça a la seva vigilància, i es comprova
    també la disponibilitat del vigilant efectiu.
    """
    resultat = []
    per_hora = defaultdict(list)
    absents = defaultdict(set, {h: set(ps) for h, ps in dia.absents_per_hora.items()})
    classes, cobertures = defaultdict(list), defaultdict(list)
    for sub in dia.files:
        clau = (sub.get("hora", ""), (sub.get("professor_absent") or "").strip())
        if sub.get("tipus_absencia") == "VIGILANCIA":
            classes[clau].append(sub)
        elif sub.get("tipus_absencia") == "VIGILANCIA_ABSENT":
            cobertures[clau].append(sub)
            absents[clau[0]].add(clau[1])

    def nom(valor):
        valor = (valor or "").strip()
        return "" if valor in ("---", "PENDENT") or valor.startswith("-- selecciona") else valor

    def afegeix(tipus, gravetat, vigs, missatge, professor="", grup=None, efectiva=None):
        v = vigs[0] if vigs else {}
        if tipus in ("classe_coberta", "classe_sense_cobertura"):
            for anterior in resultat:
                if (anterior["tipus"], anterior["hora"], anterior["professor"], anterior["grup"]) == (
                    tipus,
                    v.get("hora") or "",
                    professor,
                    grup,
                ):
                    anterior["files"].extend(
                        str(f["id"]) for f in vigs if f.get("id") is not None and str(f["id"]) not in anterior["files"]
                    )
                    return
        resultat.append(
            {
                "tipus": tipus,
                "gravetat": gravetat,
                "hora": v.get("hora") or "",
                "files": [str(v["id"]) for v in vigs if v.get("id") is not None],
                "professor": professor,
                "grup": v.get("grups") or "" if grup is None else grup,
                "aula": v.get("aula") or "",
                "cobertura_efectiva": efectiva,
                "missatge": missatge.removeprefix("ℹ️ "),
            }
        )

    def present(p, hora):
        return p and p not in absents[hora] and p not in dia.baixes

    def classe_pendent(p, hora):
        a = dia.activitat(p, hora)
        return bool(
            a.get("assignatura") and a.get("grup") and not sense_classe(p, a["grup"], dia.alliberats.get(hora, []))
        )

    def cobertura_classe(p, hora):
        a = dia.activitat(p, hora)
        for sub in classes[(hora, p)]:
            if (sub.get("grup") or "") != (a.get("grup") or ""):
                continue
            q = nom(sub.get("substitut"))
            if not present(q, hora) or classe_pendent(q, hora):
                continue
            if any(nom(v.get("vigilant")) == q and v.get("hora") == hora for v in dia.vigilancies):
                continue
            if sum(1 for s in dia.files if s.get("hora") == hora and nom(s.get("substitut")) == q) != 1:
                continue
            return q
        return None

    if dia.vigilancies and dia.horari is None:
        afegeix(
            "horari_no_disponible", "avis", dia.vigilancies, _("⚠️ No s’ha pogut completar la comprovació de l’horari")
        )

    efectius = defaultdict(list)
    for v in dia.vigilancies:
        hora, p, aula = v.get("hora") or "", nom(v.get("vigilant")), nom(v.get("aula"))
        per_hora[hora].append(v)
        if not hora:
            afegeix(
                "sense_hora",
                "important",
                [v],
                _("❌ Vigilància sense hora ({tipus}, {grup})").format(
                    tipus=_("VIGILÀNCIA") if v.get("tipus") == "VIGILÀNCIA" else v.get("tipus") or "",
                    grup=v.get("grups") or "",
                ),
            )
        if not p:
            afegeix(
                "sense_vigilant",
                "important",
                [v],
                _("❌ {hora}: {tipus} sense vigilant assignat").format(
                    hora=hora, tipus=_("VIGILÀNCIA") if v.get("tipus") == "VIGILÀNCIA" else v.get("tipus") or ""
                ),
            )
        if not aula:
            afegeix(
                "sense_aula",
                "important",
                [v],
                _("🏫 {hora}: {tipus} sense aula assignada").format(
                    hora=hora, tipus=_("VIGILÀNCIA") if v.get("tipus") == "VIGILÀNCIA" else v.get("tipus") or ""
                ),
            )
        if not p or not hora:
            continue
        if p in dia.baixes:
            afegeix(
                "vigilant_exclos",
                "important",
                [v],
                _("🔄 {hora}: {vigilant} té una absència coberta però és assignat com a vigilant").format(
                    hora=hora, vigilant=p
                ),
                p,
            )
            continue
        efectiu = p
        if p in absents[hora]:
            compatibles = [
                s
                for s in cobertures[(hora, p)]
                if (not s.get("grup") or s.get("grup") == v.get("grups"))
                and (not s.get("aula") or s.get("aula") == aula)
            ]
            efectiu = next(
                (nom(s.get("substitut")) for s in compatibles if present(nom(s.get("substitut")), hora)), None
            )
            if not efectiu:
                afegeix(
                    "vigilant_absent_sense_cobertura",
                    "important",
                    [v],
                    _("⚠️ {hora}: Vigilant {vigilant} absent sense cobertura").format(hora=hora, vigilant=p),
                    p,
                )
                continue
            afegeix(
                "vigilant_absent_cobert",
                "informacio",
                [v],
                _("ℹ️ {hora}: Vigilant {vigilant} absent (cobert per {substitut})").format(
                    hora=hora, vigilant=p, substitut=efectiu
                ),
                p,
                efectiva=efectiu,
            )
        efectius[(hora, efectiu)].append(v)
        if dia.horari is None:
            continue
        a = dia.activitat(efectiu, hora)
        assig, grup = a.get("assignatura") or "", a.get("grup") or ""
        if classe_pendent(efectiu, hora):
            substitut = cobertura_classe(efectiu, hora)
            if substitut:
                afegeix(
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
                afegeix(
                    "classe_sense_cobertura",
                    "important",
                    [v],
                    _("❌ {hora}: {vigilant} vigila; {assignatura} de {grup} queda sense substitut").format(
                        hora=hora, vigilant=efectiu, assignatura=assig, grup=grup
                    ),
                    efectiu,
                    grup,
                )
        elif (assig or grup) and sense_classe(efectiu, grup, dia.alliberats.get(hora, [])):
            afegeix(
                "alliberat",
                "informacio",
                [v],
                _("ℹ️ {hora}: Vigilant {vigilant} alliberat manualment").format(hora=hora, vigilant=efectiu),
                efectiu,
                grup,
                efectiva=efectiu,
            )
        elif assig and not grup:
            from config.constants import PRIORITATS

            if assig not in PRIORITATS:
                afegeix(
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
        # La mateixa comprovació de jornada a totes les presentacions.
        hores = dia.horari.hores
        primera, ultima = dia.horari.get_jornada_professor(dia.dia, efectiu)
        if hora in hores and primera in hores and ultima in hores:
            if hores.index(hora) < hores.index(primera):
                afegeix(
                    "fora_jornada",
                    "avis",
                    [v],
                    _("🕐 {professor} → arriba abans a {hora} (primera hora: {primera})").format(
                        professor=efectiu, hora=hora, primera=primera
                    ),
                    efectiu,
                    efectiva=efectiu,
                )
            elif hores.index(hora) > hores.index(ultima):
                afegeix(
                    "fora_jornada",
                    "avis",
                    [v],
                    _("🕐 {professor} → queda més estona a {hora} (última hora: {ultima})").format(
                        professor=efectiu, hora=hora, ultima=ultima
                    ),
                    efectiu,
                    efectiva=efectiu,
                )

    for hora, vigs in per_hora.items():
        if not hora:
            continue
        for camp, tipus in [("vigilant", "vigilant_repetit"), ("aula", "aula_repetida")]:
            grups = defaultdict(list)
            for v in vigs:
                valor = nom(v.get(camp))
                if valor and not (camp == "aula" and valor == "ENLLAÇ"):
                    grups[valor].append(v)
            for valor, files in grups.items():
                if len(files) > 1:
                    missatge = (
                        _("🔄 {hora}: {vigilant} assignat {count} vegades com a vigilant").format(
                            hora=hora, vigilant=valor, count=len(files)
                        )
                        if camp == "vigilant"
                        else _("🏫 {hora}: Aula {aula} duplicada").format(hora=hora, aula=valor)
                    )
                    afegeix(tipus, "avis", files, missatge, valor if camp == "vigilant" else "")
    for (hora, p), vigs in efectius.items():
        # Una cobertura de vigilant absent és la seva vigilància, no una segona feina.
        altres = [
            s
            for s in dia.files
            if s.get("hora") == hora and nom(s.get("substitut")) == p and s.get("tipus_absencia") != "VIGILANCIA_ABSENT"
        ]
        if altres:
            afegeix(
                "vigilant_i_substitut",
                "important",
                vigs,
                _("⚠️ {hora}: {professor} és vigilant i substitut alhora").format(hora=hora, professor=p),
                p,
            )
        # Si dues cobertures acaben en el mateix vigilant també hi ha doble feina.
        originals = {nom(v.get("vigilant")) for v in vigs}
        if len(vigs) > 1 and len(originals) > 1:
            afegeix(
                "vigilant_efectiu_repetit",
                "avis",
                vigs,
                _("🔄 {hora}: {vigilant} assignat {count} vegades com a vigilant").format(
                    hora=hora, vigilant=p, count=len(vigs)
                ),
                p,
                efectiva=p,
            )
    ordre = {h: i for i, h in enumerate(dia.horari.hores)} if dia.horari is not None else {}
    return sorted(resultat, key=lambda p: (ordre.get(p["hora"], 999), p["hora"], p["files"], p["tipus"]))
