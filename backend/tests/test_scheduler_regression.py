"""
Regressió dels motors del planificador d'exàmens (v2, v2-backtrack, v3).

Fa servir l'horari de la institució d'exemple (data/exemple/teachers.xml, que
es distribueix amb el repositori) i una configuració d'exàmens de 2-BAT
definida aquí mateix, sense cap base de dades. Els titulars són els
professors de l'XML d'exemple (Prof N) que fan classe a 2-BAT.

Si un canvi al motor fa variar EXPECTED_SNAPSHOT de manera intencionada,
torna a executar el test, revisa els valors nous i actualitza'ls.
"""
import io
import json
import random
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
from routes.scheduler_helpers import extreure_hores_examen_des_alliberaments
from scheduler_engine.factory import crear_motor


XML_PATH = BACKEND_DIR.parent / "data" / "exemple" / "teachers.xml"

NIVELL = "2-BAT"
DURADA_TITULAR = 2
DATES = ["2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23"]  # dl-dj

# assignatura -> [(grup, titular)]
ASSIGNACIONS = {
    "Català": [("2-BAT-A", "Prof 28"), ("2-BAT-B", "Prof 28")],
    "Castellà": [("2-BAT-A", "Prof 18"), ("2-BAT-B", "Prof 18")],
    "Anglès": [("2-BAT-A", "Prof 15"), ("2-BAT-B", "Prof 15")],
    "Història": [("2-BAT-A", "Prof 9"), ("2-BAT-B", "Prof 9")],
    "Filosofia": [("2-BAT-A", "Prof 48"), ("2-BAT-B", "Prof 48")],
    "2.1": [("2-BAT-A", "Prof 7")],
    "2.2": [("2-BAT-A", "Prof 20")],
    "2.3": [("2-BAT-A", "Prof 31")],
    "2.4": [("2-BAT-A", "Prof 3")],
}

# Snapshot de regressió amb les dades d'aquest fitxer.
EXPECTED_SNAPSHOT = {
    "v2": {"cost_total": 250.0, "total_sessions": 9},
    "v2-backtrack": {"cost_total": 250, "total_sessions": 9},
    "v3": {"cost_total": 250.0, "total_sessions": 9},
}


def _config_examens():
    return {
        "assignatures": {
            assignatura: {
                "assignacions": [
                    {"grup": grup, "titular": titular, "aula": ""}
                    for grup, titular in assignacions
                ]
            }
            for assignatura, assignacions in ASSIGNACIONS.items()
        }
    }


def _restriccions():
    return {
        "restriccions_dures": {
            "no_mateix_dia": [["Català (2-BAT)", "Castellà (2-BAT)", "Anglès (2-BAT)"]],
            "no_mateix_slot": {},
            "mateix_slot": [
                {"nom": "Modalitat 1", "assignatures": ["2.1 (2-BAT)", "2.2 (2-BAT)"], "pes": 100},
                {"nom": "Modalitat 2", "assignatures": ["2.3 (2-BAT)", "2.4 (2-BAT)"], "pes": 100},
            ],
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
        "pesos_percentatge": {
            "substitucio": 80,
            "professor_abans": 30,
            "professor_despres": 30,
            "professor_no_treballa": 60,
        },
        "costos_professors": {
            "globals": {
                "substitucio": 80,
                "abans_jornada": 30,
                "despres_jornada": 30,
                "no_treballa_dia": 60,
            },
            "individuals": {},
        },
    }


def _alliberaments():
    # Exàmens a les 08:00 i a les 11:30 (i=true); la resta, només alliberats.
    slots = {
        "08:00": {"a": True, "i": True},
        "09:00": {"a": True, "i": False},
        "11:30": {"a": True, "i": True},
        "12:30": {"a": True, "i": False},
    }
    return {
        NIVELL: {
            "durada": DURADA_TITULAR,
            "dates": list(DATES),
            "config": {data: dict(slots) for data in DATES},
        }
    }


CAT_DIES = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]


