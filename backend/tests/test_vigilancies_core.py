"""
Tests de core/vigilancia_core.py (VigilanciaCore). No toca cap base de
dades ni sistema de fitxers real.

Són "characterization tests": capturen el comportament REAL del codi
actual (incloent-hi branques secundàries i casos "lletjos", com
excepcions silencioses) perquè serveixin de xarxa de seguretat davant
de qualsevol canvi futur, encara que algun comportament no sigui ideal.

NOTA: core/vigilancia_data.py (VigilanciaDataManager) queda FORA d'aquest
fitxer: `from models import Vigilancia, converters` hi falla en import
(`converters` no existeix a models.py) — el mòdul no es pot ni carregar
ara mateix. És codi mort/orfe: cap route ni core l'importa actualment
(confirmat: `import main` carrega l'app sencera sense error). No s'ha
arreglat aquí, fora de l'abast d'aquesta tasca.
"""
from config import constants
from core.vigilancia_core import VigilanciaCore


class FakeHorari:
    """Simula el gestor d'horari: `horari` (dict niat dia->hora->prof->activitat)
    i `get_activitat`."""

    def __init__(self, horari=None):
        self.horari = horari or {}

    def get_activitat(self, dia, hora, professor):
        return self.horari.get(dia, {}).get(hora, {}).get(professor)


class FakeAlliberats:
    def __init__(self, disponibles_per_hora):
        self._disponibles = disponibles_per_hora

    def get_tots_disponibles(self, dia, hora, grups_sense_classe):
        return list(self._disponibles.get(hora, []))


def _nucli(**overrides):
    """Crea un VigilanciaCore amb configuració per defecte, sobreescrivible."""
    nucli = VigilanciaCore()
    cfg = dict(
        assignatures_config=None,
        professors=[],
        absents_actuals={},
        horari_gestor=None,
        alliberats_gestor=None,
        grups_sense_classe=set(),
        dia_actual="Dilluns",
    )
    cfg.update(overrides)
    nucli.set_config(**cfg)
    return nucli


# ===== get_categoria_prioritat / is_activitat_auto_assignable =====

def test_categoria_prioritat_retorna_index_de_la_categoria(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"CD"}])
    nucli = _nucli()
    assert nucli.get_categoria_prioritat("Guàrdia") == 0
    assert nucli.get_categoria_prioritat("CD") == 1


def test_categoria_prioritat_no_trobada_retorna_longitud_total(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"CD"}])
    nucli = _nucli()
    assert nucli.get_categoria_prioritat("Inexistent") == 2


def test_activitat_auto_assignable_si_categoria_activa(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"CD"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True, True])
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("Guàrdia") is True


def test_activitat_no_auto_assignable_si_categoria_inactiva(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}, {"CD"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [False, True])
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("Guàrdia") is False


