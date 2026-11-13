"""Els exàmens del planificador: cada assignatura de la configuració
d'exàmens amb el seu nivell, «Assignatura (nivell)» (els noms de sessió que
fan servir les restriccions i els motors). El nivell surt de les taules de la
configuració d'exàmens (grups de cada nivell i abreviatures), no del nom del grup."""

from configuracio_examens.repositories import MasterConfigRepository
from scheduler_engine.core.nivells import NivellsDelsGrups


def nivells_master(db) -> list[str]:
    """Els nivells de la configuració d'exàmens, els més llargs primer."""
    master = MasterConfigRepository.get_master_config(db)
    nivells = list((master or {}).get("nivells", {}).keys())
    return sorted([n for n in nivells if n], key=len, reverse=True)


def nivells_dels_grups(db) -> NivellsDelsGrups:
    """Les taules de la configuració d'exàmens: els grups de cada nivell i les abreviatures."""
    return NivellsDelsGrups.de_master(MasterConfigRepository.get_master_config(db))


def examens(assignacions, taules: NivellsDelsGrups, only_nivells: list[str] | None = None) -> list[str]:
    """«Assignatura (nivell)» de cada assignació, per a cada nivell dels seus
    grups (només dels nivells `only_nivells`, si se'n donen); un grup que no és
    a cap nivell, el nom sol."""
    options = set()
    for a in assignacions:
        nom = a.get("assignatura") if isinstance(a, dict) else a.assignatura
        grup = a.get("grup") if isinstance(a, dict) else a.grup
        if not nom:
            continue
        nivells = taules.nivells(grup)
        for nivell in nivells:
            if not only_nivells or nivell in only_nivells:
                options.add(f"{nom} ({nivell})")
        if not nivells and not only_nivells:
            options.add(nom)
    return sorted(options)
