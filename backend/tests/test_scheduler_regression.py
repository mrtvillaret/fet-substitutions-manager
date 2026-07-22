import io
import json
import os
import random
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

# Ensure local backend modules are importable without venv activation.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scheduler_engine.core.date_mapping import construir_mapa_dia_data_iso
from scheduler_engine.defaults import (
    DEFAULT_COST_PROFESSORS,
    DEFAULT_DURADA_TITULAR,
)
from routes.scheduler_helpers import extreure_hores_examen_des_alliberaments
from scheduler_engine.factory import crear_motor


CAT_DIES = [
    "Dilluns",
    "Dimarts",
    "Dimecres",
    "Dijous",
    "Divendres",
    "Dissabte",
    "Diumenge",
]

# Snapshot mínim de regressió (fixture: data/demo, BAC2).
EXPECTED_SNAPSHOT = {
    "v2": {"cost_total": 510.0, "total_sessions": 15},
    "v2-backtrack": {"cost_total": 510, "total_sessions": 15},
    "v3": {"cost_total": 510.0, "total_sessions": 15},
}


def _load_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _fetch_config_value(cur, key):
    cur.execute("select valor from configuracio where clau=?", (key,))
    row = cur.fetchone()
    return row[0] if row else None


def _build_config_from_db(cur):
    cur.execute("select assignatura, grup, titular, aula from configuracio_examens")
    config = {"assignatures": {}}
    for assignatura, grup, titular, aula in cur.fetchall():
        config["assignatures"].setdefault(assignatura, {"assignacions": []})[
            "assignacions"
        ].append(
            {
                "grup": grup,
                "titular": titular or "",
                "aula": aula or "",
            }
        )
    return config


def _build_restriccions_from_db(cur):
    data = {
        "restriccions_dures": {
            "no_mateix_dia": [],
            "no_mateix_slot": {},
            "mateix_slot": [],
            "assignatures_dia_fix": {},
            "assignatures_hora_fix": {},
            "professors_horari_estricte": [],
            "professors_limit_dies_especifics": {},
            "slots_valids_per_nivell": {},
            "combinacions_permeses": [],
            "assignatures_dies_exclosos": [],
        },
        "preferencies": {"mateix_dia": [], "dies_diferents": []},
        "pesos_optimitzacio": {},
        "pesos_percentatge": {},
    }

    cur.execute(
        "select tipus, clau, configuracio, pes from exam_restriccions where activa = 1"
    )
    for tipus, clau, configuracio, pes in cur.fetchall():
        try:
            val = json.loads(configuracio) if configuracio else None
        except Exception:
            val = configuracio
        pes = 100 if pes is None else int(pes)

        if tipus in data["restriccions_dures"]:
            target = data["restriccions_dures"][tipus]
            if isinstance(target, list):
                if tipus in ("mateix_slot", "combinacions_permeses"):
                    if isinstance(val, list):
                        target.append({"nom": clau or "", "assignatures": val, "pes": pes})
                    elif val:
                        target.append(val)
                elif tipus == "assignatures_dies_exclosos":
                    if isinstance(val, dict) and val:
                        val["pes"] = pes
                        target.append(val)
                else:
                    target.append(val or clau)
            elif clau:
                target[clau] = val
                target[f"_pes_{clau}"] = pes

        elif tipus in ("dies_diferents", "mateix_dia"):
            assignatures = val if isinstance(val, list) else _load_json(val, [])
            data["preferencies"][tipus].append({"assignatures": assignatures, "pes": pes})

        elif tipus == "pes_optimitzacio" and clau:
            data["pesos_optimitzacio"][clau] = pes

    costos = {"globals": {}, "individuals": {}}
    try:
        cur.execute("select professor, tipus, pes from exam_costos_professors")
        for professor, tipus, pes in cur.fetchall():
            if professor is None:
                costos["globals"][tipus] = int(pes)
            else:
                costos["individuals"].setdefault(professor, {})[tipus] = int(pes)
    except Exception:
        pass

    data["costos_professors"] = costos
    data["pesos_percentatge"] = {
        "substitucio": costos["globals"].get(
            "substitucio", DEFAULT_COST_PROFESSORS["substitucio"]
        ),
        "professor_abans": costos["globals"].get(
            "abans_jornada", DEFAULT_COST_PROFESSORS["abans_jornada"]
        ),
        "professor_despres": costos["globals"].get(
            "despres_jornada", DEFAULT_COST_PROFESSORS["despres_jornada"]
        ),
        "professor_no_treballa": costos["globals"].get(
            "no_treballa_dia", DEFAULT_COST_PROFESSORS["no_treballa_dia"]
        ),
    }

    return data