def test_activitat_no_trobada_a_cap_categoria_no_es_assignable(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("Desconeguda") is False


def test_activitat_buida_mai_es_assignable(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("") is False


def test_fallback_defensiu_quan_ordre_prioritats_encara_buit(monkeypatch):
    # Characterization: si encara no s'han carregat categories des de BD
    # (ORDRE_PRIORITATS buit), es fa servir un fallback basat en PRIORITATS.
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [])
    monkeypatch.setattr(constants, "PRIORITATS", {"Guàrdia": 1})
    nucli = _nucli()
    assert nucli.is_activitat_auto_assignable("Guàrdia") is True
    assert nucli.is_activitat_auto_assignable("alliberat") is True
    assert nucli.is_activitat_auto_assignable("QualsevolAltra") is False


# ===== is_professor_assignable =====

def test_professor_absent_no_es_assignable(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    nucli = _nucli(absents_actuals={"Prof_A": ["09:00"]})
    assert nucli.is_professor_assignable("Prof_A", "09:00", "Guàrdia") is False


def test_professor_present_assignable_si_activitat_ho_es(monkeypatch):
    monkeypatch.setattr(constants, "ORDRE_PRIORITATS", [{"Guàrdia"}])
    monkeypatch.setattr(constants, "CATEGORIES_ACTIVES", [True])
    nucli = _nucli(absents_actuals={"Prof_A": ["10:00"]})
    # Absent a una altra hora, no a aquesta -> no bloqueja
    assert nucli.is_professor_assignable("Prof_A", "09:00", "Guàrdia") is True


# ===== buscar_professor_titular: ordre de prioritats =====

def _config_assignatures(assignacions):
    return {"assignatures": {"Matemàtiques": {"assignacions": assignacions}}}


def test_titular_prioritat1_match_exacte_grup_i_aula():
    nucli = _nucli(assignatures_config=_config_assignatures([
        {"grup": "1-ESO-A", "aula": "A01", "titular": "Prof_Exacte"},
        {"grup": "1-ESO-A", "aula": "A02", "titular": "Prof_Altra_Aula"},
    ]))
    assert nucli.buscar_professor_titular("Matemàtiques", "1-ESO-A", "A01") == "Prof_Exacte"


def test_titular_prioritat2_match_grup_ignora_enllac():
    nucli = _nucli(assignatures_config=_config_assignatures([
        {"grup": "1-ESO-A", "aula": "ENLLAÇ", "titular": "Prof_Enllac"},
        {"grup": "1-ESO-A", "aula": "A09", "titular": "Prof_Grup"},
    ]))
    # Cap match d'aula exacta; ha de trobar el del mateix grup, saltant l'ENLLAÇ
    assert nucli.buscar_professor_titular("Matemàtiques", "1-ESO-A", "A99") == "Prof_Grup"


def test_titular_prioritat3_match_nomes_aula():
    nucli = _nucli(assignatures_config=_config_assignatures([
        {"grup": "2-ESO-B", "aula": "A01", "titular": "Prof_Aula"},
    ]))
    assert nucli.buscar_professor_titular("Matemàtiques", "", "A01") == "Prof_Aula"


def test_titular_prioritat4_enllac_amb_grup_compatible():
    nucli = _nucli(assignatures_config=_config_assignatures([
        {"grup": "1-ESO-A-B", "aula": "ENLLAÇ", "titular": "Prof_Enllac"},
    ]))
    # "1-ESO-A" ha de trobar l'ENLLAÇ perquè "1-ESO-A" és part de "1-ESO-A-B"
    assert nucli.buscar_professor_titular("Matemàtiques", "1-ESO-A", "") == "Prof_Enllac"


def test_titular_prioritat5_fallback_primer_de_la_llista():
    nucli = _nucli(assignatures_config=_config_assignatures([
        {"grup": "", "aula": "", "titular": "Prof_Fallback"},
    ]))
    assert nucli.buscar_professor_titular("Matemàtiques", "Cap-Grup", "Cap-Aula") == "Prof_Fallback"


def test_titular_assignatura_no_configurada_retorna_none():
    nucli = _nucli(assignatures_config=_config_assignatures([]))
    assert nucli.buscar_professor_titular("Assignatura_Inexistent") is None


def test_titular_sense_config_retorna_none():
    nucli = _nucli(assignatures_config=None)
    assert nucli.buscar_professor_titular("Matemàtiques") is None


def test_es_titular_per_assignatura_compara_amb_el_trobat():
    nucli = _nucli(assignatures_config=_config_assignatures([
        {"grup": "1-ESO-A", "aula": "A01", "titular": "Prof_Exacte"},
    ]))
    assert nucli.es_titular_per_assignatura("Prof_Exacte", "Matemàtiques", "1-ESO-A", "A01") is True
    assert nucli.es_titular_per_assignatura("Un_Altre", "Matemàtiques", "1-ESO-A", "A01") is False


# ===== validar_professor_disponible_vigilancia =====

def test_validar_disponible_absent_retorna_absent():
    nucli = _nucli(absents_actuals={"Prof_A": ["09:00"]})
    resultat = nucli.validar_professor_disponible_vigilancia("Prof_A", "09:00", set())
    assert resultat == "ABSENT"


def test_validar_disponible_ocupat_examens_retorna_ocupat():
    nucli = _nucli()
    nucli.professors_ocupats_examens = {"09:00": {"Prof_A"}}
    resultat = nucli.validar_professor_disponible_vigilancia("Prof_A", "09:00", set())
    assert resultat == "OCUPAT VIGILÀNCIA"


def test_validar_disponible_ja_assignat_retorna_ja_assignat():
    nucli = _nucli()
    resultat = nucli.validar_professor_disponible_vigilancia("Prof_A", "09:00", {"Prof_A"})
    assert resultat == "JA ASSIGNAT"


def test_validar_disponible_sense_conflicte_retorna_buit():
    nucli = _nucli()
    resultat = nucli.validar_professor_disponible_vigilancia("Prof_A", "09:00", set())
    assert resultat == ""


def test_validar_disponible_prioritza_absent_sobre_ja_assignat():
    # Characterization: si és absent I ja està assignat, guanya "ABSENT"
    # (es comprova primer), no "JA ASSIGNAT".
    nucli = _nucli(absents_actuals={"Prof_A": ["09:00"]})
    resultat = nucli.validar_professor_disponible_vigilancia("Prof_A", "09:00", {"Prof_A"})
    assert resultat == "ABSENT"


# ===== get_disponibles_for_vigilance =====

def test_disponibles_for_vigilance_sense_alliberats_gestor_retorna_buit():
    nucli = _nucli(alliberats_gestor=None)
    assert nucli.get_disponibles_for_vigilance("09:00", {"hora": "09:00"}) == []


def test_disponibles_for_vigilance_usa_grups_per_hora_si_es_dict():
    capturat = {}

    class AlliberatsEspia(FakeAlliberats):
        def get_tots_disponibles(self, dia, hora, grups_sense_classe):
            capturat["grups"] = grups_sense_classe
            return [("Prof_A", "alliberat", "")]

    nucli = _nucli(
        alliberats_gestor=AlliberatsEspia({}),
        grups_sense_classe={"09:00": {"1-ESO-A"}, "10:00": {"2-ESO-B"}},
    )
    resultat = nucli.get_disponibles_for_vigilance("09:00", {"hora": "09:00"})
    assert resultat == [("Prof_A", "alliberat", "")]
    assert capturat["grups"] == {"1-ESO-A"}


def test_disponibles_for_vigilance_usa_set_pla_com_a_fallback():
    capturat = {}

    class AlliberatsEspia(FakeAlliberats):
        def get_tots_disponibles(self, dia, hora, grups_sense_classe):
            capturat["grups"] = grups_sense_classe
            return []

    nucli = _nucli(alliberats_gestor=AlliberatsEspia({}), grups_sense_classe={"1-ESO-A"})
    nucli.get_disponibles_for_vigilance("09:00", {"hora": "09:00"})
    assert capturat["grups"] == {"1-ESO-A"}


def test_disponibles_for_vigilance_no_filtra_absents(monkeypatch):
    # Characterization explícita del comentari del codi: a diferència de
    # substitucions, aquí NO es filtren els absents (es mostren amb avís).
    nucli = _nucli(
        alliberats_gestor=FakeAlliberats({"09:00": [("Prof_Absent", "alliberat", "")]}),
        absents_actuals={"Prof_Absent": ["09:00"]},
    )
    resultat = nucli.get_disponibles_for_vigilance("09:00", {"hora": "09:00"})
    assert resultat == [("Prof_Absent", "alliberat", "")]


def test_disponibles_for_vigilance_excepcio_silenciosa_retorna_buit():
    # Characterization: si el col·laborador peta, l'excepció s'empassa en
    # silenci (except Exception: return []) sense cap log ni rastre.
    class AlliberatsTrencat:
        def get_tots_disponibles(self, dia, hora, grups_sense_classe):
            raise RuntimeError("simulat")

    nucli = _nucli(alliberats_gestor=AlliberatsTrencat())
    assert nucli.get_disponibles_for_vigilance("09:00", {"hora": "09:00"}) == []


# ===== get_titular_status =====

def test_titular_status_absent():
    nucli = _nucli(absents_actuals={"Prof_A": ["09:00"]})
    assert nucli.get_titular_status("Prof_A", "09:00") == "absent"


def test_titular_status_alliberat_via_disponibles():
    nucli = _nucli(alliberats_gestor=FakeAlliberats({"09:00": [("Prof_A", "alliberat", "")]}))
    assert nucli.get_titular_status("Prof_A", "09:00") == "alliberat"


def test_titular_status_disponible_via_altres_tipus():
    nucli = _nucli(alliberats_gestor=FakeAlliberats({"09:00": [("Prof_A", "Guàrdia", "")]}))
    assert nucli.get_titular_status("Prof_A", "09:00") == "disponible"


def test_titular_status_classe_amb_horari():
    horari = FakeHorari({"Dilluns": {"09:00": {"Prof_A": {"grup": "1-ESO-A", "assignatura": "Matemàtiques"}}}})
    nucli = _nucli(horari_gestor=horari, grups_sense_classe=set())
    assert nucli.get_titular_status("Prof_A", "09:00") == "classe"


def test_titular_status_alliberat_si_grup_a_grups_sense_classe():
    horari = FakeHorari({"Dilluns": {"09:00": {"Prof_A": {"grup": "1-ESO-A", "assignatura": "Matemàtiques"}}}})
    nucli = _nucli(horari_gestor=horari, grups_sense_classe={"1-ESO-A"})
    assert nucli.get_titular_status("Prof_A", "09:00") == "alliberat"


def test_titular_status_lliure_sense_activitat():
    horari = FakeHorari({"Dilluns": {"09:00": {}}})
    nucli = _nucli(horari_gestor=horari)
    assert nucli.get_titular_status("Prof_A", "09:00") == "lliure"


def test_titular_status_lliure_si_horari_peta(monkeypatch):
    class HorariTrencat:
        def get_activitat(self, dia, hora, professor):
            raise RuntimeError("simulat")

    nucli = _nucli(horari_gestor=HorariTrencat())
    # Characterization: qualsevol excepció consultant l'horari es tradueix
    # silenciosament en "lliure" (comportament optimista per defecte).
    assert nucli.get_titular_status("Prof_A", "09:00") == "lliure"


def test_titular_status_sense_horari_gestor_retorna_lliure():
    nucli = _nucli(horari_gestor=None)
    assert nucli.get_titular_status("Prof_A", "09:00") == "lliure"


# ===== extract_professor_name =====

def test_extract_professor_name_neteja_emojis_i_parentesi():
    assert VigilanciaCore().extract_professor_name("👨‍🏫 Prof_A (Guàrdia)") == "Prof_A"


def test_extract_professor_name_neteja_avis():
    assert VigilanciaCore().extract_professor_name("⚠️ Prof_B") == "Prof_B"


def test_extract_professor_name_sense_res_a_netejar():
    assert VigilanciaCore().extract_professor_name("Prof_C") == "Prof_C"


# ===== get_professors_que_tenien_grup =====

def test_professors_que_tenien_grup_match_exacte():
    horari = FakeHorari({"Dilluns": {"09:00": {
        "Prof_A": {"grup": "1-ESO-A", "assignatura": "Matemàtiques"},
        "Prof_B": {"grup": "2-ESO-B", "assignatura": "Castellà"},
    }}})
    nucli = _nucli(horari_gestor=horari)
    resultat = nucli.get_professors_que_tenien_grup("1-ESO-A", "09:00", randomize=False)
    assert resultat == ["Prof_A"]


def test_professors_que_tenien_grup_match_grup_composat():
    horari = FakeHorari({"Dilluns": {"09:00": {
        "Prof_A": {"grup": "4-ESO-ABC", "assignatura": "Matemàtiques"},
    }}})
    nucli = _nucli(horari_gestor=horari)
    resultat = nucli.get_professors_que_tenien_grup("4-ESO-A", "09:00", randomize=False)
    assert resultat == ["Prof_A"]


def test_professors_que_tenien_grup_ignora_sense_assignatura():
    horari = FakeHorari({"Dilluns": {"09:00": {
        "Prof_A": {"grup": "1-ESO-A", "assignatura": ""},
    }}})
    nucli = _nucli(horari_gestor=horari)
    assert nucli.get_professors_que_tenien_grup("1-ESO-A", "09:00", randomize=False) == []


def test_professors_que_tenien_grup_multiples_grups_separats_per_coma():
    horari = FakeHorari({"Dilluns": {"09:00": {
        "Prof_A": {"grup": "1-ESO-A", "assignatura": "Matemàtiques"},
        "Prof_B": {"grup": "2-ESO-B", "assignatura": "Castellà"},
    }}})
    nucli = _nucli(horari_gestor=horari)
    resultat = sorted(nucli.get_professors_que_tenien_grup("1-ESO-A, 2-ESO-B", "09:00", randomize=False))
    assert resultat == ["Prof_A", "Prof_B"]


def test_professors_que_tenien_grup_sense_grup_retorna_buit():
    nucli = _nucli(horari_gestor=FakeHorari())
    assert nucli.get_professors_que_tenien_grup("", "09:00") == []


def test_professors_que_tenien_grup_sense_horari_gestor_retorna_buit():
    nucli = _nucli(horari_gestor=None)
    assert nucli.get_professors_que_tenien_grup("1-ESO-A", "09:00") == []


# ===== get_vigilants_assignats_hora =====

def test_vigilants_assignats_hora_placeholder_sempre_buit():
    # Characterization: el mètode és un placeholder no implementat, sempre
    # retorna un set buit independentment de l'estat real.
    nucli = _nucli()
    assert nucli.get_vigilants_assignats_hora("09:00") == set()


