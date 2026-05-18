"""Helpers d'analisi i report pel scheduler."""

from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from scheduler_engine.defaults import DEFAULT_DURADA_TITULAR


def _diagnosticar_incompatibilitats(
    gen,
    restriccions: dict,
    dies_utilitzar: list[str],
    dia_a_data_iso: dict[str, str],
    alliberaments_cfg: dict,
    nivells_actius: list[str],
) -> list[str]:
    """
    Calcula incompatibilitats quan l'horari no és viable.
    Retorna missatges breus per mostrar en un popup.
    Usa InfeasibilityDiagnostic (no analitzar_tots_slots).
    """
    try:
        from scheduler_engine.core.diagnostic import (
            InfeasibilityDiagnostic, construir_dies_efectius,
        )

        hores_examen = list(getattr(gen, 'hores_examen', []) or [])
        if not hores_examen or not dies_utilitzar:
            return []

        dies_efectius = construir_dies_efectius(dies_utilitzar, dia_a_data_iso)
        if not dies_efectius:
            return []

        items_gen = []
        try:
            slots_est = max(1, len(dies_efectius) * max(1, len(hores_examen)))
            items_gen = gen.preparar_particio_nivells(slots_disponibles=slots_est) or []
        except Exception:
            pass

        if not items_gen:
            return []

        diag = InfeasibilityDiagnostic(
            restriccions=restriccions,
            dies_efectius=dies_efectius,
            hores_examen=hores_examen,
            nivells_actius=nivells_actius or [],
        )
        return diag.run(items_gen)

    except Exception:
        return []


def _identificar_sessions_no_collocades(horari: dict, gen) -> list[str]:
    """
    Quan InfeasibilityDiagnostic no detecta incompatibilitats estructurals,
    identifica quines sessions no s'han col·locat.

    Estratègia 1 (si hi ha resultat parcial): compara sessions_per_nivell amb
    l'horari parcial usant índexs per-curs, evitant contaminació creuada
    (ex: FILOSOFIA 1-BATX col·locat no ha de marcar FILOSOFIA 2-BATX com a col·locat).

    Fallback: usa recompte_nivells del metadata (cobreix dies=[] i sessions no
    identificades per nom).
    """
    sessions_per_nivell = getattr(gen, 'sessions_per_nivell', {}) or {}
    has_partial = bool(horari.get('dies'))

    manquen_per_nivell: dict = defaultdict(list)

    # Estratègia 1: comparació per-curs
    if has_partial and sessions_per_nivell:
        noms_per_curs: dict = defaultdict(set)
        for dia in (horari.get('dies') or []):
            for slot in dia.get('sessions', []):
                for sess in slot.get('sessions_simultanees', []):
                    curs = sess.get('curs') or ''
                    nom = sess.get('nom') or ''
                    nom_base = sess.get('nom_base') or ''
                    if nom:
                        noms_per_curs[curs].add(nom)
                    if nom_base:
                        noms_per_curs[curs].add(nom_base)

        for nivell, sessions in sessions_per_nivell.items():
            collocats = noms_per_curs.get(nivell, set())
            for s in (sessions or []):
                nom = (s.get('nom') if isinstance(s, dict) else getattr(s, 'nom', '')) or ''
                nom_base = (s.get('nom_base') if isinstance(s, dict) else getattr(s, 'nom_base', '')) or ''
                if nom and nom not in collocats and (not nom_base or nom_base not in collocats):
                    manquen_per_nivell[nivell].append(nom)

    # Fallback: recompte_nivells (dies=[] o sessions no identificades per nom)
    if not manquen_per_nivell:
        recompte = (horari.get('metadata') or {}).get('recompte_nivells') or {}
        for niv, info in sorted(recompte.items()):
            p = (info or {}).get('pendents', 0)
            if p > 0:
                e = (info or {}).get('esperats', 0)
                c = (info or {}).get('collocats', 0)
                manquen_per_nivell[niv] = [f"\x00RECOMPTE\x00{p}\x00{e}\x00{c}"]
        if not manquen_per_nivell:
            return []

    suffix_hint = " — reviseu les restriccions o amplieu el rang de dates"
    result = []
    for nivell, manquen in sorted(manquen_per_nivell.items()):
        manquen_u = list(dict.fromkeys(manquen))
        # Missatge de fallback (recompte per nivell)
        if len(manquen_u) == 1 and manquen_u[0].startswith('\x00RECOMPTE\x00'):
            _, _, p_s, e_s, c_s = manquen_u[0].split('\x00')
            p, e, c = int(p_s), int(e_s), int(c_s)
            if c == 0:
                result.append(f"{nivell}: cap sessió col·locada ({p} previstes){suffix_hint}")
            else:
                result.append(f"{nivell}: {p} sessió(ns) no col·locada(s) ({c}/{e} col·locades){suffix_hint}")
        elif len(manquen_u) == 1:
            result.append(f"No s'ha pogut col·locar '{manquen_u[0]}' ({nivell}){suffix_hint}")
        else:
            exemple = manquen_u[0]
            altres = len(manquen_u) - 1
            sfx = f" i {altres} més" if altres else ""
            result.append(f"{nivell}: no s'han pogut col·locar '{exemple}'{sfx}{suffix_hint}")
    return result


