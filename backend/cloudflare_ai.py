import base64,json,re
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image,ImageOps
try: import pymupdf
except Exception: pymupdf=None
from .config import CLOUDFLARE_ACCOUNT_ID,CLOUDFLARE_API_TOKEN,CLOUDFLARE_AI_MODEL,CLOUDFLARE_AI_TIMEOUT

URL="https://api.cloudflare.com/client/v4/accounts/{}/ai/run/{}"
REFERENCE_FILE=Path(__file__).resolve().parent/"data"/"medical_tests.json"

SYSTEM="""You are Aarogyam clinical document understanding AI. Your primary task is to understand the visual information in the supplied image/document, regardless of its source or format. It may be a laboratory slip, analyzer display photo, computer-screen screenshot, WhatsApp screenshot, photograph of a printed report, scanned report, handwritten report, PDF page, pathology/histopathology report, microbiology report, urine/stool examination, blood grouping document, referral note, or another clinical report. Do not classify the source before extracting it; understand the actual visible data and its meaning. Extract only what is visible; never invent credentials, values, units, reference ranges, methods or comments. Understand tables, columns, labels, handwriting, screenshots, photographs, mixed layouts and narrative paragraphs.

Return ONLY JSON with:
patient_credentials: name, age, gender, patient_id, uhid, referring_doctor, received_on, reported_on, phone.
report: department, title, test_type.
result_sections: an array of sections. Each section has section and items. Each item has name and value, with optional unit, reference_range, flag, method, comment, result_type.

Use result_type as quantitative, qualitative, observation, narrative or special when the document clearly supports that interpretation. Unit and reference_range are OPTIONAL and must be empty/omitted when not visible. Never discard a clinically relevant result because it has no unit or reference range. Preserve Positive/Negative/Reactive/Nil/Present/Absent, descriptive observations, culture organisms/sensitivity, blood group, and narrative findings. For narrative reports, preserve the meaningful text under an appropriate item/section rather than inventing a numeric result.

Reference ranges must come from the document, never medical knowledge. Extract every visible clinically relevant result, BUT EXCLUDE NON-CLINICAL OPERATIONAL/MACHINE METADATA. Never return analyzer operational lines such as CALIBRATION STATUS, CALIBRATION, QC, QUALITY CONTROL, reagent lot/batch/expiry information, cuvette lot/batch information, cartridge/kit lot numbers, machine/instrument/device status, maintenance/service messages, printer/device diagnostics, internal run IDs, barcode/QR text, rack/position/cuvette identifiers, or similar instrument-control text. A line is not a clinical result merely because it contains a number. Only return a test parameter when it represents a patient clinical measurement, qualitative observation, or narrative clinical finding. Preserve questionable clinical digits rather than guessing. Unknown or uncommon clinical tests must be returned exactly as seen; do not reject them because they are absent from any reference list."""
def _img(img):
    img=ImageOps.exif_transpose(img).convert("RGB"); m=1800
    if max(img.size)>m:
        s=m/max(img.size); img=img.resize((max(1,int(img.width*s)),max(1,int(img.height*s))),Image.Resampling.LANCZOS)
    b=BytesIO(); img.save(b,"JPEG",quality=84,optimize=True)
    return {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(b.getvalue()).decode()}}
def _parts(paths):
    out=[]
    for path in paths:
        p=Path(path); ext=p.suffix.lower()
        if ext==".pdf":
            if not pymupdf: raise RuntimeError("PyMuPDF is required for PDF extraction")
            d=pymupdf.open(path)
            try:
                for i,page in enumerate(d):
                    if i>=8: break
                    pix=page.get_pixmap(matrix=pymupdf.Matrix(1.7,1.7),alpha=False)
                    out.append(_img(Image.open(BytesIO(pix.tobytes("png")))))
            finally: d.close()
        elif ext in {".jpg",".jpeg",".png",".webp",".bmp",".tif",".tiff"}:
            with Image.open(path) as im: out.append(_img(im))
        else: raise ValueError("Unsupported document type. Upload an image or PDF.")
    return out
