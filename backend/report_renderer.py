from io import BytesIO
from pathlib import Path
from copy import deepcopy
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
    Flowable,
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
        "background_opacity": 100,
        "border": "#E2E5EC",
        "spacing": 12,
        "line_spacing": 1.25,
        "row_gap": 4,
        "width_percent": 100,
        "height": 0,
        "transparent": False,
        "title": "PATIENT INFORMATION",
        "title_align": "left",
        "title_size": 9,
        "title_style": "bold",
        "title_color": "#151A2D",
        "labels": {},
        "top_spacing": 0,
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
        "report_title": "LABORATORY REPORT",
        "report_title_align": "left",
        "report_title_size": 12,
        "report_title_style": "bold",
        "report_title_color": "#151A2D",
        "report_title_line_color": "#5F52E8",
        "section_title": "EXAMINATION RESULTS",
        "section_style": "bold",
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
    out["manual"] = {
        "header_text": "",
        "footer_text": "",
        "text_color": "#52606D",
        "logo_path": "",
        "logo_position": "right",
        "logo_width": 90,
        "logo_height": 35,
    }
    if isinstance(layout, dict):
        for group in ("page", "patient", "results", "appearance", "manual"):
            if isinstance(layout.get(group), dict):
                out[group].update(layout[group])
    return out


def _color(value, fallback):
    try:
        return colors.HexColor(str(value))
    except Exception:
        return fallback


def _styled_font(layout, style="bold"):
    style = str(style or "bold").lower()
    return _font_name(layout, bold=style in ("bold", "bold_italic"), italic=style in ("italic", "bold_italic"))


def _color_opacity(value, opacity, fallback):
    base = _color(value, fallback)
    try:
        alpha = max(0.0, min(1.0, float(opacity) / 100.0))
    except Exception:
        alpha = 1.0
    return colors.Color(base.red, base.green, base.blue, alpha=alpha)


