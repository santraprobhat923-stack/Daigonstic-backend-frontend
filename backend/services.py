import hashlib,json,re,secrets
from pathlib import Path
from PIL import Image
from .report_renderer import make_pdf_body_on_template
try: import pytesseract
except Exception: pytesseract=None
from .config import STORAGE_DIR
from .models import Notification,WAJob

UNIT_RE=r"(?:mg/dL|g/dL|gm/dL|ng/dL|ng/mL|pg/mL|µIU/mL|uIU/mL|mIU/L|IU/L|IU/mL|U/L|mmol/L|µmol/L|umol/L|mEq/L|mmHg|%|fL|pg|sec|/HPF|/hpf|cells/HPF|million/µL|million/uL|10\^\d+/µL|10\^\d+/uL|10\d+/µL|10\d+/uL|[A-Za-zµ]+/[A-Za-zµ]+)"
NUMBER_RE=r"[<>]?\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?"

def _clean_line(line):
    return re.sub(r"\s+"," ",line).strip(" :-|\t")

def _looks_like_test_name(name):
    name=_clean_line(name)
    if len(name)<2 or len(name)>80 or not re.search(r"[A-Za-z]",name): return False
    low=name.lower()
    blocked=("patient","patient id","patient code","name","age","sex","gender","mobile","phone",
             "whatsapp","address","sample","specimen","barcode","report","date","time","reference",
             "range","normal","result","unit","value","doctor","laboratory","diagnostic centre",
             "diagnostic center","collection","received","registration","referred","uhid","id number","associate","age / gender")
    return not any(re.search(r"\b"+re.escape(x)+r"\b",low) for x in blocked)

def _ocr_variants(path):
    if not pytesseract: return []
    img=Image.open(path).convert("L")
    w,h=img.size
    if max(w,h)<2400:
        img=img.resize((w*2,h*2),Image.Resampling.LANCZOS)
    from PIL import ImageOps,ImageFilter
    base=ImageOps.autocontrast(img)
    variants=[img,base,base.filter(ImageFilter.SHARPEN)]
    readings=[]
    for v in variants:
        for psm in (6,4,11):
            try: t=pytesseract.image_to_string(v,config=f"--psm {psm}")
            except Exception: t=""
            if t and t.strip(): readings.append(t)
    return readings

def _first_field(readings,patterns):
    candidates=[]
    for text in readings:
        for raw in text.splitlines():
            line=_clean_line(raw)
            if not line: continue
            for p in patterns:
                m=re.search(p,line,re.I)
                if m:
                    value=_clean_line(m.group(1))
                    if value: candidates.append(value)
    if not candidates: return ""
    labels=r"\b(?:age|sex|gender|mobile|phone|whatsapp|patient\s*(?:id|code)|uhid|referred\s*by|received\s*on|reported\s*on)\b"
    clean=[x for x in candidates if not re.search(labels,x,re.I)]
    return max(clean,key=lambda x:(len(x),len(x.split()))) if clean else max(candidates,key=len)

def _patient_fields(readings):
    fields={"name":[],"age":[],"sex":[],"phone":[],"code":[],"uhid":[],"referred_by":[],"received_on":[],"reported_on":[]}
    patterns={
      "name":[r"\bpatient\s*(?:name|nm)\s*[:#-]\s*(.+?)$",r"\bname\s*[:#-]\s*(.+?)$"],
      "age":[r"\bage\s*[/,:#-]?\s*(\d{1,3})(?:\s*(?:years?|yrs?))?\b"],
      "sex":[r"\b(?:sex|gender)\s*[/,:#-]?\s*(male|female|m|f)\b"],
      "phone":[r"\b(?:phone|mobile|mob|contact|whatsapp)\s*(?:no\.?|number)?\s*[:#-]?\s*(\+?\d[\d\s().-]{8,})"],
      "code":[r"\b(?:patient\s*(?:id|code)|patient\s*no\.?|id\s*number)\s*[:#-]?\s*([A-Za-z0-9_/-]{3,})\b"],
      "uhid":[r"\b(?:uhid|uhid\s*no\.?)\s*[:#-]?\s*([A-Za-z0-9_/-]{3,})\b"],
      "referred_by":[r"\b(?:referred\s*by|ref\.?\s*by|referrer)\s*[:#-]\s*(.+?)$"],
      "received_on":[r"\b(?:received\s*on|sample\s*(?:received|collection)\s*date)\s*[:#-]?\s*([0-9A-Za-z ./:-]{6,})$"],
      "reported_on":[r"\b(?:reported\s*on|report\s*date)\s*[:#-]?\s*([0-9A-Za-z ./:-]{6,})$"]
    }
    for text in readings:
        for raw in text.splitlines():
            line=_clean_line(raw)
            if not line: continue
            for key,ps in patterns.items():
                for p in ps:
                    m=re.search(p,line,re.I)
                    if m:
                        v=_clean_line(m.group(1))
                        if v and len(v)<120: fields[key].append(v)
    out={}
    for key,vals in fields.items():
        if not vals: out[key]=""; continue
        norm={}
        for v in vals:
            k=re.sub(r"[^a-z0-9]+","",v.lower())
            norm[k]=norm.get(k,0)+1
        out[key]=max(vals,key=lambda v:(norm[re.sub(r"[^a-z0-9]+","",v.lower())],len(v)))
    if out["name"]:
        out["name"]=re.sub(r"\s*(?:age|sex|gender|mobile|phone|uhid|patient\s*(?:id|code))\s*[:#-].*$","",out["name"],flags=re.I).strip(" :-")
    return out

