"""
Esborra del tot un centre: la seva carpeta (gestor.db, XML, logo...) i els
seus usuaris. Des de la web només es pot desactivar.

1. Diu què s'esborrarà: la carpeta (fitxers i mida) i els usuaris.
2. Demana confirmació escrivint el nom del centre.
3. Fa una còpia comprimida de la carpeta i dels usuaris (usuaris.json, amb
   els hash de les contrasenyes, per poder-los restaurar) i comprova que es
   pot llegir. Les BD es copien amb l'API de còpia de SQLite: la còpia és
   coherent encara que el backend hi estigui escrivint.
4. Esborra els usuaris i la carpeta, i recorda on és la còpia: conté les
   dades del centre i, per protecció de dades, s'ha d'esborrar quan ja no
   calgui.

No esborra el centre propi d'un superadmin: abans cal canviar-li el centre.

Ús, des de backend/ i amb el mateix entorn que el backend (el .env):
    venv/bin/python -m scripts.esborra_centre <centre> [--copia-dir <carpeta>]
Amb Docker:
    docker compose exec backend python -m scripts.esborra_centre <centre>

La còpia va, per defecte, a <carpeta de dades>/_esborrats/<centre>_AAAAMMDD-HHMMSS.tar.gz
(«_esborrats» no pot ser el nom de cap centre).
"""

import argparse
import io
import json
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path


def _mida(carpeta: Path) -> tuple[int, int]:
    fitxers = [p for p in carpeta.rglob("*") if p.is_file()]
    return len(fitxers), sum(p.stat().st_size for p in fitxers)


def _copia_bd(origen: Path, desti: Path) -> None:
    font, copia = sqlite3.connect(origen), sqlite3.connect(desti)
    try:
        font.backup(copia)
    finally:
        copia.close()
        font.close()


def _fa_copia(carpeta: Path, centre: str, usuaris: list[dict], copia_dir: Path) -> Path:
    copia_dir.mkdir(parents=True, exist_ok=True)
    desti = copia_dir / f"{centre}_{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
    with tempfile.TemporaryDirectory() as temporal, tarfile.open(desti, "w:gz") as tar:
        tar.add(carpeta, arcname=centre, recursive=False)
        for cami in sorted(carpeta.rglob("*")):
            nom = f"{centre}/{cami.relative_to(carpeta).as_posix()}"
            if cami.is_file() and cami.suffix == ".db":
                bd = Path(temporal) / "copia.db"
                bd.unlink(missing_ok=True)
                _copia_bd(cami, bd)
                tar.add(bd, arcname=nom)
            elif not cami.name.endswith((".db-wal", ".db-shm", ".db-journal")):
                tar.add(cami, arcname=nom, recursive=False)
        dades = json.dumps(usuaris, ensure_ascii=False, indent=2, default=str).encode()
        info = tarfile.TarInfo("usuaris.json")
        info.size, info.mtime = len(dades), int(datetime.now().timestamp())
        tar.addfile(info, io.BytesIO(dades))
    # Abans d'esborrar res: la còpia es pot llegir sencera
    with tarfile.open(desti) as tar:
        for membre in tar:
            if membre.isfile():
                tar.extractfile(membre).read()
    return desti


def main(args: list[str], entrada=input) -> int:
    parser = argparse.ArgumentParser(description="Esborra del tot un centre, amb còpia.")
    parser.add_argument("centre")
    parser.add_argument("--copia-dir", type=Path, help="on es desa la còpia (per defecte, <dades>/_esborrats)")
    opcions = parser.parse_args(args)
    centre = opcions.centre

    from auth.repositories import UserRepository  # noqa: PLC0415 — El CLI valida arguments abans d’inicialitzar l’aplicació.
    from centres import services  # noqa: PLC0415 — El CLI valida arguments abans d’inicialitzar l’aplicació.
    from database import DATA_BASE_DIR, AuthSessionLocal, get_data_dir_for_institucio  # noqa: PLC0415 — El CLI valida arguments abans d’inicialitzar l’aplicació.
    from errors_domini import ErrorDeDomini  # noqa: PLC0415 — El CLI valida arguments abans d’inicialitzar l’aplicació.
    from models import User  # noqa: PLC0415 — El CLI valida arguments abans d’inicialitzar l’aplicació.

    with AuthSessionLocal() as auth_db:
        try:
            services.comprova_es_pot_esborrar_definitivament(auth_db, centre)
        except ErrorDeDomini as error:
            print(f"No s'esborra res: {error}")
            return 1

        carpeta = get_data_dir_for_institucio(centre)
        usuaris = UserRepository.list_by_institucio(auth_db, centre)
        nombre, mida = _mida(carpeta)
        print(f"S'esborrarà el centre «{centre}»:")
        print(f"  - la carpeta {carpeta} ({nombre} fitxers, {mida / 1024 / 1024:.1f} MB)")
        print(f"  - {len(usuaris)} usuaris:")
        for user in sorted(usuaris, key=lambda u: u.username):
            print(f"      {user.username} ({user.role}{'' if user.active else ', inactiu'})")

        if entrada(f"Per confirmar-ho, escriu el nom del centre ({centre}): ").strip() != centre:
            print("No coincideix: no s'esborra res.")
            return 1

        columnes = [c.name for c in User.__table__.columns]
        copia = _fa_copia(
            carpeta,
            centre,
            [{c: getattr(u, c) for c in columnes} for u in usuaris],
            opcions.copia_dir or DATA_BASE_DIR / "_esborrats",
        )
        print(f"Còpia: {copia}")

        services.esborra_definitivament(auth_db, centre)
    print(f"Esborrat: la carpeta i {len(usuaris)} usuaris.")
    print(f"La còpia és a {copia}.")
    print("Conté les dades del centre (també personals): per protecció de dades, esborra-la quan ja no calgui.")
    return 0


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()  # el mateix entorn que el backend (main.py)
    sys.exit(main(sys.argv[1:]))
