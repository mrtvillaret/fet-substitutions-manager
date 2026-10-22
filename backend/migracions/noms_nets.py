"""
Migració de la regla dels noms (noms.py) sobre les dades ja desades: els noms
de professors, assignatures (activitats) i aules queden nets (sense espais al
principi ni al final).

- Llistes: si en netejar-los dos valors d'una mateixa llista queden iguals, es
  fusionen i es conserva la fila modificada més recentment (updated_at; si la
  taula no en té, created_at). Una llista és una taula i una clau
  (LLISTES); mai no es comparen ni es toquen files de taules diferents: una
  mateixa activitat pot ser alhora a «No substituir» i a les prioritats.
- Registres (substitucions, vigilàncies, baixes): només es netegen.
- Configuració: ultim_professor_subs es neteja; les llistes d'activitats
  alliberables, netes i sense repetits; les claus de les durades per sessió,
  netes.
- El buit és vàlid; un nom fet només d'espais queda buit.

No escriu cap nom: només recomptes. Les BD es diuen «bd 1, 2...» en l'ordre
en què es donen.

Ús, des de backend/:
    venv/bin/python -m migracions.noms_nets --recompte <gestor.db> [<gestor.db>...]
    venv/bin/python -m migracions.noms_nets --aplica   <gestor.db> [<gestor.db>...]

--aplica fa abans una còpia de cada BD (<bd>.abans-noms-nets-AAAAMMDD-HHMMSS,
amb l'API de còpia de SQLite) i aplica cada BD en una sola transacció.
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

from noms import nom_net

# taula: (columnes de noms, clau de la llista)
LLISTES = {
    "no_substituir": (["assignatura"], ["assignatura"]),
    "assignatures_prioritat": (["assignatura"], ["categoria_id", "assignatura"]),
    "professors": (["nom"], ["nom"]),
    "assignatures": (["nom"], ["nivell_id", "nom"]),
    "configuracio_examens": (["assignatura", "titular", "aula"], ["assignatura", "grup"]),
    "propostes_descartades": (["assignatura", "titular"], ["assignatura", "grup", "titular"]),
    "exam_costos_professors": (["professor"], ["professor", "tipus"]),
}
# taula: columnes de noms (registres: es netegen, no es fusionen mai)
REGISTRES = {
    "substitucions": ["professor_absent", "assignatura", "substitut", "aula"],
    "vigilancies": ["vigilant", "aula"],
    "professors_baixa": ["professor"],
}
CLAUS_LLISTA = ["activitats_alliberables", "activitats_alliberades_per_defecte"]
CLAU_TEXT = "ultim_professor_subs"
CLAU_DICT = "scheduler_durades_per_sessio"


def _columnes(con, taula):
    return {r[1] for r in con.execute(f"pragma table_info({taula})")}


def _taules(con):
    return {r[0] for r in con.execute("select name from sqlite_master where type='table'")}


def _net(v):
    return nom_net(v) if isinstance(v, str) else v


def _llista(con, taula, cols, clau, aplica, resum):
    existents = _columnes(con, taula)
    cols = [c for c in cols if c in existents]
    if not cols or not set(clau) <= existents:
        return
    temps = "updated_at" if "updated_at" in existents else ("created_at" if "created_at" in existents else None)
    sel = ", ".join(["id"] + clau + ([temps] if temps else []))
    grups = defaultdict(list)
    for fila in con.execute(f"select {sel} from {taula}"):
        grups[tuple(_net(v) for v in fila[1 : 1 + len(clau)])].append(fila)
    esborrades = []
    for files in grups.values():
        if len(files) > 1 and len({f[1 : 1 + len(clau)] for f in files}) > 1:
            # Es queda la modificada més recentment (i, si empaten, la darrera creada)
            guanyadora = max(files, key=lambda f: ((f[-1] or "") if temps else "", f[0]))
            esborrades += [f[0] for f in files if f[0] != guanyadora[0]]
    resum[f"{taula}: fusions"] = len(esborrades)
    if aplica and esborrades:
        con.executemany(f"delete from {taula} where id = ?", [(i,) for i in esborrades])
    _neteja_columnes(con, taula, cols, aplica, resum)


def _neteja_columnes(con, taula, cols, aplica, resum):
    for col in cols:
        canvis = [
            (nom_net(v), i)
            for i, v in con.execute(f"select id, {col} from {taula}")
            if isinstance(v, str) and v != nom_net(v)
        ]
        resum[f"{taula}.{col}: valors nets"] = len(canvis)
        if aplica and canvis:
            con.executemany(f"update {taula} set {col} = ? where id = ?", canvis)


def _configuracio(con, aplica, resum):
    if "configuracio" not in _taules(con):
        return

    def llegeix(clau):
        fila = con.execute("select valor from configuracio where clau = ?", (clau,)).fetchone()
        return fila[0] if fila else None

    def desa(clau, valor):
        if aplica:
            con.execute("update configuracio set valor = ? where clau = ?", (valor, clau))

    text = llegeix(CLAU_TEXT)
    canvia = isinstance(text, str) and text != nom_net(text)
    resum[f"configuracio[{CLAU_TEXT}]: valors nets"] = int(canvia)
    if canvia:
        desa(CLAU_TEXT, nom_net(text))

    for clau in CLAUS_LLISTA:
        try:
            valor = json.loads(llegeix(clau) or "null")
        except ValueError:
            continue
        if not isinstance(valor, list):
            continue
        nova = list(dict.fromkeys(_net(v) for v in valor))  # netes i sense repetits, en el mateix ordre
        repetits_abans = len(valor) - len(dict.fromkeys(valor))  # no són cosa d'aquesta regla
        resum[f"configuracio[{clau}]: fusions"] = len(valor) - len(nova) - repetits_abans
        if nova != valor:
            desa(clau, json.dumps(nova, ensure_ascii=False))

    try:
        durades = json.loads(llegeix(CLAU_DICT) or "null")
    except ValueError:
        durades = None
    if isinstance(durades, dict):
        nou = {}
        for k, v in durades.items():
            kn = _net(k)
            if kn not in nou or k == kn:  # en una col·lisió, mana la clau que ja era neta
                nou[kn] = v
        resum[f"configuracio[{CLAU_DICT}]: fusions"] = len(durades) - len(nou)
        if nou != durades:
            desa(CLAU_DICT, json.dumps(nou, ensure_ascii=False))


def migra(cami: str, aplica: bool) -> dict:
    """Recompte (i, amb `aplica`, canvis) d'una BD gestor.db. Retorna {què: quantes}."""
    resum = {}
    # El recompte obre la BD en només lectura: no hi pot escriure res
    con = sqlite3.connect(cami) if aplica else sqlite3.connect(f"file:{cami}?mode=ro", uri=True)
    try:
        taules = _taules(con)
        con.execute("begin")
        for taula, (cols, clau) in LLISTES.items():
            if taula in taules:
                _llista(con, taula, cols, clau, aplica, resum)
        for taula, cols in REGISTRES.items():
            if taula in taules:
                existents = _columnes(con, taula)
                _neteja_columnes(con, taula, [c for c in cols if c in existents], aplica, resum)
        _configuracio(con, aplica, resum)
        if aplica:
            con.commit()
            assert con.execute("pragma integrity_check").fetchone()[0] == "ok"
        else:
            con.rollback()
    finally:
        con.close()
    return resum


def copia(cami: str) -> str:
    desti = f"{cami}.abans-noms-nets-{datetime.now():%Y%m%d-%H%M%S}"
    font, nou = sqlite3.connect(cami), sqlite3.connect(desti)
    try:
        font.backup(nou)
    finally:
        font.close()
        nou.close()
    return desti


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--recompte", action="store_true", help="només comptar (no escriu res)")
    mode.add_argument("--aplica", action="store_true", help="còpia de seguretat i migració")
    parser.add_argument("bds", nargs="+")
    args = parser.parse_args(argv)
    for n, cami in enumerate(args.bds, 1):
        if args.aplica:
            copia(cami)
        resum = migra(cami, aplica=args.aplica)
        print(f"bd {n}{' (aplicada, amb còpia)' if args.aplica else ''}")
        for que, quantes in resum.items():
            print(f"    {que:55} {quantes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
