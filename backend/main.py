import json,secrets,hmac,hashlib
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,Form,HTTPException,Request,Depends,BackgroundTasks
from fastapi.responses import FileResponse,HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import Base,engine,get_db,SessionLocal
from .models import Centre,Report,Notification,CreditOrder,CreditTransaction
from .auth import hash_password,check_password,token_for,centre_id
from .config import STORAGE_DIR,CREDIT_PRICE_INR,WHATSAPP_PROVIDER,WHATSAPP_PAYMENT_TEMPLATE,WHATSAPP_REPORT_TEMPLATE,RAZORPAY_KEY_ID,RAZORPAY_KEY_SECRET,RAZORPAY_WEBHOOK_SECRET
from .services import extract,sha,notify,queue_wa,make_pdf,report_dict
from .workers.whatsapp_worker import start_worker
from .superadmin import router as superadmin_router,ensure_superadmin,setting as system_setting
try: import razorpay
except Exception: razorpay=None
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
            if "enabled" not in cols: conn.execute(text("ALTER TABLE centres ADD COLUMN enabled BOOLEAN DEFAULT 1"))
            if "created_at" not in cols: conn.execute(text("ALTER TABLE centres ADD COLUMN created_at DATETIME"))
            if "password" in cols:
                rows=conn.execute(text("SELECT id,password FROM centres WHERE (password_hash IS NULL OR password_hash='') AND password IS NOT NULL")).fetchall()
                for row in rows:
                    conn.execute(text("UPDATE centres SET password_hash=:h WHERE id=:id"),{"h":hash_password(row[1]),"id":row[0]})
        if "reports" in tables:
            cols=[x[1] for x in conn.execute(text("PRAGMA table_info(reports)"))]
            if "image_hashes" not in cols: conn.execute(text("ALTER TABLE reports ADD COLUMN image_hashes TEXT DEFAULT '[]'"))
            if "token" not in cols: conn.execute(text("ALTER TABLE reports ADD COLUMN token VARCHAR"))
        if "wa_jobs" in tables:
            cols=[x[1] for x in conn.execute(text("PRAGMA table_info(wa_jobs)"))]
            if "attempt_count" not in cols: conn.execute(text("ALTER TABLE wa_jobs ADD COLUMN attempt_count INTEGER DEFAULT 0"))
            if "last_error" not in cols: conn.execute(text("ALTER TABLE wa_jobs ADD COLUMN last_error TEXT DEFAULT ''"))
            if "next_attempt_at" not in cols: conn.execute(text("ALTER TABLE wa_jobs ADD COLUMN next_attempt_at DATETIME"))
migrate_legacy_sqlite()
app=FastAPI(title="Aarogyam")
app.mount("/static",StaticFiles(directory="frontend"),name="static")
app.mount("/superadmin-static",StaticFiles(directory="frontend"),name="superadmin-static")
app.include_router(superadmin_router)
@app.on_event("startup")
def startup():
    db=SessionLocal()
    try: ensure_superadmin(db)
    finally: db.close()
    start_worker()
def current(request:Request,db:Session=Depends(get_db)):
    cid=centre_id(request); c=db.get(Centre,cid)
    if not c: raise HTTPException(401,"Centre not found")
    if not c.enabled: raise HTTPException(403,"Centre account is suspended. Contact Aarogyam support.")
    return c
@app.get("/superadmin")
def superadmin_home():
    index_path=Path("frontend/superadmin.html")
    if not index_path.is_file(): raise HTTPException(500,"Super Admin frontend not found")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))
@app.get("/")
def home():
    # Read the HTML directly instead of FileResponse. This avoids a Content-Length
    # mismatch observed on Android/Termux shared storage when serving the app shell.
    index_path=Path("frontend/index.html")
    if not index_path.is_file():
        raise HTTPException(500,"Frontend index.html not found")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))
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
def _razorpay_client(db=None):
    key_id=system_setting(db,"razorpay_key_id",RAZORPAY_KEY_ID) if db else RAZORPAY_KEY_ID
    key_secret=system_setting(db,"razorpay_key_secret",RAZORPAY_KEY_SECRET) if db else RAZORPAY_KEY_SECRET
    if not razorpay or not key_id or not key_secret:
        raise HTTPException(503,"Razorpay is not configured on the server")
    return razorpay.Client(auth=(key_id,key_secret)),key_id

@app.get("/api/credits")
def credits(c=Depends(current),db:Session=Depends(get_db)):
    tx=db.query(CreditTransaction).filter_by(centre_id=c.id).order_by(CreditTransaction.id.desc()).limit(100).all()
    return {"balance":c.credits,"price_inr":float(system_setting(db,"credit_price_inr",str(CREDIT_PRICE_INR))),"transactions":[
        {"id":t.id,"type":t.type,"credits":t.credits,"amount_inr":t.amount_inr,"reference":t.reference,"created_at":t.created_at.isoformat()}
        for t in tx
    ]}

