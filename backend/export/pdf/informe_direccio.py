"""
Generador d'informe de direcció en PDF
Informe complet d'absències, substitucions i vigilàncies
"""
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from i18n_setup import translate as _, setup_translation

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Paleta de colors moderna
C_NAVY     = colors.HexColor("#1e3a5f")
C_BLUE     = colors.HexColor("#2980b9")
C_TEAL     = colors.HexColor("#16a085")
C_GREEN    = colors.HexColor("#27ae60")
C_ORANGE   = colors.HexColor("#e67e22")
C_RED      = colors.HexColor("#c0392b")
C_GREY_BG  = colors.HexColor("#f4f6f8")
C_GREY_MID = colors.HexColor("#bdc3c7")
C_GREY_TXT = colors.HexColor("#7f8c8d")
C_WHITE    = colors.white
C_BLACK    = colors.HexColor("#2c3e50")

PAGE_W, PAGE_H = A4
MARGIN = 1.5 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


def _s(name, **kwargs):
    """Crea un ParagraphStyle ràpid"""
    return ParagraphStyle(name, **kwargs)


STYLES = {
    "title": _s("title",
        fontName="Helvetica-Bold", fontSize=22, textColor=C_WHITE,
        alignment=TA_LEFT, leading=28),
    "subtitle": _s("subtitle",
        fontName="Helvetica", fontSize=11, textColor=colors.HexColor("#a8c8e8"),
        alignment=TA_LEFT, leading=16),
    "section": _s("section",
        fontName="Helvetica-Bold", fontSize=13, textColor=C_NAVY,
        alignment=TA_LEFT, leading=18, spaceBefore=8),
    "kpi_num": _s("kpi_num",
        fontName="Helvetica-Bold", fontSize=26, textColor=C_NAVY,
        alignment=TA_CENTER, leading=30),
    "kpi_lbl": _s("kpi_lbl",
        fontName="Helvetica", fontSize=8, textColor=C_GREY_TXT,
        alignment=TA_CENTER, leading=11),
    "table_header": _s("th",
        fontName="Helvetica-Bold", fontSize=9, textColor=C_WHITE,
        alignment=TA_CENTER, leading=12),
    "table_cell": _s("td",
        fontName="Helvetica", fontSize=8.5, textColor=C_BLACK,
        alignment=TA_LEFT, leading=12),
    "table_cell_c": _s("tdc",
        fontName="Helvetica", fontSize=8.5, textColor=C_BLACK,
        alignment=TA_CENTER, leading=12),
    "table_cell_r": _s("tdr",
        fontName="Helvetica", fontSize=8.5, textColor=C_BLACK,
        alignment=TA_RIGHT, leading=12),
    "table_cell_bold": _s("tdb",
        fontName="Helvetica-Bold", fontSize=8.5, textColor=C_BLACK,
        alignment=TA_LEFT, leading=12),
    "note": _s("note",
        fontName="Helvetica-Oblique", fontSize=8, textColor=C_GREY_TXT,
        alignment=TA_LEFT, leading=11),
    "footer": _s("footer",
        fontName="Helvetica", fontSize=8, textColor=C_GREY_TXT,
        alignment=TA_CENTER, leading=11),
}



def _table_style_base(header_color=C_NAVY, row_alt=C_GREY_BG):
    return TableStyle([
        # Capçalera
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        # Files
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 1), (-1, -1), 8.5),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        # Línies
        ("LINEBELOW",  (0, 0), (-1, 0), 0.5, header_color),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, row_alt]),
        ("GRID", (0, 0), (-1, -1), 0.3, C_GREY_MID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def _header_block(nom_centre: str, data_inici: str, data_final: str, timestamp: str,
                  logo_path: str = None) -> list:
    """Bloc de capçalera amb fons fosc, logo opcional i nom del centre"""
    def fmt(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return d

    text_cell = [
        Paragraph(_("Informe de Substitucions"), STYLES["title"]),
        Paragraph(
            f"<font size='13'><b>{nom_centre}</b></font><br/>"
            f"<font size='9' color='#a8c8e8'>{_('Període')}: {fmt(data_inici)} – {fmt(data_final)}"
            f" &nbsp;|&nbsp; {_('Generat')}: {timestamp}</font>",
            STYLES["subtitle"]
        ),
    ]

    if logo_path and Path(logo_path).exists():
        MAX_H = 1.8 * cm
        MAX_W = 4.0 * cm
        from PIL import Image as PILImage
        with PILImage.open(logo_path) as pil_img:
            img_w, img_h = pil_img.size
        aspect = img_w / img_h
        # Escalar preservant proporció dins dels límits màxims
        logo_h = MAX_H
        logo_w_img = logo_h * aspect
        if logo_w_img > MAX_W:
            logo_w_img = MAX_W
            logo_h = MAX_W / aspect
        logo_img = Image(logo_path, width=logo_w_img, height=logo_h)
        logo_img.hAlign = "CENTER"
        logo_w = logo_w_img + 0.6 * cm
        header_data = [[logo_img, text_cell]]
        col_w = [logo_w, CONTENT_W - logo_w]
        style_extra = [("VALIGN", (0, 0), (0, 0), "MIDDLE")]
    else:
        header_data = [[text_cell]]
        col_w = [CONTENT_W]
        style_extra = []

    t = Table(header_data, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING",   (0, 0), (-1, -1), 20),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 20),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        *style_extra,
    ]))
    return [t, Spacer(1, 0.5 * cm)]