def _alignment(value):
    return {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}.get(
        str(value or "left").lower(), TA_LEFT
    )


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
    """
    Return the report body frame from the saved page settings.

    The designer and PDF compiler use the same page coordinates:
      left/right/bottom are distances from the corresponding page edges,
      top is the distance down from the top edge.
    ReportLab uses points and a bottom-left origin, so the top margin is
    converted to a bottom-based frame boundary here.
    """
    page_w, page_h = _page_size(layout)
    page = layout.get("page") or {}

    left = max(0, float(page.get("left", 52) or 0))
    right = max(0, float(page.get("right", 52) or 0))
    top_offset = max(0, float(page.get("top", 132) or 0))
    bottom = max(0, float(page.get("bottom", 82) or 0))

    # Saved designer geometry is authoritative. Do not scale, clamp, or
    # otherwise repair the user's coordinates here.
    return left, right, page_h - top_offset, bottom


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
            fontSize=6.6 * 0.75,
            leading=8 * 0.75,            textColor=muted,
            spaceAfter=1,
        ),
        "patient_value": ParagraphStyle(
            "patient_value",
            fontName=base_font,
            fontSize=float(patient.get("font_size", 8.5)) * 0.75,
            leading=float(patient.get("font_size", 8.5)) * max(0.8, float(patient.get("line_spacing", 1.25))) * 0.75,
            textColor=text,
        ),
        "patient_title": ParagraphStyle(
            "patient_title",
            fontName=_styled_font(layout, patient.get("title_style", "bold")),
            fontSize=float(patient.get("title_size", 9)) * 0.75,
            leading=(float(patient.get("title_size", 9)) + 1) * 0.75,
            textColor=_color(patient.get("title_color"), text),
            alignment=_alignment(patient.get("title_align", "left")),
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
            fontSize=float(results.get("header_size", 7.5)) * 0.75,
            leading=(float(results.get("header_size", 7.5)) + 1) * 0.75,
            textColor=text,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontName=base_font,
            fontSize=float(results.get("font_size", 9)) * 0.75,
            leading=(float(results.get("font_size", 9)) + 2) * 0.75,
            textColor=text,
        ),
        "table_value": ParagraphStyle(
            "table_value",
            fontName=bold_font,
            fontSize=float(results.get("font_size", 9)) * 0.75,
            leading=(float(results.get("font_size", 9)) + 2) * 0.75,
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


class _PatientPositioned(Flowable):
    """
    Draw a fixed designer element at an absolute page position.

    The browser designer uses the top-left of the body overlay as its
    coordinate origin. ReportLab uses a bottom-left page origin. This class
    deliberately returns zero flow height so Platypus can never move the
    patient block, while drawOn() converts the saved designer x/y to the
    exact PDF position.
    """
    def __init__(self, content, x=0, y=0, origin_x=0, origin_y=0):
        Flowable.__init__(self)
        self.content = content
        self.x = float(x or 0)
        self.y = float(y or 0)
        self.origin_x = float(origin_x or 0)
        self.origin_y = float(origin_y or 0)
        self._w = 0
        self._h = 0

    def wrap(self, availWidth, availHeight):
        w, h = self.content.wrap(availWidth, 1000000)
        self._w = w
        self._h = h
        # IMPORTANT: this element must not participate in Platypus flow.
        return 0, 0

    def drawOn(self, canv, _x, _y, _sW=0):
        if not self._w and not self._h:
            self.wrap(0, 0)

        # ReportLab does not expose the active Frame as a public
        # attribute on a Flowable during drawOn(). Use the exact frame
        # origin captured from the saved page geometry instead.
        pdf_x = self.origin_x + self.x
        pdf_y = self.origin_y - self.y - self._h

        self.content.drawOn(canv, pdf_x, pdf_y, _sW=0)


def _patient_block(patient, layout, styles, available_width):
    cfg = layout["patient"]
    visible = list(cfg.get("visible") or DEFAULT_LAYOUT["patient"]["visible"])
    order = list(cfg.get("order") or DEFAULT_LAYOUT["patient"]["order"])
    items = [k for k in order if k in visible and k in FIELD_LABELS]
    if "age_gender" not in items and ("age_gender" in visible or "age" in visible or "sex" in visible):
        insert_at = 1 if "name" in items else 0
        items.insert(insert_at, "age_gender")
    if "name" in visible and "name" not in items:
        items.insert(0, "name")
    if not items:
        return Spacer(1, 6)

    cols = 1 if int(cfg.get("columns", 2)) == 1 else 2
    cols = min(cols, len(items))
    width_percent = float(cfg.get("width_percent", 100) or 100)
    block_width = available_width * width_percent / 100.0
    gap = 7 * 0.75 if cols == 2 else 0
    col_width = (block_width - gap * (cols - 1)) / cols

    rows = []
    for i in range(0, len(items), cols):
        row = []
        for key in items[i:i + cols]:
            labels = cfg.get("labels") or {}
            label = str(labels.get(key) or FIELD_LABELS[key]).upper()
            value = _safe_text(_patient_value(patient, key))
            row.append([
                Paragraph(label, styles["patient_label"]),
                Paragraph(value, styles["patient_value"]),
            ])
        while len(row) < cols:
            row.append("")
        rows.append(row)

    cell_tables = []
    row_gap = max(0, float(cfg.get("row_gap", 4) or 0))
    label_bold = bool(cfg.get("label_bold", True))
    for row in rows:
        cells = []
        for cell in row:
            if not cell:
                cells.append("")
                continue
            label_markup = f"<b>{cell[0].text}</b>" if label_bold else cell[0].text
            value_markup = cell[1].text
            cells.append(Paragraph(
                f"{label_markup} : {value_markup}",
                styles["patient_value"],
            ))
        cell_tables.append(cells)

    patient_table = Table(
        cell_tables,
        colWidths=[col_width] * cols,
        hAlign="LEFT",
        repeatRows=0,
    )
    # Mirror the browser grid's explicit row-gap without allowing Platypus
    # to reflow the block. The gap is added only between rows.
    if row_gap and len(rows) > 1:
        patient_table.setStyle(TableStyle([
            ("BOTTOMPADDING", (0, i), (-1, i), row_gap * 0.75)
            for i in range(len(rows) - 1)
        ]))

    bg = _color_opacity(cfg.get("background"), cfg.get("background_opacity", 100), colors.HexColor("#F5F7FA"))
    border = _color(cfg.get("border"), colors.HexColor("#E1E5EC"))

    style_cmds = [
        ("LEFTPADDING", (0, 0), (-1, -1), 10 * 0.75),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10 * 0.75),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]

    if cfg.get("style", "card") != "plain":
        style_cmds += [
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BOX", (0, 0), (-1, -1), 0.7, border),
        ]

    title = str(cfg.get("title") or "PATIENT INFORMATION")
    min_height = float(cfg.get("height", 0) or 0) * 0.75
    outer = Table(
        [[Paragraph(_safe_text(title), styles["patient_title"])],
         [patient_table]],
        colWidths=[block_width],
        rowHeights=[min_height] if min_height > 0 else None,
        hAlign="LEFT",
        style=TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 10 * 0.75),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10 * 0.75),
            ("TOPPADDING", (0, 0), (-1, 0), 0),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 5 * 0.75),
            ("TOPPADDING", (0, 1), (-1, 1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 0),
            ("LINEBELOW", (0, 0), (-1, 0), 1 * 0.75, border),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), bg)
            if cfg.get("style", "card") != "plain" and not cfg.get("transparent", False)
            else ("BACKGROUND", (0, 0), (-1, -1), colors.Color(0, 0, 0, alpha=0)),
            ("BOX", (0, 0), (-1, -1), 0.7, border)
            if cfg.get("style", "card") != "plain"
            else ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ]),
    )
    # Do not replace the table style after construction. ReportLab applies
    # TableStyle commands additively, so an empty replacement would erase the
    # exact background, border, padding and alignment rules above.

    position = cfg.get("position") or {}
    # The designer stores drag coordinates in CSS pixels. PDF coordinates
    # are points, so every saved x/y value is converted exactly once.
    px_to_pt = 72.0 / 96.0
    x_offset = float(position.get("x", 0) or 0) * px_to_pt
    y_offset = float(position.get("y", 0) or 0) * px_to_pt

    # The patient is positioned relative to the report frame's
    # top-left corner, exactly like the browser designer overlay.
    frame_left, _, frame_top, _ = _metrics(layout)
    positioned = _PatientPositioned(
        outer,
        x_offset,
        y_offset,
        origin_x=frame_left,
        origin_y=frame_top,
    )

    # Measure once so the report cursor can start immediately after the
    # fixed patient block, exactly as the browser preview does. The patient
    # itself remains zero-height to Platypus and therefore can never be
    # shifted by the flow engine.
    _, patient_height = outer.wrap(block_width, 1000000)

    # The report flow starts immediately after the measured patient block.
    # Do not inject a fixed gap or hidden top-spacing value: the saved
    # designer position is the only positional adjustment.
    return [positioned, Spacer(1, y_offset + patient_height)]


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
    weights = {"name":2.5,"value":1.0,"unit":1.0,"reference_range":1.4}
    raw = [weights.get(k, 1 / len(columns)) for k in columns]
    total = sum(raw) or 1
    return columns, [usable * w / total for w in raw]


