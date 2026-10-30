"""
Tests dels PDF (pdf/router.py i pdf/informes.py): el text que escriuen els
usuaris (camps de vigilàncies, substitut, comentaris) ha d'arribar al PDF com
a text, no interpretat com a etiquetes de ReportLab. Abans, un simple
"Examen <font" feia fallar el PDF de tot el dia, i "<img src=...>" feia que el
generador llegís fitxers del servidor.
"""

import uuid

import pytest
from suport_api import client_per, crea_app, crea_usuari, entra, nova_institucio

from pdf import generacio, informes, services
from pdf import router as pdf
from rate_limit import limiter
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


@pytest.mark.parametrize(
    "ruta, params",
    [
        (f"/api/pdf/complete/{DATA}", {}),
        (f"/api/pdf/vigilancies/{DATA}", {}),
        ("/api/pdf/vigilancies/interval", {"data_inici": DATA, "data_final": DATA}),
    ],
)
@pytest.mark.parametrize("opcio", [{"format": "x"}, {"mida_lletra": 3}])
def test_un_format_o_una_mida_desconeguts_no_deixen_directoris_temporals(
    client, monkeypatch, tmp_path, ruta, params, opcio
):
    _prepara(client, "Física")
    monkeypatch.setattr(generacio.tempfile, "gettempdir", lambda: str(tmp_path))

    resposta = client.get(ruta, params={**params, **opcio})

    assert resposta.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_pdf_complet_sense_cap_seccio_dona_400(client):
    resposta = client.get(
        f"/api/pdf/complete/{DATA}",
        params={"include_substitutions": False, "include_vigilancies": False},
    )

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "Cal incloure almenys una secció al PDF"


# ------------------------------------------- disponibles de tots els dies


def test_el_pdf_de_disponibles_de_tots_els_dies_comenca_a_la_data_donada(client):
    resp = client.post("/api/pdf/disponibles-tots-dies", json={"data_inici": DATA})
    assert resp.status_code == 200, resp.text[:300]
    assert resp.headers["content-type"] == "application/pdf"


def test_el_pdf_de_disponibles_amb_una_data_mal_escrita_dona_400(client):
    # Abans començava avui sense dir res
    assert client.post("/api/pdf/disponibles-tots-dies", json={"data_inici": "20/04/2026"}).status_code == 400


def test_disponibles_informa_del_dia_que_falla_i_esborra_el_temporal(client, monkeypatch, tmp_path):
    def falla_dia(data, institucio):
        raise RuntimeError("fallada simulada")

    monkeypatch.setattr(pdf.Dia, "de_text", falla_dia)
    monkeypatch.setattr(pdf.tempfile, "gettempdir", lambda: str(tmp_path))

    resposta = client.post("/api/pdf/disponibles-tots-dies", json={"data_inici": DATA})

    assert resposta.status_code == 500
    assert DATA in resposta.json()["detail"]
    assert list(tmp_path.iterdir()) == []


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


def test_interval_carrega_l_horari_vigent_de_cada_data(client, monkeypatch):
    data_seguent = "2026-04-21"
    for data in (DATA, data_seguent):
        resposta = client.post(
            f"/api/vigilancies/{data}",
            json={
                "hora": "10:00",
                "tipus": "Física",
                "grups": "2-BAT-A",
                "aula": "A01",
                "vigilant": "Prof 21",
                "nivell": "2-BAT",
            },
        )
        assert resposta.status_code == 200, resposta.text

    original = pdf.Dia.de_text
    dates_carregades = []

    def registra_data(data, institucio):
        dates_carregades.append(data)
        return original(data, institucio)

    monkeypatch.setattr(pdf.Dia, "de_text", registra_data)
    resposta = client.get(
        "/api/pdf/vigilancies/interval",
        params={"data_inici": DATA, "data_final": data_seguent},
    )
    assert resposta.status_code == 200, resposta.text[:300]
    assert set(dates_carregades) >= {DATA, data_seguent}


