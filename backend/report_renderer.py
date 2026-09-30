from io import BytesIO
from pathlib import Path
import json
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, LETTER, LEGAL, A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from PyPDF2 import PdfReader, PdfWriter


PAGE_SIZES = {"A4": A4, "A5": A5, "LETTER": LETTER, "LEGAL": LEGAL}
PAGE_W, PAGE_H = A4

DEFAULT_LAYOUT = {
    "page": {
        "size": "A4",
        "left": 52,
        "right": 52,
        "top": 132,
        "bottom": 82,
    },
    "patient": {
        "visible": [
            "name", "age", "sex", "code", "uhid", "referred_by",
            "received_on", "reported_on", "phone"
        ],
        "order": [
            "name", "age_gender", "code", "uhid", "referred_by",
            "received_on", "reported_on", "phone"
        ],
        "columns": 2,
        "style": "card",
        "font_size": 8.5,
        "label_bold": True,
        "background": "#F5F6F8",
        "border": "#E2E5EC",
    },
    "results": {
        "columns": ["name", "value", "unit", "reference_range"],
        "section_order": [],
        "section_align": "left",
        "section_bold": True,
        "section_font_size": 7.9,
        "section_text": "#151A2D",
        "section_padding": 5,
        "section_headers": True,
        "section_background": "#ECEAFB",
        "table_header_background": "#F7F7FA",
        "font_size": 9,
        "header_size": 7.5,
        "show_grid": False,
    },
    "appearance": {
        "text": "#151A2D",
        "accent": "#5F52E8",
        "font": "Helvetica",
    },
}

FIELD_LABELS = {
    "name": "Patient Name",
    "age_gender": "Age / Gender",
    "age": "Age",
    "sex": "Gender",
    "code": "Patient ID",
    "uhid": "UHID",
    "referred_by": "Referred By",
    "received_on": "Received On",
    "reported_on": "Reported On",
    "phone": "Phone",
}

RESULT_LABELS = {
    "name": "TEST",
    "value": "RESULT",
    "unit": "UNIT",
    "reference_range": "REFERENCE",
}


def _merge_layout(layout):
    out = json.loads(json.dumps(DEFAULT_LAYOUT))
    if isinstance(layout, dict):
        for group in ("page", "patient", "results", "appearance"):
            if isinstance(layout.get(group), dict):
                out[group].update(layout[group])
    return out


def _color(value, fallback):
    try:
        return colors.HexColor(str(value))
    except Exception:
        return fallback


def _font_name(layout, bold=False, italic=False):
    base = str(layout.get("appearance", {}).get("font") or "Helvetica")
    allowed = {"Helvetica", "Times-Roman", "Courier"}
    if base not in allowed:
        base = "Helvetica"
    if bold:
        return {
            "Helvetica": "Helvetica-Bold",
            "Times-Roman": "Times-Bold",
            "Courier": "Courier-Bold",
        }[base]
    if italic:
        return {
            "Helvetica": "Helvetica-Oblique",
            "Times-Roman": "Times-Italic",
            "Courier": "Courier-Oblique",
        }[base]
    return base


def _page_size(layout):
    page = layout.get("page", {})
    if page.get("width") and page.get("height"):
        try:
            return float(page["width"]), float(page["height"])
        except Exception:
            pass
    key = str(page.get("size", "A4")).upper()
    return PAGE_SIZES.get(key, A4)


def _metrics(layout):
    page = layout["page"]
    left = max(12, float(page.get("left", 52)))
    right = max(12, float(page.get("right", 52)))
    top = max(24, float(page.get("top", 132)))
    bottom = max(24, float(page.get("bottom", 82)))
    _, page_h = _page_size(layout)
    return left, right, page_h - top, bottom


def _safe_text(value):
    return escape(str(value or "").strip()).replace("\n", "<br/>")


def _patient_value(patient, key):
    if key == "age_gender":
        age = str(patient.get("age", "") or "").strip()
        sex = str(patient.get("sex", "") or "").strip()
        if age and sex:
            return f"{age}Y / {sex.upper()}" if age.isdigit() else f"{age} / {sex.upper()}"
        return age or sex.upper()
    return patient.get(key, "")


