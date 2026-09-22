from datetime import datetime
from sqlalchemy import Column,Integer,String,Float,Boolean,Text,DateTime,ForeignKey,UniqueConstraint
from .database import Base
class Centre(Base):
    __tablename__="centres"
    id=Column(Integer,primary_key=True)
    name=Column(String,nullable=False)
    email=Column(String,unique=True,index=True,nullable=False)
    password_hash=Column(String,nullable=False)
    whatsapp_enabled=Column(Boolean,default=False,nullable=False)
    upi_id=Column(String,default="",nullable=False)
    credits=Column(Integer,default=10,nullable=False)
    template_path=Column(String,default="",nullable=False)
class Report(Base):
    __tablename__="reports"
    id=Column(Integer,primary_key=True)
    centre_id=Column(Integer,ForeignKey("centres.id"),index=True,nullable=False)
    patient_name=Column(String,default="")
    patient_age=Column(String,default="")
    patient_sex=Column(String,default="")
    patient_phone=Column(String,default="")
    patient_code=Column(String,default="")
    status=Column(String,default="OCR_REVIEW")
    verified_data=Column(Text,default="{}")
    ocr_text=Column(Text,default="")
    image_paths=Column(Text,default="[]")
    image_hashes=Column(Text,default="[]")
    pdf_path=Column(String,default="")
    charge=Column(Float,default=0)
    payment=Column(String,default="NOT_REQUIRED")
    token=Column(String,unique=True,index=True)
    created_at=Column(DateTime,default=datetime.utcnow)
class Notification(Base):
    __tablename__="notifications"
    id=Column(Integer,primary_key=True)
    centre_id=Column(Integer,index=True)
    report_id=Column(Integer)
    kind=Column(String)
    message=Column(Text)
    created_at=Column(DateTime,default=datetime.utcnow)
class WAJob(Base):
    __tablename__="wa_jobs"
    id=Column(Integer,primary_key=True)
    centre_id=Column(Integer,index=True)
    report_id=Column(Integer,index=True)
    kind=Column(String)
    status=Column(String,default="PENDING")
    payload=Column(Text)
    created_at=Column(DateTime,default=datetime.utcnow)
    __table_args__=(UniqueConstraint("report_id","kind",name="uq_wa_report_kind"),)
