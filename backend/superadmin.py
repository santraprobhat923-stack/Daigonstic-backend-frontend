import base64,hashlib,hmac,json,time
from fastapi import APIRouter,Depends,Form,HTTPException,Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import get_db
from .models import SuperAdmin,SystemSetting,Centre,Report,CreditTransaction,CreditOrder,WAJob,Notification
from .auth import hash_password,check_password
from .config import SECRET_KEY

router=APIRouter()

def encrypt_secret(value):
    # Android/Termux-safe reversible storage for the local prototype.
    # Production deployment should replace this with a real secret manager/encryption key.
    key=hashlib.sha256(SECRET_KEY.encode()).digest()
    raw=value.encode()
    return base64.urlsafe_b64encode(bytes(b ^ key[i % len(key)] for i,b in enumerate(raw))).decode()

def decrypt_secret(value):
    try:
        key=hashlib.sha256(SECRET_KEY.encode()).digest()
        raw=base64.urlsafe_b64decode(value.encode())
        return bytes(b ^ key[i % len(key)] for i,b in enumerate(raw)).decode()
    except Exception:
        return ""

def super_token(admin_id):
    body=json.dumps({"sid":int(admin_id),"role":"superadmin","exp":int(time.time())+43200},separators=(",",":")).encode()
    sig=hmac.new(SECRET_KEY.encode(),body,hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body+b"."+sig).decode()

def super_admin(request:Request,db:Session=Depends(get_db)):
    t=request.headers.get("Authorization","")
    if not t.startswith("Bearer "):raise HTTPException(401,"Super Admin login required")
    try:
        raw=base64.urlsafe_b64decode(t[7:].encode());body,sig=raw.rsplit(b".",1)
        if not hmac.compare_digest(sig,hmac.new(SECRET_KEY.encode(),body,hashlib.sha256).digest()):raise ValueError()
        p=json.loads(body)
        if p.get("role")!="superadmin" or p["exp"]<time.time():raise ValueError()
        a=db.get(SuperAdmin,int(p["sid"]))
        if not a or not a.enabled:raise ValueError()
        return a
    except Exception:raise HTTPException(401,"Invalid or expired Super Admin session")

def setting(db,key,default=""):
    row=db.query(SystemSetting).filter_by(key=key).first()
    if not row:return default
    return decrypt_secret(row.value) if row.is_secret else row.value

def save_setting(db,key,value,is_secret=False):
    row=db.query(SystemSetting).filter_by(key=key).first()
    if not row:row=SystemSetting(key=key);db.add(row)
    row.value=encrypt_secret(value) if is_secret else value;row.is_secret=is_secret