def _kpi_cards(stats: dict) -> list:
    """Fila de targetes KPI"""
    total_abs   = stats["total_absencies"]
    total_serv  = stats["total_serveis"]
    total_baixa = stats["total_baixes"]
    total_subs  = stats["total_substitucions"]
    cobertura   = stats["cobertura_pct"]
    dies_actius = stats["dies_actius"]

    def card(num, lbl, color):
        data = [
            [Paragraph(str(num), _s("kn", fontName="Helvetica-Bold", fontSize=24,
                                    textColor=color, alignment=TA_CENTER, leading=28))],
            [Paragraph(lbl, _s("kl", fontName="Helvetica", fontSize=7.5,
                               textColor=C_GREY_TXT, alignment=TA_CENTER, leading=10))],
        ]
        t = Table(data, colWidths=[(CONTENT_W / 6) - 0.15 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_GREY_BG),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("LINEABOVE",     (0, 0), (-1, 0), 3, color),
        ]))
        return t

    row = [[
        card(total_abs,            _("Absències"),         C_ORANGE),
        card(total_serv,           _("Serveis"),           C_BLUE),
        card(total_baixa,          _("Baixes"),            C_RED),
        card(total_subs,           _("Substitucions"),     C_TEAL),
        card(f"{cobertura:.0f}%",  _("Cobertura"),         C_GREEN),
        card(dies_actius,          _("Dies amb incid."),   C_NAVY),
    ]]
    t = Table(row, colWidths=[(CONTENT_W / 6)] * 6, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return [t, Spacer(1, 0.5 * cm)]


def _section_title(text: str, color=C_NAVY) -> list:
    return [
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_GREY_MID, spaceAfter=4),
        Paragraph(text, STYLES["section"]),
        Spacer(1, 0.2 * cm),
    ]


