"""
Absència coberta: un professor absent que té un substitut extern a l'XML.
Durant el període, l'absent queda fora de tot. La regla es resol en un sol
punt: l'horari d'una data (helpers.get_horari, per on passa Dia) ja no el
té (absencia_coberta.services.sense_absents_coberts).
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

# Peces per saber qui té una absència coberta: només les pot fer servir el
# mòdul (i el punt únic de helpers.get_horari, que crida les seves funcions)
PROHIBIT = re.compile(
    r"\b(AbsenciaCobertaRepository|absents_coberts_en|PROFESSORS_BAIXA|professors_de_baixa|esta_de_baixa|GestorBaixes)\b"
)
# La taula, fora del mòdul: el model i la migració dels noms
TAULA = re.compile(r"\bprofessors_baixa\b")
TAULA_PERMESA = {"models.py", "migracions/noms_nets.py"}
# (el model, AbsenciaCoberta, també el fan servir la purga de dades,
# gestio_dades.py, i l'informe de direcció, que en compta els registres:
# pdf/repositories.py)


def test_cap_codi_fora_del_modul_comprova_qui_te_una_absencia_coberta():
    errors = []
    for fitxer in BACKEND.rglob("*.py"):
        parts = fitxer.relative_to(BACKEND).parts
        if parts[0].startswith("venv") or "tests" in parts or parts[0] == "absencia_coberta":
            continue
        relatiu = "/".join(parts)
        for n, linia in enumerate(fitxer.read_text(encoding="utf-8").splitlines(), 1):
            if PROHIBIT.search(linia):
                errors.append(f"{relatiu}:{n}: {linia.strip()}")
            elif TAULA.search(linia) and relatiu not in TAULA_PERMESA:
                errors.append(f"{relatiu}:{n}: (taula) {linia.strip()}")
    assert errors == []
