import os
from pathlib import Path
DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./aarogyam.db")
STORAGE_DIR=Path(os.getenv("STORAGE_DIR","./storage"))
CREDIT_PRICE_INR=float(os.getenv("CREDIT_PRICE_INR","2.50"))
SECRET_KEY=os.getenv("SECRET_KEY","change-this-in-production")
WHATSAPP_PROVIDER=os.getenv("WHATSAPP_PROVIDER","mock")
PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL","")
STORAGE_DIR.mkdir(parents=True,exist_ok=True)
