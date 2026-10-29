"""
Tests dels PDF (routes/pdf.py i routes/informes.py): el text que escriuen els
usuaris (camps de vigilàncies, substitut, comentaris) ha d'arribar al PDF com
a text, no interpretat com a etiquetes de ReportLab. Abans, un simple
"Examen <font" feia fallar el PDF de tot el dia, i "<img src=...>" feia que el
generador llegís fitxers del servidor.
"""

import uuid

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from rate_limit import limiter
from routes import informes, pdf
from substitucions import router as substitucions
from vigilancies.router import router as vigilancies_router

APP = crea_app(vigilancies_router, substitucions.router, pdf.router, informes.router)
DATA = "2026-04-20"  # dilluns
TEXT_PERILLÓS = "Aula <font"  # etiqueta sense tancar
IMATGE = "<img src='/etc/hostname' width='9' height='9'/>"
MARCATGE = "<b>negreta</b>"

PDFS = [
    f"/api/pdf/vigilancies/{DATA}",
    f"/api/pdf/complete/{DATA}",
    f"/api/pdf/vigilancies/interval?data_inici={DATA}&data_final={DATA}",
    f"/api/informes/direccio?data_inici={DATA}&data_final={DATA}",
    f"/api/informes/professor?data_inici={DATA}&data_final={DATA}&mostrar_taules=true",
]


@pytest.fixture(autouse=True)
def _limiter_net():
    limiter.reset()
    yield


@pytest.fixture
def centre():
    return nova_institucio(amb_xml=True)


@pytest.fixture
def client(centre):
    nom = f"admin_{uuid.uuid4().hex[:8]}"
    crea_usuari(nom, centre, "admin")
    return entra(client_per(APP), nom)


def _prepara(client, valor):
    """Vigilància i substitució amb `valor` a tots els camps de text lliure."""
    resp = client.post(
        f"/api/vigilancies/{DATA}",
        json={
            "hora": "10:00",
            "tipus": valor,
            "grups": valor,
            "aula": valor,
            "vigilant": "Prof 21",
            "comentaris": valor,
            "nivell": valor,
        },
    )
    assert resp.status_code == 200, resp.text
    client.put(f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["11:30"], "updated_at_map": {}})
    assert any(
        s["hora"] == "11:30" for s in client.get(f"/api/substitucions/{DATA}", params={"include_all": True}).json()
    )
    resp = client.put(
        f"/api/substitucions/{DATA}/11:30/Prof 15", json={"substitut": valor, "comentaris": valor, "force": True}
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("ruta", PDFS)
@pytest.mark.parametrize("valor", [TEXT_PERILLÓS, IMATGE, MARCATGE])
def test_el_text_dels_usuaris_no_trenca_ni_s_interpreta_al_pdf(client, ruta, valor):
    _prepara(client, valor)
    resp = client.get(ruta)
    assert resp.status_code == 200, resp.text[:300]
    assert resp.headers["content-type"] == "application/pdf"


# ------------------------------------------------ espai per escriure a mà


def _text_pdf(contingut: bytes) -> str:
    """Text del PDF amb pdftotext (poppler-utils); sense l'eina, el test se salta."""
    import shutil
    import subprocess

    if not shutil.which("pdftotext"):
        pytest.skip("cal pdftotext (poppler-utils)")
    return subprocess.run(["pdftotext", "-", "-"], input=contingut, capture_output=True, check=True).stdout.decode()


def _hores_del_pdf(client, **params):
    client.put(f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["11:30"], "updated_at_map": {}})
    resp = client.get(f"/api/pdf/complete/{DATA}", params=params)
    assert resp.status_code == 200, resp.text[:300]
    return [linia for linia in _text_pdf(resp.content).splitlines() if linia.startswith("Hora ")]


def test_per_defecte_nomes_surten_les_hores_amb_substitucions(client):
    assert _hores_del_pdf(client) == ["Hora 11:30"]


def test_amb_espai_a_ma_surten_les_hores_on_hi_pot_haver_substitucions(client):
    # Dilluns a l'horari d'exemple: hi ha classe a totes les hores menys al pati,
    # a les 13:30, a les 14:30 i a les 17:00, on ningú no té cap activitat.
    hores = _hores_del_pdf(client, blank_rows=True)
    assert sorted(hores) == sorted(f"Hora {h}" for h in ["08:00", "09:00", "10:00", "11:30", "12:30", "15:00", "16:00"])


def test_l_espai_a_ma_no_afecta_el_pdf_nomes_de_vigilancies(client):
    assert _hores_del_pdf(client, blank_rows=True, include_substitutions=False) == []


# ------------------------------------------------ format «taula del dia»


def _text_dia(client, **params):
    client.put(f"/api/substitucions/{DATA}/absencies/Prof 15", json={"hores_absencia": ["11:30"], "updated_at_map": {}})
    client.post(
        f"/api/vigilancies/{DATA}",
        json={
            "hora": "10:00",
            "tipus": "Física",
            "grups": "2-BAT-A",
            "aula": "A01",
            "vigilant": "Prof 21",
            "nivell": "2-BAT",
        },
    )
    resp = client.get(f"/api/pdf/complete/{DATA}", params={"format": "dia", **params})
    assert resp.status_code == 200, resp.text[:300]
    return _text_pdf(resp.content)


