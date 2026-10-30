"""
Taules dels PDF de substitucions i de vigilàncies: un sol codi i uns sols
estils per als dos formats (taula del dia i una secció per hora), per als dos
PDF i per a l'interval. El model és la taula del dia del PDF de substitucions;
els colors surten del perfil d'impressió (config/pdf.json).

Les columnes són lògiques (hora, qui, on, assignatura, persona, observacions)
i cada tipus en dona l'etiqueta i el valor:

    substitucions   Hora · Absent       · Grup        · Assignatura · Substitut · Observacions
    vigilàncies     Hora · Curs         · Aula        · Assignatura · Vigilant  · Observacions
    totes dues      Hora · Absent / Curs · Grup / Aula · Assignatura · Substitut / Vigilant · Observacions

Quan van juntes, dins de cada hora primer les substitucions i després les
vigilàncies, aquestes en cursiva i amb fons de color, amb una nota sota la
taula. Només surten les hores que tenen alguna fila (o, amb l'espai per
escriure a mà, les que en podrien tenir).
"""

from dataclasses import dataclass
from typing import Callable, Dict, List

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from i18n_setup import translate as _


@dataclass(frozen=True)
class TipusTaula:
    """Què posa cada tipus de fila a les columnes lògiques."""

    etiquetes: Dict[str, str]  # columna lògica -> etiqueta (sense traduir)
    valors: Callable[[dict], Dict[str, str]]  # fila -> {columna lògica: text}


# Valors del perfil d'impressió si el perfil no els té
PER_DEFECTE = {
    "substitutions_header_bg": "#2c3e50",
    "substitutions_header_text": "#ffffff",
    "content_bg": "#ffffff",
    "grid_color": "#808080",
    "grid_width": 0.6,
    "hour_color": "#c0392b",
    "hour_bg": "#e9ecef",
    "hour_line_color": "#000000",
    "hour_line_width": 1.5,
    "person_color": "#2c3e50",
    "vigilances_row_bg": "#fcf3d4",
}
# Amb compressió, la lletra i els espais es redueixen
REDUCCIO_COMPRESSIO = 0.85


def _text(valor) -> str:
    from pdf.engine import _text as text_segur

    return text_segur(valor)


def _valors_substitucio(sub: dict) -> dict:
    substitut = sub.get("substitut", "") or ""
    if substitut in ("---", "PENDENT"):  # els pendents no s'hi escriuen
        substitut = ""
    grup = sub.get("grup", "") or ""
    aula = sub.get("aula", "") or ""
    return {
        "hora": sub.get("hora", "") or "",
        "qui": sub.get("professor_absent", sub.get("professor", "")),
        "on": f"{grup} ({aula})" if aula and grup else grup,  # mai l'aula sola, sense grup
        "assignatura": sub.get("assignatura"),
        "persona": substitut,
        "observacions": sub.get("comentaris"),
    }


def curs_vigilancia(vig: dict) -> str:
    """Curs que es mostra d'una vigilància: el nivell, o el que es dedueix del grup."""
    nivell = vig.get("nivell", "")
    # Don't show "GENERAL" as course - it's for special vigilances
    if nivell == "GENERAL":
        nivell = ""
    # Only show level if there's an explicit group selection
    if not nivell:
        grup = vig.get("grups", "") or vig.get("grup", "")
        # ONLY extract level from explicit group selection, NOT from aula
        if grup and "-" in grup:
            parts = grup.split("-")
            if len(parts) >= 2:
                if parts[1] == "ESO":
                    nivell = f"{parts[0]}{'r' if parts[0] in ['1', '3'] else 't'} ESO"
                elif parts[1] == "BATX":
                    nivell = f"{parts[0]}{'r' if parts[0] == '1' else 'n'} BATX"
    return nivell


def _valors_vigilancia(vig: dict) -> dict:
    vigilant = vig.get("vigilant", "") or ""
    if vigilant.startswith("-- selecciona"):  # el text del desplegable no és un vigilant
        vigilant = ""
    return {
        "hora": vig.get("hora", "") or "",
        "qui": curs_vigilancia(vig),
        "on": vig.get("aula"),
        "assignatura": vig.get("tipus", ""),
        "persona": vigilant,
        "observacions": vig.get("comentaris"),
    }