def _taula_evolucio_mensual(per_mes: list) -> list:
    """Taula d'evolució mensual"""
    elems = _section_title(_("Evolució mensual"))

    headers = [_("Mes"), _("Absències"), _("Serveis"), _("Total incid."), _("Substitucions"), _("Cobertura")]
    rows = [headers]
    tot_abs = tot_serv = tot_subs = 0
    for m in per_mes:
        total = m["absencies"] + m["serveis"]
        cob = f"{m['cobertura']:.0f}%" if total > 0 else "—"
        rows.append([
            m["mes"],
            str(m["absencies"]),
            str(m["serveis"]),
            str(total),
            str(m["substitucions"]),
            cob,
        ])
        tot_abs  += m["absencies"]
        tot_serv += m["serveis"]
        tot_subs += m["substitucions"]

    tot_total = tot_abs + tot_serv
    tot_cob = f"{tot_subs / tot_total * 100:.0f}%" if tot_total > 0 else "—"
    rows.append([_("TOTAL"), str(tot_abs), str(tot_serv), str(tot_total), str(tot_subs), tot_cob])

    col_w = [3.8*cm, 2.2*cm, 2.2*cm, 2.5*cm, 2.8*cm, 2.3*cm]
    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = _table_style_base(C_NAVY)
    for col in range(1, 6):
        st.add("ALIGN", (col, 1), (col, -1), "CENTER")
    # Fila TOTAL en negreta amb fons destacat
    last = len(rows) - 1
    st.add("BACKGROUND", (0, last), (-1, last), colors.HexColor("#d5e8f5"))
    st.add("FONTNAME",   (0, last), (-1, last), "Helvetica-Bold")
    st.add("LINEABOVE",  (0, last), (-1, last), 1, C_NAVY)
    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _mini_bar(value: int, max_val: int, width: float, color) -> Table:
    """Barra de progrés horitzontal inline"""
    if max_val == 0:
        fill_w = 0
    else:
        fill_w = max(width * value / max_val, 0.01 * cm if value > 0 else 0)
    empty_w = max(width - fill_w, 0)
    data = [[""]]
    bar = Table(data, colWidths=[fill_w], rowHeights=[0.35 * cm])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    if empty_w > 0:
        outer = Table([[bar, ""]], colWidths=[fill_w, empty_w], rowHeights=[0.35 * cm])
        outer.setStyle(TableStyle([
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e8ecf0")),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        return outer
    return bar


def _taula_professors_absencies(professors: list, top: int = 20) -> list:
    """Rànquing de professors per absències amb barra visual"""
    elems = _section_title(_("Professors amb més absències"))

    BAR_W = 4.5 * cm
    max_total = professors[0]["total"] if professors else 1

    headers = ["#", _("Professor/a"), _("Abs"), _("Serv"), _("Total"), "", "%"]
    rows = [headers]
    for i, p in enumerate(professors[:top], 1):
        total_global = sum(x["total"] for x in professors) or 1
        pct = p["total"] / total_global * 100
        bar = _mini_bar(p["total"], max_total, BAR_W, C_ORANGE)
        rows.append([
            str(i),
            p["nom"],
            str(p["absencies"]),
            str(p["serveis"]),
            str(p["total"]),
            bar,
            f"{pct:.1f}%",
        ])

    col_w = [0.7*cm, 4.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, BAR_W, 1.6*cm]
    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = _table_style_base(C_ORANGE)
    for col in [2, 3, 4, 6]:
        st.add("ALIGN", (col, 1), (col, -1), "CENTER")
    st.add("VALIGN", (5, 1), (5, -1), "MIDDLE")
    t.setStyle(st)
    elems.append(t)
    if len(professors) > top:
        elems.append(Paragraph(_("* Mostrant els {top} primers de {total} professors").format(top=top, total=len(professors)), STYLES["note"]))
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _text_color_for_bg(bg: colors.Color) -> colors.Color:
    """Text blanc si el fons és fosc, negre si és clar"""
    luminance = 0.299 * bg.red + 0.587 * bg.green + 0.114 * bg.blue
    return C_WHITE if luminance < 0.65 else C_BLACK


def _heatmap_color_blue(value: int, max_val: int) -> colors.Color:
    """Color de blanc a blau per serveis (#2980b9)"""
    if max_val == 0 or value == 0:
        return C_WHITE
    intensity = min(value / max_val, 1.0)
    base_r, base_g, base_b = 0.161, 0.502, 0.725  # #2980b9
    r = 1.0 - intensity * (1.0 - base_r)
    g = 1.0 - intensity * (1.0 - base_g)
    b = 1.0 - intensity * (1.0 - base_b)
    return colors.Color(r, g, b)


def _taula_matriu_professors_mesos(per_professor_mes_abs: dict, per_professor_mes_serv: dict,
                                    mesos: list, professors: list) -> list:
    """Matriu heatmap professors × mesos amb absències (taronja) i serveis (blau)"""
    elems = _section_title(_("Evolució d'absències per professor i mes"))

    if not mesos:
        return elems

    mesos_curts = [m.split()[0][:3] for m in mesos]

    max_abs  = max((v for d in per_professor_mes_abs.values()  for v in d.values()), default=1) or 1
    max_serv = max((v for d in per_professor_mes_serv.values() for v in d.values()), default=1) or 1

    # Capçalera
    header = [
        Paragraph(_("Professor/a"), _s("ph", fontName="Helvetica-Bold", fontSize=7.5,
                                    textColor=C_WHITE, alignment=TA_LEFT, leading=10))
    ] + [
        Paragraph(mc, _s("mhc", fontName="Helvetica-Bold", fontSize=7,
                         textColor=C_WHITE, alignment=TA_CENTER, leading=9))
        for mc in mesos_curts
    ] + [
        Paragraph(_("Abs"), _s("tha", fontName="Helvetica-Bold", fontSize=7,
                            textColor=C_WHITE, alignment=TA_CENTER, leading=9)),
        Paragraph(_("Serv"), _s("ths", fontName="Helvetica-Bold", fontSize=7,
                             textColor=C_WHITE, alignment=TA_CENTER, leading=9)),
    ]

    # Pre-calcular backgrounds per determinar color text
    bg_matrix = {}
    for p in professors[:len(per_professor_mes_abs)]:
        nom = p["nom"]
        abs_data  = per_professor_mes_abs.get(nom, {})
        serv_data = per_professor_mes_serv.get(nom, {})
        for mes in mesos:
            a = abs_data.get(mes, 0)
            s = serv_data.get(mes, 0)
            if a > 0 and a >= s:
                bg_matrix[(nom, mes)] = _heatmap_color(a, max_abs)
            elif s > 0:
                bg_matrix[(nom, mes)] = _heatmap_color_blue(s, max_serv)
            else:
                bg_matrix[(nom, mes)] = C_WHITE

    rows = [header]
    for p in professors[:len(per_professor_mes_abs)]:
        nom = p["nom"]
        abs_data  = per_professor_mes_abs.get(nom, {})
        serv_data = per_professor_mes_serv.get(nom, {})
        tot_abs  = p["absencies"]
        tot_serv = p["serveis"]

        row = [Paragraph(nom, _s("pn", fontName="Helvetica", fontSize=7.5,
                                 textColor=C_BLACK, alignment=TA_LEFT, leading=10))]
        for mes in mesos:
            a = abs_data.get(mes, 0)
            s = serv_data.get(mes, 0)
            if a == 0 and s == 0:
                cell = Paragraph("—", _s("pz", fontName="Helvetica", fontSize=7,
                                         textColor=C_GREY_MID, alignment=TA_CENTER, leading=9))
            else:
                a_str = f'<font color="#c0392b"><b>{a}</b></font>' if a > 0 else '<font color="#c0392b">0</font>'
                s_str = f'<font color="#7c3aed">{s}</font>' if s > 0 else '<font color="#7c3aed">0</font>'
                cell = Paragraph(
                    f'{a_str}/{s_str}',
                    _s("pcell", fontName="Helvetica", fontSize=7.5,
                       alignment=TA_CENTER, leading=10)
                )
            row.append(cell)

        row.append(Paragraph(str(tot_abs) if tot_abs else "—",
                             _s("pta", fontName="Helvetica-Bold", fontSize=7.5,
                                textColor=colors.HexColor("#c0392b"), alignment=TA_CENTER, leading=10)))
        row.append(Paragraph(str(tot_serv) if tot_serv else "—",
                             _s("pts", fontName="Helvetica-Bold", fontSize=7.5,
                                textColor=colors.HexColor("#7c3aed"), alignment=TA_CENTER, leading=10)))
        rows.append(row)

    n_mesos = len(mesos)
    nom_w  = 3.8 * cm
    tot_w  = 1.0 * cm
    mes_w  = (CONTENT_W - nom_w - 2 * tot_w) / n_mesos
    col_w  = [nom_w] + [mes_w] * n_mesos + [tot_w, tot_w]

    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), C_NAVY),
        ("TOPPADDING",     (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, 0), 5),
        ("TOPPADDING",     (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING",  (0, 1), (-1, -1), 3),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ("GRID",           (0, 0), (-1, -1), 0.3, C_GREY_MID),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GREY_BG]),
        # Columnes totals destacades
        ("BACKGROUND",     (-2, 0), (-1, 0), C_ORANGE),
        ("BACKGROUND",     (-2, 1), (-2, -1), colors.HexColor("#fff0e0")),
        ("BACKGROUND",     (-1, 1), (-1, -1), colors.HexColor("#e8f4fb")),
        ("LINEABOVE",      (0, -1), (-1, -1), 0.5, C_GREY_MID),
    ])

    # Heatmap: fons taronja per absències, blau per serveis (el que és més gran domina)
    for r_idx, p in enumerate(professors[:len(per_professor_mes_abs)], start=1):
        nom = p["nom"]
        abs_data  = per_professor_mes_abs.get(nom, {})
        serv_data = per_professor_mes_serv.get(nom, {})
        for c_idx, mes in enumerate(mesos, start=1):
            a = abs_data.get(mes, 0)
            s = serv_data.get(mes, 0)
            if a > 0 and a >= s:
                st.add("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), _heatmap_color(a, max_abs))
            elif s > 0:
                st.add("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), _heatmap_color_blue(s, max_serv))

    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.2 * cm))
    elems.append(Paragraph(
        f'<font color="#c0392b">■ {_("Absències reals")}</font> &nbsp;&nbsp; '
        f'<font color="#7c3aed">■ {_("Serveis / comissions")}</font> &nbsp;&nbsp; '
        f'{_("Intensitat de color: proporció respecte al màxim del curs")}',
        STYLES["note"]
    ))
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _taula_matriu_substitucions_mesos(per_substitut_mes: dict, mesos: list,
                                       professors_subs: list) -> list:
    """Matriu heatmap substituts × mesos"""
    elems = _section_title(_("Evolució de substitucions fetes per professor i mes"))

    if not mesos or not per_substitut_mes:
        return elems

    mesos_curts = [m.split()[0][:3] for m in mesos]
    max_val = max((v for d in per_substitut_mes.values() for v in d.values()), default=1) or 1

    C_TEAL_HM = colors.HexColor("#16a085")

    def _heatmap_teal(value, max_v):
        if max_v == 0 or value == 0:
            return C_WHITE
        intensity = min(value / max_v, 1.0)
        r = 1.0 - intensity * (1.0 - 0.086)
        g = 1.0 - intensity * (1.0 - 0.627)
        b = 1.0 - intensity * (1.0 - 0.522)
        return colors.Color(r, g, b)

    header = [
        Paragraph(_("Professor/a"), _s("sh", fontName="Helvetica-Bold", fontSize=7.5,
                                    textColor=C_WHITE, alignment=TA_LEFT, leading=10))
    ] + [
        Paragraph(mc, _s("shc", fontName="Helvetica-Bold", fontSize=7,
                         textColor=C_WHITE, alignment=TA_CENTER, leading=9))
        for mc in mesos_curts
    ] + [
        Paragraph(_("Total"), _s("sht", fontName="Helvetica-Bold", fontSize=7,
                              textColor=C_WHITE, alignment=TA_CENTER, leading=9))
    ]

    rows = [header]
    for p in professors_subs[:len(per_substitut_mes)]:
        nom = p["nom"]
        mes_data = per_substitut_mes.get(nom, {})
        total = p["total"]
        row = [Paragraph(nom, _s("spn", fontName="Helvetica", fontSize=7.5,
                                 textColor=C_BLACK, alignment=TA_LEFT, leading=10))]
        for mes in mesos:
            val = mes_data.get(mes, 0)
            if val == 0:
                cell = Paragraph("—", _s("spz", fontName="Helvetica", fontSize=7,
                                         textColor=C_GREY_MID, alignment=TA_CENTER, leading=9))
            else:
                cell = Paragraph(
                    f"<b>{val}</b>",
                    _s("spcell", fontName="Helvetica-Bold", fontSize=7.5,
                       textColor=C_NAVY, alignment=TA_CENTER, leading=10)
                )
            row.append(cell)
        row.append(Paragraph(str(total),
                             _s("sptot", fontName="Helvetica-Bold", fontSize=7.5,
                                textColor=C_TEAL, alignment=TA_CENTER, leading=10)))
        rows.append(row)

    n_mesos = len(mesos)
    nom_w = 3.8 * cm
    tot_w = 1.2 * cm
    mes_w = (CONTENT_W - nom_w - tot_w) / n_mesos
    col_w = [nom_w] + [mes_w] * n_mesos + [tot_w]

    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), C_TEAL),
        ("TOPPADDING",     (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, 0), 5),
        ("TOPPADDING",     (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING",  (0, 1), (-1, -1), 3),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ("GRID",           (0, 0), (-1, -1), 0.3, C_GREY_MID),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GREY_BG]),
        ("BACKGROUND",     (-1, 1), (-1, -1), colors.HexColor("#e0f5f1")),
    ])

    for r_idx, p in enumerate(professors_subs[:len(per_substitut_mes)], start=1):
        nom = p["nom"]
        mes_data = per_substitut_mes.get(nom, {})
        for c_idx, mes in enumerate(mesos, start=1):
            val = mes_data.get(mes, 0)
            if val > 0:
                st.add("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx),
                       _heatmap_teal(val, max_val))

    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.2 * cm))
    elems.append(Paragraph(
        _("Intensitat de color: proporció respecte al màxim del curs"),
        STYLES["note"]
    ))
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _taula_professors_substitucions(professors: list, top: int = 20) -> list:
    """Rànquing de professors per substitucions fetes"""
    elems = _section_title(_("Professors que han fet més substitucions"))

    headers = ["#", _("Professor/a"), _("Substitucions fetes"), _("% sobre total")]
    total_global = sum(p["total"] for p in professors) or 1
    rows = [headers]
    for i, p in enumerate(professors[:top], 1):
        pct = p["total"] / total_global * 100
        rows.append([
            str(i),
            p["nom"],
            str(p["total"]),
            f"{pct:.1f}%",
        ])

    col_w = [0.8*cm, 7*cm, 4*cm, 3*cm]
    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = _table_style_base(C_TEAL)
    for col in range(2, 4):
        st.add("ALIGN", (col, 1), (col, -1), "CENTER")
    t.setStyle(st)
    elems.append(t)
    if len(professors) > top:
        elems.append(Paragraph(_("* Mostrant els {top} primers de {total} professors").format(top=top, total=len(professors)), STYLES["note"]))
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _heatmap_color(value: int, max_val: int) -> colors.Color:
    """Color de blanc a taronja fosc segons intensitat"""
    if max_val == 0 or value == 0:
        return C_WHITE
    intensity = min(value / max_val, 1.0)
    # Blanc → taronja (#e67e22)
    base_r, base_g, base_b = 0.902, 0.494, 0.133
    r = 1.0 - intensity * (1.0 - base_r)
    g = 1.0 - intensity * (1.0 - base_g)
    b = 1.0 - intensity * (1.0 - base_b)
    return colors.Color(r, g, b)


