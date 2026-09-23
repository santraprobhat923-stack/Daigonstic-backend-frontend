import hashlib,json,re,secrets
from io import BytesIO
from pathlib import Path
from PIL import Image
from .report_renderer import make_pdf_body_on_template
try: import pytesseract
except Exception: pytesseract=None
from .config import STORAGE_DIR
from .models import Notification,WAJob

# OCR is intentionally layout-tolerant: diagnostic slips vary widely between
# analyzers and centres. We run several Tesseract passes and merge useful
# readings before parsing. OCR remains draft data until technician review.
UNIT_RE=r"(?:mg/dL|g/dL|gm/dL|ng/dL|ng/mL|pg/mL|µIU/mL|uIU/mL|mIU/L|IU/L|IU/mL|U/L|mmol/L|µmol/L|umol/L|mEq/L|mmHg|%|fL|pg|sec|/HPF|/hpf|cells/HPF|million/µL|million/uL|10\^\d+/µL|10\^\d+/uL|10\d+/µL|10\d+/uL|[A-Za-zµ]+/[A-Za-zµ]+)"
NUMBER_RE=r"[<>]?\d+(?:[.,]\d+)?"

def _clean_line(line):
    return re.sub(r"\s+"," ",line).strip(" :-|\t")

def _looks_like_test_name(name):
    name=_clean_line(name)
    if len(name)<2 or len(name)>80 or not re.search(r"[A-Za-z]",name): return False
    low=name.lower()
    blocked=("patient","patient id","patient code","name","age","sex","gender","mobile","phone",
             "whatsapp","address","sample","specimen","barcode","report","date","time","reference",
             "range","normal","result","unit","value","doctor","laboratory","diagnostic centre",
             "diagnostic center","collection","received","registration")
    return not any(re.search(r"\b"+re.escape(x)+r"\b",low) for x in blocked)

def _ocr_variants(path):
    if not pytesseract: return []
    img=Image.open(path).convert("L")
    w,h=img.size
    if max(w,h)<2400:
        img=img.resize((w*2,h*2),Image.Resampling.LANCZOS)
    from PIL import ImageOps,ImageFilter
    base=ImageOps.autocontrast(img)
    variants=[img,base,base.filter(ImageFilter.SHARPEN)]
    readings=[]
    for v in variants:
        for psm in (6,4,11):
            try: t=pytesseract.image_to_string(v,config=f"--psm {psm}")
            except Exception: t=""
            if t and t.strip(): readings.append(t)
    return readings

def _first_field(readings,patterns):
    candidates=[]
    for text in readings:
        for raw in text.splitlines():
            line=_clean_line(raw)
            if not line: continue
            for p in patterns:
                m=re.search(p,line,re.I)
                if m:
                    value=_clean_line(m.group(1))
                    if value: candidates.append(value)
    if not candidates: return ""
    labels=r"\b(?:age|sex|gender|mobile|phone|whatsapp|patient\s*(?:id|code))\b"
    clean=[x for x in candidates if not re.search(labels,x,re.I)]
    return min(clean or candidates,key=len)

def _parse_tests(readings):
    tests=[]; seen=set(); current_section="Examination Results"
    section_patterns=[
        re.compile(r"^(physical|chemical|microscopical|microscopic|macroscopic|hematological|haematological|biochemical|serological|urine|stool|blood|hormone|lipid|liver|kidney|renal|thyroid|coagulation|immunology|cytology|clinical pathology).{0,45}(?:examination|profile|panel|test|report)?$",re.I)
    ]
    skip=re.compile(r"^(department|report on|examination of|end of report|patient information|reference range|normal range)$",re.I)
    qualitative=r"(?:positive|negative|normal|reactive|non-reactive|nil|none|absent|present(?:\s*\([+-]\))?|not seen|brownish|yellowish|yellow|greenish|black|soft|formed|semi[- ]formed|acidic|alkaline)"
    for text in readings:
        for raw in text.splitlines():
            line=_clean_line(raw)
            if not line: continue
            line=re.sub(r"[|]+"," ",line).strip(" :-")
            if skip.match(line): continue
            normalized=re.sub(r"\s+"," ",line)
            if any(p.match(normalized) for p in section_patterns) and not re.search(r"[:=]\s*",normalized):
                current_section=normalized.strip()
                continue
            patterns=[
                rf"^(.{{2,70}}?)\s*[:=]\s*({NUMBER_RE}|{qualitative}|[A-Za-z][A-Za-z0-9 .()+/-]{{1,55}}?)\s*({UNIT_RE})?\s*$",
                rf"^(.{{2,70}}?)\s+({NUMBER_RE})\s+({UNIT_RE})\s*$",
            ]
            m=None
            for pat in patterns:
                m=re.match(pat,normalized,re.I)
                if m: break
            if not m:
                # Handle report rows where the OCR loses the colon/delimiter.
                m=re.match(rf"^(.{{2,55}}?)\s+({qualitative})\s*$",normalized,re.I)
            if m:
                name=_clean_line(m.group(1)); value=_clean_line(m.group(2)); unit=_clean_line(m.group(3) or "") if len(m.groups())>=3 else ""
                if _looks_like_test_name(name) and len(name.split())<=14:
                    key=(re.sub(r"[^a-z0-9]+","",name.lower()),value.lower(),unit.lower(),current_section.lower())
                    if key not in seen:
                        tests.append({"name":name,"value":value,"unit":unit,"section":current_section}); seen.add(key)
    return tests