def _json(payload):
    r=payload.get("result") or {}; raw=""
    if isinstance(r,dict) and isinstance(r.get("response"),dict): return r["response"]
    if isinstance(r,dict) and isinstance(r.get("response"),str): raw=r["response"]
    elif isinstance(r,dict) and isinstance(r.get("choices"),list):
        raw=r["choices"][0].get("message",{}).get("content","") if r["choices"] else ""
    else: raw=r.get("text","") if isinstance(r,dict) else ""
    raw=str(raw).strip()
    raw=re.sub(r"^\`\`\`(?:json)?\s*","",raw,flags=re.I)
    raw=re.sub(r"\s*\`\`\`$","",raw)
    try: return json.loads(raw)
    except Exception:
        a,b=raw.find("{"),raw.rfind("}")
        if a>=0 and b>a: return json.loads(raw[a:b+1])
        raise ValueError("Cloudflare AI returned invalid JSON")
def _clean(v): return str(v or "").strip()
def _num(v):
    m=re.search(r"[<>]?\s*(-?\d+(?:\.\d+)?)",_clean(v).replace(",",".")); return float(m.group(1)) if m else None
def abnormal(value,ref):
    v,r=_clean(value).lower(),_clean(ref).lower()
    if not v or not r: return "UNKNOWN"
    pos={"positive","reactive","present","detected"}; neg={"negative","non-reactive","nonreactive","absent","not detected","nil","none","normal"}
    if (v in pos and r in neg) or (v in neg and r in pos): return "ABNORMAL"
    if (v in pos and r in pos) or (v in neg and r in neg): return "NORMAL"
    n=_num(v)
    if n is None: return "UNKNOWN"
    m=re.fullmatch(r"\s*(<=|>=|<|>)?\s*(-?\d+(?:\.\d+)?)\s*",r.replace(",",".")) 
    if m:
        op,x=m.group(1),float(m.group(2))
        if op=="<" and n>=x or op=="<=" and n>x: return "HIGH"
        if op==">" and n<=x or op==">=" and n<x: return "LOW"
        return "NORMAL"
    ns=re.findall(r"-?\d+(?:[.,]\d+)?",r)
    if len(ns)>=2:
        lo,hi=sorted(float(x.replace(",",".")) for x in ns[:2])
        return "LOW" if n<lo else "HIGH" if n>hi else "NORMAL"
    return "UNKNOWN"

def _reference():
    try:
        raw=json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))
        aliases={}
        for item in raw.get("tests",[]):
            canonical=_clean(item.get("name"))
            if not canonical: continue
            meta={"name":canonical,"section":_clean(item.get("section")),"result_type":_clean(item.get("type"))}
            for alias in [canonical]+list(item.get("aliases") or []):
                key=re.sub(r"[^a-z0-9]+","",_clean(alias).lower())
                if key: aliases[key]=meta
        return aliases
    except Exception:
        return {}
TEST_REFERENCE=_reference()

OPERATIONAL_METADATA_RE = re.compile(r"(?:^|\b)(?:calibration(?:\s+status|\s+ok)?|qc(?:\s+(?:status|passed|pass|ok|failed|fail))?|quality\s+control(?:\s+(?:status|passed|pass|ok|failed|fail))?|reagent(?:\s+(?:lot|batch|expiry|expiration|exp))?|cuvette(?:\s+(?:lot|batch|id))?|cartridge(?:\s+(?:lot|batch|id))?|kit(?:\s+(?:lot|batch|id))?|machine(?:\s+status)?|instrument(?:\s+status)?|device(?:\s+(?:status|diagnostic))?|maintenance|service(?:\s+(?:mode|status))?|barcode|bar\s*code|qr(?:\s*code)?|run(?:\s+id)?|rack(?:\s+(?:no|number|id))?|position(?:\s+(?:no|number|id))?)(?:\b|\s*[:#=-])",re.I)
def _is_operational_metadata(name,value=""):
    n=_clean(name); v=_clean(value)
    if not n: return True
    if OPERATIONAL_METADATA_RE.search(n) or OPERATIONAL_METADATA_RE.search((n+" "+v)[:240]): return True
    compact=re.sub(r"[^A-Za-z0-9]","",n)
    if compact and len(compact)>=8 and re.fullmatch(r"[A-Za-z0-9]+",compact) and re.search(r"\d",compact) and re.search(r"[A-Za-z]",compact) and not re.search(r"\s",n): return True
    return False