def _color_cobertura(pct: int) -> colors.Color:
    """Verd si alta cobertura, vermell si baixa"""
    if pct >= 90:
        return colors.HexColor("#27ae60")
    if pct >= 70:
        return colors.HexColor("#e67e22")
    return colors.HexColor("#c0392b")


def _taula_grups_per_nivell(grups_data: dict) -> list:
    """Taula resum de grups agrupada per nivell amb cobertura"""
    elems = _section_title(_("Impacte per grup i nivell"))

    ordre = grups_data["ordre_nivells"]
    per_nivell = grups_data["per_nivell"]
    grups_ordenats = grups_data["grups_ordenats"]

    # ── Part 1: Resum per nivell ───────────────────────────────────────
    elems.append(Paragraph(_("Resum per nivell"), _s("sub",
        fontName="Helvetica-Bold", fontSize=10, textColor=C_NAVY,
        leading=14, spaceBefore=4)))
    elems.append(Spacer(1, 0.2*cm))

    headers_niv = [_("Nivell"), _("Grups"), _("Absències"), _("Cobertes"), _("Pendents"), _("Cobertura")]
    rows_niv = [headers_niv]
    for niv in ordre:
        if niv not in per_nivell:
            continue
        v = per_nivell[niv]
        rows_niv.append([
            niv,
            str(v["n_grups"]),
            str(v["absencies"]),
            str(v["cobertes"]),
            str(v["pendents"]),
            f"{v['pct']}%",
        ])
    # Fila total
    tot_abs = sum(v["absencies"] for v in per_nivell.values())
    tot_cob = sum(v["cobertes"]  for v in per_nivell.values())
    tot_pen = tot_abs - tot_cob
    tot_pct = round(tot_cob / tot_abs * 100) if tot_abs else 0
    rows_niv.append([_("TOTAL"), "—", str(tot_abs), str(tot_cob), str(tot_pen), f"{tot_pct}%"])

    col_niv = [3*cm, 1.8*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
    t_niv = Table(rows_niv, colWidths=col_niv, hAlign="LEFT")
    st_niv = _table_style_base(C_NAVY)
    for col in range(1, 6):
        st_niv.add("ALIGN", (col, 1), (col, -1), "CENTER")
    # Color cobertura per fila de nivell
    for r_idx, niv in enumerate([n for n in ordre if n in per_nivell], start=1):
        pct = per_nivell[niv]["pct"]
        c = _color_cobertura(pct)
        st_niv.add("TEXTCOLOR", (5, r_idx), (5, r_idx), c)
        st_niv.add("FONTNAME",  (5, r_idx), (5, r_idx), "Helvetica-Bold")
    # Fila total
    last = len(rows_niv) - 1
    st_niv.add("BACKGROUND", (0, last), (-1, last), colors.HexColor("#d5e8f5"))
    st_niv.add("FONTNAME",   (0, last), (-1, last), "Helvetica-Bold")
    st_niv.add("LINEABOVE",  (0, last), (-1, last), 1, C_NAVY)
    st_niv.add("TEXTCOLOR",  (5, last), (5, last), _color_cobertura(tot_pct))
    t_niv.setStyle(st_niv)
    elems.append(t_niv)
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph(
        '<font color="#27ae60">■ ≥90%</font>  '
        '<font color="#e67e22">■ 70-89%</font>  '
        '<font color="#c0392b">■ &lt;70%</font>',
        STYLES["note"]
    ))
    elems.append(Spacer(1, 0.4*cm))
    return elems


