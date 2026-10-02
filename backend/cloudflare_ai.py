import base64,json,re
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image,ImageOps
try: import pymupdf
except Exception: pymupdf=None
from .config import CLOUDFLARE_ACCOUNT_ID,CLOUDFLARE_API_TOKEN,CLOUDFLARE_AI_MODEL,CLOUDFLARE_AI_TIMEOUT
URL="https://api.cloudflare.com/client/v4/accounts/{}/ai/run/{}"
SYSTEM="""You are Aarogyam laboratory document extraction AI. Read the supplied image pages visually and semantically. Extract only what is visible; never invent credentials, values, units or reference ranges. Input may be digital analyzer slips, scanned reports, handwritten notes or legacy reports. Understand tables, columns, labels and handwriting. Return ONLY JSON with patient_credentials, report and test_results. patient_credentials fields: name, age, gender, patient_id, uhid, referring_doctor, received_on, reported_on, phone. report fields: department,title,test_type. Each test_results item fields: test_name,result_value,unit,reference_range,section. Extract every visible result including qualitative Positive/Negative/Reactive/Nil/Present/Absent. Preserve questionable digits rather than guessing. Reference ranges must come from the document, never medical knowledge. If absent use empty string."""
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
                    pix=page.get_pixmap(matrix=pymupdf.Matrix(1.7,1.7),alpha=False); out.append(_img(Image.open(BytesIO(pix.tobytes("png")))))
            finally: d.close()
        elif ext in {".jpg",".jpeg",".png",".webp",".bmp",".tif",".tiff"}:
            with Image.open(path) as im: out.append(_img(im))
        else: raise ValueError("Unsupported document type. Upload an image or PDF.")
    return out
def _json(payload):
    r=payload.get("result") or {}; raw=""
    if isinstance(r,dict) and isinstance(r.get("response"),dict): return r["response"]
    if isinstance(r,dict) and isinstance(r.get("response"),str): raw=r["response"]
    elif isinstance(r,dict) and isinstance(r.get("choices"),list): raw=r["choices"][0].get("message",{}).get("content","") if r["choices"] else ""
    else: raw=r.get("text","") if isinstance(r,dict) else ""
    raw=str(raw).strip(); raw=re.sub(r"^```(?:json)?\s*","",raw,flags=re.I); raw=re.sub(r"\s*```$","",raw)
    try: return json.loads(raw)
    except Exception:
        a,b=raw.find("{"),raw.rfind("}");
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
def normalize(data):
    p=data.get("patient_credentials") or {}; h=data.get("report") or {}; tests=[]
    for x in data.get("test_results") or []:
        if not isinstance(x,dict): continue
        t={"name":_clean(x.get("test_name")),"value":_clean(x.get("result_value")),"unit":_clean(x.get("unit")),"reference_range":_clean(x.get("reference_range")),"section":_clean(x.get("section")) or "Examination Results"}
        if not t["name"] or not t["value"]: continue
        t["abnormal_status"]=abnormal(t["value"],t["reference_range"]); t["abnormal"]=t["abnormal_status"] in {"LOW","HIGH","ABNORMAL"}; tests.append(t)
    return {"patient":{"name":_clean(p.get("name")),"age":_clean(p.get("age")),"sex":_clean(p.get("gender")),"phone":_clean(p.get("phone")),"code":_clean(p.get("patient_id")),"uhid":_clean(p.get("uhid")),"referred_by":_clean(p.get("referring_doctor")),"received_on":_clean(p.get("received_on")),"reported_on":_clean(p.get("reported_on"))},"tests":tests,"report":{"department":_clean(h.get("department")),"title":_clean(h.get("title")),"test_type":_clean(h.get("test_type"))},"extraction_engine":"cloudflare_workers_ai","ai_schema_version":"1.0"}
def extract_with_cloudflare(paths):
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN: raise RuntimeError("Cloudflare AI is not configured. Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN.")
    body={"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":[{"type":"text","text":"Extract this entire laboratory document into the requested JSON. Combine all supplied pages. Do not invent missing data."}]+_parts(paths)}],"temperature":0,"max_tokens":6000}
    r=requests.post(URL.format(CLOUDFLARE_ACCOUNT_ID,CLOUDFLARE_AI_MODEL),headers={"Authorization":"Bearer "+CLOUDFLARE_API_TOKEN,"Content-Type":"application/json"},json=body,timeout=CLOUDFLARE_AI_TIMEOUT)
    if r.status_code>=400: raise RuntimeError("Cloudflare AI request failed ("+str(r.status_code)+"): "+r.text[:600])
    payload=r.json()
    if not payload.get("success",True): raise RuntimeError("Cloudflare AI request failed: "+str(payload.get("errors")))
    return normalize(_json(payload))