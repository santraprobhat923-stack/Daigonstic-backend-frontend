import json,time,threading
from pathlib import Path
from .config import WHATSAPP_PROVIDER
from .database import SessionLocal
from .models import WAJob
try:
 import requests
except Exception: requests=None
def send_meta(payload):
    token=__import__("os").getenv("WHATSAPP_TOKEN",""); phone_id=__import__("os").getenv("WHATSAPP_PHONE_NUMBER_ID","")
    if not token or not phone_id or not requests: return False,"Meta credentials not configured"
    to=payload.get("phone","").replace(" ","")
    if payload["kind"]=="PAYMENT_REQUEST":
        text=f"Payment pending for your diagnostic report. Amount: ₹{payload.get('amount',0)}. UPI: {payload.get('upi','')}"
    else:
        base=__import__("os").getenv("PUBLIC_BASE_URL","").rstrip("/")
        text=f"Your diagnostic report is ready: {base}{payload.get('url','')}"
    u=f"https://graph.facebook.com/v23.0/{phone_id}/messages"
    r=requests.post(u,headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},json={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text}},timeout=20)
    return r.ok,r.text
def run():
    while True:
        db=SessionLocal()
        try:
            job=db.query(WAJob).filter(WAJob.status=="PENDING").order_by(WAJob.id).first()
            if job:
                job.status="PROCESSING"; db.commit()
                p=json.loads(job.payload); p["kind"]=job.kind
                ok,detail=(True,"mock") if WHATSAPP_PROVIDER=="mock" else send_meta(p)
                job.status="SENT" if ok else "RETRY"
                db.commit()
            else: time.sleep(2)
        except Exception:
            db.rollback(); time.sleep(3)
        finally: db.close()
def start_worker():
    threading.Thread(target=run,daemon=True,name="aarogyam-whatsapp").start()