def _result_mode(rows):
    """Choose a renderer that matches the clinical data actually extracted."""
    explicit = []
    for row in rows or []:
        value = str(row.get("result_type") or "").strip().lower()
        if value:
            explicit.append(value)
    for wanted in ("narrative", "special", "quantitative", "observation", "qualitative"):
        if wanted in explicit:
            return wanted
    if any(str(r.get("unit") or "").strip() or str(r.get("reference_range") or "").strip() for r in rows or []):
        return "quantitative"
    return "observation"


NARRATIVE_NOTE_NAMES = {
    "impression", "interpretation", "conclusion", "comment", "comments",
    "advice", "remark", "remarks", "note", "notes",
    "recommendation", "recommendations", "clinical correlation",
}


def _is_narrative_note(row):
    """Identify report-level narrative notes that should not become table rows."""
    if str(row.get("result_type") or "").strip().lower() == "narrative":
        return True
    name = " ".join(str(row.get("name") or "").strip().lower().split())
    return name in NARRATIVE_NOTE_NAMES


def _extract_narrative_notes(tests):
    """Split narrative notes from normal clinical result rows."""
    normal = []
    notes = []
    for row in tests or []:
        if _is_narrative_note(row):
            value = str(row.get("value") or row.get("comment") or "").strip()
            if value:
                notes.append({
                    "label": str(row.get("name") or "Interpretation").strip(),
                    "value": value,
                })
        else:
            normal.append(row)
    return normal, notes