@router.post("/api/superadmin/login")
def login(email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
    a=db.query(SuperAdmin).filter_by(email=email.strip().lower()).first()
    if not a or not a.enabled or not check_password(password,a.password_hash):raise HTTPException(401,"Invalid Super Admin credentials")
    a.last_login=__import__('datetime').datetime.utcnow();db.commit()
    return {"access_token":super_token(a.id),"name":a.name,"email":a.email}

@router.get("/api/superadmin/me")
def me(a=Depends(super_admin)):return {"name":a.name,"email":a.email}

@router.get("/api/superadmin/dashboard")
def dashboard(a=Depends(super_admin),db:Session=Depends(get_db)):
    centres=db.query(Centre).all()
    tx=db.query(CreditTransaction).filter(CreditTransaction.type=="RECHARGE").all()
    return {"centres":len(centres),"active_centres":sum(1 for c in centres if c.enabled),"suspended_centres":sum(1 for c in centres if not c.enabled),
            "reports":db.query(func.count(Report.id)).scalar() or 0,
            "pending_verifications":db.query(func.count(Report.id)).filter(Report.status=="OCR_REVIEW").scalar() or 0,
            "payment_pending":db.query(func.count(Report.id)).filter(Report.status=="PAYMENT_PENDING").scalar() or 0,
            "credits_sold":sum((x.credits or 0) for x in tx),"revenue_inr":round(sum((x.amount_inr or 0) for x in tx),2),
            "wa_pending":db.query(func.count(WAJob.id)).filter(WAJob.status.in_(["PENDING","PROCESSING","RETRY"])).scalar() or 0,
            "wa_failed":db.query(func.count(WAJob.id)).filter(WAJob.status=="DEAD_LETTER").scalar() or 0,
            "credit_price_inr":float(setting(db,"credit_price_inr","2.50"))}

@router.get("/api/superadmin/centres")
def centres(a=Depends(super_admin),db:Session=Depends(get_db)):
    rows=[]
    for c in db.query(Centre).order_by(Centre.id.desc()).all():
        reports=db.query(func.count(Report.id)).filter(Report.centre_id==c.id).scalar() or 0
        used=-(db.query(func.coalesce(func.sum(CreditTransaction.credits),0)).filter(CreditTransaction.centre_id==c.id,CreditTransaction.type=="REPORT_USAGE").scalar() or 0)
        last=db.query(func.max(Report.created_at)).filter(Report.centre_id==c.id).scalar()
        rows.append({"id":c.id,"name":c.name,"email":c.email,"enabled":c.enabled,"credits":c.credits,"reports":reports,"credits_used":used,
                     "last_activity":last.isoformat() if last else None,"whatsapp_enabled":c.whatsapp_enabled,"upi_id":c.upi_id,"template_configured":bool(c.template_path)})
    return rows

@router.get("/api/superadmin/centres/{centre_id}")
def centre_detail(centre_id:int,a=Depends(super_admin),db:Session=Depends(get_db)):
    c=db.get(Centre,centre_id)
    if not c: raise HTTPException(404,"Centre not found")
    reports=db.query(Report).filter_by(centre_id=c.id).order_by(Report.id.desc()).limit(50).all()
    tx=db.query(CreditTransaction).filter_by(centre_id=c.id).order_by(CreditTransaction.id.desc()).limit(50).all()
    return {"centre":{"id":c.id,"name":c.name,"email":c.email,"enabled":c.enabled,"credits":c.credits,"whatsapp_enabled":c.whatsapp_enabled,
             "upi_id":c.upi_id,"template_configured":bool(c.template_path),"created_at":c.created_at.isoformat() if c.created_at else None},
            "reports":[{"id":r.id,"patient_name":r.patient_name,"status":r.status,"payment":r.payment,"created_at":r.created_at.isoformat() if r.created_at else None} for r in reports],
            "transactions":[{"id":x.id,"type":x.type,"credits":x.credits,"amount_inr":x.amount_inr,"reference":x.reference,"created_at":x.created_at.isoformat() if x.created_at else None} for x in tx]}

@router.put("/api/superadmin/centres/{centre_id}/status")
def centre_status(centre_id:int,enabled:bool=Form(...),a=Depends(super_admin),db:Session=Depends(get_db)):
    c=db.get(Centre,centre_id)
    if not c: raise HTTPException(404,"Centre not found")
    c.enabled=enabled; db.commit()
    return {"ok":True,"centre_id":c.id,"enabled":c.enabled}

@router.get("/api/superadmin/monitoring")
def monitoring(a=Depends(super_admin),db:Session=Depends(get_db)):
    return {"ocr_review":[{"id":r.id,"centre_id":r.centre_id,"patient":r.patient_name,"created_at":r.created_at.isoformat() if r.created_at else None} for r in db.query(Report).filter(Report.status=="OCR_REVIEW").order_by(Report.id.desc()).limit(50)],
            "payment_pending":[{"id":r.id,"centre_id":r.centre_id,"patient":r.patient_name,"payment":r.payment,"created_at":r.created_at.isoformat() if r.created_at else None} for r in db.query(Report).filter(Report.status=="PAYMENT_PENDING").order_by(Report.id.desc()).limit(50)],
            "whatsapp":[{"id":j.id,"centre_id":j.centre_id,"report_id":j.report_id,"kind":j.kind,"status":j.status,"attempts":j.attempt_count,"error":j.last_error,"created_at":j.created_at.isoformat() if j.created_at else None} for j in db.query(WAJob).order_by(WAJob.id.desc()).limit(100)]}

@router.get("/api/superadmin/activity")
def activity(a=Depends(super_admin),db:Session=Depends(get_db)):
    return [{"id":n.id,"centre_id":n.centre_id,"report_id":n.report_id,"kind":n.kind,"message":n.message,"created_at":n.created_at.isoformat() if n.created_at else None}
            for n in db.query(Notification).order_by(Notification.id.desc()).limit(100)]

@router.post("/api/superadmin/centres")
def create_centre(name:str=Form(...),email:str=Form(...),password:str=Form(...),credits:int=Form(10),a=Depends(super_admin),db:Session=Depends(get_db)):
    email=email.strip().lower(); name=name.strip()
    if not name or not email or len(password)<10: raise HTTPException(400,"Name, email and a 10+ character password are required")
    if db.query(Centre).filter_by(email=email).first(): raise HTTPException(409,"Email already exists")
    if credits<0: raise HTTPException(400,"Credits cannot be negative")
    c=Centre(name=name,email=email,password_hash=hash_password(password),credits=credits); db.add(c); db.commit(); db.refresh(c)
    return {"ok":True,"centre_id":c.id,"name":c.name,"email":c.email,"credits":c.credits}

@router.put("/api/superadmin/centres/{centre_id}/credits")
def adjust_credits(centre_id:int,credits:int=Form(...),a=Depends(super_admin),db:Session=Depends(get_db)):
    c=db.get(Centre,centre_id)
    if not c:raise HTTPException(404,"Centre not found")
    if credits<0:raise HTTPException(400,"Credits cannot be negative")
    delta=credits-c.credits;c.credits=credits
    if delta:db.add(CreditTransaction(centre_id=c.id,type="SUPERADMIN_ADJUSTMENT",credits=delta,amount_inr=0,reference="superadmin"))
    db.commit();return {"ok":True,"centre_id":c.id,"credits":c.credits}

@router.get("/api/superadmin/settings")
def settings(a=Depends(super_admin),db:Session=Depends(get_db)):
    return {"razorpay_mode":setting(db,"razorpay_mode","test"),"razorpay_key_id":setting(db,"razorpay_key_id",""),"razorpay_configured":bool(setting(db,"razorpay_key_id","") and setting(db,"razorpay_key_secret","")),"razorpay_webhook_configured":bool(setting(db,"razorpay_webhook_secret","")),"whatsapp_provider":setting(db,"whatsapp_provider","mock"),"whatsapp_configured":bool(setting(db,"whatsapp_token","") and setting(db,"whatsapp_phone_number_id","")),"whatsapp_phone_number_id":setting(db,"whatsapp_phone_number_id",""),"credit_price_inr":setting(db,"credit_price_inr","2.50")}

@router.put("/api/superadmin/settings")
def save_settings(razorpay_mode:str=Form("test"),razorpay_key_id:str=Form(""),razorpay_key_secret:str=Form(""),razorpay_webhook_secret:str=Form(""),whatsapp_provider:str=Form("mock"),whatsapp_token:str=Form(""),whatsapp_phone_number_id:str=Form(""),credit_price_inr:float=Form(2.50),a=Depends(super_admin),db:Session=Depends(get_db)):
    if credit_price_inr<=0:raise HTTPException(400,"Credit price must be greater than zero")
    values=[("razorpay_mode",razorpay_mode.lower(),False),("razorpay_key_id",razorpay_key_id.strip(),False),("razorpay_key_secret",razorpay_key_secret.strip(),True),("razorpay_webhook_secret",razorpay_webhook_secret.strip(),True),("whatsapp_provider",whatsapp_provider.lower(),False),("whatsapp_token",whatsapp_token.strip(),True),("whatsapp_phone_number_id",whatsapp_phone_number_id.strip(),False),("credit_price_inr",f"{credit_price_inr:.2f}",False)]
    for k,v,secret in values:
        if secret and not v: continue
        save_setting(db,k,v,secret)
    db.commit();return {"ok":True}

@router.put("/api/superadmin/password")
def change_password(current_password:str=Form(...),new_password:str=Form(...),a=Depends(super_admin),db:Session=Depends(get_db)):
    if not check_password(current_password,a.password_hash):raise HTTPException(400,"Current password is incorrect")
    if len(new_password)<10:raise HTTPException(400,"New password must be at least 10 characters")
    a.password_hash=hash_password(new_password);db.commit();return {"ok":True}

@router.post("/api/superadmin/logout")
def logout(a=Depends(super_admin)):return {"ok":True}

def ensure_superadmin(db):
    email=__import__('os').getenv("SUPERADMIN_EMAIL","").strip().lower()
    password=__import__('os').getenv("SUPERADMIN_PASSWORD","")
    if not email or not password:return
    a=db.query(SuperAdmin).filter_by(email=email).first()
    if not a:
        db.add(SuperAdmin(name="Aarogyam Super Admin",email=email,password_hash=hash_password(password),enabled=True));db.commit()
