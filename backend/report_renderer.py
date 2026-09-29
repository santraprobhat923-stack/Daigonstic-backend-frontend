from io import BytesIO
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from PyPDF2 import PdfReader, PdfWriter

PAGE_W, PAGE_H = A4
DEFAULT_LAYOUT = {
    "page": {"left": 52, "right": 52, "top": 132, "bottom": 82},
    "patient": {
        "visible": ["name","age","sex","code","uhid","referred_by","received_on","reported_on","phone"],
        "order": ["name","age_gender","code","uhid","referred_by","received_on","reported_on","phone"],
        "columns": 2,
        "style": "card",
        "font_size": 8.5,
        "label_bold": True,
        "background": "#F5F6F8",
        "border": "#E2E5EC",
    },
    "results": {
        "columns": ["name","value","unit","reference_range"],
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
        for group in ("page","patient","results","appearance"):
            if isinstance(layout.get(group), dict):
                out[group].update(layout[group])
    return out

def _color(value, fallback):
    try:
        return HexColor(str(value))
    except Exception:
        return fallback

def _font_name(layout, bold=False, italic=False):
    base = str(layout.get("appearance",{}).get("font") or "Helvetica")
    allowed = {"Helvetica","Times-Roman","Courier"}
    if base not in allowed:
        base = "Helvetica"
    if bold:
        return {"Helvetica":"Helvetica-Bold","Times-Roman":"Times-Bold","Courier":"Courier-Bold"}[base]
    if italic:
        return {"Helvetica":"Helvetica-Oblique","Times-Roman":"Times-Italic","Courier":"Courier-Oblique"}[base]
    return base

def _metrics(layout):
    page = layout["page"]
    left = float(page.get("left",52))
    right = float(page.get("right",52))
    top = float(page.get("top",132))
    bottom = float(page.get("bottom",82))
    return left, right, PAGE_H-top, bottom

def _text(c, text, x, y, font="Helvetica", size=9, color=black):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y, str(text or ""))

def _wrap(c, text, max_width, font="Helvetica", size=9):
    words = str(text or "").split()
    if not words:
        return [""]
    lines, line = [], ""
    for word in words:
        candidate = word if not line else line + " " + word
        if stringWidth(candidate, font, size) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]

def _age_gender(patient):
    age, sex = patient.get("age", ""), patient.get("sex", "")
    if age and sex:
        return f"{age}Y / {str(sex).upper()}" if str(age).isdigit() else f"{age} / {str(sex).upper()}"
    return age or str(sex).upper()

def _patient_value(patient, key):
    if key == "age_gender":
        return _age_gender(patient)
    return patient.get(key, "")

def _draw_label_value(c, label, value, x, y, width, layout):
    patient_cfg = layout["patient"]
    size = float(patient_cfg.get("font_size",8.5))
    label_font = _font_name(layout, bold=bool(patient_cfg.get("label_bold",True)))
    value_font = _font_name(layout)
    text_color = _color(layout["appearance"].get("text"), black)
    _text(c, label, x, y, label_font, size, text_color)
    label_w = stringWidth(label, label_font, size)
    colon_x = x + label_w + 3
    _text(c, ":", colon_x, y, value_font, size, text_color)
    value_x = colon_x + 7
    max_w = max(40, width - (value_x - x))
    lines = _wrap(c, value, max_w, value_font, size)
    for i, line in enumerate(lines):
        if i:
            y -= 11
        _text(c, line, value_x, y, value_font, size, text_color)
    return y

