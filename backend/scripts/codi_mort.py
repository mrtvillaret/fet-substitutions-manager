"""Codi mort del backend (vulture): falla si en troba.

    python -m scripts.codi_mort                 # el que no fa servir ningú (la CI)
    python -m scripts.codi_mort --sense-tests   # informe: el que només fan servir els tests

Excepcions (falsos positius de vulture, que no veu qui crida el framework):
- decoradors: les rutes de FastAPI, els validadors de Pydantic, els
  listeners de SQLAlchemy i els context managers;
- noms: les revisions d'Alembic, la configuració dels models i els que
  criden ReportLab, logging o tarfile;
- les variables de schemas.py i models.py: són camps de Pydantic i columnes
  de la BD (es fan servir en serialitzar o a la BD). Les classes, no: una
  classe d'esquema que no fa servir ningú sí que surt.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FORA = {"tests", "data", "exports", "locales", "__pycache__"}
DECORADORS = [
    "@router.*",
    "@router_admin.*",
    "@app.*",
    "@*.exception_handler",
    "@field_validator",
    "@model_validator",
    "@field_serializer",
    "@event.listens_for",
    "@contextmanager",
    "@asynccontextmanager",
    "@pytest.fixture",
]
NOMS = [
    # Alembic
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
    "upgrade",
    "downgrade",
    # Pydantic i SQLAlchemy
    "model_config",
    "__tablename__",
    "__table_args__",
    # Els que criden ReportLab (draw, hAlign), logging (disabled) i tarfile (mtime)
    "draw",
    "hAlign",
    "disabled",
    "mtime",
    # Columna que s'escriu a la BD (horari/repositories.py) i no es llegeix aquí
    "ultima_aparicio",
    # El paràmetre que SQLAlchemy passa al listener «connect» (database.py)
    "connection_record",
    "test_*",
]
CAMPS = re.compile(r"(^|/)(schemas|models)\.py:\d+: unused variable")


def _carpetes(amb_tests: bool) -> list[str]:
    codi = sorted(
        str(p.relative_to(BACKEND))
        for p in BACKEND.iterdir()
        if (p.is_dir() and p.name not in FORA and not p.name.startswith((".", "venv")))
        or (p.is_file() and p.suffix == ".py")
    )
    return codi + (["tests"] if amb_tests else [])


def troballes(amb_tests: bool = True) -> list[str]:
    ordre = [sys.executable, "-m", "vulture", *_carpetes(amb_tests), "--min-confidence", "60"]
    ordre += ["--ignore-decorators", ",".join(DECORADORS), "--ignore-names", ",".join(NOMS)]
    sortida = subprocess.run(ordre, cwd=BACKEND, capture_output=True, text=True, check=False).stdout
    return [linia for linia in sortida.splitlines() if linia and not CAMPS.search(linia)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sense-tests", action="store_true", help="informe del que només fan servir els tests")
    args = parser.parse_args(argv)
    if args.sense_tests:
        amb = set(troballes(amb_tests=True))
        nomes_tests = [linia for linia in troballes(amb_tests=False) if linia not in amb]
        print("\n".join(nomes_tests) or "Res que només facin servir els tests")
        return 0
    trobat = [linia for linia in troballes() if not linia.startswith("tests/")]
    print("\n".join(trobat) or "Cap codi mort")
    return 1 if trobat else 0


if __name__ == "__main__":
    sys.exit(main())