def test_interval_informa_si_l_exportador_no_genera_fitxer(client, monkeypatch, tmp_path):
    resposta = client.post(
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
    assert resposta.status_code == 200, resposta.text
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    monkeypatch.setattr(generacio.tempfile, "mkdtemp", lambda: str(export_dir))
    monkeypatch.setattr(generacio.PDFCompletExporter, "exportar", lambda *args, **kwargs: "")

    resposta = client.get(
        "/api/pdf/vigilancies/interval",
        params={"data_inici": DATA, "data_final": DATA},
    )

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == "No s'ha generat el fitxer PDF de l'interval"
    assert not export_dir.exists()


@pytest.mark.parametrize("informe", ["direccio", "professor", "professors-llista"])
def test_informes_rebutgen_un_interval_invertit(client, informe):
    resposta = client.get(
        f"/api/informes/{informe}",
        params={"data_inici": "2026-04-21", "data_final": DATA},
    )

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "La data inicial ha de ser anterior o igual a la final"


def test_informe_direccio_compta_nomes_les_absencies_cobertes_de_l_interval(client, centre):
    import sqlite3

    from database import get_data_db_session, get_data_dir_for_institucio

    conn = sqlite3.connect(get_data_dir_for_institucio(centre) / "gestor.db")
    conn.executemany(
        "INSERT INTO professors_baixa (professor, data_inici, data_final) VALUES (?, ?, ?)",
        [
            ("Abans", "2026-03-01", "2026-03-10"),
            ("Dins", "2026-04-15", "2026-04-22"),
            ("Després", "2026-05-01", "2026-05-10"),
        ],
    )
    conn.commit()
    conn.close()

    with get_data_db_session(centre) as db:
        dades = services.dades_direccio(db, DATA, DATA, [])

    assert dades["stats"]["total_baixes"] == 1


def test_els_informes_llegeixen_les_substitucions_per_data(centre):
    # Una substitució creada més tard d'un dia anterior va abans: l'ordre
    # decideix els empats dels rànquings de l'informe de direcció
    from datetime import date

    from database import get_data_db_session
    from models import Substitucio
    from pdf.repositories import InformesRepository

    with get_data_db_session(centre) as db:
        for dia, professor in ((date(2026, 3, 3), "Prof 2"), (date(2026, 3, 2), "Prof 1")):
            db.add(Substitucio(data=dia, hora="08:00", professor_absent=professor, tipus_absencia="ABSENCIA"))
        db.commit()
        files = InformesRepository.substitucions_entre(db, "2026-03-01", "2026-03-31")

    assert [(f["data"], f["professor_absent"]) for f in files] == [("2026-03-02", "Prof 1"), ("2026-03-03", "Prof 2")]


def test_l_informe_d_un_professor_nomes_inclou_aquell_professor(centre):
    # Abans filtrava per un tros del nom: «Prof 1» també treia Prof 10 i Prof 15
    from datetime import date

    from database import get_data_db_session
    from models import Substitucio

    with get_data_db_session(centre) as db:
        for professor in ("Prof 1", "Prof 10", "Prof 15"):
            db.add(
                Substitucio(
                    data=date(2026, 4, 20),
                    hora="08:00",
                    professor_absent=professor,
                    grup="1-ESO-A",
                    assignatura="Català",
                    tipus_absencia="ABSENCIA",
                )
            )
        db.commit()

        def noms(professor):
            return [p["nom"] for p in services.dades_professors(db, DATA, DATA, professor)]

        assert noms("Prof 1") == ["Prof 1"]
        assert noms(" prof 1 ") == ["Prof 1"]
        assert noms("Prof") == []
        assert noms(None) == ["Prof 1", "Prof 10", "Prof 15"]


def test_l_informe_de_direccio_nomes_compta_absencies_i_serveis(centre):
    # Una vigilància de vigilant absent es pot resoldre reassignant-la (sense
    # substitució) o posant-hi substitut: no compta, com les encadenades i les
    # vigilàncies (FUNCIONAMENT.md, apartat 6)
    from datetime import date

    from database import get_data_db_session
    from models import Substitucio

    files = [
        ("ABSENCIA", "Prof 1", "Prof 5", "08:00"),
        ("SERVEI", "Prof 2", "", "09:00"),
        ("VIGILANCIA_ABSENT", "Prof 3", "Prof 6", "10:00"),
        ("ENCADENADA", "Prof 5", "Prof 7", "08:00"),
        ("VIGILANCIA", "Prof 8", "Prof 9", "11:30"),
    ]
    with get_data_db_session(centre) as db:
        for tipus, absent, substitut, hora in files:
            db.add(
                Substitucio(
                    data=date(2026, 4, 20),
                    hora=hora,
                    professor_absent=absent,
                    substitut=substitut,
                    grup="1-ESO-A",
                    assignatura="Català",
                    tipus_absencia=tipus,
                )
            )
        db.commit()
        dades = services.dades_direccio(db, DATA, DATA, [])

    stats = dades["stats"]
    assert (stats["total_absencies"], stats["total_serveis"]) == (1, 1)
    assert (stats["total_necessiten"], stats["total_substitucions"], stats["cobertura_pct"]) == (2, 1, 50)
    assert [(m["absencies"], m["serveis"], m["substitucions"], m["cobertura"]) for m in dades["per_mes"]] == [
        (1, 1, 1, 50)
    ]
    assert set(dades["per_hora"]) == {"08:00", "09:00"}
    assert "per_dia" not in dades  # (no el dibuixa ningú)
    assert sum(v["absencies"] for v in dades["per_dia_hora"].values()) == 2
    assert [p["nom"] for p in dades["professors_substitucions"]] == ["Prof 5"]
    assert [(g["absencies"], g["cobertes"]) for g in dades["grups_data"]["grups_ordenats"]] == [(2, 1)]


def test_l_informe_per_professor_nomes_compta_absencies_i_serveis(centre):
    # El mateix criteri que l'informe de direcció (FUNCIONAMENT.md, apartat 6)
    from datetime import date

    from database import get_data_db_session
    from models import Substitucio

    files = [
        ("ABSENCIA", "Prof 1", "Prof 5", "08:00"),
        ("VIGILANCIA_ABSENT", "Prof 1", "Prof 6", "10:00"),
        ("VIGILANCIA_ABSENT", "Prof 3", "Prof 5", "11:30"),
        ("ENCADENADA", "Prof 5", "Prof 7", "08:00"),
    ]
    with get_data_db_session(centre) as db:
        for tipus, absent, substitut, hora in files:
            db.add(
                Substitucio(
                    data=date(2026, 4, 20),
                    hora=hora,
                    professor_absent=absent,
                    substitut=substitut,
                    grup="1-ESO-A",
                    assignatura="Català",
                    tipus_absencia=tipus,
                )
            )
        db.commit()
        dades = {p["nom"]: p for p in services.dades_professors(db, DATA, DATA)}

    assert set(dades) == {"Prof 1", "Prof 5"}
    assert [s["tipus_absencia"] for s in dades["Prof 1"]["absencies"]] == ["ABSENCIA"]
    assert [s["hora"] for s in dades["Prof 5"]["substitucions_fetes"]] == ["08:00"]


def test_l_informe_per_professor_va_per_ordre_alfabetic_natural(centre):
    # Abans, per text: «Prof 10» abans de «Prof 6», i els accents al final
    from datetime import date

    from database import get_data_db_session
    from models import Substitucio

    with get_data_db_session(centre) as db:
        for professor in ("Prof 10", "Prof 6", "Àlex", "Zoe"):
            db.add(
                Substitucio(
                    data=date(2026, 4, 20),
                    hora="08:00",
                    professor_absent=professor,
                    grup="1-ESO-A",
                    assignatura="Català",
                    tipus_absencia="ABSENCIA",
                )
            )
        db.commit()
        noms = [p["nom"] for p in services.dades_professors(db, DATA, DATA)]

    assert noms == ["Àlex", "Prof 6", "Prof 10", "Zoe"]


def test_l_informe_d_un_professor_sense_res_a_l_interval_ho_diu(client):
    resposta = client.get(
        "/api/informes/professor",
        params={"data_inici": DATA, "data_final": DATA, "professor": "Prof Sense Res"},
    )

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == (
        "Prof Sense Res no té absències ni substitucions fetes entre el 20/04/2026 i el 20/04/2026"
    )
