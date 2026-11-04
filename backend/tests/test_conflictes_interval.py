"""L'interval analitza cada dia i imprimeix problemes sense diàleg previ."""

import subprocess

from test_pdf_api import DATA, centre, client  # noqa: F401


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
