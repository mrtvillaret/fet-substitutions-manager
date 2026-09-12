"""
Tests de exam_import.py: deducció de nivell i generació de propostes
d'assignacions a partir d'un horari ja carregat.
"""
from exam_import import deriva_nivell, generar_propostes


class HorariFals:
    """Simula prou de GestorHorariWeb perquè generar_propostes hi treballi:
    només cal l'atribut .horari amb la mateixa forma que fa servir la funció
    (horari[dia][hora][professor] = {"assignatura", "grup", "aula"})."""

    def __init__(self, horari):
        self.horari = horari


def test_deriva_nivell_amb_subgrup():
    assert deriva_nivell("1-ESO-A") == "1-ESO"
    assert deriva_nivell("4-ESO-C") == "4-ESO"


def test_deriva_nivell_grup_nu():
    # Sense sufix de lletres: es proposa tal qual (no s'inventa cap subgrup)
    assert deriva_nivell("1-BATX") == "1-BATX"


def test_deriva_nivell_combinat():
    # Sufix de diverses lletres (grup combinat ja fusionat): treu el nivell igual
    assert deriva_nivell("1-BATX-AB") == "1-BATX"


def test_generar_propostes_ignora_activitats_sense_grup():
    horari = HorariFals({
        "Dilluns": {
            "08:00": {
                "Zapata_M": {"assignatura": "Guàrdia", "grup": "", "aula": ""},
            }
        }
    })
    assert generar_propostes(horari) == []


def test_generar_propostes_ignora_hores_sense_assignatura():
    horari = HorariFals({
        "Dilluns": {
            "08:00": {
                "Zapata_M": {"assignatura": "", "grup": "1-ESO-A", "aula": ""},
            }
        }
    })
    assert generar_propostes(horari) == []


def test_generar_propostes_cas_normal():
    horari = HorariFals({
        "Dilluns": {
            "08:00": {
                "Zapata_M": {"assignatura": "Llatí", "grup": "1-BATX-A", "aula": "A01"},
            }
        }
    })
    propostes = generar_propostes(horari)
    assert propostes == [{
        "assignatura": "Llatí",
        "grup": "1-BATX-A",
        "titular": "Zapata_M",
        "aula": "A01",
        "nivell": "1-BATX",
    }]


def test_generar_propostes_assignatura_sense_transformacio():
    # No es toca el nom de l'assignatura (sense codis, sense majúscules, etc.)
    horari = HorariFals({
        "Dilluns": {
            "08:00": {
                "Prof": {"assignatura": "  1.1-Optativa X  ", "grup": "1-ESO-A", "aula": ""},
            }
        }
    })
    propostes = generar_propostes(horari)
    assert propostes[0]["assignatura"] == "1.1-Optativa X"


def test_generar_propostes_aula_mes_freqüent():
    # Si la mateixa combinació assignatura+grup+titular surt amb aules
    # diferents a hores diferents, es proposa la més freqüent.
    horari = HorariFals({
        "Dilluns": {
            "08:00": {"Prof": {"assignatura": "Mates", "grup": "1-ESO-A", "aula": "A01"}},
            "09:00": {"Prof": {"assignatura": "Mates", "grup": "1-ESO-A", "aula": "A01"}},
        },
        "Dimarts": {
            "08:00": {"Prof": {"assignatura": "Mates", "grup": "1-ESO-A", "aula": "A02"}},
        },
    })
    propostes = generar_propostes(horari)
    assert len(propostes) == 1
    assert propostes[0]["aula"] == "A01"


def test_generar_propostes_ordenades():
    horari = HorariFals({
        "Dilluns": {
            "08:00": {
                "ProfB": {"assignatura": "Zoologia", "grup": "1-ESO-A", "aula": ""},
                "ProfA": {"assignatura": "Anglès", "grup": "1-ESO-A", "aula": ""},
            }
        }
    })
    propostes = generar_propostes(horari)
    assert [p["assignatura"] for p in propostes] == ["Anglès", "Zoologia"]
