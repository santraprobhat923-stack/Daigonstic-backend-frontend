from io import BytesIO
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from PyPDF2 import PdfReader, PdfWriter

PAGE_W, PAGE_H = A4
LEFT = 52
RIGHT = 52
BODY_TOP = PAGE_H - 132
BODY_BOTTOM = 82

def _text(c, text, x, y, font="Helvetica", size=9):
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

def _draw_label_value(c, label, value, x, y, width):
    label_font, value_font, size = "Helvetica-Bold", "Helvetica", 8.5
    _text(c, label, x, y, label_font, size)
    label_w = stringWidth(label, label_font, size)
    colon_x = x + label_w + 3
    _text(c, ":", colon_x, y, value_font, size)
    value_x = colon_x + 7
    max_w = max(40, width - (value_x - x))
    lines = _wrap(c, value, max_w, value_font, size)
    for i, line in enumerate(lines):
        if i:
            y -= 11
        _text(c, line, value_x, y, value_font, size)
    return y

def _patient_block(c, patient, y):
    c.setFillGray(0.96)
    c.roundRect(LEFT, y - 78, PAGE_W - LEFT - RIGHT, 78, 5, fill=1, stroke=0)
    c.setFillGray(0)
    _text(c, "PATIENT INFORMATION", LEFT + 10, y - 15, "Helvetica-Bold", 8.5)

    top = y - 29
    col = (PAGE_W - LEFT - RIGHT - 20) / 2
    rows = [
        (("Name", patient.get("name")), ("Age / Gender", _age_gender(patient))),
        (("Patient ID", patient.get("code")), ("UHID", patient.get("uhid"))),
        (("Referred By", patient.get("referred_by")), ("Received On", patient.get("received_on"))),
        (("Reported On", patient.get("reported_on")), ("Phone", patient.get("phone"))),
    ]
    current = top
    for left_item, right_item in rows:
        if not (left_item[1] or right_item[1]):
            continue
        _draw_label_value(c, left_item[0], left_item[1], LEFT + 10, current, col - 5)
        _draw_label_value(c, right_item[0], right_item[1], LEFT + 10 + col, current, col - 5)
        current -= 13
    return y - 86

def _age_gender(patient):
    age, sex = patient.get("age", ""), patient.get("sex", "")
    if age and sex:
        return f"{age}Y / {str(sex).upper()}" if str(age).isdigit() else f"{age} / {str(sex).upper()}"
    return age or str(sex).upper()

def _draw_section(c, title, rows, y):
    if y < BODY_BOTTOM + 70:
        c.showPage()
        y = BODY_TOP
    c.setFillGray(0.92)
    c.roundRect(LEFT, y - 18, PAGE_W - LEFT - RIGHT, 18, 3, fill=1, stroke=0)
    c.setFillGray(0)
    _text(c, title.upper(), LEFT + 8, y - 12, "Helvetica-Bold", 8.5)
    y -= 29
    name_x = LEFT + 8
    result_x = LEFT + 290
    unit_x = PAGE_W - RIGHT - 72
    for row in rows:
        name = str(row.get("name", "")).strip()
        value = str(row.get("value", "")).strip()
        unit = str(row.get("unit", "")).strip()
        name_lines = _wrap(c, name, result_x - name_x - 15, "Helvetica", 9)
        value_lines = _wrap(c, value, unit_x - result_x - 12, "Helvetica", 9)
        count = max(len(name_lines), len(value_lines), 1)
        for i in range(count):
            yy = y - i * 11
            _text(c, name_lines[i] if i < len(name_lines) else "", name_x, yy, "Helvetica", 9)
            _text(c, value_lines[i] if i < len(value_lines) else "", result_x, yy, "Helvetica", 9)
            if i == 0 and unit:
                _text(c, unit, unit_x, yy, "Helvetica", 8)
        y -= max(18, count * 11 + 7)
        if y < BODY_BOTTOM + 28:
            c.showPage()
            y = BODY_TOP
    return y - 8

def _group_tests(tests):
    groups = {}
    order = []
    for t in tests or []:
        section = str(t.get("section") or "Examination Results").strip()
        if section not in groups:
            groups[section] = []
            order.append(section)
        groups[section].append(t)
    return [(name, groups[name]) for name in order]

def render_body(data):
    body = BytesIO()
    c = canvas.Canvas(body, pagesize=A4)
    patient = data.get("patient") or {}
    report = data.get("report") or {}
    y = BODY_TOP
    y = _patient_block(c, patient, y)

    department = report.get("department") or data.get("department") or ""
    title = report.get("title") or data.get("title") or "LABORATORY REPORT"
    if department:
        _text(c, department.upper(), LEFT, y, "Helvetica-Bold", 10)
        y -= 16
    _text(c, title.upper(), LEFT, y, "Helvetica-Bold", 10)
    c.line(LEFT, y - 5, PAGE_W - RIGHT, y - 5)
    y -= 25

    for section, rows in _group_tests(data.get("tests") or []):
        y = _draw_section(c, section, rows, y)

    if not data.get("tests"):
        _text(c, "No verified test results were entered.", LEFT + 8, y, "Helvetica-Oblique", 9)

    c.save()
    body.seek(0)
    return body

def make_pdf_body_on_template(template_path, data, out):
    body = render_body(data)
    out.parent.mkdir(parents=True, exist_ok=True)
    if template_path and Path(template_path).exists():
        base = PdfReader(template_path)
        overlay = PdfReader(body)
        writer = PdfWriter()
        for index, page in enumerate(base.pages):
            if index < len(overlay.pages):
                page.merge_page(overlay.pages[index])
            writer.add_page(page)
        with open(out, "wb") as f:
            writer.write(f)
    else:
        out.write_bytes(body.read())
