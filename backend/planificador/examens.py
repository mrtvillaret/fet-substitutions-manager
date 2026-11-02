"""Els exàmens del planificador: cada assignatura de la configuració
d'exàmens amb el seu nivell, «Assignatura (nivell)» (els noms de sessió que
fan servir les restriccions i els motors)."""

from configuracio_examens.repositories import MasterConfigRepository


def nivells_master(db) -> list[str]:
    """Els nivells de la configuració d'exàmens, els més llargs primer (per
    trobar el nivell d'un grup pel nom)."""
    master = MasterConfigRepository.get_master_config(db)
    nivells = list((master or {}).get("nivells", {}).keys())
    return sorted([n for n in nivells if n], key=len, reverse=True)


def detecta_nivell(grup: str, nivells: list[str]) -> str | None:
    if not grup:
        return None
    for nivell in nivells:
        if nivell in grup:
            return nivell
    return None


def examens(assignacions, nivells: list[str], only_nivells: list[str] | None = None) -> list[str]:
    """«Assignatura (nivell)» de cada assignació (només dels nivells
    `only_nivells`, si se'n donen); sense nivell, el nom sol."""
    options = set()
    for a in assignacions:
        nom = a.get("assignatura") if isinstance(a, dict) else a.assignatura
        grup = a.get("grup") if isinstance(a, dict) else a.grup
        if not nom:
            continue
        nivell = detecta_nivell(grup, nivells)
        if nivell:
            if not only_nivells or nivell in only_nivells:
                options.add(f"{nom} ({nivell})")
        else:
            if not only_nivells:
                options.add(nom)
    return sorted(options)
