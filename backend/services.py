import hashlib,json,re,secrets
from io import BytesIO
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader,PdfWriter
try: import pytesseract
except Exception: pytesseract=None
from .config import STORAGE_DIR
from .models import Notification,WAJob

# Common laboratory units. Kept broad so the parser works across CBC, thyroid,
# chemistry and routine diagnostic slips.
UNIT_RE=r"(?:mg/dL|g/dL|gm/dL|ng/dL|ng/mL|pg/mL|µIU/mL|uIU/mL|mIU/L|IU/L|IU/mL|U/L|mmol/L|µmol/L|umol/L|mEq/L|mmHg|%|fL|pg|sec|/HPF|/hpf|cells/HPF|million/µL|million/uL|10\^\d+/µL|10\^\d+/uL|[A-Za-zµ]+/[A-Za-zµ]+)"
NUMBER_RE=r"[<>]?\d+(?:[.,]\d+)?"

def _clean_line(line):
    return re.sub(r"\s+"," ",line).strip(" :-|\t")

def _looks_like_test_name(name):
    name=_clean_line(name)
    if len(name)<2 or len(name)>60: return False
    low=name.lower()
    blocked=("patient","name","age","sex","gender","mobile","phone","whatsapp","address",
             "sample","specimen","barcode","report","date","time","reference","range",
             "normal","result","unit","value","doctor","laboratory","diagnostic")
    return not any(re.search(r"\b"+re.escape(x)+r"\b",low) for x in blocked)

def _parse_tests(text):
    tests=[]
    seen=set()
    for raw in text.splitlines():
        line=_clean_line(raw)
        if not line: continue

        # First handle normal "TEST : VALUE UNIT" / "TEST VALUE UNIT" rows.
        patterns=[
            rf"^(.{{2,50}}?)\s*[:=]\s*({NUMBER_RE}|positive|negative|normal|reactive|non-reactive)\s*([A-Za-zµ%/][A-Za-z0-9µ%/^.\-]*)?$",
            rf"^(.{{2,50}}?)\s+({NUMBER_RE})\s+({UNIT_RE})$",
            rf"^(.{{2,50}}?)\s+({NUMBER_RE})\s+([A-Za-zµ%/][A-Za-z0-9µ%/^.\-]*)\s*$",
        ]
        match=None
        for pat in patterns:
            m=re.match(pat,line,re.I)
            if m:
                match=m; break
        if match:
            name=_clean_line(match.group(1))
            value=match.group(2).replace(",",".")
            unit=_clean_line(match.group(3) or "")
            if _looks_like_test_name(name):
                key=(name.lower(),value.lower(),unit.lower())
                if key not in seen:
                    tests.append({"name":name,"value":value,"unit":unit}); seen.add(key)
                continue

        # Table-like OCR often loses column separators. Find the first numeric
        # result and treat text before it as the test name, text after it as unit.
        m=re.search(rf"\b({NUMBER_RE})\b",line)
        if m:
            name=_clean_line(line[:m.start()])
            value=m.group(1).replace(",",".")
            tail=_clean_line(line[m.end():])
            tail=re.sub(r"^[|:=-]+","",tail).strip()
            unit_match=re.match(rf"^({UNIT_RE})\b",tail,re.I)
            unit=unit_match.group(1) if unit_match else (tail.split()[0] if tail and len(tail.split()[0])<=18 else "")
            if _looks_like_test_name(name) and len(name.split())<=10:
                key=(name.lower(),value.lower(),unit.lower())
                if key not in seen:
                    tests.append({"name":name,"value":value,"unit":unit}); seen.add(key)
    return tests

def extract(path):
    text=pytesseract.image_to_string(Image.open(path),config="--psm 6") if pytesseract else ""
    def f(p):
        m=re.search(p,text,re.I)
        return m.group(1).strip() if m else ""
    patient={"name":f(r"(?:patient|name)\s*[:#-]?\s*([A-Za-z][A-Za-z .'-]{1,80})"),
             "age":f(r"age\s*[:#-]?\s*(\d{1,3})"),
             "sex":f(r"(?:sex|gender)\s*[:#-]?\s*(male|female|m|f)"),
             "phone":f(r"(?:phone|mobile|whatsapp)\s*[:#-]?\s*(\+?\d[\d -]{8,})"),
             "code":f(r"(?:patient\s*(?:id|code)|id)\s*[:#-]?\s*([A-Za-z0-9_-]{3,})")}
    return text,{"patient":patient,"tests":_parse_tests(text)}

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