def test_format_dia_una_taula_amb_substitucions_i_vigilancies(client):
    text = _text_dia(client)
    assert "Hora 11:30" not in text  # sense títols per hora
    assert "Prof 15" in text and "Física" in text and "Prof 21" in text
    assert "Absent / Curs" in text and "Substitut / Vigilant" in text  # una sola capçalera
    assert "Les files en cursiva amb fons de color" in text  # nota de les vigilàncies


@pytest.mark.parametrize(
    "idioma, etiquetes",
    [
        ("es", ["Ausente / Curso", "Grupo / Aula", "Sustituto / Vigilante", "vigilancias de examen"]),
        ("en", ["Absent / Course", "Group / Classroom", "Substitute / Invigilator", "exam invigilations"]),
        ("it", ["Assente / Anno", "Gruppo / Aula", "Supplente / Sorvegliante", "sorveglianze d"]),
    ],
)
def test_la_capcalera_combinada_i_la_nota_es_tradueixen(client, centre, idioma, etiquetes):
    from database import get_data_db_session
    from repositories import ConfiguracioRepository

    with get_data_db_session(centre) as db:
        ConfiguracioRepository.set(db, "idioma", idioma)
        db.commit()
    text = " ".join(_text_dia(client).split())
    for etiqueta in etiquetes:
        assert etiqueta in text, (etiqueta, text[:400])


def test_format_dia_amb_espai_a_ma_mostra_les_hores_detectades(client):
    linies = [linia.strip() for linia in _text_dia(client, blank_rows=True).splitlines()]
    for hora in ("08:00", "15:00", "16:00"):
        assert hora in linies
    # (per línies: el peu «Generat ... a les 17:05» no ha de comptar)
    assert "17:00" not in linies and "PATI" not in linies


def test_format_desconegut_dona_400(client):
    assert client.get(f"/api/pdf/complete/{DATA}", params={"format": "x"}).status_code == 400


def test_format_dia_sense_espai_a_ma_nomes_mostra_les_hores_amb_files(client):
    # Abans hi sortien totes les hores amb classe, amb una fila en blanc (i una
    # hora buida quan les seves absències no es mostraven)
    linies = [linia.strip() for linia in _text_dia(client).splitlines()]
    assert "10:00" in linies and "11:30" in linies
    for hora in ("08:00", "09:00", "12:30", "15:00", "16:00", "17:00", "PATI"):
        assert hora not in linies


def test_format_dia_amb_lletra_mes_gran(client):
    text = _text_dia(client, mida_lletra=1.35)
    assert "Prof 15" in text and "Prof 21" in text


def test_mida_de_lletra_desconeguda_dona_400(client):
    resp = client.get(f"/api/pdf/complete/{DATA}", params={"format": "dia", "mida_lletra": 3})
    assert resp.status_code == 400


# ------------------------------------------- disponibles de tots els dies


def test_el_pdf_de_disponibles_de_tots_els_dies_comenca_a_la_data_donada(client):
    resp = client.post("/api/pdf/disponibles-tots-dies", json={"data_inici": DATA})
    assert resp.status_code == 200, resp.text[:300]
    assert resp.headers["content-type"] == "application/pdf"


def test_el_pdf_de_disponibles_amb_una_data_mal_escrita_dona_400(client):
    # Abans començava avui sense dir res
    assert client.post("/api/pdf/disponibles-tots-dies", json={"data_inici": "20/04/2026"}).status_code == 400


# ------------------------------------------------ ordre de les substitucions


@pytest.mark.parametrize(
    "ordre, esperat",
    [
        # 10:00: Prof 15 fa Anglès amb 3-ESO-A i Prof 1, E.F. amb 3-ESO-C
        (None, ["Prof 15", "Prof 1"]),  # sense ordre: per curs
        ("curs", ["Prof 15", "Prof 1"]),
        ("professor", ["Prof 1", "Prof 15"]),
    ],
)
def test_el_pdf_segueix_l_ordre_triat_a_la_pantalla(client, ordre, esperat):
    import re

    for professor in ("Prof 15", "Prof 1"):
        client.put(
            f"/api/substitucions/{DATA}/absencies/{professor}", json={"hores_absencia": ["10:00"], "updated_at_map": {}}
        )
    resp = client.get(f"/api/pdf/complete/{DATA}", params={"ordre": ordre} if ordre else {})
    assert resp.status_code == 200, resp.text[:300]
    text = _text_pdf(resp.content)
    posicions = {p: re.search(rf"{p}(?!\d)", text).start() for p in ("Prof 15", "Prof 1")}
    assert sorted(posicions, key=posicions.get) == esperat


def test_un_ordre_desconegut_dona_400(client):
    assert client.get(f"/api/pdf/complete/{DATA}", params={"ordre": "nom"}).status_code == 400
