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

def _patient_block(c, patient, y, layout):
    left, right, _, _ = _metrics(layout)
    cfg = layout["patient"]
    visible = list(cfg.get("visible") or DEFAULT_LAYOUT["patient"]["visible"])
    order = list(cfg.get("order") or DEFAULT_LAYOUT["patient"]["order"])
    items = [k for k in order if k in visible and k in FIELD_LABELS]
    if "name" in visible and "name" not in items:
        items.insert(0,"name")
    if not items:
        return y - 10
    cols = 1 if int(cfg.get("columns",2)) == 1 else 2
    width = PAGE_W-left-right
    gap = 20
    col_width = (width-gap*(cols-1))/cols
    rows = [items[i:i+cols] for i in range(0,len(items),cols)]
    row_h = 14
    height = 42 + len(rows)*row_h + 8
    bg = _color(cfg.get("background"), HexColor("#F5F6F8"))
    border = _color(cfg.get("border"), HexColor("#E2E5EC"))
    if cfg.get("style","card") != "plain":
        c.setFillColor(bg); c.setStrokeColor(border)
        c.roundRect(left, y-height, width, height, 5, fill=1, stroke=1)
    text_color = _color(layout["appearance"].get("text"), black)
    _text(c, "PATIENT INFORMATION", left+10, y-15, _font_name(layout,bold=True), 8.5, text_color)
    current = y-29
    for row in rows:
        for idx,key in enumerate(row):
            value = _patient_value(patient,key)
            x = left + idx*(col_width+gap)
            _draw_label_value(c, FIELD_LABELS[key], value, x, current, col_width, layout)
        current -= row_h
    return y-height-8

def _draw_section(c, title, rows, y, layout):
    left, right, body_top, bottom = _metrics(layout)
    results = layout["results"]
    text_color = _color(layout["appearance"].get("text"), black)
    accent = _color(layout["appearance"].get("accent"), HexColor("#5F52E8"))
    if y < bottom + 70:
        c.showPage(); y = body_top
    if results.get("section_headers",True):
        c.setFillColor(_color(results.get("section_background"), HexColor("#ECEAFB")))
        c.roundRect(left, y-18, PAGE_W-left-right, 18, 3, fill=1, stroke=0)
        _text(c, title.upper(), left+8, y-12, _font_name(layout,bold=True), 8.5, text_color)
        y -= 29
    columns = [x for x in results.get("columns",[]) if x in RESULT_LABELS]
    if not columns:
        columns = DEFAULT_LAYOUT["results"]["columns"]
    available = PAGE_W-left-right-16
    widths = {"name": available*.42, "value": available*.18, "unit": available*.16, "reference_range": available*.24}
    xs=[]; cursor=left+8
    for key in columns:
        xs.append(cursor); cursor += widths.get(key,available/len(columns))
    header_bg = _color(results.get("table_header_background"), HexColor("#F7F7FA"))
    c.setFillColor(header_bg)
    c.rect(left, y-2, PAGE_W-left-right, 18, fill=1, stroke=0)
    header_size=float(results.get("header_size",7.5))
    for x,key in zip(xs,columns):
        _text(c, RESULT_LABELS[key], x, y+10, _font_name(layout,bold=True), header_size, text_color)
    y -= 4
    size=float(results.get("font_size",9))
    for row in rows:
        values={k:str(row.get(k,"") or "").strip() for k in columns}
        line_sets={k:_wrap(c,values[k],widths.get(k,80)-10,_font_name(layout),size) for k in columns}
        count=max([len(v) for v in line_sets.values()] or [1])
        if y-count*11 < bottom+28:
            c.showPage(); y=body_top
            if results.get("section_headers",True):
                c.setFillColor(_color(results.get("section_background"), HexColor("#ECEAFB")))
                c.roundRect(left,y-18,PAGE_W-left-right,18,3,fill=1,stroke=0)
                _text(c,title.upper(),left+8,y-12,_font_name(layout,bold=True),8.5,text_color)
                y-=29
            for x,key in zip(xs,columns):
                _text(c,RESULT_LABELS[key],x,y+10,_font_name(layout,bold=True),header_size,text_color)
        for i in range(count):
            yy=y-i*11
            for x,key in zip(xs,columns):
                lines=line_sets[key]
                _text(c,lines[i] if i<len(lines) else "",x,yy,_font_name(layout),size,text_color)
        if results.get("show_grid"):
            c.setStrokeColor(HexColor("#E8E9EE")); c.line(left,y-count*11-5,PAGE_W-right,y-count*11-5)
        y -= max(18,count*11+7)
    return y-8

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
        base=PdfReader(template_path); overlay=PdfReader(body); writer=PdfWriter()
        for index,page in enumerate(base.pages):
            if index < len(overlay.pages):
                page.merge_page(overlay.pages[index])
            writer.add_page(page)
        with open(out,"wb") as f: writer.write(f)
    else:
        out.write_bytes(body.read())