def _derive_dies_utilitzar(selected_dates):
    seen = set()
    dies = []
    for date_iso in sorted(selected_dates):
        wd = datetime.strptime(date_iso, "%Y-%m-%d").weekday()
        name = CAT_DIES[wd]
        if name not in seen:
            seen.add(name)
            dies.append(name)
    return dies


class SchedulerRegressiondemoBAC2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Aquest test compara la sortida del motor amb un snapshot fix, així
        # que necessita el mateix conjunt de dades que el va generar. No es
        # distribueix amb el repositori: apunta TEST_DATA_DIR a un directori
        # teu amb gestor.db i teachers.xml per executar-lo.
        arrel = BACKEND_DIR.parent
        data_dir = Path(os.environ.get("TEST_DATA_DIR", arrel / "data" / "demo"))
        cls.db_path = data_dir / "gestor.db"
        cls.xml_path = data_dir / "teachers.xml"

        if not cls.db_path.exists() or not cls.xml_path.exists():
            raise unittest.SkipTest(
                f"Fixture absent a {data_dir}: calen gestor.db i teachers.xml. "
                "Defineix TEST_DATA_DIR per apuntar al teu conjunt de dades."
            )

        con = sqlite3.connect(cls.db_path)
        cur = con.cursor()

        cls.config = _build_config_from_db(cur)
        cls.restriccions = _build_restriccions_from_db(cur)

        cls.durada_titular = int(
            _fetch_config_value(cur, "scheduler_durada_titular")
            or DEFAULT_DURADA_TITULAR
        )
        cls.nivells_actius = _load_json(
            _fetch_config_value(cur, "scheduler_selected_nivells"), ["BAC2"]
        )
        cls.selected_dates = _load_json(
            _fetch_config_value(cur, "scheduler_selected_dates"), []
        )
        if not cls.selected_dates:
            cls.selected_dates = ["2026-02-12", "2026-02-13", "2026-02-16", "2026-02-17"]

        cls.alliberaments_per_nivell = _load_json(
            _fetch_config_value(cur, "scheduler_alliberaments_per_nivell"), {}
        )
        cls.hores_examen, cls.hores_per_nivell = extreure_hores_examen_des_alliberaments(
            cls.alliberaments_per_nivell
        )
        cls.ultim_professor = _fetch_config_value(cur, "ultim_professor_subs") or ""

        cur.execute("select assignatura from no_substituir")
        cls.no_substituir = {row[0] for row in cur.fetchall()}
        con.close()

        cls.dies_utilitzar = _derive_dies_utilitzar(cls.selected_dates)
        cls.dia_a_data_iso = construir_mapa_dia_data_iso(
            dies_utilitzar=cls.dies_utilitzar,
            selected_dates=cls.selected_dates,
            data_inici_iso=min(cls.selected_dates),
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as cfg_file:
            json.dump(cls.config, cfg_file, ensure_ascii=False)
            cls.cfg_path = cfg_file.name
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as restr_file:
            json.dump(cls.restriccions, restr_file, ensure_ascii=False)
            cls.restr_path = restr_file.name

        cls.results = {}
        for motor in ["v2", "v2-backtrack", "v3"]:
            cls.results[motor] = cls._run_motor(motor)

    @classmethod
    def tearDownClass(cls):
        for p in (getattr(cls, "cfg_path", None), getattr(cls, "restr_path", None)):
            if p and os.path.exists(p):
                os.unlink(p)

    @classmethod
    def _run_motor(cls, motor):
        random.seed(12345)
        override_params = {}
        if motor == "v3":
            override_params = {
                "temperatura_inicial": 300.0,
                "temperatura_final": 0.1,
                "factor_refredament": 0.95,
                "iteracions_per_temperatura": 25,
                "max_iteracions": 2500,
                "intents_solucio_inicial": 5,
            }

        gen, method_name = crear_motor(
            motor,
            cls.cfg_path,
            str(cls.xml_path),
            restriccions_path=cls.restr_path,
            ultim_professor=cls.ultim_professor,
            nivells_actius=cls.nivells_actius,
            hores_examen=cls.hores_examen,
            hores_per_nivell=cls.hores_per_nivell,
            durada_titular=cls.durada_titular,
            no_substituir=cls.no_substituir,
            alliberaments_per_nivell=cls.alliberaments_per_nivell,
            **override_params,
        )
        gen.carregar_dades()
        gen.carregar_horaris_professors()

        method = getattr(gen, method_name)
        kwargs = {
            "data_inici": datetime.strptime(min(cls.selected_dates), "%Y-%m-%d").strftime(
                "%d/%m/%Y"
            ),
            "data_inici_iso": min(cls.selected_dates),
            "dies_utilitzar": cls.dies_utilitzar,
            "dia_a_data_iso": cls.dia_a_data_iso,
            "max_dies": len(cls.dies_utilitzar),
        }
        if motor == "v2":
            kwargs.update(
                {
                    "max_intents_validacio": 40,
                    "estrategia": "ponderada",
                    "epsilon": 0.15,
                    "track_intents": True,
                }
            )
        elif motor == "v2-backtrack":
            kwargs.update({"max_solucions": 5, "random_seed": 12345, "seeds_count": 1})

        # Silencia logs de traça dels motors durant test.
        with redirect_stdout(io.StringIO()):
            result = method(**kwargs)

        if motor == "v2-backtrack":
            result = result[0] if result else {"metadata": {}}

        return result

    def test_motors_return_expected_structure(self):
        for motor, result in self.results.items():
            with self.subTest(motor=motor):
                self.assertIsInstance(result, dict)
                self.assertIn("metadata", result)
                self.assertIsInstance(result.get("metadata"), dict)
                self.assertIn("dies", result)
                self.assertIsInstance(result.get("dies"), list)

    def test_snapshot_cost_and_sessions(self):
        for motor, expected in EXPECTED_SNAPSHOT.items():
            with self.subTest(motor=motor):
                metadata = self.results[motor].get("metadata", {})
                self.assertEqual(expected["total_sessions"], metadata.get("total_sessions"))
                self.assertEqual(expected["cost_total"], metadata.get("cost_total"))

    def test_invariant_one_level_per_slot(self):
        for motor, result in self.results.items():
            with self.subTest(motor=motor):
                for dia in result.get("dies", []):
                    for slot in dia.get("sessions", []):
                        items_per_nivell = {}
                        for sessio in slot.get("sessions_simultanees", []):
                            nivell = sessio.get("curs")
                            if not nivell:
                                continue
                            # Un item pot contenir diverses sessions del mateix nivell.
                            item_id = sessio.get("item_id") or sessio.get("item_label") or sessio.get("nom")
                            items_per_nivell.setdefault(nivell, set()).add(item_id)

                        for nivell, item_ids in items_per_nivell.items():
                            self.assertLessEqual(
                                len(item_ids),
                                1,
                                (
                                    f"Motor {motor}: més d'un item per nivell al slot "
                                    f"{dia.get('dia')} {slot.get('hora')} ({nivell}: {sorted(item_ids)})"
                                ),
                            )


if __name__ == "__main__":
    unittest.main()
