"""
Assignació automàtica de vigilants. Cada hora es resol sencera, amb totes les
files alhora (assignació òptima): l'ordre de les files no decideix qui va on.

Per a cada parella professor–fila, una puntuació per graons, de més a menys
important (un graó més alt sempre guanya, sumi el que sumi la resta):
  1. files cobertes;
  2. el titular de la fila ENLLAÇ (aula «ENLLAÇ») a la seva fila;
  3. cada titular a una fila de la qual és titular;
  4. qui tenia classe amb el grup (o amb una classe que l'inclou), a la fila;
  5. el nivell: mateix nivell > nivell proper (afinitats, per proximitat) >
     qualsevol alliberat > guàrdia (i, entre guàrdies, la categoria i el pes
     de les prioritats);
  6. l'atzar (uniforme), només per desfer empats.
Així, que un titular de diversos grups vagi al grup on tenia classe, al que
quedaria sense vigilant o a qualsevol si tots queden coberts, surt de la
puntuació sense cap regla a part.

Qui pot vigilar a una hora: qui no és absent, no vigila ja una altra fila i
està alliberat (el seu grup o ell, sense classe) o fa una activitat de les
prioritats sense grup (guàrdia...), sempre que la seva categoria es pugui
assignar automàticament. Les guàrdies només entren si es demanen
(«disponibles»). El titular, a la seva fila, hi va sempre que estigui
alliberat o faci una activitat de les prioritats, sigui quina sigui la
categoria i encara que no es demanin disponibles.

Els grups i els nivells es comparen sempre amb les taules (abreviatures,
grups de cada nivell), mai amb trossos de text.

També hi ha les afinitats de nivells (quins nivells són propers).
"""

import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from repositories import ConfiguracioRepository

VIGILANCIES_AFINITATS_KEY = "vigilancies_afinitats"
AULA_ENLLAC = "ENLLAÇ"


def normalize_vigilancies_afinitats(rows: List[Dict[str, Any]]) -> List[Dict[str, List[str]]]:
    """Normalitza i valida files d'afinitats."""
    normalized: List[Dict[str, List[str]]] = []
    seen_bases = set()
    rows = rows or []

    for row in rows:
        if not isinstance(row, dict):
            continue
        base = str(row.get("base", "")).strip()
        if not base or base in seen_bases:
            continue
        ordre_raw = row.get("ordre", [])
        if isinstance(ordre_raw, str):
            ordre_items = [x.strip() for x in ordre_raw.split(",")]
        elif isinstance(ordre_raw, list):
            ordre_items = [str(x).strip() for x in ordre_raw]
        else:
            ordre_items = []
        ordre = []
        for item in ordre_items:
            if item and item not in ordre:
                ordre.append(item)

        if base not in ordre:
            ordre.insert(0, base)
        if not ordre:
            ordre = [base]

        normalized.append({"base": base, "ordre": ordre})
        seen_bases.add(base)

    return normalized


def get_vigilancies_afinitats(db: Session) -> List[Dict[str, List[str]]]:
    """
    Carrega afinitats de BD (sense fallback hardcoded).
    """
    raw = ConfiguracioRepository.get(db, VIGILANCIES_AFINITATS_KEY)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        normalized = normalize_vigilancies_afinitats(parsed if isinstance(parsed, list) else [])
        return normalized
    except (ValueError, TypeError):
        return []


def save_vigilancies_afinitats(db: Session, rows: List[Dict[str, Any]]) -> List[Dict[str, List[str]]]:
    normalized = normalize_vigilancies_afinitats(rows)
    ConfiguracioRepository.set(
        db,
        VIGILANCIES_AFINITATS_KEY,
        json.dumps(normalized, ensure_ascii=False),
        tipus="json",
        descripcio="Afinitats de grups per autoassignació de vigilàncies",
    )
    return normalized


# ------------------------------------------------------------ titular


def titulars_de(files_config: list, tipus: str, grups: str, aula: str, abreviatures=None, nivells=None):
    """Els titulars possibles d'un examen segons la configuració d'exàmens i,
    si cal, per què cal avisar: (frozenset de titulars, motiu o None).

    - Les files de la mateixa assignatura i el mateix grup; si no n'hi ha cap,
      les dels grups que són dins del grup de l'examen, desfets amb les taules
      (una abreviatura, un nivell, diversos grups: «3-ESO-ABC» → 3-ESO-A...).
    - Si tenen un sol titular, és aquell. Si en tenen diversos, l'aula de
      l'examen tria; si no, tots són candidats (l'assignació òptima en tria un)
      i el motiu és "diversos_titulars".
    - Si l'assignatura té files però cap per al grup: cap titular, motiu
      "cap_fila_grup". Si l'assignatura no en té cap: cap titular, sense motiu.
    """
    de_lassignatura = [f for f in files_config if f.get("assignatura") == tipus]
    if not de_lassignatura:
        return frozenset(), None
    files = [f for f in de_lassignatura if f.get("grup") == grups]
    if not files:
        del_examen = grups_de(grups, abreviatures or {}, nivells)
        files = [
            f
            for f in de_lassignatura
            if (g := grups_de(f.get("grup", ""), abreviatures or {}, nivells)) and g <= del_examen
        ]
    titulars = {f.get("titular") for f in files if f.get("titular")}
    if not titulars:
        return frozenset(), "cap_fila_grup"
    if len(titulars) == 1:
        return frozenset(titulars), None
    de_laula = {f.get("titular") for f in files if f.get("titular") and (f.get("aula") or "") == (aula or "")}
    if len(de_laula) == 1:
        return frozenset(de_laula), None
    return frozenset(de_laula or titulars), "diversos_titulars"