@app.post("/api/credits/razorpay/order")
def create_credit_order(credits:int=Form(...),c=Depends(current),db:Session=Depends(get_db)):
    if credits<1 or credits>100000: raise HTTPException(400,"Choose a valid credit quantity")
    client,key_id=_razorpay_client(db)
    price_inr=float(system_setting(db,"credit_price_inr",str(CREDIT_PRICE_INR)))
    amount_paise=int(round(credits*price_inr*100))
    if amount_paise<100: raise HTTPException(400,"Recharge amount is below Razorpay minimum")
    try:
        order=client.order.create({"amount":amount_paise,"currency":"INR","receipt":f"centre_{c.id}_{secrets.token_hex(6)}","notes":{"centre_id":str(c.id),"credits":str(credits)}})
    except Exception:
        raise HTTPException(502,"Could not create Razorpay order")
    row=CreditOrder(centre_id=c.id,razorpay_order_id=order["id"],credits=credits,amount_paise=amount_paise,status="CREATED")
    db.add(row); db.commit()
    return {"key_id":key_id,"order_id":order["id"],"amount":amount_paise,"currency":"INR","credits":credits}

@app.post("/api/credits/razorpay/verify")
def verify_credit_payment(order_id:str=Form(...),payment_id:str=Form(...),signature:str=Form(...),c=Depends(current),db:Session=Depends(get_db)):
    row=db.query(CreditOrder).filter_by(razorpay_order_id=order_id,centre_id=c.id).first()
    if not row: raise HTTPException(404,"Recharge order not found")
    if row.status=="PAID": return {"ok":True,"credits":c.credits,"message":"Recharge already applied"}
    try:
        _razorpay_client(db)[0].utility.verify_payment_signature({"razorpay_order_id":order_id,"razorpay_payment_id":payment_id,"razorpay_signature":signature})
    except Exception:
        raise HTTPException(400,"Razorpay payment verification failed")
    existing=db.query(CreditTransaction).filter_by(razorpay_payment_id=payment_id).first()
    if existing:
        row.status="PAID"; db.commit()
        return {"ok":True,"credits":c.credits,"message":"Recharge already recorded"}
    c.credits += row.credits
    row.status="PAID"
    db.add(CreditTransaction(centre_id=c.id,type="RECHARGE",credits=row.credits,amount_inr=row.amount_paise/100,reference=order_id,razorpay_payment_id=payment_id))
    notify(db,c.id,None,"CREDIT_RECHARGE",f"{row.credits} credits added successfully.")
    db.commit()
    return {"ok":True,"credits":c.credits,"message":f"{row.credits} credits added"}

@app.post("/api/credits/razorpay/webhook")
async def razorpay_webhook(request:Request,db:Session=Depends(get_db)):
    webhook_secret=system_setting(db,"razorpay_webhook_secret",RAZORPAY_WEBHOOK_SECRET)
    if not webhook_secret: raise HTTPException(503,"Razorpay webhook secret is not configured")
    body=await request.body()
    received=request.headers.get("x-razorpay-signature","")
    expected=hmac.new(webhook_secret.encode(),body,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received,expected): raise HTTPException(400,"Invalid webhook signature")
    try: payload=json.loads(body)
    except Exception: raise HTTPException(400,"Invalid webhook payload")
    if payload.get("event")=="payment.captured":
        ent=payload.get("payload",{}).get("payment",{}).get("entity",{})
        payment_id=ent.get("id",""); order_id=ent.get("order_id","")
        row=db.query(CreditOrder).filter_by(razorpay_order_id=order_id).first()
        if row and row.status!="PAID" and not db.query(CreditTransaction).filter_by(razorpay_payment_id=payment_id).first():
            centre=db.get(Centre,row.centre_id)
            if centre:
                centre.credits += row.credits; row.status="PAID"
                db.add(CreditTransaction(centre_id=centre.id,type="RECHARGE",credits=row.credits,amount_inr=row.amount_paise/100,reference=order_id,razorpay_payment_id=payment_id))
                notify(db,centre.id,None,"CREDIT_RECHARGE",f"{row.credits} credits added successfully.")
                db.commit()
    return {"ok":True}
def process_ocr(report_id, centre_id, paths):
    db=SessionLocal()
    try:
        r=db.get(Report,report_id)
        if not r or r.centre_id!=centre_id: return
        merged={"patient":{},"tests":[]}; texts=[]; errors=[]
        for raw_path in paths:
            try:
                t,d=extract(raw_path); texts.append(t)
                for k,v in d["patient"].items():
                    if v and not merged["patient"].get(k): merged["patient"][k]=v
                merged["tests"]+=d["tests"]
            except Exception as e:
                errors.append(f"OCR failed for {Path(raw_path).name}: {e}")
        r.verified_data=json.dumps(merged)
        r.ocr_text="\n".join(texts + errors)
        p=merged.get("patient",{})
        r.patient_name=p.get("name",""); r.patient_age=p.get("age",""); r.patient_sex=p.get("sex","")
        r.patient_phone=p.get("phone",""); r.patient_code=p.get("code","")
        r.status="OCR_REVIEW"
        notify(db,centre_id,report_id,"OCR_READY",f"Report #{report_id} is ready for technician verification.")
        db.commit()
    except Exception:
        db.rollback()
        try:
            r=db.get(Report,report_id)
            if r:
                r.status="OCR_REVIEW"
                r.ocr_text=(r.ocr_text or "") + "\nOCR processing encountered an error. Please review the image."
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()