def _taula_matriu_grups_mesos(grups_data: dict) -> list:
    """Matriu heatmap grups × mesos"""
    elems = _section_title(_("Evolució d'absències per grup i mes"))

    per_grup_mes = grups_data["per_grup_mes"]
    mesos = grups_data["mesos"]
    grups_ordenats = grups_data["grups_ordenats"]

    if not mesos or not grups_ordenats:
        return elems

    mesos_curts = [m.split()[0][:3] for m in mesos]
    max_val = max(
        (v for d in per_grup_mes.values() for v in d.values()),
        default=1
    ) or 1

    header = [
        Paragraph(_("Grup"), _s("gh", fontName="Helvetica-Bold", fontSize=7.5,
                              textColor=C_WHITE, alignment=TA_LEFT, leading=10)),
        Paragraph(_("Niv."), _s("ghn", fontName="Helvetica-Bold", fontSize=7,
                              textColor=C_WHITE, alignment=TA_CENTER, leading=9)),
    ] + [
        Paragraph(mc, _s("ghc", fontName="Helvetica-Bold", fontSize=7,
                         textColor=C_WHITE, alignment=TA_CENTER, leading=9))
        for mc in mesos_curts
    ] + [
        Paragraph(_("Tot."), _s("ght", fontName="Helvetica-Bold", fontSize=7,
                             textColor=C_WHITE, alignment=TA_CENTER, leading=9))
    ]

    rows = [header]
    for g in grups_ordenats:
        nom = g["nom"]
        mes_data = per_grup_mes.get(nom, {})
        row = [
            Paragraph(nom, _s("gn", fontName="Helvetica", fontSize=7.5,
                              textColor=C_BLACK, alignment=TA_LEFT, leading=10)),
            Paragraph(g["nivell"].replace(" ", "\n"), _s("gnv", fontName="Helvetica", fontSize=6.5,
                              textColor=C_GREY_TXT, alignment=TA_CENTER, leading=8)),
        ]
        for mes in mesos:
            val = mes_data.get(mes, 0)
            if val == 0:
                cell = Paragraph("—", _s("gz", fontName="Helvetica", fontSize=7,
                                         textColor=C_GREY_MID, alignment=TA_CENTER, leading=9))
            else:
                bg = _heatmap_color(val, max_val)
                tc = _text_color_for_bg(bg)
                cell = Paragraph(
                    f'<font color="{tc.hexval()}"><b>{val}</b></font>',
                    _s("gcell", fontName="Helvetica-Bold", fontSize=7.5,
                       alignment=TA_CENTER, leading=10)
                )
            row.append(cell)
        row.append(Paragraph(str(g["absencies"]),
                             _s("gtot", fontName="Helvetica-Bold", fontSize=7.5,
                                textColor=C_NAVY, alignment=TA_CENTER, leading=10)))
        rows.append(row)

    n_mesos = len(mesos)
    nom_w  = 2.8*cm
    niv_w  = 1.5*cm
    tot_w  = 1.0*cm
    mes_w  = (CONTENT_W - nom_w - niv_w - tot_w) / n_mesos
    col_w  = [nom_w, niv_w] + [mes_w]*n_mesos + [tot_w]

    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), C_NAVY),
        ("TOPPADDING",     (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, 0), 5),
        ("TOPPADDING",     (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING",  (0, 1), (-1, -1), 3),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ("GRID",           (0, 0), (-1, -1), 0.3, C_GREY_MID),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GREY_BG]),
        ("BACKGROUND",     (-1, 1), (-1, -1), colors.HexColor("#eaf0f8")),
        ("FONTNAME",       (-1, 1), (-1, -1), "Helvetica-Bold"),
    ])

    for r_idx, g in enumerate(grups_ordenats, start=1):
        mes_data = per_grup_mes.get(g["nom"], {})
        for c_idx, mes in enumerate(mesos, start=2):  # +2 per nom+niv
            val = mes_data.get(mes, 0)
            if val > 0:
                st.add("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx),
                       _heatmap_color(val, max_val))

    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.2*cm))
    elems.append(Paragraph(
        _("Intensitat de color: proporció d'absències respecte al màxim del curs"),
        STYLES["note"]
    ))
    elems.append(Spacer(1, 0.4*cm))
    return elems


