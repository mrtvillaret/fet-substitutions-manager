"""Precheck i explicació del no viable sobre el problema immutable.

Conserva causes, indicis, ordre i suggeriments del contracte existent.
Només el precheck decideix si s'omet la cerca; el diagnòstic explica un
resultat ja no viable i no transforma les seves heurístiques en proves.
"""

import re as _re
from collections import Counter, defaultdict

from errors_servidor import registra_excepcio
from planificador.compartit.constants import ETIQUETES_CAUSES
from planificador.compartit.franja import Franja, dia_de_prefix, franja
from planificador.compartit.missatges import missatge, unics
from planificador.compartit.normalitzacio import dia_nom_per_horari, normalitzar_text
from planificador.compartit.normalitzacio import normalitzar_dia as _normalitzar_dia
from planificador.motor.avaluador import causa_dura
from planificador.motor.compatibilitat import DIAGNOSTIC, Cami
from planificador.motor.construccio import particio_nova
from planificador.motor.disponibilitat import Disponibilitat, analitza_motor, analitzar_disponibilitat_sessio
from planificador.motor.durades import examen_hi_cap, vigilancia
from planificador.motor.estrategies.backtracking import causa_principal
from planificador.motor.model import descongela
from planificador.motor.regles import (
    _pes_obligatori,
    construeix_regles,
    es_slot_valid_per_nivell,
    percent_assignatura_fix,
    percent_no_mateix_slot,
    recompte_limit_professor,
    sessio_al_grup,
    valor_restriccio,
    viola_restriccio_dia_hora_fixos,
)

_ISO_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Missatge propi d'un examen fixat (dia i/o hora obligatoris) que no té cap
# franja, segons què passa a la franja fixada (revisió 5.1)
MISSATGE_FIXAT = {
    "examen_fixat": "fixat_fora_de_dates",  # la franja fixada no és entre les planificades
    "franja_prohibida": "fixat_a_franja_prohibida",
    "nivell_sense_inici": "fixat_a_hora_sense_inici",
}


def _examens_sense_prou_dates(items: list[tuple[str, set[str]]]) -> tuple[list[str], list[str]] | None:
    """Exàmens que han d'anar en dates diferents i, entre tots, tenen menys dates possibles que
    exàmens (Hall): (noms, dates) o None si es poden repartir. Es busca amb un aparellament
    examen → data; si n'hi ha un sense data, els exàmens que s'hi poden arribar per camins
    alternats són el conjunt bloquejat. Els que no tenen cap data s'expliquen per altres causes."""
    items = [(nom, dates) for nom, dates in items if dates]
    data_de: dict[int, str] = {}
    examen_de: dict[str, int] = {}

    def aparella(i: int, vistes: set[str]) -> bool:
        for data in sorted(items[i][1]):
            if data in vistes:
                continue
            vistes.add(data)
            if data not in examen_de or aparella(examen_de[data], vistes):
                data_de[i], examen_de[data] = data, i
                return True
        return False

    for i in range(len(items)):
        if not aparella(i, set()):
            # Els exàmens que arriben a i per camins alternats (data → examen que la té)
            conjunt, pendents = {i}, [i]
            while pendents:
                for data in items[pendents.pop()][1]:
                    j = examen_de.get(data)
                    if j is not None and j not in conjunt:
                        conjunt.add(j)
                        pendents.append(j)
            ordre = sorted(conjunt)
            return [items[j][0] for j in ordre], sorted(set().union(*(items[j][1] for j in ordre)))
    return None


def _es_data_iso(s: str) -> bool:
    return bool(_ISO_RE.match(s)) if s else False


def _sessio_a_diccionari(sessio) -> dict:
    if isinstance(sessio, dict):
        return {
            "nom": sessio.get("nom", ""),
            "nom_base": sessio.get("nom_base", ""),
            "curs": sessio.get("curs"),
            "examens": sessio.get("examens", []),
        }
    return {
        "nom": getattr(sessio, "nom", ""),
        "nom_base": getattr(sessio, "nom_base", ""),
        "curs": getattr(sessio, "curs", None),
        "examens": getattr(sessio, "examens", []),
    }


def _etiqueta_item(item: dict) -> str:
    sessions = item.get("sessions") or []
    noms = [_sessio_a_diccionari(s).get("nom") for s in sessions]
    noms = [n for n in noms if n]
    return " + ".join(noms) if noms else item.get("nom") or ""


