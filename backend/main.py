import json,secrets
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,Form,HTTPException,Request,Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import Base,engine,get_db
from .models import Centre,Report,Notification
from .auth import hash_password,check_password,token_for,centre_id
from .config import STORAGE_DIR,CREDIT_PRICE_INR
from .services import extract,sha,notify,queue_wa,make_pdf,report_dict
from .workers.whatsapp_worker import start_worker
Base.metadata.create_all(engine)
def migrate_legacy_sqlite():
    if "sqlite" not in str(engine.url): return
    with engine.begin() as conn:
        tables=[x[0] for x in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))]
        if "centres" in tables:
            cols=[x[1] for x in conn.execute(text("PRAGMA table_info(centres)"))]
            if "password_hash" not in cols: conn.execute(text("ALTER TABLE centres ADD COLUMN password_hash VARCHAR"))
            if "whatsapp_enabled" not in cols: conn.execute(text("ALTER TABLE centres ADD COLUMN whatsapp_enabled BOOLEAN DEFAULT 0"))
            if "upi_id" not in cols: conn.execute(text("ALTER TABLE centres ADD COLUMN upi_id VARCHAR DEFAULT ''"))
            if "credits" not in cols: conn.execute(text("ALTER TABLE centres ADD COLUMN credits INTEGER DEFAULT 10"))
            if "template_path" not in cols: conn.execute(text("ALTER TABLE centres ADD COLUMN template_path VARCHAR DEFAULT ''"))
            if "password" in cols:\n                rows=conn.execute(text("SELECT id,password FROM centres WHERE (password_hash IS NULL OR password_hash='') AND password IS NOT NULL")).fetchall()\n                for row in rows: conn.execute(text("UPDATE centres SET password_hash=:h WHERE id=:id"),{"h":hash_password(row[1]),"id":row[0]})
        if "reports" in tables:
            cols=[x[1] for x in conn.execute(text("PRAGMA table_info(reports)"))]
            if "image_hashes" not in cols: conn.execute(text("ALTER TABLE reports ADD COLUMN image_hashes TEXT DEFAULT '[]'"))
            if "token" not in cols: conn.execute(text("ALTER TABLE reports ADD COLUMN token VARCHAR"))
migrate_legacy_sqlite()
app=FastAPI(title="Aarogyam")
app.mount("/static",StaticFiles(directory="frontend"),name="static")
@app.on_event("startup")
def startup(): start_worker()
def current(request:Request,db:Session=Depends(get_db)):
    cid=centre_id(request); c=db.get(Centre,cid)
    if not c: raise HTTPException(401,"Centre not found")
    return c
