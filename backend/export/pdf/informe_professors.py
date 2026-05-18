"""
Generador d'informe per professor en PDF.
Per a cada professor: grid horari amb absències i substitucions fetes.
"""
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from i18n_setup import translate as _, setup_translation
from utils.hores import normalitzar_hora as _normalitzar_hora

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Flowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

C_NAVY     = colors.HexColor("#1e3a5f")
C_TEAL     = colors.HexColor("#16a085")
C_GREEN    = colors.HexColor("#27ae60")
C_ORANGE   = colors.HexColor("#e67e22")
C_RED      = colors.HexColor("#c0392b")
C_PURPLE   = colors.HexColor("#7c3aed")
C_GREY_BG  = colors.HexColor("#f4f6f8")
C_GREY_MID = colors.HexColor("#bdc3c7")
C_GREY_TXT = colors.HexColor("#7f8c8d")
C_WHITE    = colors.white
C_BLACK    = colors.HexColor("#2c3e50")

PAGE_W, PAGE_H = A4
MARGIN    = 1.5 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

DIES_ORDRE = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres"]
DIES_CURT  = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres"]


def _s(name, **kw):
    return ParagraphStyle(name, **kw)


def _fmt_data(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return d


def _dia_setmana(d: str) -> str:
    dies = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]
    try:
        return dies[datetime.strptime(d, "%Y-%m-%d").weekday()]
    except Exception:
        return ""


def _heatmap(value: int, max_val: int, base_color: tuple) -> colors.Color:
    """Interpolació blanc → color base segons intensitat"""
    if max_val == 0 or value == 0:
        return C_WHITE
    intensity = min(value / max_val, 1.0)
    r = 1.0 - intensity * (1.0 - base_color[0])
    g = 1.0 - intensity * (1.0 - base_color[1])
    b = 1.0 - intensity * (1.0 - base_color[2])
    return colors.Color(r, g, b)


# Base colors (r,g,b 0-1)
BASE_ORANGE = (0.902, 0.494, 0.133)  # #e67e22
BASE_TEAL   = (0.086, 0.627, 0.522)  # #16a085


class DiagonalCell(Flowable):
    """
    Cel·la amb divisió diagonal:
      triangle sup-esq = absències (taronja)
      triangle inf-dret = substitucions (teal)
    """
    def __init__(self, width, height, val_abs, val_sub, max_abs, max_sub):
        super().__init__()
        self.width   = width
        self.height  = height
        self.val_abs = val_abs
        self.val_sub = val_sub
        self.max_abs = max_abs
        self.max_sub = max_sub

    def draw(self):
        c   = self.canv
        w   = float(self.width)
        h   = float(self.height)
        va  = self.val_abs
        vs  = self.val_sub

        c_abs = _heatmap(va, self.max_abs, BASE_ORANGE)
        c_sub = _heatmap(vs, self.max_sub, BASE_TEAL)

        # Triangle superior-esquerra (absències)
        c.setFillColor(c_abs)
        p = c.beginPath()
        p.moveTo(0, 0)
        p.lineTo(0, h)
        p.lineTo(w, h)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

        # Triangle inferior-dret (substitucions)
        c.setFillColor(c_sub)
        p = c.beginPath()
        p.moveTo(0, 0)
        p.lineTo(w, 0)
        p.lineTo(w, h)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

        # Línia diagonal blanca
        c.setStrokeColor(C_WHITE)
        c.setLineWidth(0.8)
        c.line(0, 0, w, h)

        # Valor absències (cantonada sup-esq)
        if va > 0:
            lum = 0.299 * c_abs.red + 0.587 * c_abs.green + 0.114 * c_abs.blue
            c.setFillColor(C_WHITE if lum < 0.7 else C_BLACK)
            c.setFont("Helvetica-Bold", min(7, h * 0.35))
            c.drawString(2, h - 9, str(va))

        # Valor substitucions (cantonada inf-dret)
        if vs > 0:
            lum = 0.299 * c_sub.red + 0.587 * c_sub.green + 0.114 * c_sub.blue
            c.setFillColor(C_WHITE if lum < 0.7 else C_BLACK)
            c.setFont("Helvetica", min(7, h * 0.35))
            c.drawRightString(w - 2, 2, str(vs))