def _taula_matriu_dia_hora(per_dia_hora: dict, per_hora: dict, hores_xml: list = None) -> list:
    """Matriu hores × dies amb heatmap d'absències"""
    elems = _section_title(_("Distribució per dia de la setmana i hora"))

    # Claus canòniques neutres d'idioma (índex del dia, 0=dilluns) — coincideixen
    # amb les guardades a informes.py. La traducció es fa només a l'etiqueta mostrada.
    dies_ordre = list(range(5))
    dies_curt  = [_("Dll"), _("Dmt"), _("Dmc"), _("Djo"), _("Div")]

    # Usar ordre del XML si disponible, sinó ordenar cronològicament amb no-hora al final
    def _sort_key_hora(h):
        return (1, h) if not h[:2].replace(":", "").isdigit() else (0, h)

    if hores_xml:
        hores_ordre = [h for h in hores_xml if h in per_hora]
        # Hores a les dades però no al XML → afegir ordenades cronològicament
        hores_ordre += sorted([h for h in per_hora if h not in hores_ordre], key=_sort_key_hora)
    else:
        hores_ordre = sorted(per_hora.keys(), key=_sort_key_hora)

    # Màxim d'absències per normalitzar el heatmap
    max_abs = max(
        (per_dia_hora.get((dia, hora), {}).get("absencies", 0)
         for dia in dies_ordre for hora in hores_ordre),
        default=1
    ) or 1

    # Capçalera
    header_row = [
        Paragraph(_("Hora"), _s("mh", fontName="Helvetica-Bold", fontSize=8,
                              textColor=C_WHITE, alignment=TA_CENTER, leading=10))
    ]
    for dc in dies_curt:
        header_row.append(
            Paragraph(dc, _s("mh2", fontName="Helvetica-Bold", fontSize=8,
                             textColor=C_WHITE, alignment=TA_CENTER, leading=10))
        )

    rows = [header_row]

    for hora in hores_ordre:
        row = [Paragraph(hora, _s("mhr", fontName="Helvetica-Bold", fontSize=8,
                                  textColor=C_NAVY, alignment=TA_CENTER, leading=10))]
        for dia in dies_ordre:
            d = per_dia_hora.get((dia, hora), {"absencies": 0, "substitucions": 0})
            abs_n = d["absencies"]
            sub_n = d["substitucions"]
            if abs_n == 0:
                cell_text = Paragraph(
                    "—",
                    _s("mc0", fontName="Helvetica", fontSize=8,
                       textColor=C_GREY_MID, alignment=TA_CENTER, leading=10)
                )
            else:
                pct = int(sub_n / abs_n * 100) if abs_n > 0 else 0
                cell_text = Paragraph(
                    f'<font size="11" color="{C_NAVY.hexval()}"><b>{abs_n}</b></font>'
                    f'<br/><font size="7" color="#16a085">▶ {sub_n} ({pct}%)</font>',
                    _s("mc", fontName="Helvetica", fontSize=8,
                       alignment=TA_CENTER, leading=12)
                )
            row.append(cell_text)
        rows.append(row)

    # Fila de totals per dia
    total_row = [Paragraph(_("TOTAL"), _s("mtt", fontName="Helvetica-Bold", fontSize=7.5,
                                        textColor=C_NAVY, alignment=TA_CENTER, leading=10))]
    for dia in dies_ordre:
        tot_abs = sum(
            per_dia_hora.get((dia, h), {}).get("absencies", 0) for h in hores_ordre
        )
        tot_sub = sum(
            per_dia_hora.get((dia, h), {}).get("substitucions", 0) for h in hores_ordre
        )
        pct = int(tot_sub / tot_abs * 100) if tot_abs > 0 else 0
        total_row.append(Paragraph(
            f'<b>{tot_abs}</b><br/><font size="7" color="#16a085">{tot_sub} ({pct}%)</font>',
            _s("mtt2", fontName="Helvetica-Bold", fontSize=8,
               alignment=TA_CENTER, leading=12)
        ))
    rows.append(total_row)

    # Amplades: hora + 5 dies
    hora_w = 1.8 * cm
    dia_w  = (CONTENT_W - hora_w) / 5
    col_w  = [hora_w] + [dia_w] * 5

    t = Table(rows, colWidths=col_w, hAlign="LEFT")

    st = TableStyle([
        # Capçalera
        ("BACKGROUND",    (0, 0), (-1, 0), C_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        # Columna hora
        ("BACKGROUND",    (0, 1), (0, -2), colors.HexColor("#eaf0f8")),
        ("FONTNAME",      (0, 1), (0, -2), "Helvetica-Bold"),
        # Fila total
        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#d5e8f5")),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE",     (0, -1), (-1, -1), 1, C_NAVY),
        # General
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_GREY_MID),
        ("TOPPADDING",    (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ])

    # Heatmap: color de fons per cada cel·la de dades
    for r_idx, hora in enumerate(hores_ordre, start=1):
        for c_idx, dia in enumerate(dies_ordre, start=1):
            abs_n = per_dia_hora.get((dia, hora), {}).get("absencies", 0)
            bg = _heatmap_color(abs_n, max_abs)
            st.add("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), bg)

    t.setStyle(st)
    elems.append(t)

    # Llegenda
    elems.append(Spacer(1, 0.2 * cm))
    elems.append(Paragraph(
        _("Cada cel·la mostra: <b>absències totals</b> (fons: intensitat = més absències) "
        "i <font color='#16a085'>▶ substitucions cobertes (%)</font>"),
        STYLES["note"]
    ))
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _taula_distribucio(per_dia: dict, per_hora: dict) -> list:
    """Taules de distribució per dia i hora"""
    elems = _section_title(_("Distribució per dia de la setmana i hora"))

    # Subtaula: per dia. Clau canònica = índex (0=dilluns); nom traduït només per mostrar.
    dies_nom = [_("Dilluns"), _("Dimarts"), _("Dimecres"), _("Dijous"), _("Divendres")]
    rows_dia = [[_("Dia"), _("Absències"), _("Substitucions")]]
    for idx, nom in enumerate(dies_nom):
        d = per_dia.get(idx, {})
        rows_dia.append([nom, str(d.get("absencies", 0)), str(d.get("substitucions", 0))])

    # Subtaula: per hora
    hores_ordre = sorted(per_hora.keys(), key=lambda h: h if h != "Pati" else "ZZ")
    rows_hora = [[_("Hora"), _("Absències"), _("Substitucions")]]
    for hora in hores_ordre:
        h = per_hora[hora]
        rows_hora.append([hora, str(h.get("absencies", 0)), str(h.get("substitucions", 0))])

    col_dia = [4*cm, 3*cm, 3.5*cm]
    col_hora = [3*cm, 2.5*cm, 3*cm]

    t_dia = Table(rows_dia, colWidths=col_dia)
    t_dia.setStyle(_table_style_base(C_BLUE))

    t_hora = Table(rows_hora, colWidths=col_hora)
    t_hora.setStyle(_table_style_base(C_BLUE))

    # Posem les dues taules juntes en una fila
    wrapper = Table(
        [[t_dia, Spacer(1, 1), t_hora]],
        colWidths=[sum(col_dia) + 0.3*cm, 0.5*cm, sum(col_hora) + 0.3*cm],
    )
    wrapper.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elems.append(wrapper)
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def _taula_vigilancies(vig_stats: dict) -> list:
    """Estadístiques de vigilàncies"""
    elems = _section_title(_("Vigilàncies d'examen"))

    rows = [[_("Concepte"), _("Total")]]
    rows.append([_("Total vigilàncies programades"), str(vig_stats.get("total", 0))])
    rows.append([_("Vigilants absents (cobertura necessària)"), str(vig_stats.get("absents", 0))])
    rows.append([_("Vigilants absents coberts"), str(vig_stats.get("coberts", 0))])
    rows.append([_("Vigilants absents pendents"), str(vig_stats.get("pendents", 0))])

    col_w = [10*cm, 4*cm]
    t = Table(rows, colWidths=col_w, hAlign="LEFT")
    st = _table_style_base(C_TEAL)
    st.add("ALIGN", (1, 1), (1, -1), "CENTER")
    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.4 * cm))
    return elems


def generar_informe_pdf(
    dades: dict,
    nom_centre: str,
    data_inici: str,
    data_final: str,
    export_dir: str = "exports",
    logo_path: str = None,
    lang: str = "ca",
) -> str:
    """
    Genera l'informe de direcció en PDF.
    `dades` ha de contenir: stats, per_mes, professors_absencies,
    professors_substitucions, per_dia, per_hora, vigilancies
    """
    setup_translation(lang)
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%y%m%d_%H%M%S")
    filename = export_path / f"informe_direccio_{ts}.pdf"

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")

    doc = SimpleDocTemplate(
        str(filename),
        pagesize=A4,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        title=_("Informe de Substitucions"),
        author=nom_centre,
    )

    story = []

    # Capçalera
    story += _header_block(nom_centre, data_inici, data_final, timestamp, logo_path=logo_path)

    # KPIs
    story += _kpi_cards(dades["stats"])

    # Evolució mensual
    if dades.get("per_mes"):
        story += _taula_evolucio_mensual(dades["per_mes"])

    # Matriu professors × mesos (absències + serveis)
    if dades.get("per_professor_mes_abs") and dades.get("mesos_ordenats"):
        story.append(PageBreak())
        story += _taula_matriu_professors_mesos(
            dades["per_professor_mes_abs"],
            dades["per_professor_mes_serv"],
            dades["mesos_ordenats"],
            dades["professors_absencies"],
        )

    # Matriu substitucions × mesos
    if dades.get("per_substitut_mes") and dades.get("mesos_ordenats"):
        story.append(PageBreak())
        story += _taula_matriu_substitucions_mesos(
            dades["per_substitut_mes"],
            dades["mesos_ordenats"],
            dades["professors_substitucions"],
        )

    # Matriu dia × hora
    if dades.get("per_dia_hora"):
        story.append(PageBreak())
        story += _taula_matriu_dia_hora(
            dades["per_dia_hora"],
            dades.get("per_hora", {}),
            hores_xml=dades.get("hores_ordre"),
        )

    # Grups per nivell + matriu grups × mesos
    if dades.get("grups_data"):
        story.append(PageBreak())
        story += _taula_grups_per_nivell(dades["grups_data"])
        story.append(PageBreak())
        story += _taula_matriu_grups_mesos(dades["grups_data"])

    # Peu de pàgina
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width=CONTENT_W, thickness=0.3, color=C_GREY_MID))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        _("Informe generat el {timestamp} · {nom_centre}").format(timestamp=timestamp, nom_centre=nom_centre),
        STYLES["footer"]
    ))

    doc.build(story)
    return str(filename)