def _canonicalize(name):
    clean=re.sub(r"\s+"," ",_clean(name)).strip(" :-|")
    key=re.sub(r"[^a-z0-9]+","",clean.lower())
    meta=TEST_REFERENCE.get(key)
    return (meta["name"],meta) if meta else (clean,{})

def _iter_results(data):
    sections=data.get("result_sections")
    if isinstance(sections,list):
        for sec in sections:
            if not isinstance(sec,dict): continue
            section=_clean(sec.get("section")) or "Examination Results"
            for item in sec.get("items") or []:
                if isinstance(item,dict):
                    yield section,item
    for item in data.get("test_results") or []:
        if isinstance(item,dict):
            yield(_clean(item.get("section")) or "Examination Results"),item

def normalize(data):
    p=data.get("patient_credentials") or {}
    h=data.get("report") or {}
    tests=[]
    sections={}
    order=[]
    for section,x in _iter_results(data):
        raw_name=x.get("name") if "name" in x else x.get("test_name")
        raw_value=x.get("value") if "value" in x else x.get("result_value")
        name,meta=_canonicalize(raw_name)
        value=_clean(raw_value)
        if not name or not value: continue
        if _is_operational_metadata(name,value): continue
        section=_clean(section) or meta.get("section") or "Examination Results"
        if section=="Examination Results" and meta.get("section"): section=meta["section"]
        t={
            "name":name,
            "value":value,
            "unit":_clean(x.get("unit")),
            "reference_range":_clean(x.get("reference_range")),
            "section":section,
            "result_type":_clean(x.get("result_type")) or meta.get("result_type") or "observation",
        }
        for key in ("flag","method","comment"):
            val=_clean(x.get(key))
            if val: t[key]=val
        t["abnormal_status"]=abnormal(t["value"],t["reference_range"])
        t["abnormal"]=t["abnormal_status"] in {"LOW","HIGH","ABNORMAL"}
        tests.append(t)
        if section not in sections:
            sections[section]=[]; order.append(section)
        sections[section].append({k:v for k,v in t.items() if k not in {"section","abnormal_status","abnormal"}})

    result_sections=[{"section":s,"items":sections[s]} for s in order]
    return {
        "patient":{
            "name":_clean(p.get("name")),"age":_clean(p.get("age")),"sex":_clean(p.get("gender")),
            "phone":_clean(p.get("phone")),"code":_clean(p.get("patient_id")),"uhid":_clean(p.get("uhid")),
            "referred_by":_clean(p.get("referring_doctor")),"received_on":_clean(p.get("received_on")),"reported_on":_clean(p.get("reported_on"))
        },
        "tests":tests,
        "result_sections":result_sections,
        "report":{"department":_clean(h.get("department")),"title":_clean(h.get("title")),"test_type":_clean(h.get("test_type"))},
        "extraction_engine":"cloudflare_workers_ai",
        "ai_schema_version":"2.0"
    }

def extract_with_cloudflare(paths):
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise RuntimeError("Cloudflare AI is not configured. Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN.")
    body={"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":[{"type":"text","text":"Understand and extract the complete supplied clinical image/document into the requested JSON. The source may be any image, screenshot, photograph, scanned/printed report, analyzer display, WhatsApp image, or PDF page. Combine all supplied pages/images when there are multiple inputs. Do not invent missing data."}]+_parts(paths)}],"temperature":0,"max_tokens":6000,"chat_template_kwargs":{"enable_thinking":False}}
    r=requests.post(URL.format(CLOUDFLARE_ACCOUNT_ID,CLOUDFLARE_AI_MODEL),headers={"Authorization":"Bearer "+CLOUDFLARE_API_TOKEN,"Content-Type":"application/json","User-Agent":"Aarogyam/1.0"},json=body,timeout=CLOUDFLARE_AI_TIMEOUT)
    if r.status_code>=400: raise RuntimeError("Cloudflare AI request failed ("+str(r.status_code)+"): "+r.text[:600])
    payload=r.json()
    if not payload.get("success",True): raise RuntimeError("Cloudflare AI request failed: "+str(payload.get("errors")))
    return normalize(_json(payload))
