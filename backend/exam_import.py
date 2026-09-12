"""
Deriva propostes d'assignacions d'exàmens (assignatura/grup/titular/aula) a
partir de l'horari XML ja carregat, per estalviar la introducció manual.

Regles:
- Assignatura: el nom tal com surt al XML, sense cap transformació. No es
  tracta cap codi especial: cada Subject+Grup de l'horari és una possible
  sessió d'examen; ja s'agruparan o es descartaran manualment (o al futur
  planificador) si cal.
- Sense grup, no hi ha proposta: una activitat sense `Students` associats
  (guàrdies, pati, reunions...) no pot ser una sessió d'examen.
- Nivell d'un grup -> el prefix abans del sufix final de lletres ("1-ESO-A" -> "1-ESO")
- Grup "nu" (igual al seu nivell, p.ex. "1-BATX" sense sufix): es proposa tal
  qual (grup=nivell="1-BATX"). No s'intenta endevinar cap grup combinat ja
  configurat (en general, en una importació nova, encara no n'hi ha cap) —
  es deixa editar a mà a la taula de revisió.
"""
import re
from collections import defaultdict, Counter
from typing import Dict, List, Set

# Sufix de subgrup real: només lletres A-D (convenció dels centres), amb o
# sense guionet abans (les convencions de nom varien per centre: "1-ESO-A"
# a un centre, "ESO1A" a un altre). Mai paraules senceres com "BATX".
_GRUP_LLETRES_PATTERN = re.compile(r"^(.*?)-?([A-D]{1,4})$")


def normalitza_assignatura(subject: str) -> str:
    """Retorna l'assignatura tal com surt al XML (només neteja espais)."""
    return (subject or "").strip()


def deriva_nivell(grup: str) -> str:
    """Nivell d'un codi de grup: '1-ESO-A' -> '1-ESO'; '1-BATX' -> '1-BATX'."""
    m = _GRUP_LLETRES_PATTERN.match(grup)
    if m:
        return m.group(1)
    return grup


def generar_propostes(horari) -> List[Dict]:
    """
    horari: GestorHorariWeb ja carregat (horari.horari[dia][hora][professor] = dades)

    Retorna una llista de propostes úniques {assignatura, grup, titular, aula, nivell}.
    """
    combos: Dict[tuple, Counter] = defaultdict(Counter)

    for dia_hores in horari.horari.values():
        for professors_hora in dia_hores.values():
            for professor, dades in professors_hora.items():
                assignatura = normalitza_assignatura(dades.get("assignatura", ""))
                grup = (dades.get("grup") or "").strip()
                if not assignatura or not grup:
                    continue

                nivell = deriva_nivell(grup)
                aula = (dades.get("aula") or "").strip()
                combos[(assignatura, grup, professor, nivell)][aula] += 1

    propostes = []
    for (assignatura, grup, titular, nivell), aules_counter in combos.items():
        aula = aules_counter.most_common(1)[0][0] if aules_counter else ""
        propostes.append({
            "assignatura": assignatura,
            "grup": grup,
            "titular": titular,
            "aula": aula,
            "nivell": nivell,
        })

    propostes.sort(key=lambda p: (p["nivell"], p["assignatura"], p["grup"], p["titular"]))
    return propostes


def nivells_amb_substitucions(db) -> Set[str]:
    """Nivells que realment s'utilitzen al centre (apareixen a l'històric de
    substitucions/vigilàncies), per descartar Infantil/Primària o altres
    etapes que l'XML conté però que no fan servir aquest mòdul."""
    from models import Substitucio, Vigilancia

    grups_historics = set()

    for (grup,) in db.query(Substitucio.grup).filter(
        Substitucio.grup.isnot(None), Substitucio.grup != ""
    ).distinct():
        grups_historics.add(grup)

    for (grups,) in db.query(Vigilancia.grups).filter(
        Vigilancia.grups.isnot(None), Vigilancia.grups != ""
    ).distinct():
        grups_historics.add(grups)

    nivells = set()
    for combinat in grups_historics:
        for part in combinat.split(","):
            part = part.strip()
            if part and part != "-":
                nivells.add(deriva_nivell(part))
    return nivells