class DiagnosticIncompatibilitats:
    """
    Analitza per què un motor no pot generar un horari complet.

    Ús:
        diag = DiagnosticIncompatibilitats(
            restriccions, dies_efectius, hores_examen, nivells_actius
        )
        missatges = diag.executa(items)
    """

    def __init__(
        self,
        restriccions: dict,
        dies_efectius: list[tuple[str, str]],  # [(dia_nom, prefix_data)]
        hores_examen: list[str],
        nivells_actius: list[str],
        analitza=None,
    ):
        """`analitza(sessio, dia, hora, data_iso)` és l'anàlisi de disponibilitat
        del motor: només es fa servir si hi ha professors amb horari estricte,
        perquè el motor de restriccions els pugui comprovar."""
        self.analitza = analitza
        self.restriccions = restriccions
        self.dies_efectius = dies_efectius  # [(dia_nom, prefix)]
        self.hores_examen = list(hores_examen or [])
        self.nivells_actius = list(nivells_actius or [])
        self.regles = construeix_regles(restriccions)
        estrictes = restriccions.get("restriccions_dures", {}).get("professors_horari_estricte", [])
        self.professors_estrictes = (
            [k for k in estrictes if not k.startswith("_")] if isinstance(estrictes, dict) else list(estrictes or [])
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def executa(self, items: list[dict]) -> list[dict]:
        """
        Retorna una llista de missatges d'incompatibilitat útils.

        `items` és la llista retornada per gen.preparar_particio_nivells().
        Cada item té: {'sessions': [...], 'nom': str, 'curs': str, ...}
        """
        if not items:
            return []

        # Calcular dates viables per ítem (sense context d'altres ítems)
        # Per examen (id de l'ítem), no per nom: dos exàmens amb el mateix nom
        # es trepitjaven i el que quedava fora podia no sortir
        dates_per_item: dict[int, set[str]] = {}
        causa_per_item: dict[int, str] = {}
        for item in items:
            dates, causa = self._dates_viables(item)
            dates_per_item[id(item)] = dates
            if not dates:
                causa_per_item[id(item)] = causa

        missatges: list[dict] = []

        def afegeix(msg: dict):
            if msg not in missatges:
                missatges.append(msg)

        # 1. Ítems sense cap franja viable — agrupar per nivell+causa (evita 19 línies iguals)

        sense_slot_per_nivell_causa: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for item in items:
            etiqueta = _etiqueta_item(item)
            if not dates_per_item[id(item)]:
                causa = causa_per_item.get(id(item), "desconeguda")
                fixat = self._missatge_fixat(item, causa)
                if fixat:
                    afegeix(fixat)
                    continue
                sessions = item.get("sessions") or []
                nivell = item.get("curs") or (_sessio_a_diccionari(sessions[0]).get("curs") if sessions else None) or ""
                sense_slot_per_nivell_causa[nivell][causa].append(etiqueta)

        for nivell, per_causa in sorted(sense_slot_per_nivell_causa.items()):
            for causa, etiquetes in sorted(per_causa.items(), key=lambda item: ETIQUETES_CAUSES.get(item[0], item[0])):
                n = len(etiquetes)
                if n == 1:
                    afegeix(missatge("examen_sense_hora_causa", nom=etiquetes[0], causa=causa))
                else:
                    exemple = etiquetes[0].split(" + ")[0]  # Primer nom del primer ítem
                    afegeix(missatge("examens_sense_hora_causa", nivell=nivell, count=n, causa=causa, nom=exemple))

        # 2. Restriccions no_mateix_dia: parelles atrapades i sobrecàrrega per grup
        self._comprova_no_mateix_dia(items, dates_per_item, afegeix)

        # 3. Límit d'exàmens per professor obligatori: més exàmens que no poden
        # anar fora dels dies restringits que el màxim
        self._comprova_limit_professor(items, dates_per_item, afegeix)

        slots_per_item = {id(item): self._slots_viables(item) for item in items}

        # 4. Restriccions no_mateix_slot: més ítems incompatibles que hores possibles
        self._comprova_no_mateix_slot(items, slots_per_item, afegeix)

        # 5. Capacitat genèrica per nivell (sense restricció específica)
        self._comprova_capacitat(items, slots_per_item, afegeix)

        return missatges

    # ------------------------------------------------------------------
    # Funcions auxiliars privades
    # ------------------------------------------------------------------

    def _viola(self, sessio, dia_nom: str, hora: str, prefix: str):
        """La restricció dura que impedeix posar la sessió a la franja, sense
        context d'altres exàmens (dia_sessions=None: ni el límit per
        professor ni la preferència de dia, que es comproven a part). Amb
        professors d'horari estricte, també els seus (cal l'anàlisi)."""
        s_dict = _sessio_a_diccionari(sessio)
        analisi = None
        if self.analitza and self.professors_estrictes:
            analisi = self.analitza(
                sessio if isinstance(sessio, dict) else s_dict, dia_nom, hora, prefix if _es_data_iso(prefix) else None
            )
        ubicacio = Franja(f"{prefix}_{hora}", prefix, dia_nom, prefix if _es_data_iso(prefix) else None, hora)
        return causa_dura(s_dict, ubicacio, self.regles, self.nivells_actius, analisi=analisi, politiques=DIAGNOSTIC)

    def _slots_viables(self, item: dict) -> set[str]:
        """Les hores (prefix_hora) on l'ítem es pot col·locar sense context
        d'altres ítems."""
        sessions = item.get("sessions") or []
        slots: set[str] = set()
        for dia_nom, prefix in self.dies_efectius:
            for hora in self.hores_examen:
                if not any(self._viola(s, dia_nom, hora, prefix) for s in sessions):
                    slots.add(f"{prefix}_{hora}")
        return slots

    def _dates_viables(self, item: dict) -> tuple[set[str], str]:
        """
        Retorna (dates_on_hi_ha_slot_valid, causa_principal_si_cap_data).

        Comprova cada (dia, hora) amb causa_dura() sense context
        d'altres ítems (sessions_dia=[], sessions_slot=[], dia_sessions=None).
        La causa és la que bloqueja més franges, i «examen fixat» només si no
        n'hi ha cap altra (`causa_principal`): d'un examen fixat interessa què
        passa a la seva franja.
        """
        sessions = item.get("sessions") or []
        dates: set[str] = set()
        causa_counts: Counter = Counter()

        for dia_nom, prefix in self.dies_efectius:
            for hora in self.hores_examen:
                ok = True
                for sessio in sessions:
                    violacio = self._viola(sessio, dia_nom, hora, prefix)
                    if violacio:
                        causa_counts[violacio.clau] += 1
                        ok = False
                        break
                if ok:
                    dates.add(prefix)
                    break  # Una hora confirmada per aquesta data és suficient

        if dates:
            return dates, ""

        return dates, causa_principal(causa_counts) or "desconeguda"

    def _missatge_fixat(self, item: dict, causa: str) -> dict | None:
        """Per a un examen amb dia i/o hora fixats (obligatoris) que no té cap
        franja: què passa a la franja fixada. Sense pin, o amb una altra
        causa (p. ex. l'horari estricte d'un professor), None: surt el
        missatge general amb la causa."""
        codi = MISSATGE_FIXAT.get(causa)
        if not codi:
            return None
        dures = self.restriccions.get("restriccions_dures", {})
        dies_fixos = {k: v for k, v in (dures.get("assignatures_dia_fix") or {}).items() if not k.startswith("_")}
        hores_fixes = {k: v for k, v in (dures.get("assignatures_hora_fix") or {}).items() if not k.startswith("_")}
        for sessio in item.get("sessions") or []:
            s_dict = _sessio_a_diccionari(sessio)
            dia = valor_restriccio(dies_fixos, s_dict)
            dia = dia.get("data") if isinstance(dia, dict) else dia  # com a _comprova_no_mateix_dia
            hora = valor_restriccio(hores_fixes, s_dict)
            if not (dia or hora) or percent_assignatura_fix(s_dict, dures) < 100:
                continue
            params = {"nom": s_dict.get("nom") or _etiqueta_item(item), "dia": str(dia or ""), "hora": str(hora or "")}
            if causa == "nivell_sense_inici":
                params["nivell"] = s_dict.get("curs") or item.get("curs") or ""
            return missatge(codi, **params)
        return None

    def _comprova_no_mateix_dia(self, items: list[dict], dates_per_item: dict[int, set[str]], afegeix) -> None:
        """
        Detecta problemes amb restriccions 'no_mateix_dia':
        - Parelles d'ítems que no es poden separar en dies distints
        - Grups on el nombre d'ítems supera el nombre de dies disponibles
        """

        dures = self.restriccions.get("restriccions_dures", {})
        no_mateix_dia_cfg = dures.get("no_mateix_dia", [])
        if not no_mateix_dia_cfg:
            return

        # Mapa dia_fix per assignatura (valor pot ser data ISO o nom de dia)
        dia_fix_cfg: dict[str, str] = {}
        dies_fixats_originals = dures.get("assignatures_dia_fix") or {}
        if isinstance(dies_fixats_originals, dict):
            for k, v in dies_fixats_originals.items():
                if k.startswith("_"):
                    continue
                valor_data = v.get("data") if isinstance(v, dict) else v
                if isinstance(valor_data, str) and valor_data:
                    dia_fix_cfg[k] = valor_data

        n_dies = len(self.dies_efectius)

        for idx, restriccio in enumerate(no_mateix_dia_cfg, start=1):
            if isinstance(restriccio, dict):
                assignatures = restriccio.get("assignatures", [])
                pes = restriccio.get("pes", 100)
            else:
                assignatures = list(restriccio)
                pes = 100
            if not _pes_obligatori(pes):
                continue

            referencia = {"index": idx, "assignatures": assignatures}

            # Trobar ítems del grup
            items_grup: list[tuple[str, set[str]]] = []
            for item in items:
                for s in item.get("sessions") or []:
                    if sessio_al_grup(_sessio_a_diccionari(s), assignatures):
                        items_grup.append((_etiqueta_item(item), dates_per_item[id(item)]))
                        break

            if len(items_grup) < 2:
                continue

            n_items_grup = len(items_grup)

            # Detecció directa: ítems del grup amb dia_fix al mateix dia
            # (funciona fins i tot quan dates_per_item és buit per alliberaments)
            fixes_per_label: dict[str, str] = {}
            for item in items:
                for s in item.get("sessions") or []:
                    s_dict = _sessio_a_diccionari(s)
                    if not sessio_al_grup(s_dict, assignatures):
                        continue
                    nom = s_dict.get("nom") or s_dict.get("nom_base") or ""
                    nom_base = s_dict.get("nom_base") or ""
                    data_fixada = dia_fix_cfg.get(nom) or dia_fix_cfg.get(nom_base)
                    if data_fixada:
                        etiqueta = _etiqueta_item(item)
                        fixes_per_label[etiqueta] = data_fixada
                    break

            per_data: dict[str, list[str]] = defaultdict(list)
            for etiqueta, data_fixada in fixes_per_label.items():
                per_data[data_fixada].append(etiqueta)
            for data_fixada, en_conflicte in per_data.items():
                if len(en_conflicte) >= 2:
                    afegeix(missatge("fixats_mateix_dia", **referencia, noms=en_conflicte, dia=data_fixada))

            # Detectar sobrecàrrega: grup té més ítems que dies disponibles
            if n_items_grup > n_dies:
                afegeix(missatge("dies_insuficients", **referencia, count=n_items_grup, dies=n_dies))
                continue  # Amb això ja n'hi ha prou

            # Exàmens que, entre tots, tenen menys dates possibles que exàmens: demostra que no
            # Hi caben. Abans es mirava per parelles i sortia també quan es podien repartir.
            bloquejats = _examens_sense_prou_dates(items_grup)
            if bloquejats:
                noms, dates = bloquejats
                afegeix(missatge("dates_insuficients_examens", **referencia, noms=noms, dies=", ".join(dates)))

    def _comprova_limit_professor(self, items: list[dict], dates_per_item: dict[int, set[str]], afegeix) -> None:
        """Límit d'exàmens per professor obligatori (pes >= 100, revisió 5.2):
        els exàmens del professor (de les assignatures del límit) que només
        tenen dates possibles en dies restringits hi aniran per força; si en
        són més que el màxim, no hi ha horari. Es compten amb la mateixa regla
        que el motor i el cost (`recompte_limit_professor`). El check_hard del
        diagnòstic no ho pot veure: va sense context d'altres exàmens."""
        limits = self.restriccions.get("restriccions_dures", {}).get("professors_limit_dies_especifics") or {}
        if not isinstance(limits, dict):
            return
        dia_de = {prefix: dia for dia, prefix in self.dies_efectius}
        for professor, cfg in limits.items():
            if str(professor).startswith("_") or not isinstance(cfg, dict) or cfg.get("max_examens") is None:
                continue
            if not _pes_obligatori(cfg.get("pes_penalitzacio", 0)):
                continue
            restringits = {_normalitzar_dia(d) for d in cfg.get("dies_restringits", [])}
            # Una data candidata compta si és del límit per la seva data o pel nom del dia
            forcades: dict[str, list[dict]] = defaultdict(list)  # data → sessions que hi aniran per força
            noms: list[str] = []
            for item in items:
                dates = dates_per_item[id(item)]
                if not dates:
                    continue  # sense cap data ja surt com a «sense cap hora»
                if any(p not in restringits and dia_nom_per_horari(dia_de.get(p, p)) not in restringits for p in dates):
                    continue  # té alguna data fora dels dies restringits
                sessions = [_sessio_a_diccionari(s) for s in item.get("sessions") or []]
                if not recompte_limit_professor(professor, cfg, {}, sessions).examens:
                    continue  # no és del professor (o no és de les assignatures del límit)
                forcades[min(dates)].extend(sessions)
                noms.append(_etiqueta_item(item))
            recompte = recompte_limit_professor(professor, cfg, forcades)
            if recompte.excedent:
                afegeix(
                    missatge(
                        "limit_professor_insuficient",
                        professor=professor,
                        max=int(cfg["max_examens"]),
                        count=recompte.examens,
                        noms=noms,
                        dies=", ".join(cfg.get("dies_restringits", [])),
                    )
                )

    def _comprova_no_mateix_slot(self, items: list[dict], slots_per_item: dict[int, set[str]], afegeix) -> None:
        """Detecta grups no_mateix_slot que no hi caben: dos ítems limitats a
        la mateixa hora única, o més ítems que hores possibles entre tots."""
        dures = self.restriccions.get("restriccions_dures", {})
        grups = dures.get("no_mateix_slot", {})
        if not grups or not isinstance(grups, dict):
            return

        for grup_nom, grup_val in grups.items():
            if grup_nom.startswith("_"):
                continue
            assignatures = grup_val if isinstance(grup_val, list) else grup_val.get("assignatures", [])
            # El pes real del grup (`_pes_<grup>` o «pes»): un de tou no fa inviable res.
            if percent_no_mateix_slot(self.restriccions, grup_nom) < 100:
                continue

            referencia = {"grup": grup_nom, "assignatures": assignatures}

            # Els ítems sense cap hora possible ja surten com a «sense cap franja»
            items_grup: list[tuple[str, set[str]]] = []
            for item in items:
                if any(sessio_al_grup(_sessio_a_diccionari(s), assignatures) for s in (item.get("sessions") or [])):
                    slots = slots_per_item[id(item)]
                    if slots:
                        items_grup.append((_etiqueta_item(item), slots))

            if len(items_grup) < 2:
                continue

            parelles = False
            for i in range(len(items_grup)):
                etiqueta_a, slots_a = items_grup[i]
                for j in range(i + 1, len(items_grup)):
                    etiqueta_b, slots_b = items_grup[j]
                    if len(slots_a) == 1 and slots_a == slots_b:
                        parelles = True
                        afegeix(missatge("parella_mateixa_hora", **referencia, nom=etiqueta_a, altre=etiqueta_b))

            # Si no hi ha cap parella atrapada, pot ser que no hi càpiguen tots
            hores_conjunt = set().union(*(slots for _, slots in items_grup))
            if not parelles and len(items_grup) > len(hores_conjunt):
                afegeix(missatge("hores_insuficients", **referencia, count=len(items_grup), hores=len(hores_conjunt)))

    def _comprova_capacitat(self, items: list[dict], slots_per_item: dict[int, set[str]], afegeix) -> None:
        """Detecta nivells amb més ítems que hores possibles (la unió de les
        de tots els ítems del nivell). Exclou els ítems sense cap hora, que ja
        surten per separat."""

        items_per_nivell: dict[str, int] = defaultdict(int)
        slots_per_nivell: dict[str, set[str]] = defaultdict(set)

        for item in items:
            sessions = item.get("sessions") or []
            nivell = item.get("curs") or (_sessio_a_diccionari(sessions[0]).get("curs") if sessions else None)
            if not nivell:
                continue
            slots = slots_per_item[id(item)]
            if not slots:
                continue  # Ja reportat com "sense cap franja" — no comptar aquí
            items_per_nivell[nivell] += 1
            slots_per_nivell[nivell].update(slots)

        for nivell, count in items_per_nivell.items():
            slots = slots_per_nivell[nivell]
            if count > len(slots):
                n_dates = len({slot.rsplit("_", 1)[0] for slot in slots})
                afegeix(missatge("capacitat_nivell_dates", nivell=nivell, count=count, hores=len(slots), dies=n_dates))


# ------------------------------------------------------------------
# Funció d'utilitat per construir dies_efectius des de dies_utilitzar
# ------------------------------------------------------------------


def construir_dies_efectius(
    dies_utilitzar: list[str],
    dia_a_data_iso: dict | None = None,
) -> list[tuple[str, str]]:
    """
    Converteix la llista de dies_utilitzar en parelles (dia_nom, prefix).
    Suporta tant dates ISO com noms de dia.

    Per als noms de dia, expan la llista completa de dates ISO (dia_a_data_iso pot
    tenir llistes per suportar múltiples ocurrències del mateix dia de la setmana).
    Així el diagnòstic comprova TOTES les dates, igual que el motor.
    """
    resultat: list[tuple[str, str]] = []
    for d in dies_utilitzar or []:
        if _es_data_iso(d):
            dia_nom, iso = dia_de_prefix(d)
            if iso:
                resultat.append((dia_nom, iso))
        else:
            _map = dia_a_data_iso or {}
            iso = _map.get(_normalitzar_dia(d)) or _map.get(d)
            if isinstance(iso, list):
                # Expandir totes les dates (no agafar només la primera)
                for iso_date in iso:
                    if isinstance(iso_date, str) and iso_date:
                        resultat.append((d, iso_date))
                if not iso:
                    resultat.append((d, d))
            elif isinstance(iso, str) and iso:
                resultat.append((d, iso))
            else:
                resultat.append((d, d))
    return resultat


def identifica_sessions_no_collocades(horari: dict, sessions_per_nivell: dict) -> list[dict]:
    """
    Quan DiagnosticIncompatibilitats no detecta incompatibilitats estructurals,
    identifica quines sessions no s'han col·locat.

    Estratègia 1 (si hi ha resultat parcial): compara sessions_per_nivell amb
    l'horari parcial usant índexs per-curs, evitant contaminació creuada
    (ex: FILOSOFIA 1-BATX col·locat no ha de marcar FILOSOFIA 2-BATX com a col·locat).

    Fallback: usa recompte_nivells del metadata (cobreix dies=[] i sessions no
    identificades per nom).
    """
    te_parcial = bool(horari.get("dies"))

    manquen_per_nivell: dict = defaultdict(list)

    # Estratègia 1: comparació per-curs
    if te_parcial and sessions_per_nivell:
        noms_per_curs: dict = defaultdict(set)
        for dia in horari.get("dies") or []:
            for slot in dia.get("sessions", []):
                for sess in slot.get("sessions_simultanees", []):
                    curs = sess.get("curs") or ""
                    nom = sess.get("nom") or ""
                    nom_base = sess.get("nom_base") or ""
                    if nom:
                        noms_per_curs[curs].add(nom)
                    if nom_base:
                        noms_per_curs[curs].add(nom_base)

        for nivell, sessions in sessions_per_nivell.items():
            collocats = noms_per_curs.get(nivell, set())
            for s in sessions or []:
                nom = (s.get("nom") if isinstance(s, dict) else getattr(s, "nom", "")) or ""
                nom_base = (s.get("nom_base") if isinstance(s, dict) else getattr(s, "nom_base", "")) or ""
                if nom and nom not in collocats and (not nom_base or nom_base not in collocats):
                    manquen_per_nivell[nivell].append(nom)

    # Reserva: recompte_nivells (dies=[] o sessions no identificades per nom)
    if not manquen_per_nivell:
        recompte = (horari.get("metadata") or {}).get("recompte_nivells") or {}
        for niv, info in sorted(recompte.items()):
            p = (info or {}).get("pendents", 0)
            if p > 0:
                e = (info or {}).get("esperats", 0)
                c = (info or {}).get("collocats", 0)
                manquen_per_nivell[niv] = [f"\x00RECOMPTE\x00{p}\x00{e}\x00{c}"]
        if not manquen_per_nivell:
            return []

    resultat = []
    for nivell, manquen in sorted(manquen_per_nivell.items()):
        manquen_unics = list(dict.fromkeys(manquen))
        # Missatge de reserva (recompte per nivell)
        if len(manquen_unics) == 1 and manquen_unics[0].startswith("\x00RECOMPTE\x00"):
            _, _, p_s, e_s, c_s = manquen_unics[0].split("\x00")
            p, e, c = int(p_s), int(e_s), int(c_s)
            if c == 0:
                resultat.append(missatge("nivell_cap_collocat", nivell=nivell, count=p))
            else:
                resultat.append(missatge("nivell_pendents", nivell=nivell, count=p, collocats=c, esperats=e))
        elif len(manquen_unics) == 1:
            resultat.append(missatge("examen_pendent", nom=manquen_unics[0], nivell=nivell))
        else:
            exemple = manquen_unics[0]
            altres = len(manquen_unics) - 1
            resultat.append(missatge("examens_pendents_nivell", nivell=nivell, nom=exemple, count=altres))
    return resultat


def afegeix_recompte_nivells(horari: dict, sessions_per_nivell: dict) -> None:
    """
    Afegeix al metadata un recompte d'items col·locats per nivell i alerta si en falten.
    """
    metadata = horari.setdefault("metadata", {})

    esperats = {nivell: len(llista or []) for nivell, llista in (sessions_per_nivell or {}).items()}
    vistos_per_nivell = defaultdict(set)
    for dia in horari.get("dies", []):
        for slot in dia.get("sessions", []):
            for sessio in slot.get("sessions_simultanees", []):
                nivell = sessio.get("curs")
                if not nivell:
                    continue
                key = (sessio.get("id") or sessio.get("nom"), nivell)
                vistos_per_nivell[nivell].add(key)

    recompte = {}
    incomplets = []
    for nivell, total in esperats.items():
        collocats = len(vistos_per_nivell.get(nivell, set()))
        pendents = max(0, total - collocats)
        recompte[nivell] = {
            "esperats": total,
            "collocats": collocats,
            "pendents": pendents,
        }
        if pendents > 0:
            incomplets.append((nivell, pendents, total))

    metadata["recompte_nivells"] = recompte
    if incomplets:
        logs = metadata.setdefault("logs", [])
        for nivell, pendents, total in incomplets:
            logs.append(missatge("nivell_incomplet", nivell=nivell, collocats=total - pendents, esperats=total))


def explicacio_no_disponible(meta: dict) -> None:
    """No s'ha pogut preparar (tota) l'explicació de per què no és viable: la
    generació continua, i la resposta ho diu amb la referència del registre
    (la pantalla en mostra l'avís). Es crida des d'un `except`."""
    ref = registra_excepcio("No s'ha pogut preparar l'explicació de l'horari no viable")
    meta.setdefault("explicacio_no_disponible", {"ref": ref})


class Diagnostic:
    def __init__(self, problema, politiques):
        self.problema = problema
        self.politiques = politiques
        self.hores_examen = list(problema.hores_inici)
        self.sessions_per_nivell = {
            nivell: [e.a_diccionari() for e in problema.examens if e.curs == nivell] for nivell in problema.nivells
        }
        self.disponibilitat = Disponibilitat(problema)

    def preparar_particio_nivells(self, slots_disponibles):
        # El precheck i el diagnòstic del motor antic sempre criden la partició
        # nova de la base, també quan després genera el recuit.
        return [
            descongela(it.dades)
            for it in particio_nova(self.problema.examens, self.problema.regles, self.problema.nivells)
        ]

    def analitzar_disponibilitat_sessio(self, sessio, dia, hora, sessions_al_slot=None, data_iso=None):
        if self.politiques.cami == Cami.RECUIT:
            # El diagnòstic del recuit només analitza vigilància; normalitza
            # la graella abans de tallar, com la funció del core antic.
            return analitzar_disponibilitat_sessio(
                sessio,
                dia,
                hora,
                descongela(self.problema.horaris_professors),
                list(self.problema.graella),
                list(self.problema.nivells),
                durada_titular=vigilancia(
                    sessio.get("nom"), self.problema.durades_vigilancia, self.problema.durada_titular
                ),
                no_substituir_norm={normalitzar_text(a) for a in self.problema.no_substituir if a},
                sessions_al_slot=sessions_al_slot,
                alliberaments_per_nivell=descongela(self.problema.alliberaments),
                data_iso=data_iso,
                nivells_dels_grups=self.problema.nivells_dels_grups(),
            )
        return analitza_motor(
            self.problema, self.disponibilitat, sessio, franja(f"{data_iso or dia}_{hora}"), sessions_al_slot or ()
        )

    def precheck(self, pla):
        return self._precheck(self.problema.regles.a_diccionari(), pla.dies, pla.nivells, pla.dates)

    def marca_pendents(self, horari):
        afegeix_recompte_nivells(horari, self.sessions_per_nivell)
        pendents = sum(i["pendents"] for i in horari["metadata"]["recompte_nivells"].values())
        if pendents:
            meta = horari["metadata"]
            meta.setdefault("logs", []).append(missatge("sessions_pendents", count=pendents))
            if meta.get("viable", True):
                meta["viable"] = False
                meta["error"] = missatge("examens_pendents")

    def incompatibilitats(self, pla):
        if not self.hores_examen or not pla.dies:
            return []
        dies = construir_dies_efectius(pla.dies, pla.dia_a_data_iso)
        if not dies:
            return []
        items = self.preparar_particio_nivells(max(1, len(dies) * max(1, len(self.hores_examen))))
        return DiagnosticIncompatibilitats(
            self.problema.regles.a_diccionari(),
            dies,
            self.hores_examen,
            pla.nivells or [],
            analitza=lambda sessio, dia, hora, data_iso: self.analitzar_disponibilitat_sessio(
                sessio, dia, hora, sessions_al_slot=None, data_iso=data_iso
            ),
        ).executa(items)

    def explica_no_viable(self, horari, pla, causes, del_precheck=False):
        meta = horari["metadata"]
        error = meta.get("error", missatge("examens_pendents"))
        try:
            diagnostic = self.incompatibilitats(pla)
        except Exception:
            explicacio_no_disponible(meta)
            diagnostic = []
        if diagnostic and del_precheck:
            incompat = diagnostic
        else:
            del_motor = meta.get("incompatibilitats") or causes
            if not del_motor:
                try:
                    del_motor = identifica_sessions_no_collocades(horari, self.sessions_per_nivell)
                except Exception:
                    explicacio_no_disponible(meta)
                    del_motor = []
            incompat = unics(diagnostic + list(del_motor))
        if meta.get("motiu_aturada"):
            incompat = unics([error] + incompat)
        if incompat:
            meta["incompatibilitats"] = incompat
        meta["logs"] = unics(pla.cfg.avisos(pla.nivells) + meta.get("logs", []) + [error])

    def _precheck(
        self,
        restriccions: dict,
        dies_utilitzar: list[str],
        nivells_actius: list[str],
        selected_dates: list[str] = None,
    ) -> list[dict]:
        """
        Precheck ràpid i segur (sense heurístiques):
          1) Capacitat per nivell (items <= slots físics disponibles)
          2) Cada ítem té almenys un slot possible
          3) Per nivell, unió de slots possibles >= nombre d'items
        Si falla, l'error arriba a qui el crida (generacio.py genera igualment).
        """

        hores_examen = list(self.hores_examen)
        if not dies_utilitzar or not hores_examen:
            return []

        # Llista efectiva de (dia_nom, sk_prefix) — usa dates reals si disponibles
        if selected_dates:
            dies_efectius = []
            for prefix in sorted(selected_dates):
                dia_nom, iso = dia_de_prefix(prefix)
                if iso:
                    dies_efectius.append((dia_nom, iso))
        else:
            dies_efectius = [(d, d) for d in dies_utilitzar]

        slots_disponibles = len(dies_efectius) * len(hores_examen)
        items = self.preparar_particio_nivells(slots_disponibles=max(1, slots_disponibles)) or []

        if not items:
            sessions_per_nivell = self.sessions_per_nivell
            for nivell in nivells_actius or []:
                sessions = sessions_per_nivell.get(nivell) or []
                for s in sessions:
                    items.append(
                        {
                            "curs": nivell,
                            "sessions": [s],
                            "nom": _sessio_a_diccionari(s).get("nom"),
                        }
                    )

        if not items:
            return []

        def _hi_cap(sessions, hora: str) -> bool:
            # La durada de cada examen (no una durada per nivell).
            return all(examen_hi_cap(_sessio_a_diccionari(s).get("nom"), hora, self.problema) for s in sessions)

        nivells_items = set()
        sessions_del_nivell = defaultdict(list)
        for item in items:
            sessions = item.get("sessions") or []
            nivell = None
            if item.get("curs"):
                nivell = item.get("curs")
            elif sessions:
                nivell = _sessio_a_diccionari(sessions[0]).get("curs")
            if nivell:
                nivells_items.add(nivell)
                sessions_del_nivell[nivell].extend(sessions)

        # Slots físics per nivell: només inici d'examen vàlid per durada + restricció franges_valids_per_nivell.
        slots_fisics_per_nivell = defaultdict(set)
        for nivell in sorted(nivells_items or set(nivells_actius or [])):
            for dia_nom, sk_prefix in dies_efectius:
                for hora in hores_examen:
                    # Una franja compta per al nivell si hi cap almenys un dels seus exàmens.
                    if not any(_hi_cap([s], hora) for s in sessions_del_nivell.get(nivell, [])):
                        continue
                    if not es_slot_valid_per_nivell(nivell, dia_nom, hora, restriccions):
                        continue
                    slots_fisics_per_nivell[nivell].add(f"{sk_prefix}_{hora}")

        incompat = []
        vistos = []

        # Capacitat base per nivell (abans de fixos per assignatura).
        items_per_nivell = defaultdict(int)
        for item in items:
            sessions = item.get("sessions") or []
            nivell = item.get("curs") or (_sessio_a_diccionari(sessions[0]).get("curs") if sessions else None)
            if not nivell:
                continue
            items_per_nivell[nivell] += 1

        for nivell, count in items_per_nivell.items():
            nombre_franges = len(slots_fisics_per_nivell.get(nivell, set()))
            if count > nombre_franges:
                msg = missatge("capacitat_nivell", nivell=nivell, count=count, hores=nombre_franges)
                if msg not in vistos:
                    vistos.append(msg)
                    incompat.append(msg)

        # Cobertura mínima per ítem i unió de franges per nivell (després de fixos).
        slots_items_per_nivell = defaultdict(set)
        for item in items:
            sessions = item.get("sessions") or []
            if not sessions:
                continue
            nivell = item.get("curs") or _sessio_a_diccionari(sessions[0]).get("curs")
            if not nivell:
                continue

            candidats = set()
            for dia_nom, sk_prefix in dies_efectius:
                for hora in hores_examen:
                    if not _hi_cap(sessions, hora):
                        continue
                    slot_ok = True
                    for sessio in sessions:
                        s_dict = _sessio_a_diccionari(sessio)
                        if viola_restriccio_dia_hora_fixos(
                            s_dict, dia_nom, hora, restriccions, nivells_actius, sk_prefix
                        ):
                            slot_ok = False
                            break
                    if slot_ok:
                        candidats.add(f"{sk_prefix}_{hora}")

            if not candidats:
                msg = missatge("examen_sense_hora", nom=_etiqueta_item(item), nivell=nivell)
                if msg not in vistos:
                    vistos.append(msg)
                    incompat.append(msg)
            else:
                slots_items_per_nivell[nivell].update(candidats)

        for nivell, count in items_per_nivell.items():
            nombre_franges = len(slots_items_per_nivell.get(nivell, set()))
            if count and nombre_franges and count > nombre_franges:
                msg = missatge("capacitat_nivell_fixos", nivell=nivell, count=count, hores=nombre_franges)
                if msg not in vistos:
                    vistos.append(msg)
                    incompat.append(msg)
            elif count and nombre_franges == 0:
                msg = missatge("nivell_sense_hora", nivell=nivell)
                if msg not in vistos:
                    vistos.append(msg)
                    incompat.append(msg)

        return incompat