def _sessio_to_dict_precheck(sessio) -> dict:
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


def _item_label_precheck(item: dict) -> str:
    sessions = item.get("sessions") or []
    noms = []
    for s in sessions:
        s_dict = _sessio_to_dict_precheck(s)
        nom = s_dict.get("nom")
        if nom:
            noms.append(nom)
    if noms:
        return " + ".join(noms)
    return item.get("nom") or "(sense nom)"


def _precheck_incompatibilitats_deterministes(
    gen,
    restriccions: dict,
    dies_utilitzar: list[str],
    nivells_actius: list[str],
    selected_dates: list[str] = None,
) -> list[str]:
    """
    Precheck ràpid i segur (sense heurístiques):
      1) Capacitat per nivell (items <= slots físics disponibles)
      2) Cada ítem té almenys un slot possible
      3) Per nivell, unió de slots possibles >= nombre d'items
    """
    from datetime import datetime as _dt
    try:
        from scheduler_engine.core.constraints import (
            es_slot_valid_per_nivell,
            viola_restriccio_dia_hora_fixos,
        )
        from scheduler_engine.core.date_mapping import DIES_CAT
    except Exception:
        return []

    hores_examen = list(getattr(gen, "hores_examen", []) or [])
    if not dies_utilitzar or not hores_examen:
        return []

    # Llista efectiva de (dia_nom, sk_prefix) — usa dates reals si disponibles
    if selected_dates:
        dies_efectius = []
        for iso in sorted(selected_dates):
            try:
                dia_nom = DIES_CAT[_dt.strptime(iso, "%Y-%m-%d").weekday()]
                dies_efectius.append((dia_nom, iso))
            except (ValueError, IndexError):
                continue
    else:
        dies_efectius = [(d, d) for d in dies_utilitzar]

    slots_disponibles = len(dies_efectius) * len(hores_examen)
    items = []
    try:
        items = (
            gen.preparar_particio_nivells(slots_disponibles=max(1, slots_disponibles))
            or []
        )
    except Exception:
        items = []

    if not items:
        sessions_per_nivell = getattr(gen, "sessions_per_nivell", {}) or {}
        for nivell in nivells_actius or []:
            sessions = sessions_per_nivell.get(nivell) or []
            for s in sessions:
                items.append(
                    {
                        "curs": nivell,
                        "sessions": [s],
                        "nom": _sessio_to_dict_precheck(s).get("nom"),
                    }
                )

    if not items:
        return []

    def _hores_ocupades(hora: str, nivell: str | None) -> list[str]:
        getter = getattr(gen, "_get_hores_ocupades", None)
        if callable(getter):
            try:
                return getter(hora, nivell)
            except Exception:
                pass
        totes_hores = list(getattr(gen, "totes_hores", []) or [])
        durada = int(gen.get_durada_per_nivell(nivell) or 1)
        if hora not in totes_hores:
            return [hora]
        idx = totes_hores.index(hora)
        return totes_hores[idx : min(idx + durada, len(totes_hores))]

    nivells_items = set()
    for item in items:
        sessions = item.get("sessions") or []
        nivell = None
        if item.get("curs"):
            nivell = item.get("curs")
        elif sessions:
            nivell = _sessio_to_dict_precheck(sessions[0]).get("curs")
        if nivell:
            nivells_items.add(nivell)

    # Slots físics per nivell: només inici d'examen vàlid per durada + restricció slots_valids_per_nivell.
    slots_fisics_per_nivell = defaultdict(set)
    for nivell in sorted(nivells_items or set(nivells_actius or [])):
        for dia_nom, sk_prefix in dies_efectius:
            for hora in hores_examen:
                durada = int(gen.get_durada_per_nivell(nivell) or 1)
                hores_ocupades = _hores_ocupades(hora, nivell)
                if len(hores_ocupades) < durada:
                    continue
                if not es_slot_valid_per_nivell(
                    nivell, dia_nom, hora, restriccions, nivells_actius
                ):
                    continue
                slots_fisics_per_nivell[nivell].add(f"{sk_prefix}_{hora}")

    incompat = []
    seen = set()

    # Capacitat base per nivell (abans de fixos per assignatura).
    items_per_nivell = defaultdict(int)
    for item in items:
        sessions = item.get("sessions") or []
        nivell = item.get("curs") or (
            _sessio_to_dict_precheck(sessions[0]).get("curs") if sessions else None
        )
        if not nivell:
            continue
        items_per_nivell[nivell] += 1

    for nivell, count in items_per_nivell.items():
        slots_count = len(slots_fisics_per_nivell.get(nivell, set()))
        if count > slots_count:
            msg = f"{nivell}: {count} ítems > {slots_count} slots disponibles"
            if msg not in seen:
                seen.add(msg)
                incompat.append(msg)

    # Cobertura mínima per ítem i unió de slots per nivell (després de fixos).
    slots_items_per_nivell = defaultdict(set)
    for item in items:
        sessions = item.get("sessions") or []
        if not sessions:
            continue
        nivell = item.get("curs") or _sessio_to_dict_precheck(sessions[0]).get("curs")
        if not nivell:
            continue

        candidats = set()
        for dia_nom, sk_prefix in dies_efectius:
            for hora in hores_examen:
                durada = int(gen.get_durada_per_nivell(nivell) or 1)
                hores_ocupades = _hores_ocupades(hora, nivell)
                if len(hores_ocupades) < durada:
                    continue
                slot_ok = True
                for sessio in sessions:
                    s_dict = _sessio_to_dict_precheck(sessio)
                    if viola_restriccio_dia_hora_fixos(
                        s_dict, dia_nom, hora, restriccions, nivells_actius, sk_prefix
                    ):
                        slot_ok = False
                        break
                if slot_ok:
                    candidats.add(f"{sk_prefix}_{hora}")

        if not candidats:
            msg = f"{_item_label_precheck(item)} ({nivell}) sense cap slot viable"
            if msg not in seen:
                seen.add(msg)
                incompat.append(msg)
        else:
            slots_items_per_nivell[nivell].update(candidats)

    for nivell, count in items_per_nivell.items():
        slots_count = len(slots_items_per_nivell.get(nivell, set()))
        if count and slots_count and count > slots_count:
            msg = (
                f"{nivell}: {count} ítems > {slots_count} slots possibles després de fixos"
            )
            if msg not in seen:
                seen.add(msg)
                incompat.append(msg)
        elif count and slots_count == 0:
            msg = f"{nivell}: cap slot viable"
            if msg not in seen:
                seen.add(msg)
                incompat.append(msg)

    return incompat