def _narrative_note_block(notes, layout, styles):
    """Render interpretation/impression-style content below result tables."""
    if not notes:
        return []
    results = layout["results"]
    text_color = _color(layout["appearance"].get("text"), colors.black)
    font_size = float(results.get("font_size", 9)) * 0.75
    note_style = ParagraphStyle(
        "report_narrative_note",
        parent=styles["table_cell"],
        fontName=_font_name(layout),
        fontSize=font_size,
        leading=(font_size + 3),
        textColor=text_color,
        spaceAfter=4,
    )
    content = [Spacer(1, 4)]
    for note in notes:
        label = note["label"] or "Interpretation"
        content.append(
            Paragraph(
                f"<b>{_safe_text(label)}</b>: {_safe_text(note['value'])}",
                note_style,
            )
        )
    content.append(Spacer(1, 6))
    return content


def _result_table(title, rows, layout, styles, available_width):
    """Render one clinical section without assuming a pathology-only schema."""
    results = layout["results"]
    mode = _result_mode(rows)

    text_style = styles["table_cell"]
    value_style = styles["table_value"]
    abnormal_value_style = ParagraphStyle(
        "table_abnormal_value",
        parent=value_style,
        fontName=_styled_font(layout, "bold"),
        textColor=colors.HexColor("#111827"),
    )
    header_style = styles["table_header"]

    if mode == "narrative":
        narrative_style = ParagraphStyle(
            "narrative_result",
            parent=text_style,
            fontSize=float(results.get("font_size", 9)) * 0.75,
            leading=(float(results.get("font_size", 9)) + 3) * 0.75,
            spaceAfter=5 * 0.75,
        )
        content = []
        if results.get("section_headers", True):
            section_bg = _color(
                results.get("section_background"),
                colors.HexColor("#ECEAFB"),
            )
            section_style = ParagraphStyle(
                "section_narrative",
                parent=styles["section"],
                fontName=_styled_font(
                    layout,
                    results.get(
                        "section_style",
                        "bold" if results.get("section_bold", True) else "normal",
                    ),
                ),
                fontSize=float(results.get("section_font_size", 7.9)) * 0.75,
                leading=(float(results.get("section_font_size", 7.9)) + 1) * 0.75,
                textColor=_color(results.get("section_text"), colors.black),
                alignment=_alignment(results.get("section_align", "left")),
            )
            pad = max(2, float(results.get("section_padding", 5))) * 0.75
            content.append(
                Table(
                    [[Paragraph(_safe_text(str(title).upper()), section_style)]],
                    colWidths=[available_width],
                    hAlign="LEFT",
                    style=TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), section_bg),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8 * 0.75),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8 * 0.75),
                        ("TOPPADDING", (0, 0), (-1, -1), pad),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                    ]),
                )
            )
            content.append(Spacer(1, 4 * 0.75))
        for row in rows:
            name = str(row.get("name") or "").strip()
            value = str(row.get("value") or row.get("comment") or "").strip()
            if name and value:
                content.append(
                    Paragraph(
                        f"<b>{_safe_text(name)}</b><br/>{_safe_text(value)}",
                        narrative_style,
                    )
                )
            elif value:
                content.append(Paragraph(_safe_text(value), narrative_style))
        content.append(Spacer(1, 9))
        return content

    # Observation/qualitative/special sections are intentionally compact.
    if mode in ("observation", "qualitative", "special"):
        columns = ["name", "value"]
    else:
        # Quantitative results retain the designer's selected columns.
        columns = [
            key for key in results.get("columns", [])
            if key in RESULT_LABELS
        ]
        if not columns:
            columns = ["name", "value", "unit", "reference_range"]

        # Hide columns that have no data when the saved designer is using the
        # standard automatic four-column layout. This keeps observation-heavy
        # reports clean without changing the designer's explicit choice.
        standard = ["name", "value", "unit", "reference_range"]
        if columns == standard:
            if not any(str(r.get("unit") or "").strip() for r in rows):
                columns.remove("unit")
            if not any(str(r.get("reference_range") or "").strip() for r in rows):
                columns.remove("reference_range")

    weights = {
        "name": 2.5,
        "value": 1.0,
        "unit": 1.0,
        "reference_range": 1.4,
    }
    raw = [weights.get(k, 1.0) for k in columns]
    total = sum(raw) or 1.0
    widths = [available_width * weight / total for weight in raw]

    data = [[Paragraph(RESULT_LABELS[k], header_style) for k in columns]]
    for row in rows:
        data.append([
            Paragraph(
                _safe_text(row.get(key, "")),
                abnormal_value_style
                if key == "value" and row.get("abnormal")
                else (value_style if key == "value" else text_style),
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
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * 0.75),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * 0.75),
        ("TOPPADDING", (0, 0), (-1, 0), 5 * 0.75),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5 * 0.75),
        ("TOPPADDING", (0, 1), (-1, -1), float(results.get("row_spacing", 5)) * 0.75),
        ("BOTTOMPADDING", (0, 1), (-1, -1), float(results.get("row_spacing", 5)) * 0.75),
        ("LINEBELOW", (0, 0), (-1, -1), 1 * 0.75, border),
    ]
    for row_index in range(2, len(data), 2):
        style_cmds.append(("BACKGROUND", (0, row_index), (-1, row_index), row_alt))
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
            fontName=_styled_font(
                layout,
                results.get(
                    "section_style",
                    "bold" if results.get("section_bold", True) else "normal",
                ),
            ),
            fontSize=float(results.get("section_font_size", 7.9)) * 0.75,
            leading=(float(results.get("section_font_size", 7.9)) + 1) * 0.75,
            textColor=_color(results.get("section_text"), colors.black),
            alignment=_alignment(results.get("section_align", "left")),
        )
        pad = max(2, float(results.get("section_padding", 5))) * 0.75
        section_header = [
            Table(
                [[Paragraph(_safe_text(str(title).upper()), section_style)]],
                colWidths=[available_width],
                hAlign="LEFT",
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), section_bg),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8 * 0.75),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8 * 0.75),
                    ("TOPPADDING", (0, 0), (-1, -1), pad),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                ]),
            ),
            Spacer(1, 4 * 0.75),
        ]

    return section_header + [table, Spacer(1, 9)]