def titular_de(files_config: list, tipus: str, grups: str, aula: str, abreviatures=None, nivells=None) -> Optional[str]:
    """El titular, si n'hi ha un de sol (veure titulars_de)."""
    titulars, _ = titulars_de(files_config, tipus, grups, aula, abreviatures, nivells)
    return next(iter(titulars)) if len(titulars) == 1 else None


def es_enllac(aula: str) -> bool:
    return (aula or "").strip().upper() == AULA_ENLLAC


# ------------------------------------------------------------ grups i nivells


def grups_de(text: str, abreviatures: dict, nivells: dict = None) -> set:
    """Els grups que vol dir un text de grup: una llista separada per comes
    (com a l'XML) i, cadascun, l'abreviatura desfeta (`abreviatures`:
    {abreviatura: [grups]}) i el nivell desfet en els seus grups (`nivells`:
    {nivell: [grups]})."""
    nivells = nivells or {}
    resultat = set()
    for part in (text or "").split(","):
        part = part.strip()
        if part:
            for grup in abreviatures.get(part, [part]):
                resultat.update(nivells.get(grup) or [grup])
    return resultat


@dataclass
class Fila:
    id: str
    grups: set  # els grups de la fila, desfets
    nivell: str
    titulars: frozenset = frozenset()  # els titulars possibles (veure titulars_de)
    enllac: bool = False


@dataclass
class Candidat:
    nom: str
    alliberat: bool  # si no, fa una activitat de les prioritats sense grup (guàrdia...)
    grups_classe: set = field(default_factory=set)  # amb qui tenia classe a l'hora
    nivells: set = field(default_factory=set)  # els nivells d'aquests grups
    preferencia_guardia: int = 0  # entre guàrdies: categoria i pes de les prioritats
    autoassignable: bool = True  # la seva categoria de prioritat; si no, només com a titular


GRAONS = ("coberta", "enllac", "titular", "grup", "nivell", "proximitat", "guardia", "atzar")


def _graons(candidat: Candidat, fila: Fila, propers: dict, amb_guardia: bool, atzar: int):
    """Els valors de cada graó per a una parella, o None si no hi pot anar."""
    es_titular = candidat.nom in fila.titulars
    if not es_titular and (not candidat.autoassignable or not (candidat.alliberat or amb_guardia)):
        return None
    ordre = propers.get(fila.nivell) or []
    if candidat.alliberat and fila.nivell in candidat.nivells:
        nivell, proximitat = 3, 0
    elif candidat.alliberat and any(n in ordre[1:] for n in candidat.nivells):
        nivell = 2
        proximitat = len(ordre) - min(ordre.index(n) for n in candidat.nivells if n in ordre[1:])
    elif candidat.alliberat:
        nivell, proximitat = 1, 0
    else:
        nivell, proximitat = 0, 0
    return (
        1,
        int(es_titular and fila.enllac),
        int(es_titular),
        int(bool(candidat.grups_classe & fila.grups)),
        nivell,
        proximitat,
        0 if candidat.alliberat else candidat.preferencia_guardia,
        atzar,
    )


def assigna_hora(files: list, candidats: list, propers: dict, amb_guardia: bool, rng: random.Random) -> dict:
    """Les files d'una hora i qui les vigila: {fila.id: nom}. `propers`:
    {nivell: [nivell, propers per ordre...]} (les afinitats)."""
    if not files or not candidats:
        return {}
    taula = {}
    for i, fila in enumerate(files):
        for j, candidat in enumerate(candidats):
            g = _graons(candidat, fila, propers, amb_guardia, rng.randrange(1000))
            if g is not None:
                taula[i, j] = g
    if not taula:
        return {}
    # Pes lexicogràfic: cada graó val més que la suma de tots els de sota
    n = len(files)
    maxims = [max(g[k] for g in taula.values()) for k in range(len(GRAONS))]
    bases, base = [], 1
    for k in reversed(range(len(GRAONS))):
        bases.append(base)
        base *= n * maxims[k] + 1
    bases.reverse()
    pesos = [[0] * len(candidats) for _ in files]
    for (i, j), g in taula.items():
        pesos[i][j] = sum(v * b for v, b in zip(g, bases, strict=True))
    triats = assignacio_optima(pesos)
    return {files[i].id: candidats[j].nom for i, j in triats.items() if (i, j) in taula}


# ------------------------------------------------------------ assignació òptima


def assignacio_optima(pesos: list) -> dict:
    """Assignació de pes màxim (algorisme hongarès): `pesos[i][j]` >= 0 és el
    que val posar la columna j a la fila i (0: no hi va). Cada fila, com a
    molt una columna i cada columna, com a molt una fila. Retorna {fila:
    columna} de les parelles amb pes > 0."""
    n = len(pesos)
    if n == 0:
        return {}
    m = len(pesos[0])
    # Columnes de més: cada fila pot quedar sense ningú (pes 0)
    cols = m + n
    maxim = max((p for fila in pesos for p in fila), default=0)
    cost = [[maxim - (pesos[i][j] if j < m else 0) for j in range(cols)] for i in range(n)]
    # e-maxx, filles i columnes des d'1
    u = [0] * (n + 1)
    v = [0] * (cols + 1)
    p = [0] * (cols + 1)
    way = [0] * (cols + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [None] * (cols + 1)
        used = [False] * (cols + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = None
            j1 = 0
            for j in range(1, cols + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if minv[j] is None or cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if delta is None or minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(cols + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                elif minv[j] is not None:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    resultat = {}
    for j in range(1, m + 1):
        if p[j] and pesos[p[j] - 1][j - 1] > 0:
            resultat[p[j] - 1] = j - 1
    return resultat