def _draw_patient_block(c, patient, y, layout):
    left, right, _, bottom = _metrics(layout)
    cfg = layout["patient"]
    visible = list(cfg.get("visible") or DEFAULT_LAYOUT["patient"]["visible"])
    order = list(cfg.get("order") or DEFAULT_LAYOUT["patient"]["order"])
    items = [k for k in order if k in visible and k in FIELD_LABELS]
    if "name" in visible and "name" not in items:
        items.insert(0, "name")
    if not items:
        return y - 8

    cols = 1 if int(cfg.get("columns", 2)) == 1 else 2
    width = PAGE_W - left - right
    gap = 18
    col_width = (width - gap * (cols - 1)) / cols
    size = float(cfg.get("font_size", 8.7))
    label_font = _font_name(layout, bold=True)
    value_font = _font_name(layout)
    text_color = _color(layout["appearance"].get("text"), black)
    muted = _color(layout["appearance"].get("muted"), HexColor("#667085"))
    bg = _color(cfg.get("background"), HexColor("#F5F7FA"))
    border = _color(cfg.get("border"), HexColor("#E1E5EC"))

    rows = [items[i:i + cols] for i in range(0, len(items), cols)]
    row_h = 20
    height = 30 + len(rows) * row_h + 8

    if cfg.get("style", "card") != "plain":
        c.setFillColor(bg)
        c.setStrokeColor(border)
        c.setLineWidth(.7)
        c.roundRect(left, y - height, width, height, 7, fill=1, stroke=1)

    _text(c, "PATIENT INFORMATION", left + 11, y - 16,
          _font_name(layout, bold=True), 7.8, text_color)
    c.setStrokeColor(border)
    c.setLineWidth(.6)
    c.line(left + 11, y - 22, left + width - 11, y - 22)

    current = y - 36
    for row in rows:
        for idx, key in enumerate(row):
            value = _patient_value(patient, key)
            x = left + idx * (col_width + gap)
            label = FIELD_LABELS[key]
            _text(c, label.upper(), x, current, label_font, 6.6, muted)
            lines = _wrap(c, value, col_width - 4, value_font, size)
            _text(c, lines[0] if lines else "", x, current - 10,
                  value_font, size, text_color)
        current -= row_h

    return y - height - 12


def _draw_table_header(c, columns, xs, widths, y, layout):
    results = layout["results"]
    text_color = _color(layout["appearance"].get("text"), black)
    header_bg = _color(results.get("table_header_background"), HexColor("#F7F8FA"))
    border = HexColor("#E2E5EC")
    height = 20
    c.setFillColor(header_bg)
    c.setStrokeColor(border)
    c.setLineWidth(.6)
    c.roundRect(xs[0] - 5, y - 4, sum(widths) + 10, height, 4, fill=1, stroke=0)
    for x, key in zip(xs, columns):
        _text(c, RESULT_LABELS[key], x, y + 5,
              _font_name(layout, bold=True),
              float(results.get("header_size", 7.2)), text_color)
    return y - 23


