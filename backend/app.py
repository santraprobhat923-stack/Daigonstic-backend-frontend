import os,json,secrets,re
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI,UploadFile,File,HTTPException,Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine,Column,Integer,String,Float,Boolean,Text,DateTime,ForeignKey
from sqlalchemy.orm import declarative_base,sessionmaker
from PIL import Image
try: import pytesseract
except: pytesseract=None
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader,PdfWriter
from io import BytesIO
DB=os.getenv("DATABASE_URL","sqlite:///./aarogyam.db"); ROOT=Path(os.getenv("STORAGE_DIR","./storage")); ROOT.mkdir(exist_ok=True)
eng=create_engine(DB,connect_args={"check_same_thread":False} if DB.startswith("sqlite") else {}); Session=sessionmaker(bind=eng); Base=declarative_base()
class Centre(Base):
 __tablename__="centres"; id=Column(Integer,primary_key=True); name=Column(String); email=Column(String,unique=True); password=Column(String); whatsapp_enabled=Column(Boolean,default=False); upi_id=Column(String,default=""); credits=Column(Integer,default=10); template_path=Column(String,default="")
class Report(Base):
 __tablename__="reports"; id=Column(Integer,primary_key=True); centre_id=Column(Integer,index=True); patient_name=Column(String,default=""); patient_age=Column(String,default=""); patient_sex=Column(String,default=""); patient_phone=Column(String,default=""); patient_code=Column(String,default=""); status=Column(String,default="OCR_REVIEW"); verified_data=Column(Text,default="{}"); ocr_text=Column(Text,default=""); image_paths=Column(Text,default="[]"); pdf_path=Column(String,default=""); charge=Column(Float,default=0); payment=Column(String,default="NOT_REQUIRED"); token=Column(String,unique=True); created_at=Column(DateTime,default=datetime.utcnow)
class Notification(Base):
 __tablename__="notifications"; id=Column(Integer,primary_key=True); centre_id=Column(Integer,index=True); report_id=Column(Integer); kind=Column(String); message=Column(Text); created_at=Column(DateTime,default=datetime.utcnow)
class WAJob(Base):
 __tablename__="wa_jobs"; id=Column(Integer,primary_key=True); centre_id=Column(Integer); report_id=Column(Integer); kind=Column(String); status=Column(String,default="PENDING"); payload=Column(Text); created_at=Column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(eng); app=FastAPI(title="Aarogyam"); app.mount("/static",StaticFiles(directory="frontend"),name="static")
def db(): return Session()
def find(t,p):
 m=re.search(p,t,re.I); return m.group(1).strip() if m else ""
def ocr(path):
 t=pytesseract.image_to_string(Image.open(path)) if pytesseract else ""; p={"name":find(t,r"(?:patient|name)\s*[:#-]?\s*([A-Za-z][A-Za-z .'-]{1,80})"),"age":find(t,r"age\s*[:#-]?\s*(\d{1,3})"),"sex":find(t,r"(?:sex|gender)\s*[:#-]?\s*(male|female|m|f)"),"phone":find(t,r"(?:phone|mobile|whatsapp)\s*[:#-]?\s*(\+?\d[\d -]{8,})"),"code":find(t,r"(?:patient\s*(?:id|code)|id)\s*[:#-]?\s*([A-Za-z0-9_-]{3,})")}; tests=[]
 for line in t.splitlines():
  m=re.match(r"\s*([A-Za-z][A-Za-z0-9 /().+-]{1,50})\s*[:=-]\s*([<>]?[0-9]+(?:\.[0-9]+)?|positive|negative|normal|reactive|non-reactive)\s*(.*)",line,re.I)
  if m: tests.append({"name":m.group(1).strip(),"value":m.group(2),"unit":m.group(3).strip()})
 return t,{"patient":p,"tests":tests}
def notify(s,c,r,k,msg): s.add(Notification(centre_id=c,report_id=r,kind=k,message=msg))
def wa(s,c,r,kind,payload):
 if not c.whatsapp_enabled or not r.patient_phone:return
 s.add(WAJob(centre_id=c.id,report_id=r.id,kind=kind,payload=json.dumps(payload)))