def _dies_utilitzar(dates):
    dies = []
    for data in sorted(dates):
        nom = CAT_DIES[datetime.strptime(data, "%Y-%m-%d").weekday()]
        if nom not in dies:
            dies.append(nom)
    return dies


class SchedulerRegressioExempleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not XML_PATH.exists():
            raise unittest.SkipTest(f"No es troba l'XML d'exemple a {XML_PATH}")

        cls.alliberaments = _alliberaments()
        cls.hores_examen, cls.hores_per_nivell = extreure_hores_examen_des_alliberaments(
            cls.alliberaments
        )
        cls.dies_utilitzar = _dies_utilitzar(DATES)
        cls.dia_a_data_iso = construir_mapa_dia_data_iso(
            dies_utilitzar=cls.dies_utilitzar,
            selected_dates=DATES,
            data_inici_iso=min(DATES),
        )

        cls._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmpdir.name)
        cls.cfg_path = tmp / "config.json"
        cls.restr_path = tmp / "restriccions.json"
        cls.cfg_path.write_text(json.dumps(_config_examens(), ensure_ascii=False), encoding="utf-8")
        cls.restr_path.write_text(json.dumps(_restriccions(), ensure_ascii=False), encoding="utf-8")

        cls.results = {motor: cls._run_motor(motor) for motor in EXPECTED_SNAPSHOT}

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

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
            str(cls.cfg_path),
            str(XML_PATH),
            restriccions_path=str(cls.restr_path),
            ultim_professor="",
            nivells_actius=[NIVELL],
            hores_examen=cls.hores_examen,
            hores_per_nivell=cls.hores_per_nivell,
            durada_titular=DURADA_TITULAR,
            no_substituir={"Guàrdia"},
            alliberaments_per_nivell=cls.alliberaments,
            **override_params,
        )
        gen.carregar_dades()
        gen.carregar_horaris_professors()

        kwargs = {
            "data_inici": datetime.strptime(min(DATES), "%Y-%m-%d").strftime("%d/%m/%Y"),
            "data_inici_iso": min(DATES),
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
            result = getattr(gen, method_name)(**kwargs)

        if motor == "v2-backtrack":
            result = result[0] if result else {"metadata": {}}

        return result

    def test_motors_return_expected_structure(self):
        for motor, result in self.results.items():
            with self.subTest(motor=motor):
                self.assertIsInstance(result, dict)
                self.assertIsInstance(result.get("metadata"), dict)
                self.assertIsInstance(result.get("dies"), list)

    def test_snapshot_cost_and_sessions(self):
        for motor, expected in EXPECTED_SNAPSHOT.items():
            with self.subTest(motor=motor):
                metadata = self.results[motor].get("metadata", {})
                self.assertEqual(expected["total_sessions"], metadata.get("total_sessions"))
                self.assertEqual(expected["cost_total"], metadata.get("cost_total"))

    def test_restriccions_respectades(self):
        restriccions = _restriccions()["restriccions_dures"]
        for motor, result in self.results.items():
            with self.subTest(motor=motor):
                slot_de, dia_de = {}, {}
                for dia in result.get("dies", []):
                    for slot in dia.get("sessions", []):
                        for sessio in slot.get("sessions_simultanees", []):
                            slot_de[sessio.get("nom")] = (dia.get("dia"), slot.get("hora"))
                            dia_de[sessio.get("nom")] = dia.get("dia")

                self.assertEqual(
                    {f"{a} ({NIVELL})" for a in ASSIGNACIONS}, set(slot_de),
                    f"Motor {motor}: no s'han programat totes les assignatures",
                )
                for grup in restriccions["mateix_slot"]:
                    slots = {slot_de[nom] for nom in grup["assignatures"]}
                    self.assertEqual(1, len(slots), f"Motor {motor}: {grup['nom']} separada")
                for noms in restriccions["no_mateix_dia"]:
                    dies = [dia_de[nom] for nom in noms]
                    self.assertEqual(len(dies), len(set(dies)), f"Motor {motor}: {noms} el mateix dia")

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