SUBSTITUCIONS = TipusTaula(
    etiquetes={
        "hora": "Hora",
        "qui": "Absent",
        "on": "Grup",
        "assignatura": "Assignatura",
        "persona": "Substitut",
        "observacions": "Observacions",
    },
    valors=_valors_substitucio,
)

VIGILANCIES = TipusTaula(
    etiquetes={
        "hora": "Hora",
        "qui": "Curs",
        "on": "Aula",
        "assignatura": "Assignatura",
        "persona": "Vigilant",
        "observacions": "Observacions",
    },
    valors=_valors_vigilancia,
)


NOTA_VIGILANCIES = "Les files en cursiva amb fons de color són vigilàncies d'examen."


class EstilsPdf:
    """Tots els estils de les taules (i del títol de cada hora) d'un PDF: la
    lletra (base 10/9 pt × la mida triada), els espais, els colors del perfil
    i la compressió. El fan servir tots dos formats."""

    def __init__(self, exp):
        perfil = {**PER_DEFECTE, **{k: v for k, v in exp._get_profile_colors().items() if v is not None}}
        self.perfil = perfil
        self.mida = exp.mida_lletra
        self.comprimit = bool(getattr(exp, "_auto_compression_active", False))
        f = self.mida * (REDUCCIO_COMPRESSIO if self.comprimit else 1)
        self.f = f
        particio = dict(
            hyphenationLang=exp.hyphen_language_code if exp.hyphen_lang else None,
            embeddedHyphenation=1 if exp.hyphen_lang else 0,
        )
        base = dict(
            parent=exp.styles["Normal"], fontSize=10 * f, leading=12 * f, alignment=1, fontName="Helvetica", **particio
        )
        color = colors.HexColor
        self.cel = ParagraphStyle("Cel", **base)
        self.cel_vig = ParagraphStyle("CelVig", **{**base, "fontName": "Helvetica-Oblique"})
        self.persona = ParagraphStyle(
            "Persona", **{**base, "fontName": "Helvetica-Bold", "textColor": color(perfil["person_color"])}
        )
        self.persona_vig = ParagraphStyle(
            "PersonaVig", **{**base, "fontName": "Helvetica-BoldOblique", "textColor": color(perfil["person_color"])}
        )
        self.cap = ParagraphStyle(
            "Cap",
            **{
                **base,
                "fontSize": 9 * f,
                "leading": 11 * f,
                "fontName": "Helvetica-Bold",
                "textColor": color(perfil["substitutions_header_text"]),
            },
        )
        self.hora = ParagraphStyle(
            "Hora",
            **{
                **base,
                "fontSize": 11 * f,
                "leading": 13 * f,
                "fontName": "Helvetica-Bold",
                "textColor": color(perfil["hour_color"]),
            },
        )
        # El títol «Hora 10:00» del format per hores: 12 pt amb la mida ×1,2
        self.titol_hora = ParagraphStyle(
            "TitolHora",
            parent=exp.custom_styles["hora"],
            fontSize=10 * f,
            leading=12 * f,
            spaceBefore=(4 if self.comprimit else 12) * f / 1.2,
            spaceAfter=(2 if self.comprimit else 4) * f / 1.2,
            textColor=color(perfil["hour_color"]),
        )
        self.nota = ParagraphStyle(
            "Nota",
            parent=exp.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#444444"),
            spaceBefore=3,
        )
        espai = (6 if self.mida >= 1.3 else 4) * (0.5 if self.comprimit else 1)
        self.ordres = [
            ("BACKGROUND", (0, 0), (-1, 0), color(perfil["substitutions_header_bg"])),
            ("BACKGROUND", (0, 1), (-1, -1), color(perfil["content_bg"])),
            ("GRID", (0, 0), (-1, -1), perfil["grid_width"], color(perfil["grid_color"])),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), espai),
            ("BOTTOMPADDING", (0, 0), (-1, -1), espai),
            ("LEFTPADDING", (0, 0), (-1, -1), 2 if self.comprimit else 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2 if self.comprimit else 3),
        ]
        if perfil.get("use_header_line"):
            self.ordres.append(("LINEBELOW", (0, 0), (-1, 0), 1.5, color(perfil["grid_color"])))

    def fons_vigilancia(self, fila: int) -> tuple:
        return ("BACKGROUND", (0, fila), (-1, fila), colors.HexColor(self.perfil["vigilances_row_bg"]))

    def separacio_hora(self, inici: int, fi: int) -> list:
        """El bloc d'una hora a la taula del dia: l'hora a la primera columna,
        amb fons, i una línia gruixuda a sobre; no es parteix entre pàgines."""
        return [
            ("SPAN", (0, inici), (0, fi)),
            ("NOSPLIT", (0, inici), (-1, fi)),
            ("BACKGROUND", (0, inici), (0, fi), colors.HexColor(self.perfil["hour_bg"])),
            (
                "LINEABOVE",
                (0, inici),
                (-1, inici),
                self.perfil["hour_line_width"],
                colors.HexColor(self.perfil["hour_line_color"]),
            ),
        ]