def _paragraph_styles(layout):
    appearance = layout["appearance"]
    patient = layout["patient"]
    results = layout["results"]
    text = _color(appearance.get("text"), colors.black)
    muted = _color(appearance.get("muted"), colors.HexColor("#667085"))

    base_font = _font_name(layout)
    bold_font = _font_name(layout, bold=True)
    italic_font = _font_name(layout, italic=True)

    return {
        "patient_label": ParagraphStyle(
            "patient_label",
            fontName=bold_font if patient.get("label_bold", True) else base_font,
            fontSize=6.6,
            leading=8,
            textColor=muted,
            spaceAfter=1,
        ),
        "patient_value": ParagraphStyle(
            "patient_value",
            fontName=base_font,
            fontSize=float(patient.get("font_size", 8.5)),
            leading=float(patient.get("font_size", 8.5)) + 2,
            textColor=text,
        ),
        "patient_title": ParagraphStyle(
            "patient_title",
            fontName=bold_font,
            fontSize=7.8,
            leading=9,
            textColor=text,
        ),
        "report_title": ParagraphStyle(
            "report_title",
            fontName=bold_font,
            fontSize=10,
            leading=12,
            textColor=text,
            spaceAfter=4,
        ),
        "department": ParagraphStyle(
            "department",
            fontName=bold_font,
            fontSize=10,
            leading=12,
            textColor=text,
            spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "section",
            fontName=bold_font,
            fontSize=7.9,
            leading=9,
            textColor=text,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName=bold_font,
            fontSize=float(results.get("header_size", 7.5)),
            leading=float(results.get("header_size", 7.5)) + 1,
            textColor=text,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontName=base_font,
            fontSize=float(results.get("font_size", 9)),
            leading=float(results.get("font_size", 9)) + 2,
            textColor=text,
        ),
        "table_value": ParagraphStyle(
            "table_value",
            fontName=bold_font,
            fontSize=float(results.get("font_size", 9)),
            leading=float(results.get("font_size", 9)) + 2,
            textColor=text,
        ),
        "empty": ParagraphStyle(
            "empty",
            fontName=italic_font,
            fontSize=9,
            leading=11,
            textColor=text,
        ),
    }


def _patient_block(patient, layout, styles, available_width):
    cfg = layout["patient"]
    visible = list(cfg.get("visible") or DEFAULT_LAYOUT["patient"]["visible"])
    order = list(cfg.get("order") or DEFAULT_LAYOUT["patient"]["order"])
    items = [k for k in order if k in visible and k in FIELD_LABELS]
    if "name" in visible and "name" not in items:
        items.insert(0, "name")
    if not items:
        return Spacer(1, 6)

    cols = 1 if int(cfg.get("columns", 2)) == 1 else 2
    cols = min(cols, len(items))
    gap = 7 * mm if cols == 2 else 0
    col_width = (available_width - gap * (cols - 1)) / cols

    rows = []
    for i in range(0, len(items), cols):
        row = []
        for key in items[i:i + cols]:
            label = FIELD_LABELS[key].upper()
            value = _safe_text(_patient_value(patient, key))
            row.append([
                Paragraph(label, styles["patient_label"]),
                Paragraph(value, styles["patient_value"]),
            ])
        while len(row) < cols:
            row.append("")
        rows.append(row)

    cell_tables = []
    for row in rows:
        cells = []
        for cell in row:
            if not cell:
                cells.append("")
                continue
            cells.append(Table(
                [[cell[0]], [cell[1]]],
                colWidths=[col_width],
                style=TableStyle([
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]),
            ))
        cell_tables.append(cells)

    patient_table = Table(
        cell_tables,
        colWidths=[col_width] * cols,
        hAlign="LEFT",
        repeatRows=0,
    )

    bg = _color(cfg.get("background"), colors.HexColor("#F5F7FA"))
    border = _color(cfg.get("border"), colors.HexColor("#E1E5EC"))

    style_cmds = [
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]

    if cfg.get("style", "card") != "plain":
        style_cmds += [
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BOX", (0, 0), (-1, -1), 0.7, border),
        ]

    outer = Table(
        [[Paragraph("PATIENT INFORMATION", styles["patient_title"])],
         [patient_table]],
        colWidths=[available_width],
        hAlign="LEFT",
        style=TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 11),
            ("RIGHTPADDING", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("TOPPADDING", (0, 1), (-1, 1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, border),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), bg)
            if cfg.get("style", "card") != "plain"
            else ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.7, border)
            if cfg.get("style", "card") != "plain"
            else ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ]),
    )

    return [outer, Spacer(1, 9)]


def _result_columns(layout, available_width):
    columns = [x for x in layout["results"].get("columns", []) if x in RESULT_LABELS]
    if not columns:
        columns = DEFAULT_LAYOUT["results"]["columns"]

    weights = {
        "name": 0.42,
        "value": 0.18,
        "unit": 0.16,
        "reference_range": 0.24,
    }
    usable = available_width
    raw = [weights.get(k, 1 / len(columns)) for k in columns]
    total = sum(raw) or 1
    return columns, [usable * w / total for w in raw]