def _parse_tests(readings):
    tests=[]; seen=set(); current_section="Examination Results"
    section_pattern=re.compile(
        r"^(physical|chemical|microscopical|microscopic|macroscopic|hematological|haematological|"
        r"biochemical|serological|urine|stool|blood|hormone|lipid|liver|kidney|renal|thyroid|"
        r"coagulation|immunology|cytology|clinical pathology)(?:\s+.{0,45})?$",re.I)
    skip=re.compile(r"^(department|report on|examination of|end of report|patient information|"
                    r"reference range|normal range)$",re.I)
    qualitative=r"(?:positive|negative|normal|reactive|non-reactive|nil|none|absent|present(?:\s*\([+-]\))?|"
                 r"not seen|brownish|yellowish|yellow|greenish|black|soft|formed|semi[- ]formed|acidic|alkaline)"
    for text in readings:
        for raw in text.splitlines():
            line=_clean_line(raw)
            if not line: continue
            line=re.sub(r"[|]+"," ",line).strip(" :-")
            normalized=re.sub(r"\s+"," ",line)
            if skip.match(normalized): continue
            if section_pattern.match(normalized) and not re.search(r"[:=]\s*",normalized):
                current_section=normalized.strip()
                continue
            patterns=[
                rf"^(.{{2,70}}?)\s*[:=]\s*({NUMBER_RE}|{qualitative}|[A-Za-z0-9][A-Za-z0-9 .()+/%_-]{{1,70}}?)\s*({UNIT_RE})?\s*$",
                rf"^(.{{2,70}}?)\s+({NUMBER_RE})\s+({UNIT_RE})\s*$",
            ]
            m=None
            for pat in patterns:
                m=re.match(pat,normalized,re.I)
                if m: break
            if not m:
                m=re.match(rf"^(.{{2,55}}?)\s+({qualitative})\s*$",normalized,re.I)
            if m:
                name=_clean_line(m.group(1)); value=_clean_line(m.group(2))
                unit=_clean_line(m.group(3) or "") if len(m.groups())>=3 else ""
                if _looks_like_test_name(name) and len(name.split())<=14:
                    key=(re.sub(r"[^a-z0-9]+","",name.lower()),value.lower(),unit.lower(),current_section.lower())
                    if key not in seen:
                        tests.append({"name":name,"value":value,"unit":unit,"section":current_section})
                        seen.add(key)
    return tests

def _extract_report_meta(readings):
    report={}
    for text in readings:
        for raw in text.splitlines():
            line=_clean_line(raw)
            m=re.match(r"^(?:department)\s*[:#-]\s*(.+)$",line,re.I)
            if not m: m=re.match(r"^(DEPARTMENT\s+OF\s+.+)$",line,re.I)
            if m and not report.get("department"): report["department"]=_clean_line(m.group(1))
            m=re.match(r"^(?:report(?:\s+title)?|examination)\s*[:#-]\s*(.+)$",line,re.I)
            if not m: m=re.match(r"^(REPORT\s+ON\s+.+)$",line,re.I)
            if m and not report.get("title"): report["title"]=_clean_line(m.group(1))
    return report

def extract(path):
    readings=_ocr_variants(path)
    combined="\n".join(readings)
    patient={
        **_patient_fields(readings),
    }
    if re.search(r"\b(?:age|sex|gender|mobile|phone|patient\s*(?:id|code)|uhid|referred|received|reported)\b",patient["name"],re.I):
        patient["name"]=""
    return combined,{"patient":patient,"tests":_parse_tests(readings),"report":_extract_report_meta(readings)}

def sha(data): return hashlib.sha256(data).hexdigest()
def notify(db,cid,rid,kind,msg): db.add(Notification(centre_id=cid,report_id=rid,kind=kind,message=msg))
def queue_wa(db,centre,report,kind,payload):
    if not centre.whatsapp_enabled or not report.patient_phone: return
    if db.query(WAJob).filter_by(report_id=report.id,kind=kind).first(): return
    db.add(WAJob(centre_id=centre.id,report_id=report.id,kind=kind,payload=json.dumps(payload)))

def make_pdf(centre,report,data,out):
    make_pdf_body_on_template(centre.template_path, data, out)

def report_dict(r):
    return {
        "id":r.id,"patient_name":r.patient_name,"patient_age":r.patient_age,
        "patient_sex":r.patient_sex,"patient_phone":r.patient_phone,"patient_code":r.patient_code,
        "status":r.status,"payment":r.payment,"charge":r.charge,"pdf_path":r.pdf_path,
        "verified_data":json.loads(r.verified_data or "{}"),"created_at":r.created_at.isoformat()
    }
