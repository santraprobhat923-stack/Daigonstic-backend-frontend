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
def extract(path):
    text=pytesseract.image_to_string(Image.open(path)) if pytesseract else ""
    def f(p): m=re.search(p,text,re.I); return m.group(1).strip() if m else ""
    patient={"name":f(r"(?:patient|name)\s*[:#-]?\s*([A-Za-z][A-Za-z .'-]{1,80})"),"age":f(r"age\s*[:#-]?\s*(\d{1,3})"),"sex":f(r"(?:sex|gender)\s*[:#-]?\s*(male|female|m|f)"),"phone":f(r"(?:phone|mobile|whatsapp)\s*[:#-]?\s*(\+?\d[\d -]{8,})"),"code":f(r"(?:patient\s*(?:id|code)|id)\s*[:#-]?\s*([A-Za-z0-9_-]{3,})")}
    tests=[]
    for line in text.splitlines():
        m=re.match(r"\s*([A-Za-z][A-Za-z0-9 /().+-]{1,50})\s*[:=-]\s*([<>]?[0-9]+(?:\.[0-9]+)?|positive|negative|normal|reactive|non-reactive)\s*(.*)",line,re.I)
        if m: tests.append({"name":m.group(1).strip(),"value":m.group(2),"unit":m.group(3).strip()})
    return text,{"patient":patient,"tests":tests}
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
    return {"id":r.id,"patient_name":r.patient_name,"patient_age":r.patient_age,"patient_sex":r.patient_sex,"patient_phone":r.patient_phone,"patient_code":r.patient_code,"status":r.status,"payment":r.payment,"charge":r.charge,"verified_data":json.loads(r.verified_data or "{}"),"created_at":r.created_at.isoformat()}