def _afegir_recompte_nivells(horari: dict, sessions_per_nivell: dict) -> None:
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
            logs.append(f"⚠️ NIVELL INCOMPLET: {nivell} ({total - pendents}/{total})")


def _format_report_lines(tab: str, text: str) -> list[tuple[str, bool, int]]:
    lines = []
    raw_lines = [l.rstrip().replace("■", "") for l in (text or "").splitlines()]

    def add(line: str, bold: bool = False, indent: int = 0):
        if line is None:
            return
        lines.append((line, bold, indent))

    if tab == "per_slots":
        for raw in raw_lines:
            line = raw.strip()
            if not line or line.startswith("="):
                continue
            if line.startswith("📅"):
                add(line, True, 0)
                continue
            if line.startswith("⏰"):
                add(line, True, 6)
                continue
            if (
                line.endswith(":")
                and not line.startswith("✅")
                and not line.startswith("🟡")
                and not line.startswith("🔶")
            ):
                add(line, True, 12)
                continue
            if line.startswith("✅") or line.startswith("🟡") or line.startswith("🔶"):
                label, _, items = line.partition(":")
                add(f"{label}:", True, 18)
                for item in [i.strip() for i in items.split(",") if i.strip()]:
                    add(f"- {item}", False, 26)
                continue
            add(line, False, 12)
        return lines

    if tab == "per_sessio":
        for raw in raw_lines:
            line = raw.strip()
            if not line or line.startswith("="):
                continue
            if line.startswith("📝"):
                add(line, True, 0)
                continue
            if line.startswith("👥"):
                add(line, False, 10)
                continue
            if "|" in line and not line.startswith("Dia"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 8:
                    dia = parts[0]
                    hora = parts[1]
                    subs = parts[3]
                    abans = parts[4]
                    despres = parts[5]
                    no_treballa = parts[6]
                    detalls = " | ".join(parts[7:]).strip()
                    add(f"{dia}  {hora}", True, 10)
                    add(
                        f"Subs: {subs}  Abans: {abans}  Després: {despres}  No treb: {no_treballa}",
                        False,
                        16,
                    )
                    if detalls:
                        add(f"Detalls: {detalls}", False, 16)
                continue
            add(line, False, 10)
        return lines

    if tab == "professors_slot":
        for raw in raw_lines:
            line = raw.strip()
            if not line or line.startswith("="):
                continue
            if line.startswith("📅") or line.startswith("⏰") or line.startswith("⏱️"):
                add(line, True, 0 if line.startswith("📅") else 8)
                continue
            if line.startswith("✅") or line.startswith("📚"):
                add(line, True, 12)
                continue
            if line.startswith("•"):
                add(line, False, 18)
                continue
            add(line, False, 10)
        return lines

    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("="):
            continue
        add(line, False, 0)
    return lines


def _write_analysis_pdf(path: str, sections: list[tuple[str, str, str]]):
    doc = SimpleDocTemplate(
        path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=16, spaceAfter=12)
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=6
    )
    day_style = ParagraphStyle(
        "Day", parent=styles["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4
    )
    slot_style = ParagraphStyle(
        "Slot", parent=styles["Heading4"], fontSize=10, spaceBefore=6, spaceAfter=3
    )
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5, leading=12)
    label_style = ParagraphStyle("Label", parent=body_style, fontName="Helvetica-Bold")

    flow = [Paragraph("Anàlisi de possibilitats", title_style)]

    def label_color(text: str) -> colors.Color | None:
        if "Òptimes" in text:
            return colors.HexColor("#15803d")
        if "Bones" in text:
            return colors.HexColor("#c2410c")
        if "Acceptables" in text:
            return colors.HexColor("#b91c1c")
        return None

    for title, tab, text in sections:
        flow.append(Paragraph(title, section_style))
        bullet_items = []
        for line, bold, indent in _format_report_lines(tab, text):
            if not line:
                if bullet_items:
                    flow.append(ListFlowable(bullet_items, bulletType="bullet", leftIndent=18))
                    bullet_items = []
                flow.append(Spacer(1, 6))
                continue

            clean = (
                line.replace("📅", "")
                .replace("⏰", "")
                .replace("📝", "")
                .replace("⏱️", "")
                .strip()
            )
            if line.startswith("- "):
                bullet_items.append(ListItem(Paragraph(clean[2:], body_style), leftIndent=18))
                continue

            if bullet_items:
                flow.append(ListFlowable(bullet_items, bulletType="bullet", leftIndent=18))
                bullet_items = []

            if line.startswith("📅"):
                flow.append(Paragraph(clean, day_style))
                continue
            if line.startswith("⏰") or line.startswith("⏱️"):
                flow.append(Paragraph(clean, slot_style))
                continue

            if clean.endswith(":") and (
                "Òptimes" in clean or "Bones" in clean or "Acceptables" in clean
            ):
                color = label_color(clean)
                if color:
                    flow.append(
                        Paragraph(
                            f"<font color='{color.hexval()}'>" + clean + "</font>",
                            label_style,
                        )
                    )
                else:
                    flow.append(Paragraph(clean, label_style))
                continue

            style = label_style if bold else body_style
            flow.append(Paragraph(clean, style))

        if bullet_items:
            flow.append(ListFlowable(bullet_items, bulletType="bullet", leftIndent=18))
        flow.append(Spacer(1, 10))

    doc.build(flow)
