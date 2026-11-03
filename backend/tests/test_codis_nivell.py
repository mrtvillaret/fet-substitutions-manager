"""Guardià: els nivells depenen de la configuració, no de noms concrets."""

from pathlib import Path

ARREL = Path(__file__).parents[2]
CODIS_FIXOS = ("GENERAL", "RECERCA")


def _fitxers_de_codi():
    backend = ARREL / "backend"
    for fitxer in backend.rglob("*.py"):
        relatiu = fitxer.relative_to(backend)
        if not {"tests", "locales"} & set(relatiu.parts) and not any(part.startswith("venv") for part in relatiu.parts):
            yield fitxer

    frontend = ARREL / "frontend"
    for patro in ("*.js", "*.ts", "*.vue"):
        for fitxer in frontend.rglob(patro):
            relatiu = fitxer.relative_to(frontend)
            if not {"tests", "locales", "node_modules", "dist"} & set(relatiu.parts):
                yield fitxer


def test_no_hi_ha_codis_de_nivell_escrits_al_codi_productiu():
    coincidencies = []
    for fitxer in _fitxers_de_codi():
        text = fitxer.read_text(encoding="utf-8")
        for codi in CODIS_FIXOS:
            if codi in text:
                coincidencies.append(f"{fitxer.relative_to(ARREL)}: {codi}")

    assert coincidencies == []
