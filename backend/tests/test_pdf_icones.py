"""Les icones dels avisos del PDF són al codi i substitueixen els emojis."""

from pathlib import Path

from pdf.icones import _ICONES, amb_icones


def test_cada_icona_existeix():
    carpeta = Path(__file__).resolve().parents[1] / "pdf" / "icones"
    assert all((carpeta / fitxer).is_file() for fitxer in _ICONES.values())


def test_els_emojis_coneguts_es_canvien_per_la_imatge_i_la_resta_no():
    text = amb_icones("🕐 HORA 09:00: ⚠️ avís ❌ 🏫 aula 🙂")
    assert text.count("<img ") == 4
    assert "🙂" in text and "🕐" not in text
    assert amb_icones("sense cap emoji") == "sense cap emoji"