def etiqueta(columna: str, tipus_taula) -> str:
    """L'etiqueta traduïda d'una columna: la d'un tipus o, quan van juntes,
    totes dues amb una barra («Absent / Curs»), si són diferents."""
    if tipus_taula != "combinada":
        return _(tipus_taula.etiquetes[columna])
    subs, vigs = _(SUBSTITUCIONS.etiquetes[columna]), _(VIGILANCIES.etiquetes[columna])
    return subs if subs == vigs else f"{subs} / {vigs}"


def _fila(est: EstilsPdf, tipus: TipusTaula, dada: dict, columnes: list, marcada: bool) -> list:
    """Una fila de dades; `marcada`: vigilància en un PDF amb substitucions
    (cursiva i fons de color)."""
    valors = tipus.valors(dada)
    cel = est.cel_vig if marcada else est.cel
    persona = est.persona_vig if marcada else est.persona
    return [Paragraph(_text(valors[c]), persona if c == "persona" and valors[c] else cel) for c in columnes]


def _amplades(columnes: list, amb_hores_davant: bool) -> list:
    """19 cm en total; l'hora, 1,9 cm perquè «08:00» no es parteixi amb la lletra gran."""
    amples = {
        # amb observacions / sense
        True: {"hora": 1.9, "qui": 3.4, "on": 3.0, "assignatura": 3.0, "persona": 3.2, "observacions": 4.5},
        False: {"hora": 1.9, "qui": 4.4, "on": 3.4, "assignatura": 3.6, "persona": 5.7},
    }[("observacions" in columnes)]
    if not amb_hores_davant:  # format per hores sense la columna de l'hora: l'espai, a les altres
        extra = 1.9 / (len(columnes))
        return [(amples[c] + extra) * cm for c in columnes]
    return [amples[c] * cm for c in columnes]


def taula_del_dia(exp, dades_per_hora: Dict, espai_a_ma: bool, combinada: bool, tipus_sol=None) -> list:
    """Format «taula del dia»: una taula per a tot el dia, amb l'hora a la
    primera columna; la capçalera es repeteix a cada pàgina. `combinada`:
    substitucions i vigilàncies juntes; si no, `tipus_sol` diu quin tipus hi ha."""
    est = EstilsPdf(exp)
    columnes = ["hora", "qui", "on", "assignatura", "persona"] + (["observacions"] if exp.show_comments_column else [])
    tipus_taula = "combinada" if combinada else tipus_sol
    files = [[Paragraph(_text(etiqueta(c, tipus_taula)), est.cap) for c in columnes]]
    alcades = [None]
    ordres = list(est.ordres)
    hi_ha_vigilancies = False

    hores = [
        h
        for h in exp.hores
        if (h in dades_per_hora and (dades_per_hora[h]["substitucions"] or dades_per_hora[h]["vigilancies"]))
        or (espai_a_ma and exp._pot_tenir_substitucions(h))
    ]
    for hora in hores:
        dades = dades_per_hora.get(hora, {"substitucions": [], "vigilancies": []})
        inici = len(files)
        for sub in dades["substitucions"]:
            files.append([None] + _fila(est, SUBSTITUCIONS, sub, columnes[1:], False))
            alcades.append(None)
        if espai_a_ma:
            for _blanc in range(1 if dades["substitucions"] else 2):
                files.append([None] + [""] * (len(columnes) - 1))
                alcades.append(0.9 * cm * est.f)
        for vig in dades["vigilancies"]:
            if combinada:
                ordres.append(est.fons_vigilancia(len(files)))
            files.append([None] + _fila(est, VIGILANCIES, vig, columnes[1:], combinada))
            alcades.append(None)
            hi_ha_vigilancies = True
        fi = len(files) - 1
        if fi < inici:
            continue
        files[inici][0] = Paragraph(_text(hora), est.hora)
        for r in range(inici + 1, fi + 1):
            files[r][0] = ""
        ordres += est.separacio_hora(inici, fi)

    if len(files) == 1:
        return []
    taula = Table(files, colWidths=_amplades(columnes, True), rowHeights=alcades, repeatRows=1)
    taula.setStyle(TableStyle(ordres))
    contingut = [taula]
    if combinada and hi_ha_vigilancies:
        contingut.append(Paragraph(_(NOTA_VIGILANCIES), est.nota))
    return contingut


