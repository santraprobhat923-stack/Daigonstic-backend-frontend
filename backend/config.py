import os
from pathlib import Path

# Load the repository-local .env automatically when the app starts.
# This lets Termux use a local .env file without exporting secrets into the shell.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./aarogyam.db")
STORAGE_DIR=Path(os.getenv("STORAGE_DIR","./storage"))
CREDIT_PRICE_INR=float(os.getenv("CREDIT_PRICE_INR","2.50"))
SECRET_KEY=os.getenv("SECRET_KEY","change-this-in-production")
WHATSAPP_PROVIDER=os.getenv("WHATSAPP_PROVIDER","mock")
PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL","")
WHATSAPP_TOKEN=os.getenv("WHATSAPP_TOKEN","")
WHATSAPP_PHONE_NUMBER_ID=os.getenv("WHATSAPP_PHONE_NUMBER_ID","")
WHATSAPP_PAYMENT_TEMPLATE=os.getenv("WHATSAPP_PAYMENT_TEMPLATE","aarogyam_payment")
WHATSAPP_REPORT_TEMPLATE=os.getenv("WHATSAPP_REPORT_TEMPLATE","aarogyam_report")
WHATSAPP_TEMPLATE_LANG=os.getenv("WHATSAPP_TEMPLATE_LANG","en_US")
STORAGE_DIR.mkdir(parents=True,exist_ok=True)
RAZORPAY_MODE=os.getenv("RAZORPAY_MODE","test").lower()
RAZORPAY_KEY_ID=os.getenv("RAZORPAY_KEY_ID","")
RAZORPAY_KEY_SECRET=os.getenv("RAZORPAY_KEY_SECRET","")
RAZORPAY_WEBHOOK_SECRET=os.getenv("RAZORPAY_WEBHOOK_SECRET","")