def sha(data): return hashlib.sha256(data).hexdigest()
def notify(db,cid,rid,kind,msg): db.add(Notification(centre_id=cid,report_id=rid,kind=kind,message=msg))
def queue_wa(db,centre,report,kind,payload):
    if not centre.whatsapp_enabled or not report.patient_phone: return
    if db.query(WAJob).filter_by(report_id=report.id,kind=kind).first(): return
    db.add(WAJob(centre_id=centre.id,report_id=report.id,kind=kind,payload=json.dumps(payload)))
def make_pdf(centre,report,data,out):
    # The uploaded centre PDF supplies branding/header/footer. Aarogyam renders
    # only the professional diagnostic body and overlays it onto the template.
    make_pdf_body_on_template(centre.template_path, data, out)

def report_dict(r):
    return {"id":r.id,"patient_name":r.patient_name,"patient_age":r.patient_age,"patient_sex":r.patient_sex,"patient_phone":r.patient_phone,"patient_code":r.patient_code,"status":r.status,"payment":r.payment,"charge":r.charge,"pdf_path":r.pdf_path,"verified_data":json.loads(r.verified_data or "{}"),"created_at":r.created_at.isoformat()}def extract(path):
    readings=_ocr_variants(path)
    combined="\n".join(readings)
    patient={
        "name":_first_field(readings,[r"\\bpatient\\s*name\\s*[:#-]\\s*(.+?)$",r"\\bname\\s*[:#-]\\s*(.+?)$"]),
        "age":_first_field(readings,[r"\\bage\\s*[:#-]?\\s*(\\d{1,3})\\b"]),
        "sex":_first_field(readings,[r"\\b(?:sex|gender)\\s*[:#-]?\\s*(male|female|m|f)\\b"]),
        "phone":_first_field(readings,[r"\\b(?:phone|mobile|whatsapp)\\s*[:#-]?\\s*(\\+?\\d[\\d -]{8,})"]),
        "code":_first_field(readings,[r"\\b(?:patient\\s*(?:id|code)|id\\s*number)\\s*[:#-]?\\s*([A-Za-z0-9_/-]{3,})\\b"]),
        "uhid":_first_field(readings,[r"\\buhid\\s*[:#-]?\\s*([A-Za-z0-9_/-]{3,})\\b"]),
        "referred_by":_first_field(readings,[r"\\b(?:referred\\s*by|ref\\.?\\s*by)\\s*[:#-]?\\s*(.+?)$"]),
        "received_on":_first_field(readings,[r"\\breceived\\s*on\\s*[:#-]?\\s*([0-9A-Za-z ./-]{6,})$"]),
        "reported_on":_first_field(readings,[r"\\breported\\s*on\\s*[:#-]?\\s*([0-9A-Za-z ./-]{6,})$"]),
    }
    if re.search(r"\\b(?:age|sex|gender|mobile|phone|patient\\s*(?:id|code)|uhid|referred|received|reported)\\b",patient["name"],re.I):
        patient["name"]=""
    report={}
    for text in readings:
        for raw in text.splitlines():
            line=_clean_line(raw)
            m=re.match(r"^(?:department)\\s*[:#-]\\s*(.+)$",line,re.I)
            if m and not report.get("department"): report["department"]=_clean_line(m.group(1))
            m=re.match(r"^(?:report(?:\\s+title)?|examination)\\s*[:#-]\\s*(.+)$",line,re.I)
            if m and not report.get("title"): report["title"]=_clean_line(m.group(1))
    return combined,{"patient":patient,"tests":_parse_tests(readings),"report":report}

def sha(data): return hashlib.sha256(data).hexdigest()
def notify(db,cid,rid,kind,msg): db.add(Notification(centre_id=cid,report_id=rid,kind=kind,message=msg))
def queue_wa(db,centre,report,kind,payload):
    if not centre.whatsapp_enabled or not report.patient_phone: return
    if db.query(WAJob).filter_by(report_id=report.id,kind=kind).first(): return
    db.add(WAJob(centre_id=centre.id,report_id=report.id,kind=kind,payload=json.dumps(payload)))
def make_pdf(centre,report,data,out):
    body=BytesIO(); c=canvas.Canvas(body,pagesize=A4); w,h=A4
    y=h-150; c.setFont("Helvetica-Bold",12); c.drawString(55,y,"Patient Report"); y-=25
    p=data.get("patient",{}); c.setFont("Helvetica",9)
    for k,l in [("name","Patient"),("age","Age"),("sex","Sex"),("phone","WhatsApp"),("code","Patient ID")]:
        c.drawString(55,y,f"{l}: {p.get(k,'')}"); y-=16
    y-=10; c.setFont("Helvetica-Bold",10); c.drawString(55,y,"Test Results"); y-=20; c.setFont("Helvetica",9)
    for q in data.get("tests",[]): c.drawString(55,y,f"{q.get('name','')}    {q.get('value','')}    {q.get('unit','')}"); y-=16
    c.save(); body.seek(0); out.parent.mkdir(parents=True,exist_ok=True)
    if centre.template_path and Path(centre.template_path).exists():
        base=PdfReader(centre.template_path); overlay=PdfReader(body); wri=PdfWriter()
        for i,page in enumerate(base.pages):
            if i<len(overlay.pages): page.merge_page(overlay.pages[i])
            wri.add_page(page)
        with open(out,"wb") as f:wri.write(f)
    else: out.write_bytes(body.read())
def report_dict(r):
    return {"id":r.id,"patient_name":r.patient_name,"patient_age":r.patient_age,"patient_sex":r.patient_sex,"patient_phone":r.patient_phone,"patient_code":r.patient_code,"status":r.status,"payment":r.payment,"charge":r.charge,"pdf_path":r.pdf_path,"verified_data":json.loads(r.verified_data or "{}"),"created_at":r.created_at.isoformat()}