@app.get("/")
def home(): return FileResponse("frontend/index.html")
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/api/bootstrap")
def bootstrap(name:str=Form(...),email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
    if db.query(Centre).filter_by(email=email.strip().lower()).first(): raise HTTPException(409,"Email already exists")
    c=Centre(name=name.strip(),email=email.strip().lower(),password_hash=hash_password(password)); db.add(c); db.commit(); db.refresh(c)
    return {"access_token":token_for(c.id),"centre_id":c.id,"name":c.name,"credits":c.credits}
@app.post("/api/login")
def login(email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
    c=db.query(Centre).filter_by(email=email.strip().lower()).first()
    if not c or not check_password(password,c.password_hash): raise HTTPException(401,"Invalid credentials")
    return {"access_token":token_for(c.id),"centre_id":c.id,"name":c.name,"credits":c.credits}
@app.get("/api/me")
def me(c=Depends(current)): return {"centre_id":c.id,"name":c.name,"email":c.email,"credits":c.credits}
@app.post("/api/reports/upload")
def upload(files:list[UploadFile]=File(...),c=Depends(current),db:Session=Depends(get_db)):
    paths=[]; hashes=[]; merged={"patient":{},"tests":[]}; texts=[]
    for f in files:
        data=awaitable_read(f)
        h=sha(data)
        if h in hashes: continue
        p=STORAGE_DIR/f"centre_{c.id}"/"images"/(secrets.token_hex(8)+"_"+Path(f.filename or "image").name)
        p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data); paths.append(str(p)); hashes.append(h)
        t,d=extract(str(p)); texts.append(t)
        for k,v in d["patient"].items(): merged["patient"][k]=merged["patient"].get(k) or v
        merged["tests"]+=d["tests"]
    if not paths: raise HTTPException(400,"No image received")
    r=Report(centre_id=c.id,token=secrets.token_urlsafe(32),verified_data=json.dumps(merged),ocr_text="\n".join(texts),image_paths=json.dumps(paths),image_hashes=json.dumps(hashes)); db.add(r); db.commit(); db.refresh(r)
    return {"report":report_dict(r),"extracted":merged}
def awaitable_read(f):
    return f.file.read()
@app.post("/api/reports/{rid}/verify")
def verify(rid:int,data:str=Form(...),c=Depends(current),db:Session=Depends(get_db)):
    r=db.get(Report,rid)
    if not r or r.centre_id!=c.id: raise HTTPException(404,"Report not found")
    if r.status not in ("OCR_REVIEW","GENERATED"): raise HTTPException(409,"Report already released or paid")
    if c.credits<1: raise HTTPException(400,"Insufficient credits")
    try:d=json.loads(data)
    except: raise HTTPException(400,"Invalid verification data")
    out=STORAGE_DIR/f"centre_{c.id}"/"reports"/f"report_{r.id}.pdf"; make_pdf(c,r,d,out)
    c.credits-=1; r.verified_data=data; p=d.get("patient",{}); r.patient_name=p.get("name",""); r.patient_age=p.get("age",""); r.patient_sex=p.get("sex",""); r.patient_phone=p.get("phone",""); r.patient_code=p.get("code",""); r.pdf_path=str(out); r.status="GENERATED"; r.payment="PENDING" if c.whatsapp_enabled else "NOT_REQUIRED"
    notify(db,c.id,r.id,"REPORT_GENERATED",f"Report #{r.id} generated. Centre download is ready."); db.commit(); return report_dict(r)
@app.get("/api/reports")
def reports(search:str="",c=Depends(current),db:Session=Depends(get_db)):
    q=db.query(Report).filter_by(centre_id=c.id)
    if search.strip():
        s=f"%{search.strip()}%"; q=q.filter((Report.patient_name.ilike(s))|(Report.patient_code.ilike(s))|(Report.patient_phone.ilike(s)))
    return [report_dict(r) for r in q.order_by(Report.id.desc()).all()]
@app.get("/api/reports/{rid}/download")
def download(rid:int,c=Depends(current),db:Session=Depends(get_db)):
    r=db.get(Report,rid)
    if not r or r.centre_id!=c.id or not r.pdf_path or not Path(r.pdf_path).exists(): raise HTTPException(404,"Report unavailable")
    return FileResponse(r.pdf_path,media_type="application/pdf",filename=f"Aarogyam_Report_{rid}.pdf")
@app.post("/api/payments/{rid}")
def payment(rid:int,amount:float=Form(...),status:str=Form(...),c=Depends(current),db:Session=Depends(get_db)):
    r=db.get(Report,rid)
    if not r or r.centre_id!=c.id: raise HTTPException(404,"Report not found")
    r.charge=amount
    if not c.whatsapp_enabled: r.payment="NOT_REQUIRED"; r.status="GENERATED"
    elif status=="PAID":
        r.payment="PAID"; r.status="RELEASED"; notify(db,c.id,r.id,"PAYMENT_RECEIVED",f"Payment received for report #{r.id}. Report released."); queue_wa(db,c,r,"FINAL_REPORT",{"phone":r.patient_phone,"url":f"/patient/report/{r.token}"})
    else:
        r.payment="DUE"; r.status="PAYMENT_PENDING"; queue_wa(db,c,r,"PAYMENT_REQUEST",{"phone":r.patient_phone,"amount":amount,"upi":c.upi_id})
    db.commit(); return report_dict(r)
@app.post("/api/payments/{rid}/verify")
def verify_payment(rid:int,c=Depends(current),db:Session=Depends(get_db)):
    r=db.get(Report,rid)
    if not r or r.centre_id!=c.id: raise HTTPException(404,"Report not found")
    r.payment="PAID"; r.status="RELEASED"; notify(db,c.id,r.id,"PAYMENT_RECEIVED",f"Payment verified for report #{r.id}. Report released."); queue_wa(db,c,r,"FINAL_REPORT",{"phone":r.patient_phone,"url":f"/patient/report/{r.token}"}); db.commit(); return report_dict(r)
@app.get("/api/settings")
def settings_get(c=Depends(current)): return {"whatsapp_enabled":c.whatsapp_enabled,"upi_id":c.upi_id,"credits":c.credits,"credit_price_inr":CREDIT_PRICE_INR}
@app.put("/api/settings")
def settings_save(whatsapp_enabled:bool=Form(...),upi_id:str=Form(""),c=Depends(current),db:Session=Depends(get_db)):
    c.whatsapp_enabled=whatsapp_enabled; c.upi_id=upi_id.strip(); db.commit(); return {"ok":True}
@app.post("/api/settings/template")
def template(file:UploadFile=File(...),c=Depends(current),db:Session=Depends(get_db)):
    if not (file.filename or "").lower().endswith(".pdf"): raise HTTPException(400,"Template must be PDF")
    p=STORAGE_DIR/f"centre_{c.id}"/"template.pdf"; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(file.file.read()); c.template_path=str(p); db.commit(); return {"ok":True}
@app.get("/api/notifications")
def notifications(c=Depends(current),db:Session=Depends(get_db)):
    return [{"id":n.id,"kind":n.kind,"message":n.message,"created_at":n.created_at.isoformat()} for n in db.query(Notification).filter_by(centre_id=c.id).order_by(Notification.id.desc()).limit(100)]
@app.get("/patient/report/{token}")
def patient(token:str,db:Session=Depends(get_db)):
    r=db.query(Report).filter_by(token=token,status="RELEASED").first()
    if not r or not Path(r.pdf_path).exists(): raise HTTPException(404,"Report not released")
    c=db.get(Centre,r.centre_id); notify(db,c.id,r.id,"REPORT_DOWNLOADED",f"Patient downloaded report #{r.id}."); db.commit()
    return FileResponse(r.pdf_path,media_type="application/pdf",filename=f"Aarogyam_Report_{r.id}.pdf")