def _dynamic_test_type(data, grouped_tests):
    """Resolve the report's clinical test type for the dynamic section header."""
    report = data.get("report") or {}
    candidates = [
        data.get("test_type"),
        data.get("testType"),
        data.get("examination"),
        report.get("test_type"),
        report.get("testType"),
        report.get("examination"),
        report.get("title"),
        report.get("department"),
    ]
    generic = {
        "laboratory report",
        "report",
        "examination results",
        "results",
        "laboratory",
        "lab report",
    }
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value and value.lower() not in generic:
            return value.upper()
    for section, _rows in grouped_tests:
        value = str(section or "").strip()
        if value and value.lower() not in generic and value.lower() != "unclassified results":
            return value.upper()
    return "EXAMINATION RESULTS"


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
                logo_w = min(180, max(30, float(manual.get("logo_width", 90))))
                logo_h = min(90, max(18, float(manual.get("logo_height", 35))))
                position = str(manual.get("logo_position", "right")).lower()
                if position == "left":
                    logo_x = 18
                elif position == "center":
                    logo_x = (page_w - logo_w) / 2
                else:
                    logo_x = page_w - right - logo_w
                logo_y = page_h - float(manual.get("logo_y", 42)) - logo_h
                self.drawImage(
                    ImageReader(str(logo_path)),
                    logo_x,
                    logo_y,
                    width=logo_w,
                    height=logo_h,
                    preserveAspectRatio=True,
                    mask="auto",
                    anchor="sw",
                )
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
    def __init__(self, stream, layout, patient=None, **kwargs):
        self._layout = layout
        self._patient = patient or {}
        left, right, top, bottom = _metrics(layout)
        frame = Frame(
            left, bottom, _page_size(layout)[0] - left - right, top - bottom,
            id="report_body", leftPadding=0, rightPadding=0,
            topPadding=0, bottomPadding=0,
        )
        self._pagesize = _page_size(layout)
        super().__init__(stream, pagesize=self._pagesize, **kwargs)
        self.addPageTemplates([
            PageTemplate(id="report", frames=[frame], onPage=self._draw_secondary_patient)
        ])

    def _draw_secondary_patient(self, canv, doc):
        """Draw only compact patient identity on overflow pages."""
        if canv.getPageNumber() <= 1:
            return
        page_w, page_h = self._pagesize
        page = self._layout.get("page") or {}
        top = max(0.0, float(page.get("top", 132) or 0))
        left = max(0.0, float(page.get("left", 52) or 0))
        right = max(0.0, float(page.get("right", 52) or 0))
        if top < 42:
            return
        patient = self._patient
        name = str(patient.get("name") or "").strip()
        code = str(patient.get("code") or patient.get("patient_id") or "").strip()
        uhid = str(patient.get("uhid") or "").strip()
        identity = "  •  ".join(x for x in (
            f"Patient: {name}" if name else "",
            f"ID: {code}" if code else "",
            f"UHID: {uhid}" if uhid else "",
        ) if x)
        if not identity:
            return
        text = _color(self._layout.get("appearance", {}).get("text"), colors.HexColor("#151A2D"))
        border = _color((self._layout.get("patient") or {}).get("border"), colors.HexColor("#E2E5EC"))
        bg = _color_opacity((self._layout.get("patient") or {}).get("background"), 88, colors.HexColor("#F5F6F8"))
        frame_top = page_h - top
        box_h = 24
        box_y = frame_top + 5
        canv.saveState()
        canv.setFillColor(bg)
        canv.setStrokeColor(border)
        canv.roundRect(left, box_y, page_w - left - right, box_h, 3, fill=1, stroke=1)
        canv.setFillColor(text)
        canv.setFont(_font_name(self._layout, bold=True), 7.5)
        canv.drawString(left + 8, box_y + 14, identity[:180])
        canv.restoreState()

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
    title = layout["results"].get("report_title") or report.get("title") or data.get("title") or "LABORATORY REPORT"

    # The report always starts immediately after the patient credentials.
    # Do not apply a separate report-top offset here; patient positioning
    # already reserves the required flow height.
    if department:
        story.append(Paragraph(_safe_text(department).upper(), styles["department"]))

    report_style = ParagraphStyle(
        "report_title_dynamic",
        parent=styles["report_title"],
        fontName=_styled_font(layout, layout["results"].get("report_title_style", "bold")),
        fontSize=float(layout["results"].get("report_title_size", 12)) * 0.75,
        leading=(float(layout["results"].get("report_title_size", 12)) + 2) * 0.75,
        textColor=_color(layout["results"].get("report_title_color"), text_color),
        alignment=_alignment(layout["results"].get("report_title_align", "left")),
    )
    title_table = Table(
        [[Paragraph(_safe_text(title).upper(), report_style)]],
        colWidths=[available_width],
        hAlign="LEFT",
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 2 * 0.75, _color(layout["results"].get("report_title_line_color"), accent)),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * 0.75),
        ]),
    )
    story.append(title_table)
    story.append(Spacer(1, 11 * 0.75))

    tests = data.get("tests") or []
    tests, narrative_notes = _extract_narrative_notes(tests)
    grouped_tests = _group_tests(tests, layout)
    dynamic_test_type = _dynamic_test_type(data, grouped_tests)

    # Keep the designer's editable section title, while the actual clinical
    # test type remains dynamic and comes from the extracted report.
    section_title = str(
        layout["results"].get("section_title") or "EXAMINATION RESULTS"
    ).strip()
    if section_title:
        section_label_style = ParagraphStyle(
            "report_section_label",
            parent=styles["section"],
            fontName=_styled_font(
                layout,
                layout["results"].get("section_style", "bold"),
            ),
            fontSize=float(layout["results"].get("section_font_size", 8)) * 0.75,
            leading=(float(layout["results"].get("section_font_size", 8)) + 1) * 0.75,
            textColor=_color(
                layout["results"].get("section_text"),
                text_color,
            ),
            alignment=_alignment(
                layout["results"].get("section_align", "left")
            ),
        )
        story.append(
            Table(
                [[Paragraph(_safe_text(section_title).upper(), section_label_style)]],
                colWidths=[available_width],
                hAlign="LEFT",
                style=TableStyle([
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        _color(
                            layout["results"].get("section_background"),
                            colors.HexColor("#ECEAFB"),
                        ),
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8 * 0.75),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8 * 0.75),
                    ("TOPPADDING", (0, 0), (-1, -1), 5 * 0.75),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * 0.75),
                ]),
            )
        )
        story.append(Spacer(1, 3 * 0.75))

    test_type_style = ParagraphStyle(
        "dynamic_test_type",
        parent=styles["department"],
        fontName=_styled_font(
            layout,
            layout["results"].get("section_style", "bold"),
        ),
        fontSize=float(layout["results"].get("section_font_size", 8)) * 0.75,
        leading=(float(layout["results"].get("section_font_size", 8)) + 2) * 0.75,
        textColor=_color(
            layout["results"].get("section_text"),
            text_color,
        ),
        alignment=_alignment(
            layout["results"].get("section_align", "left")
        ),
        spaceAfter=5 * 0.75,
    )
    story.append(
        Paragraph(_safe_text(dynamic_test_type), test_type_style)
    )

    for section, rows in grouped_tests:
        story.extend(_result_table(section, rows, layout, styles, available_width))

    story.extend(_narrative_note_block(narrative_notes, layout, styles))

    if not tests and not narrative_notes:
        story.append(
            Paragraph(
                "No verified test results were entered.",
                styles["empty"],
            )
        )

    return story