def make_pdf(r,c,data,out):
 body=BytesIO(); x=canvas.Canvas(body,pagesize=A4); w,h=A4; y=h-95; x.setFont("Helvetica-Bold",14); x.drawString(55,y,"Diagnostic Report"); y-=35; x.setFont("Helvetica",10)
 p=data.get("patient",{});
 for k,label in [("name","Patient"),("age","Age"),("sex","Sex"),("phone","WhatsApp"),("code","Patient ID")]: x.drawString(55,y,f"{label}: {p.get(k,'')}"); y-=17
 y-=8; x.setFont("Helvetica-Bold",10); x.drawString(55,y,"Test Results"); y-=20; x.setFont("Helvetica",9)
 for q in data.get("tests",[]): x.drawString(55,y,f"{q.get('name','')}: {q.get('value','')} {q.get('unit','')}"); y-=16
 x.save(); body.seek(0); out.parent.mkdir(parents=True,exist_ok=True)
 if c.template_path and Path(c.template_path).exists() and c.template_path.lower().endswith(".pdf"):
  base=PdfReader(c.template_path); ov=PdfReader(body); wr=PdfWriter()
  for i,pag in enumerate(base.pages):
   if i<len(ov.pages): pag.merge_page(ov.pages[i])
   wr.add_page(pag)
  with open(out,"wb") as f: wr.write(f)
 else: out.write_bytes(body.read())
def rd(r): return {"id":r.id,"patient_name":r.patient_name,"patient_age":r.patient_age,"patient_sex":r.patient_sex,"patient_phone":r.patient_phone,"patient_code":r.patient_code,"status":r.status,"payment":r.payment,"charge":r.charge,"verified_data":json.loads(r.verified_data or "{}"),"created_at":r.created_at.isoformat()}
@app.get("/")
def home(): return FileResponse("frontend/index.html")
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/api/bootstrap")
def bootstrap(name:str=Form(...),email:str=Form(...),password:str=Form(...)):
 s=db();
 if s.query(Centre).filter_by(email=email).first(): raise HTTPException(409,"Email already exists")
 c=Centre(name=name,email=email,password=password,credits=10); s.add(c); s.commit(); return {"centre_id":c.id}
@app.post("/api/login")
def login(email:str=Form(...),password:str=Form(...)):
 s=db(); c=s.query(Centre).filter_by(email=email,password=password).first()
 if not c: raise HTTPException(401,"Invalid credentials")
 return {"centre_id":c.id,"name":c.name,"credits":c.credits}
@app.post("/api/reports/upload")
def upload(centre_id:int=Form(...),files:list[UploadFile]=File(...)):
 s=db(); c=s.get(Centre,centre_id)
 if not c: raise HTTPException(404,"Centre not found")
 paths=[]; merged={"patient":{},"tests":[]}; texts=[]
 for f in files:
  p=ROOT/f"centre_{c.id}"/"images"/(secrets.token_hex(10)+"_"+f.filename); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(f.file.read()); paths.append(str(p)); t,d=ocr(str(p)); texts.append(t)
  for k,v in d["patient"].items(): merged["patient"][k]=merged["patient"].get(k) or v
  merged["tests"]+=d["tests"]
 r=Report(centre_id=c.id,token=secrets.token_urlsafe(32),verified_data=json.dumps(merged),ocr_text="\n".join(texts),image_paths=json.dumps(paths)); s.add(r); s.commit(); return {"report":rd(r),"extracted":merged}
@app.post("/api/reports/{rid}/verify")
def verify(rid:int,centre_id:int=Form(...),data:str=Form(...)):
 s=db(); r=s.get(Report,rid); c=s.get(Centre,centre_id)
 if not r or not c or r.centre_id!=c.id: raise HTTPException(404,"Report not found")
 if c.credits<1: raise HTTPException(400,"Insufficient credits")
 d=json.loads(data); r.verified_data=data; p=d.get("patient",{}); r.patient_name=p.get("name",""); r.patient_age=p.get("age",""); r.patient_sex=p.get("sex",""); r.patient_phone=p.get("phone",""); r.patient_code=p.get("code",""); c.credits-=1
 out=ROOT/f"centre_{c.id}"/"reports"/f"report_{r.id}.pdf"; make_pdf(r,c,d,out); r.pdf_path=str(out); r.status="GENERATED"; r.payment="PENDING" if c.whatsapp_enabled else "NOT_REQUIRED"; notify(s,c.id,r.id,"REPORT_GENERATED",f"Report #{r.id} generated. Centre download is ready."); s.commit(); return rd(r)