def taula_per_hores(exp, files: List[dict], tipus: TipusTaula, files_en_blanc: int = 0, marcada: bool = False):
    """La taula d'una hora del format «una secció per hora», amb els mateixos
    estils que la taula del dia. `marcada`: vigilàncies en un PDF amb
    substitucions (cursiva i fons de color). `files_en_blanc`: files buides al
    final, per escriure-hi a mà."""
    est = EstilsPdf(exp)
    if exp.show_hours_column:
        columnes = ["hora", "qui", "on", "assignatura", "persona"]
    else:
        columnes = ["qui", "assignatura", "on", "persona"]
    if exp.show_comments_column:
        columnes.append("observacions")
    dades = [[Paragraph(_text(etiqueta(c, tipus)), est.cap) for c in columnes]]
    ordres = list(est.ordres)
    for fila in files:
        if marcada:
            ordres.append(est.fons_vigilancia(len(dades)))
        dades.append(_fila(est, tipus, fila, columnes, marcada))
    alcades = [None] * len(dades) + [0.9 * cm * est.f] * files_en_blanc
    dades.extend([[""] * len(columnes) for _fila_buida in range(files_en_blanc)])
    taula = Table(dades, colWidths=_amplades(columnes, exp.show_hours_column), rowHeights=alcades)
    taula.setStyle(TableStyle(ordres))
    return taula


def contingut_del_dia(exp, dades_per_hora: Dict, espai_a_ma: bool, combinada: bool, tipus_sol=None) -> list:
    """El contingut d'un dia en el format triat (exp.format_dia): la taula del
    dia o una secció per hora. El fan servir el PDF del dia i l'interval."""
    if exp.format_dia:
        return taula_del_dia(exp, dades_per_hora, espai_a_ma, combinada, tipus_sol)
    est = EstilsPdf(exp)
    contingut = []
    hi_ha_vigilancies = False
    for hora in exp.hores:
        dades = dades_per_hora.get(hora, {"substitucions": [], "vigilancies": []})
        te_files = dades["substitucions"] or dades["vigilancies"]
        if not te_files and not (espai_a_ma and exp._pot_tenir_substitucions(hora)):
            continue
        contingut.append(Paragraph(_("Hora {hora}").format(hora=hora), est.titol_hora))
        if dades["substitucions"] or espai_a_ma:
            blanc = (1 if dades["substitucions"] else 2) if espai_a_ma else 0
            contingut.append(taula_per_hores(exp, dades["substitucions"], SUBSTITUCIONS, blanc))
            if dades["vigilancies"]:
                contingut.append(Spacer(1, 0.1 * cm))
        if dades["vigilancies"]:
            contingut.append(taula_per_hores(exp, dades["vigilancies"], VIGILANCIES, marcada=combinada))
            hi_ha_vigilancies = True
    if combinada and hi_ha_vigilancies:
        contingut.append(Paragraph(_(NOTA_VIGILANCIES), est.nota))
    return contingut