def _result_table(title, rows, layout, styles, available_width):
    results = layout["results"]
    columns, widths = _result_columns(layout, available_width)
    text_style = styles["table_cell"]
    value_style = styles["table_value"]
    header_style = styles["table_header"]

    header = [Paragraph(RESULT_LABELS[k], header_style) for k in columns]
    data = [header]

    for row in rows:
        data.append([
            Paragraph(
                _safe_text(row.get(key, "")),
                value_style if key == "value" else text_style,
            )
            for key in columns
        ])

    table = Table(
        data,
        colWidths=widths,
        repeatRows=1,
        splitByRow=1,
        hAlign="LEFT",
    )

    header_bg = _color(
        results.get("table_header_background"),
        colors.HexColor("#F7F8FA"),
    )
    border = colors.HexColor("#EAECF0")
    row_alt = _color(
        results.get("row_alt_background"),
        colors.HexColor("#FBFCFE"),
    )

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.45, border),
    ]

    for row_index in range(2, len(data), 2):
        style_cmds.append(
            ("BACKGROUND", (0, row_index), (-1, row_index), row_alt)
        )

    if results.get("show_grid", False):
        style_cmds.append(("GRID", (0, 0), (-1, -1), 0.35, border))

    table.setStyle(TableStyle(style_cmds))

    section_header = []
    if results.get("section_headers", True):
        section_bg = _color(
            results.get("section_background"),
            colors.HexColor("#ECEAFB"),
        )
        section_style = ParagraphStyle(
            "section_dynamic",
            parent=styles["section"],
            fontName=_font_name(layout, bold=bool(results.get("section_bold", True))),
            fontSize=float(results.get("section_font_size", 7.9)),
            leading=float(results.get("section_font_size", 7.9)) + 1,
            textColor=_color(results.get("section_text"), colors.black),
            alignment={"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}.get(
                str(results.get("section_align", "left")).lower(), TA_LEFT
            ),
        )
        pad = max(2, float(results.get("section_padding", 5)))
        section_header = [
            Table(
                [[Paragraph(str(title).upper(), section_style)]],
                colWidths=[available_width],
                hAlign="LEFT",
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), section_bg),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), pad),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                ]),
            ),
            Spacer(1, 4),
        ]

    return section_header + [table, Spacer(1, 9)]


def _group_tests(tests, layout=None):
    groups = {}
    discovered = []
    for test in tests or []:
        section = str(test.get("section") or "Unclassified Results").strip()
        if section not in groups:
            groups[section] = []
            discovered.append(section)
        groups[section].append(test)
    configured = list((layout or {}).get("results", {}).get("section_order") or [])
    order = []
    for wanted in configured:
        wanted = str(wanted).strip()
        if wanted and wanted in groups and wanted not in order:
            order.append(wanted)
    for section in discovered:
        if section not in order:
            order.append(section)
    return [(name, groups[name]) for name in order]

class _PageCountCanvas(canvas.Canvas):
    """Canvas that writes Page X of Y after the full document is known."""
    def __init__(self, *args, **kwargs):
        self._page_states = []
        self._aarogyam_layout = kwargs.pop("_aarogyam_layout", DEFAULT_LAYOUT)
        super().__init__(*args, **kwargs)

    def showPage(self):
        self._page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._page_states)
        for state in self._page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        layout = self._aarogyam_layout
        page_w, page_h = _page_size(layout)
        _, right, _, bottom = _metrics(layout)
        text = _color(layout["appearance"].get("text"), colors.HexColor("#151A2D"))
        self.saveState()
        manual = layout.get("manual") or {}
        manual_color = _color(manual.get("text_color"), colors.HexColor("#52606D"))
        self.setFillColor(manual_color)
        self.setFont(_font_name(layout), 7)
        logo_path = Path(str(manual.get("logo_path") or ""))
        if logo_path.exists():
            try:
                logo_w = min(110, float(manual.get("logo_width", 90)))
                logo_h = min(70, float(manual.get("logo_height", 35)))
                logo_x = float(manual.get("logo_x", right))
                logo_y = page_h - float(manual.get("logo_y", 42)) - logo_h
                self.drawImage(ImageReader(str(logo_path)), logo_x, logo_y, width=logo_w, height=logo_h, preserveAspectRatio=True, mask="auto", anchor="sw")
            except Exception:
                pass
        header = str(manual.get("header_text") or "").strip()
        footer = str(manual.get("footer_text") or "").strip()
        if header:
            y = page_h - max(14, float(layout.get("page", {}).get("top", 132)) - 18)
            for line in header.splitlines()[:3]:
                self.drawCentredString(page_w / 2, y, line[:180])
                y -= 9
        if footer:
            y = max(20, float(layout.get("page", {}).get("bottom", 82)) - 18)
            for line in footer.splitlines()[:3]:
                self.drawCentredString(page_w / 2, y + 18, line[:180])
                y -= 9
        self.setFillColor(text)
        self.setFont(_font_name(layout), 7)
        self.drawRightString(page_w - right, max(10, bottom - 18), f"Page {self._pageNumber} of {total}")
        self.restoreState()