@app.post("/api/reports/upload")
def upload(background_tasks:BackgroundTasks,files:list[UploadFile]=File(...),c=Depends(current),db:Session=Depends(get_db)):
    paths=[]; hashes=[]; duplicates=0
    existing_hashes=set()
    for raw in db.query(Report.image_hashes).filter_by(centre_id=c.id).all():
        try: existing_hashes.update(json.loads(raw[0] or "[]"))
        except Exception: pass
    for f in files:
        data=awaitable_read(f)
        if not data: continue
        h=sha(data)
        if h in hashes or h in existing_hashes:
            duplicates+=1
            continue
        p=STORAGE_DIR/f"centre_{c.id}"/"images"/(secrets.token_hex(8)+"_"+Path(f.filename or "image").name)
        p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data); paths.append(str(p)); hashes.append(h)
    if not paths:
        if duplicates: raise HTTPException(409,"This image was already uploaded. No new report was created.")
        raise HTTPException(400,"No image received")
    r=Report(centre_id=c.id,token=secrets.token_urlsafe(32),verified_data=json.dumps({"patient":{},"tests":[]}),
             ocr_text="",image_paths=json.dumps(paths),image_hashes=json.dumps(hashes),status="OCR_PROCESSING")
    db.add(r); db.commit(); db.refresh(r)
    background_tasks.add_task(process_ocr,r.id,c.id,paths)
    return {"report":report_dict(r),"extracted":{"patient":{},"tests":[]},
            "uploaded_count":len(paths),"duplicate_count":duplicates,"ocr_status":"PROCESSING"}

def awaitable_read(f):
    return f.file.read()
@app.post("/api/reports/{rid}/verify")
def verify(rid:int,data:str=Form(...),c=Depends(current),db:Session=Depends(get_db)):
    r=db.get(Report,rid)
    if not r or r.centre_id!=c.id: raise HTTPException(404,"Report not found")
    if r.status=="GENERATED": return report_dict(r)
    if r.status!="OCR_REVIEW": raise HTTPException(409,"Report is not ready for verification")
    if c.credits<1: raise HTTPException(400,"Insufficient credits")
    try:d=json.loads(data)
    except: raise HTTPException(400,"Invalid verification data")
    out=STORAGE_DIR/f"centre_{c.id}"/"reports"/f"report_{r.id}.pdf"; make_pdf(c,r,d,out)
    c.credits-=1
    db.add(CreditTransaction(centre_id=c.id,type="REPORT_USAGE",credits=-1,amount_inr=0,reference=f"report_{r.id}"))
    r.verified_data=data; p=d.get("patient",{}); r.patient_name=p.get("name",""); r.patient_age=p.get("age",""); r.patient_sex=p.get("sex",""); r.patient_phone=p.get("phone",""); r.patient_code=p.get("code",""); r.pdf_path=str(out); r.status="GENERATED"; r.payment="PENDING" if c.whatsapp_enabled else "NOT_REQUIRED"
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
        r.payment="PAID"; r.status="RELEASED"; notify(db,c.id,r.id,"PAYMENT_RECEIVED",f"Payment received for report #{r.id}. Report released."); queue_wa(db,c,r,"FINAL_REPORT",{"phone":r.patient_phone,"patient_name":r.patient_name or "Patient","url":f"/patient/report/{r.token}","filename":f"Aarogyam_Report_{r.id}.pdf"})
    else:
        r.payment="DUE"; r.status="PAYMENT_PENDING"; queue_wa(db,c,r,"PAYMENT_REQUEST",{"phone":r.patient_phone,"amount":amount,"upi":c.upi_id})
    db.commit(); return report_dict(r)
@app.post("/api/payments/{rid}/verify")
def verify_payment(rid:int,c=Depends(current),db:Session=Depends(get_db)):
    r=db.get(Report,rid)
    if not r or r.centre_id!=c.id: raise HTTPException(404,"Report not found")
    r.payment="PAID"; r.status="RELEASED"; notify(db,c.id,r.id,"PAYMENT_RECEIVED",f"Payment verified for report #{r.id}. Report released."); queue_wa(db,c,r,"FINAL_REPORT",{"phone":r.patient_phone,"patient_name":r.patient_name or "Patient","url":f"/patient/report/{r.token}","filename":f"Aarogyam_Report_{r.id}.pdf"}); db.commit(); return report_dict(r)
@app.get("/api/settings")
def settings_get(c=Depends(current),db:Session=Depends(get_db)): return {"whatsapp_enabled":c.whatsapp_enabled,"upi_id":c.upi_id,"credits":c.credits,"credit_price_inr":float(system_setting(db,"credit_price_inr",str(CREDIT_PRICE_INR))),"whatsapp_provider":WHATSAPP_PROVIDER,"payment_template":WHATSAPP_PAYMENT_TEMPLATE,"report_template":WHATSAPP_REPORT_TEMPLATE}
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