@app.get("/api/reports")
def reports(centre_id:int):
 s=db(); return [rd(r) for r in s.query(Report).filter_by(centre_id=centre_id).order_by(Report.id.desc()).all()]
@app.get("/api/reports/{rid}/download")
def download(rid:int,centre_id:int):
 s=db(); r=s.get(Report,rid)
 if not r or r.centre_id!=centre_id or not r.pdf_path: raise HTTPException(404,"Report unavailable")
 return FileResponse(r.pdf_path,media_type="application/pdf",filename=f"Aarogyam_Report_{rid}.pdf")
@app.post("/api/payments/{rid}")
def payment(rid:int,centre_id:int=Form(...),amount:float=Form(...),status:str=Form(...)):
 s=db(); r=s.get(Report,rid); c=s.get(Centre,centre_id)
 if not r or not c or r.centre_id!=c.id: raise HTTPException(404,"Report not found")
 r.charge=amount
 if not c.whatsapp_enabled: r.payment="NOT_REQUIRED"
 elif status=="PAID": r.payment="PAID"; r.status="RELEASED"; notify(s,c.id,r.id,"PAYMENT_RECEIVED",f"Payment received for report #{r.id}. Report released."); wa(s,c,r,"FINAL_REPORT",{"phone":r.patient_phone,"url":f"/patient/report/{r.token}"})
 else: r.payment="DUE"; r.status="PAYMENT_PENDING"; wa(s,c,r,"PAYMENT_REQUEST",{"phone":r.patient_phone,"amount":amount,"upi":c.upi_id})
 s.commit(); return rd(r)
@app.post("/api/payments/{rid}/verify")
def verify_payment(rid:int,centre_id:int):
 s=db(); r=s.get(Report,rid); c=s.get(Centre,centre_id)
 if not r or not c or r.centre_id!=c.id: raise HTTPException(404,"Report not found")
 r.payment="PAID"; r.status="RELEASED"; notify(s,c.id,r.id,"PAYMENT_RECEIVED",f"Payment verified for report #{r.id}. Report released."); wa(s,c,r,"FINAL_REPORT",{"phone":r.patient_phone,"url":f"/patient/report/{r.token}"}); s.commit(); return rd(r)
@app.get("/api/settings")
def getsettings(centre_id:int):
 s=db(); c=s.get(Centre,centre_id); return {"whatsapp_enabled":c.whatsapp_enabled,"upi_id":c.upi_id,"credits":c.credits,"credit_price_inr":float(os.getenv("CREDIT_PRICE_INR","2.5"))}
@app.put("/api/settings")
def settings(centre_id:int,whatsapp_enabled:bool=Form(...),upi_id:str=Form("")):
 s=db(); c=s.get(Centre,centre_id); c.whatsapp_enabled=whatsapp_enabled; c.upi_id=upi_id.strip(); s.commit(); return {"ok":True}
@app.post("/api/settings/template")
def template(centre_id:int=Form(...),file:UploadFile=File(...)):
 s=db(); c=s.get(Centre,centre_id); p=ROOT/f"centre_{centre_id}"/"template.pdf"; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(file.file.read()); c.template_path=str(p); s.commit(); return {"ok":True}
@app.get("/api/notifications")
def notifications(centre_id:int):
 s=db(); return [{"id":n.id,"kind":n.kind,"message":n.message,"created_at":n.created_at.isoformat()} for n in s.query(Notification).filter_by(centre_id=centre_id).order_by(Notification.id.desc()).limit(100)]
@app.get("/patient/report/{token}")
def patient(token:str):
 s=db(); r=s.query(Report).filter_by(token=token,status="RELEASED").first()
 if not r: raise HTTPException(404,"Report not released")
 return FileResponse(r.pdf_path,media_type="application/pdf",filename=f"Aarogyam_Report_{r.id}.pdf")