class _ReportDocTemplate(BaseDocTemplate):
    def __init__(self, stream, layout, **kwargs):
        self._layout = layout
        left, right, top, bottom = _metrics(layout)
        frame = Frame(
            left,
            bottom,
            _page_size(layout)[0] - left - right,
            top - bottom,
            id="report_body",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self._pagesize = _page_size(layout)
        super().__init__(stream, pagesize=self._pagesize, **kwargs)
        self.addPageTemplates([
            PageTemplate(
                id="report",
                frames=[frame],
            )
        ])


def _build_story(data, layout, available_width):
    styles = _paragraph_styles(layout)
    patient = data.get("patient") or {}
    report = data.get("report") or {}

    story = []
    story.extend(_patient_block(patient, layout, styles, available_width))

    text_color = _color(
        layout["appearance"].get("text"),
        colors.HexColor("#151A2D"),
    )
    accent = _color(
        layout["appearance"].get("accent"),
        colors.HexColor("#5F52E8"),
    )

    department = report.get("department") or data.get("department") or ""
    title = report.get("title") or data.get("title") or "LABORATORY REPORT"

    if department:
        story.append(Paragraph(_safe_text(department).upper(), styles["department"]))

    title_table = Table(
        [[Paragraph(_safe_text(title).upper(), styles["report_title"])]],
        colWidths=[available_width],
        hAlign="LEFT",
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 1.3, accent),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    story.append(title_table)
    story.append(Spacer(1, 8))

    tests = data.get("tests") or []
    for section, rows in _group_tests(tests, layout):
        story.extend(_result_table(section, rows, layout, styles, available_width))

    if not tests:
        story.append(
            Paragraph(
                "No verified test results were entered.",
                styles["empty"],
            )
        )

    return story


def render_body(data, layout=None):
    """
    Render the dynamic Aarogyam report body using ReportLab's flowable
    document engine.

    This intentionally avoids hand-managed Y coordinates. Tables can split
    across pages, repeat their headers, and grow for wrapped values/reference
    ranges. The caller can still merge this body onto a centre PDF template.
    """
    layout = _merge_layout(layout)
    body = BytesIO()
    left, right, _, _ = _metrics(layout)
    available_width = _page_size(layout)[0] - left - right

    doc = _ReportDocTemplate(
        body,
        layout=layout,
        rightMargin=0,
        leftMargin=0,
        topMargin=0,
        bottomMargin=0,
        title="Aarogyam Laboratory Report",
        author="Aarogyam",
    )
    story = _build_story(data, layout, available_width)
    doc.build(story, canvasmaker=lambda *args, **kwargs: _PageCountCanvas(*args, _aarogyam_layout=layout, **kwargs))
    body.seek(0)
    return body


def make_pdf_body_on_template(template_path, data, out, layout=None):
    """
    Generate the dynamic multi-page report body and overlay it on the
    centre's uploaded PDF template.

    When a centre template exists, its first-page dimensions become the
    report page dimensions so the body cannot drift because of a different
    designer page-size selection.
    """
    effective_layout = _merge_layout(layout)
    base = None
    if template_path and Path(template_path).exists():
        base = PdfReader(template_path)
        if not base.pages:
            raise ValueError("Centre template PDF has no pages")
        box = base.pages[0].mediabox
        effective_layout["page"]["width"] = float(box.width)
        effective_layout["page"]["height"] = float(box.height)
        effective_layout["manual"] = {}

    body = render_body(data, effective_layout)
    out.parent.mkdir(parents=True, exist_ok=True)

    if base is not None:
        overlay = PdfReader(body)
        writer = PdfWriter()
        for index, overlay_page in enumerate(overlay.pages):
            base_page = base.pages[index] if index < len(base.pages) else base.pages[-1]
            page = base_page
            page.merge_page(overlay_page)
            writer.add_page(page)
        with open(out, "wb") as f:
            writer.write(f)
    else:
        out.write_bytes(body.read())

