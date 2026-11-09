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
- Grups junts sense abreviatura ("1-BAT-A,1-BAT-B") -> el nivell comú ("1-BAT")
- Grup "nu" (igual al seu nivell, p.ex. "1-BATX" sense sufix): es proposa tal
  qual (grup=nivell="1-BATX"). No s'intenta endevinar cap grup combinat ja
  configurat (en general, en una importació nova, encara no n'hi ha cap) —
  es deixa editar a mà a la taula de revisió.
"""

from collections import Counter, defaultdict

from nivells import deriva_nivell
from substitucions.repositories import SubstitucioRepository
from textos import nom_net
from vigilancies.repositories import VigilanciaRepository

# Sufix de subgrup real: només lletres A-D (convenció dels centres), amb o
# sense guionet abans (les convencions de nom varien per centre: "1-ESO-A"
# a un centre, "ESO1A" a un altre). Mai paraules senceres com "BATX".


def normalitza_assignatura(subject: str) -> str:
    """L'assignatura tal com surt a l'XML, amb el nom net (noms.py)."""
    return nom_net(subject or "")


def generar_propostes(horari) -> list[dict]:
    """
    horari: GestorHorariWeb ja carregat (horari.horari[dia][hora][professor] = dades)

    Retorna una llista de propostes úniques {assignatura, grup, titular, aula, nivell}.
    """
    combos: dict[tuple, Counter] = defaultdict(Counter)

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
        propostes.append(
            {
                "assignatura": assignatura,
                "grup": grup,
                "titular": titular,
                "aula": aula,
                "nivell": nivell,
            }
        )

    propostes.sort(key=lambda p: (p["nivell"], p["assignatura"], p["grup"], p["titular"]))
    return propostes


def nivells_amb_substitucions(db) -> set[str]:
    """Nivells que realment s'utilitzen al centre (apareixen a l'històric de
    substitucions/vigilàncies), per descartar Infantil/Primària o altres
    etapes que l'XML conté però que no fan servir aquest mòdul."""

    grups_historics = SubstitucioRepository.grups_usats(db) | VigilanciaRepository.grups_usats(db)

    nivells = set()
    for combinat in grups_historics:
        for part in combinat.split(","):
            part = part.strip()
            if part and part != "-":
                nivells.add(deriva_nivell(part))
    return nivells