def _capçalera_professor(nom: str, periode: str, timestamp: str) -> list:
    data = [[
        Paragraph(nom, _s("pn",
            fontName="Helvetica-Bold", fontSize=18, textColor=C_WHITE,
            alignment=TA_LEFT, leading=22)),
        Paragraph(
            f"{_('Informe individual de substitucions')}<br/>"
            f"<font size='9' color='#a8c8e8'>{_('Període')}: {periode}"
            f" &nbsp;|&nbsp; {_('Generat')}: {timestamp}</font>",
            _s("ps", fontName="Helvetica", fontSize=10,
               textColor=colors.HexColor("#a8c8e8"),
               alignment=TA_RIGHT, leading=14)),
    ]]
    t = Table(data, colWidths=[CONTENT_W * 0.55, CONTENT_W * 0.45])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [t, Spacer(1, 0.4 * cm)]


def _kpi_professor(abs_count, serv_count, cobertes, pendents, subs_fetes) -> list:
    def card(num, lbl, color):
        w = (CONTENT_W / 5) - 0.2 * cm
        t = Table([
            [Paragraph(str(num), _s("kn", fontName="Helvetica-Bold", fontSize=20,
                                    textColor=color, alignment=TA_CENTER, leading=24))],
            [Paragraph(lbl, _s("kl", fontName="Helvetica", fontSize=7,
                               textColor=C_GREY_TXT, alignment=TA_CENTER, leading=10))],
        ], colWidths=[w])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_GREY_BG),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("LINEABOVE",     (0, 0), (-1, 0), 3, color),
        ]))
        return t

    row = [[
        card(abs_count,  _("Absències"),   C_ORANGE),
        card(serv_count, _("Serveis"),     C_PURPLE),
        card(cobertes,   _("Cobertes"),    C_GREEN),
        card(pendents,   _("Pendents"),    C_RED),
        card(subs_fetes, _("Subs. fetes"), C_TEAL),
    ]]
    t = Table(row, colWidths=[(CONTENT_W / 5)] * 5, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    return [t, Spacer(1, 0.5 * cm)]


def _grid_horari(absencies: list, subs_fetes: list, hores_xml: list) -> list:
    """
    Grid horari (hores × dies) amb cel·les diagonals:
      triangle sup-esq = absències (taronja)
      triangle inf-dret = substitucions fetes (teal)
    Comptatge agregat per (dia_setmana, hora) sobre tot el període.
    """
    elems = [
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_GREY_MID, spaceAfter=4),
        Paragraph(_("Distribució per dia i hora"), _s("sec",
            fontName="Helvetica-Bold", fontSize=11, textColor=C_NAVY, leading=16)),
        Spacer(1, 0.15 * cm),
        Paragraph(
            f'<font color="#e67e22">▲ {_("Absències (triangle sup)")}</font>'
            '&nbsp;&nbsp;&nbsp;'
            f'<font color="#16a085">▼ {_("Substitucions fetes (triangle inf)")}</font>'
            f'&nbsp;&nbsp; — {_("Intensitat: proporció respecte al màxim del curs")}',
            _s("leg", fontName="Helvetica", fontSize=7.5,
               textColor=C_GREY_TXT, leading=11)
        ),
        Spacer(1, 0.25 * cm),
    ]

    # Comptatge per (dia, hora)
    abs_grid = defaultdict(int)
    sub_grid = defaultdict(int)

    for a in absencies:
        dia  = _dia_setmana(a["data"])
        hora = _normalitzar_hora(a.get("hora", "") or "")
        if dia in DIES_ORDRE and hora:
            abs_grid[(dia, hora)] += 1

    for s in subs_fetes:
        dia  = _dia_setmana(s["data"])
        hora = _normalitzar_hora(s.get("hora", "") or "")
        if dia in DIES_ORDRE and hora:
            sub_grid[(dia, hora)] += 1

    # Sempre mostrar totes les hores del XML (visió completa de l'horari)
    if hores_xml:
        hores_ordre = hores_xml
    else:
        hores_presents = set(abs_grid.keys()) | set(sub_grid.keys())
        hores_ordre = sorted({h for _, h in hores_presents},
                             key=lambda h: (1, h) if h == "Pati" else (0, h))

    if not hores_ordre:
        elems.append(Paragraph(_("Cap dada disponible."), _s("nd",
            fontName="Helvetica-Oblique", fontSize=8, textColor=C_GREY_TXT, leading=12)))
        return elems

    max_abs = max(abs_grid.values(), default=1) or 1
    max_sub = max(sub_grid.values(), default=1) or 1

    # Dimensions de la cel·la
    hora_w  = 1.6 * cm
    cell_w  = (CONTENT_W - hora_w) / len(DIES_ORDRE)
    cell_h  = 1.1 * cm

    # Capçalera
    header_data = [
        Paragraph(_("Hora"), _s("hh", fontName="Helvetica-Bold", fontSize=8,
                                textColor=C_WHITE, alignment=TA_CENTER, leading=10))
    ] + [
        Paragraph(_(d)[:3], _s("dh", fontName="Helvetica-Bold", fontSize=8,
                               textColor=C_WHITE, alignment=TA_CENTER, leading=10))
        for d in DIES_ORDRE
    ]

    rows = [header_data]
    style_cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0), C_NAVY),
        ("TOPPADDING",    (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 1), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_GREY_MID),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND",    (0, 1), (0, -1), colors.HexColor("#eaf0f8")),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS",(1, 1), (-1, -1), [C_WHITE, colors.HexColor("#fafbfc")]),
    ]

    for r_idx, hora in enumerate(hores_ordre, start=1):
        row = [
            Paragraph(hora, _s("hr", fontName="Helvetica-Bold", fontSize=7.5,
                               textColor=C_NAVY, alignment=TA_CENTER, leading=10))
        ]
        for dia in DIES_ORDRE:
            va = abs_grid.get((dia, hora), 0)
            vs = sub_grid.get((dia, hora), 0)
            if va == 0 and vs == 0:
                row.append("")  # cel·la buida però amb requadre visible
            else:
                row.append(DiagonalCell(cell_w, cell_h, va, vs, max_abs, max_sub))
        rows.append(row)

    col_w = [hora_w] + [cell_w] * len(DIES_ORDRE)
    row_h = [0.55 * cm] + [cell_h] * len(hores_ordre)

    t = Table(rows, colWidths=col_w, rowHeights=row_h, hAlign="LEFT")
    t.setStyle(TableStyle(style_cmds))
    elems.append(t)
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _taula_absencies(absencies: list) -> list:
    TIPUS_LABELS = {
        "ABSENCIA":          (_("Absència"),    C_ORANGE),
        "SERVEI":            (_("Servei"),      C_PURPLE),
        "VIGILANCIA_ABSENT": (_("Vig. absent"), colors.HexColor("#2980b9")),
    }

    if not absencies:
        return [
            HRFlowable(width=CONTENT_W, thickness=0.5, color=C_GREY_MID, spaceAfter=4),
            Paragraph(_("Absències pròpies"), _s("s1", fontName="Helvetica-Bold",
                fontSize=11, textColor=C_NAVY, leading=16)),
            Paragraph(_("Cap absència registrada."), _s("n1", fontName="Helvetica-Oblique",
                fontSize=8, textColor=C_GREY_TXT, leading=12)),
            Spacer(1, 0.3 * cm),
        ]

    elems = [
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_GREY_MID, spaceAfter=4),
        Paragraph(_("Absències pròpies"), _s("s1", fontName="Helvetica-Bold",
            fontSize=11, textColor=C_ORANGE, leading=16)),
        Spacer(1, 0.2 * cm),
    ]

    headers = [_("Data"), _("Dia"), _("Hora"), _("Grup"), _("Assignatura"), _("Tipus"), _("Substitut")]
    rows = [headers]
    style_cmds = []
    for r_idx, a in enumerate(
            sorted(absencies, key=lambda x: (x["data"], x.get("hora", ""))), start=1):
        tipus_lbl, tipus_color = TIPUS_LABELS.get(
            a["tipus_absencia"], (a["tipus_absencia"], C_GREY_TXT))
        substitut = (a.get("substitut") or "").strip()
        rows.append([
            _fmt_data(a["data"]),
            _dia_setmana(a["data"])[:3],
            a.get("hora", ""),
            a.get("grup", "") or "—",
            a.get("assignatura", "") or "—",
            tipus_lbl,
            substitut or _("Pendent"),
        ])
        style_cmds.append(("TEXTCOLOR", (5, r_idx), (5, r_idx), tipus_color))
        style_cmds.append(("FONTNAME",  (5, r_idx), (5, r_idx), "Helvetica-Bold"))
        if substitut:
            style_cmds.append(("TEXTCOLOR", (6, r_idx), (6, r_idx), C_GREEN))
        else:
            style_cmds.append(("TEXTCOLOR", (6, r_idx), (6, r_idx), C_RED))

    col_w = [2.2*cm, 1.0*cm, 1.5*cm, 1.8*cm, 4.8*cm, 2.2*cm, 4.3*cm]
    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_ORANGE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        ("ALIGN",         (0, 1), (2, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_GREY_MID),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_GREY_BG]),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])
    for cmd in style_cmds:
        st.add(*cmd)
    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _taula_substitucions_fetes(subs: list) -> list:
    TIPUS_LABELS = {
        "ABSENCIA":          (_("Absència"),    C_ORANGE),
        "SERVEI":            (_("Servei"),      C_PURPLE),
        "VIGILANCIA_ABSENT": (_("Vig. absent"), colors.HexColor("#2980b9")),
    }

    if not subs:
        return [
            HRFlowable(width=CONTENT_W, thickness=0.5, color=C_GREY_MID, spaceAfter=4),
            Paragraph(_("Substitucions fetes"), _s("s2", fontName="Helvetica-Bold",
                fontSize=11, textColor=C_NAVY, leading=16)),
            Paragraph(_("Cap substitució feta."), _s("n2", fontName="Helvetica-Oblique",
                fontSize=8, textColor=C_GREY_TXT, leading=12)),
            Spacer(1, 0.3 * cm),
        ]

    elems = [
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_GREY_MID, spaceAfter=4),
        Paragraph(_("Substitucions fetes"), _s("s2", fontName="Helvetica-Bold",
            fontSize=11, textColor=C_TEAL, leading=16)),
        Spacer(1, 0.2 * cm),
    ]

    headers = [_("Data"), _("Dia"), _("Hora"), _("Grup"), _("Assignatura"), _("Professor absent"), _("Tipus")]
    rows = [headers]
    style_cmds = []
    for r_idx, s in enumerate(
            sorted(subs, key=lambda x: (x["data"], x.get("hora", ""))), start=1):
        tipus_lbl, tipus_color = TIPUS_LABELS.get(
            s["tipus_absencia"], (s["tipus_absencia"], C_GREY_TXT))
        rows.append([
            _fmt_data(s["data"]),
            _dia_setmana(s["data"])[:3],
            s.get("hora", ""),
            s.get("grup", "") or "—",
            s.get("assignatura", "") or "—",
            s.get("professor_absent", "") or "—",
            tipus_lbl,
        ])
        style_cmds.append(("TEXTCOLOR", (6, r_idx), (6, r_idx), tipus_color))
        style_cmds.append(("FONTNAME",  (6, r_idx), (6, r_idx), "Helvetica-Bold"))

    col_w = [2.2*cm, 1.0*cm, 1.5*cm, 1.8*cm, 4.8*cm, 4.3*cm, 2.2*cm]
    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_TEAL),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        ("ALIGN",         (0, 1), (2, -1), "CENTER"),
        ("ALIGN",         (6, 1), (6, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_GREY_MID),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_GREY_BG]),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])
    for cmd in style_cmds:
        st.add(*cmd)
    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def generar_informe_professors_pdf(
    professors_data: list,
    nom_centre: str,
    data_inici: str,
    data_final: str,
    hores_xml: list = None,
    mostrar_taules: bool = False,
    export_dir: str = "exports",
    lang: str = "ca",
) -> str:
    setup_translation(lang)
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%y%m%d_%H%M%S")
    filename = export_path / f"informe_professors_{ts}.pdf"

    def fmt(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return d

    periode   = f"{fmt(data_inici)} – {fmt(data_final)}"
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")

    doc = SimpleDocTemplate(
        str(filename), pagesize=A4,
        topMargin=MARGIN, bottomMargin=MARGIN,
        leftMargin=MARGIN, rightMargin=MARGIN,
        title=_("Informe individual de substitucions"),
        author=nom_centre,
    )

    story = []
    for i, p in enumerate(professors_data):
        if i > 0:
            story.append(PageBreak())

        nom        = p["nom"]
        absencies  = p["absencies"]
        subs_fetes = p["substitucions_fetes"]

        abs_normals = [a for a in absencies if a["tipus_absencia"] == "ABSENCIA"]
        serveis     = [a for a in absencies if a["tipus_absencia"] == "SERVEI"]
        cobertes    = [a for a in absencies if (a.get("substitut") or "").strip()]
        pendents    = [a for a in absencies if not (a.get("substitut") or "").strip()]

        story += _capçalera_professor(nom, periode, timestamp)
        story += _kpi_professor(
            abs_count  = len(abs_normals),
            serv_count = len(serveis),
            cobertes   = len(cobertes),
            pendents   = len(pendents),
            subs_fetes = len(subs_fetes),
        )
        story += _grid_horari(absencies, subs_fetes, hores_xml)
        if mostrar_taules:
            story += _taula_absencies(absencies)
            story += _taula_substitucions_fetes(subs_fetes)

    doc.build(story)
    return str(filename)