def render_body(data, layout=None):
    """
    Render the dynamic Aarogyam report body.

    Fixed designer elements are drawn with absolute coordinates. The result
    tables remain flowable so long result sets can paginate, but the fixed
    patient block and the report's starting position are never allowed to
    move because another flowable changed height.
    """
    layout = _merge_layout(layout)
    body = BytesIO()
    left, right, _, _ = _metrics(layout)
    available_width = _page_size(layout)[0] - left - right

    doc = _ReportDocTemplate(
        body,
        layout=layout,
        patient=patient,
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

    A single-page letterhead is repeated for overflow pages. If the template
    has multiple pages, its pages are used in order and the last template
    page is repeated for any additional report pages.
    """
    body = render_body(data, layout)
    out.parent.mkdir(parents=True, exist_ok=True)

    if template_path and Path(template_path).exists():
        base = PdfReader(template_path)
        overlay = PdfReader(body)
        writer = PdfWriter()

        if not base.pages:
            raise ValueError("Centre template PDF has no pages")

        for index, overlay_page in enumerate(overlay.pages):
            base_page = base.pages[index] if index < len(base.pages) else base.pages[-1]
            # PyPDF2 mutates PageObject in place. Clone the clean template
            # page so page 1's merged body can never leak into page 2.
            page = deepcopy(base_page)
            page.merge_page(overlay_page)
            writer.add_page(page)

        with open(out, "wb") as f:
            writer.write(f)
    else:
        out.write_bytes(body.read())
