"""L'interval analitza cada dia i imprimeix problemes sense diàleg previ."""

import subprocess
import xml.etree.ElementTree as ET
from datetime import date

from test_pdf_api import DATA, centre, client  # noqa: F401

from database import get_data_db_session, get_data_dir_for_institucio
from models import Vigilancia, XMLVersion


def test_interval_imprimeix_l_absencia_i_la_classe_amb_l_analisi_comuna(client):
    for data, professor in [(DATA, "Prof 21"), ("2026-04-27", "Prof 30")]:
        r = client.post(
            f"/api/vigilancies/{data}",
            json={
                "hora": "10:00",
                "tipus": "Prova",
                "grups": "1-ESO-A",
                "aula": "A1",
                "vigilant": professor,
                "nivell": "1-ESO",
            },
        )
        assert r.status_code == 200
    r = client.put(
        f"/api/substitucions/{DATA}/absencies/Prof 21", json={"hores_absencia": ["10:00"], "updated_at_map": {}}
    )
    assert r.status_code == 200, r.text
    # Petició directa: l'interval no requereix cap validació ni confirmació prèvia.
    r = client.get(f"/api/pdf/vigilancies/interval?data_inici={DATA}&data_final=2026-04-27")
    assert r.status_code == 200, r.text[:300]
    text = subprocess.run(["pdftotext", "-", "-"], input=r.content, capture_output=True, check=True).stdout.decode()
    text = " ".join(text.split())
    assert "Vigilant Prof 21 absent sense cobertura" in text
    assert "Prof 30 vigila;" in text and "queda sense substitut" in text
    # Cada avís queda vinculat al seu dia, sense barrejar les absències de les hores.
    assert text.index("Vigilant Prof 21 absent sense cobertura") < text.index("Prof 30 vigila;")


def test_interval_travessa_el_mes_i_canvia_d_hores_amb_un_dia_buit(client, centre):
    carpeta = get_data_dir_for_institucio(centre)
    arbre = ET.parse(carpeta / "teachers.xml")
    for hora in arbre.getroot().iter("Hour"):
        if hora.get("name", "").strip() == "PATI":
            hora.set("name", "ESBARJO")
    arbre.write(carpeta / "nou.xml", encoding="utf-8")

    with get_data_db_session(centre) as db:
        db.add_all(
            [
                XMLVersion(path="teachers.xml", data_inici=date(2026, 3, 1), data_fi=date(2026, 3, 31)),
                XMLVersion(path="nou.xml", data_inici=date(2026, 4, 1)),
                Vigilancia(
                    data=date(2026, 4, 2),
                    hora="ESBARJO",
                    tipus="Prova abril",
                    vigilant="Prof 21",
                    grups="G",
                    aula="A",
                    nivell="",
                ),
                Vigilancia(
                    data=date(2026, 3, 31),
                    hora="PATI",
                    tipus="Prova març",
                    vigilant="Prof 21",
                    grups="G",
                    aula="A",
                    nivell="",
                ),
            ]
        )
        db.commit()

    resposta = client.get(
        "/api/pdf/vigilancies/interval",
        params={
            "data_inici": "2026-03-31",
            "data_final": "2026-04-02",
            "include_empty_days": "true",
            "dia_per_pagina": "true",
        },
    )
    assert resposta.status_code == 200, resposta.text[:300]
    assert resposta.headers["content-disposition"] == (
        "attachment; filename=vigilancies_interval_2026-03-31_a_2026-04-02_20261104_120000.pdf"
    )
    text = subprocess.run(
        ["pdftotext", "-", "-"], input=resposta.content, capture_output=True, check=True
    ).stdout.decode()
    pagines = [" ".join(pagina.split()) for pagina in text.split("\f") if pagina.strip()]
    assert len(pagines) == 3, pagines
    assert all(
        fragment in pagines[0] for fragment in ("31/03/2026 - 02/04/2026", "Dimarts, 31", "Hora PATI", "Prova març")
    )
    assert "Dimecres, 1" in pagines[1] and "Hora " not in pagines[1]
    assert all(fragment in pagines[2] for fragment in ("Dijous, 2", "Hora ESBARJO", "Prova abril"))