def _draw_section(c, title, rows, y, layout):
    left, right, body_top, bottom = _metrics(layout)
    results = layout["results"]
    text_color = _color(layout["appearance"].get("text"), black)
    accent = _color(layout["appearance"].get("accent"), HexColor("#5F52E8"))
    width = PAGE_W - left - right

    columns = [x for x in results.get("columns", []) if x in RESULT_LABELS]
    if not columns:
        columns = DEFAULT_LAYOUT["results"]["columns"]

    weights = {"name": 0.42, "value": 0.18, "unit": 0.16, "reference_range": 0.24}
    usable = width - 16
    widths = [usable * weights.get(k, 1 / len(columns)) for k in columns]
    scale = usable / sum(widths)
    widths = [w * scale for w in widths]
    xs = []
    cursor = left + 8
    for w in widths:
        xs.append(cursor)
        cursor += w

    def section_heading(current_y):
        if results.get("section_headers", True):
            bg = _color(results.get("section_background"), HexColor("#ECEAFB"))
            c.setFillColor(bg)
            c.roundRect(left, current_y - 18, width, 18, 4, fill=1, stroke=0)
            _text(c, title.upper(), left + 9, current_y - 12,
                  _font_name(layout, bold=True), 7.9, text_color)
            current_y -= 27
        return current_y

    if y < bottom + 65:
        c.showPage()
        y = body_top
    y = section_heading(y)
    y = _draw_table_header(c, columns, xs, widths, y, layout)

    size = float(results.get("font_size", 9))
    result_font = _font_name(layout)
    result_bold_font = _font_name(layout, bold=True)
    row_alt = _color(results.get("row_alt_background"), HexColor("#FBFCFE"))
    border = HexColor("#EAECF0")

    for index, row in enumerate(rows):
        values = {k: str(row.get(k, "") or "").strip() for k in columns}
        line_sets = {
            k: _wrap(c, values[k], widths[i] - 10, result_font, size)
            for i, k in enumerate(columns)
        }
        count = max([len(v) for v in line_sets.values()] or [1])
        row_height = max(21, count * 11 + 7)

        if y - row_height < bottom + 18:
            c.showPage()
            y = body_top
            y = section_heading(y)
            y = _draw_table_header(c, columns, xs, widths, y, layout)

        if index % 2 == 1:
            c.setFillColor(row_alt)
            c.rect(left + 3, y - row_height + 4, width - 6, row_height,
                   fill=1, stroke=0)

        # Result values are deliberately stronger than test names so the
        # generated report reads like a clinical result sheet, not raw OCR.
        for i, key in enumerate(columns):
            lines = line_sets[key]
            for line_index in range(count):
                yy = y - line_index * 11
                value = lines[line_index] if line_index < len(lines) else ""
                font = result_bold_font if key == "value" else result_font
                _text(c, value, xs[i], yy, font, size, text_color)

        c.setStrokeColor(border)
        c.setLineWidth(.45)
        c.line(left + 8, y - row_height + 2, left + width - 8, y - row_height + 2)
        y -= row_height

    return y - 8


def _group_tests(tests):
    groups, order = {}, []
    for t in tests or []:
        section=str(t.get("section") or "Examination Results").strip()
        if section not in groups:
            groups[section]=[]; order.append(section)
        groups[section].append(t)
    return [(name,groups[name]) for name in order]

def render_body(data, layout=None):
    layout=_merge_layout(layout)
    body=BytesIO()
    c=canvas.Canvas(body,pagesize=A4)
    patient=data.get("patient") or {}
    report=data.get("report") or {}
    left,right,body_top,bottom=_metrics(layout)
    y=body_top
    y=_patient_block(c,patient,y,layout)
    text_color=_color(layout["appearance"].get("text"),black)
    department=report.get("department") or data.get("department") or ""
    title=report.get("title") or data.get("title") or "LABORATORY REPORT"
    if department:
        _text(c,department.upper(),left,y,_font_name(layout,bold=True),10,text_color); y-=16
    _text(c,title.upper(),left,y,_font_name(layout,bold=True),10,text_color)
    c.setStrokeColor(_color(layout["appearance"].get("accent"),HexColor("#5F52E8")))
    c.line(left,y-5,PAGE_W-right,y-5); y-=25
    for section,rows in _group_tests(data.get("tests") or []):
        y=_draw_section(c,section,rows,y,layout)
    if not data.get("tests"):
        _text(c,"No verified test results were entered.",left+8,y,_font_name(layout,italic=True),9,text_color)
    c.save(); body.seek(0); return body

def make_pdf_body_on_template(template_path,data,out,layout=None):
    body=render_body(data,layout)
    out.parent.mkdir(parents=True,exist_ok=True)
    if template_path and Path(template_path).exists():
        base=PdfReader(template_path)
        overlay=PdfReader(body)
        writer=PdfWriter()

        # A letterhead is normally one page. Repeat that page for additional
        # report pages so long reports keep the same professional header/footer
        # instead of silently losing overflow content.
        for index, overlay_page in enumerate(overlay.pages):
            base_page = base.pages[index] if index < len(base.pages) else base.pages[-1]
            page = base_page
            page.merge_page(overlay_page)
            writer.add_page(page)

        with open(out,"wb") as f:
            writer.write(f)
    else:
        out.write_bytes(body.read())
