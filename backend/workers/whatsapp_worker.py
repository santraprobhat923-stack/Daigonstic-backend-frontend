import json,time,threading,re
from datetime import datetime,timedelta
import os
from ..config import (
    WHATSAPP_PROVIDER,WHATSAPP_TOKEN,WHATSAPP_PHONE_NUMBER_ID,
    PUBLIC_BASE_URL,WHATSAPP_PAYMENT_TEMPLATE,WHATSAPP_REPORT_TEMPLATE,
    WHATSAPP_TEMPLATE_LANG
)
from ..database import SessionLocal
from ..models import WAJob
try:
    import requests
except Exception:
    requests=None

MAX_ATTEMPTS=5
RETRY_DELAYS=(15,60,300,900,1800)

def _phone(value):
    return re.sub(r"\\D","",str(value or ""))

def _template(name,components):
    return {
        "messaging_product":"whatsapp",
        "to":_phone(components.pop("_phone","")),
        "type":"template",
        "template":{
            "name":name,
            "language":{"code":WHATSAPP_TEMPLATE_LANG},
            "components":components.pop("_components",[])
        }
    }

def send_meta(payload):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID or not requests:
        return False,"Meta credentials or requests library not configured"
    if not PUBLIC_BASE_URL.startswith("https://"):
        return False,"PUBLIC_BASE_URL must be a public HTTPS URL"
    phone=_phone(payload.get("phone"))
    if not phone:
        return False,"Patient WhatsApp number is missing"
    if payload.get("kind")=="PAYMENT_REQUEST":
        components=[{
            "type":"body",
            "parameters":[
                {"type":"text","text":str(payload.get("amount",0))},
                {"type":"text","text":str(payload.get("upi",""))}
            ]
        }]
        body=_template(WHATSAPP_PAYMENT_TEMPLATE,{"_phone":phone,"_components":components})
    else:
        url=PUBLIC_BASE_URL.rstrip("/")+str(payload.get("url",""))
        components=[
            {"type":"header","parameters":[{
                "type":"document",
                "document":{"link":url,"filename":payload.get("filename","Aarogyam_Report.pdf")}
            }]},
            {"type":"body","parameters":[
                {"type":"text","text":str(payload.get("patient_name") or "Patient")}
            ]}
        ]
        body=_template(WHATSAPP_REPORT_TEMPLATE,{"_phone":phone,"_components":components})
    u=f"https://graph.facebook.com/v23.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    try:
        r=requests.post(
            u,
            headers={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"},
            json=body,
            timeout=20
        )
        if r.ok:
            return True,r.text
        return False,f"Meta HTTP {r.status_code}: {r.text[:1000]}"
    except Exception as e:
        return False,str(e)

def _process_job(db,job):
    job.status="PROCESSING"
    job.attempt_count=(job.attempt_count or 0)+1
    job.last_error=""
    db.commit()
    try:
        payload=json.loads(job.payload or "{}")
        payload["kind"]=job.kind
        ok,detail=(True,"mock delivery") if WHATSAPP_PROVIDER=="mock" else send_meta(payload)
        if ok:
            job.status="SENT"
            job.last_error=""
            job.next_attempt_at=None
        else:
            if job.attempt_count>=MAX_ATTEMPTS:
                job.status="DEAD_LETTER"
                job.last_error=detail
                job.next_attempt_at=None
            else:
                job.status="RETRY"
                job.last_error=detail
                delay=RETRY_DELAYS[min(job.attempt_count-1,len(RETRY_DELAYS)-1)]
                job.next_attempt_at=datetime.utcnow()+timedelta(seconds=delay)
        db.commit()
    except Exception as e:
        db.rollback()
        try:
            job=db.get(WAJob,job.id)
            if job:
                if (job.attempt_count or 0)>=MAX_ATTEMPTS:
                    job.status="DEAD_LETTER"
                    job.next_attempt_at=None
                else:
                    job.status="RETRY"
                    delay=RETRY_DELAYS[min(max((job.attempt_count or 1)-1,0),len(RETRY_DELAYS)-1)]
                    job.next_attempt_at=datetime.utcnow()+timedelta(seconds=delay)
                job.last_error=str(e)
                db.commit()
        except Exception:
            db.rollback()

def run():
    while True:
        db=SessionLocal()
        try:
            now=datetime.utcnow()
            job=(db.query(WAJob)
                 .filter(
                     ((WAJob.status=="PENDING")|(WAJob.status=="RETRY")),
                     ((WAJob.next_attempt_at==None)|(WAJob.next_attempt_at<=now))
                 )
                 .order_by(WAJob.id)
                 .first())
            if job:
                _process_job(db,job)
            else:
                time.sleep(2)
        except Exception:
            db.rollback()
            time.sleep(3)
        finally:
            db.close()

def start_worker():
    threading.Thread(target=run,daemon=True,name="aarogyam-whatsapp").start()
