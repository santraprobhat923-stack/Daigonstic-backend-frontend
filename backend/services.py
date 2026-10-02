import base64,hashlib,json,re,secrets,shutil,subprocess
from difflib import SequenceMatcher
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
    # Reject OCR debris that can otherwise look like a short test name.
    if "\\" in name or re.fullmatch(r"[IVXLCDM]+",name,re.I):
        return False
    low=name.lower()
    blocked=("patient","patient id","patient code","name","age","sex","gender","mobile","phone",
             "whatsapp","address","sample","specimen","barcode","report","date","time","reference",
             "range","normal","result","unit","value","doctor","laboratory","diagnostic centre",
             "diagnostic center","collection","received","registration","referred","uhid","id number","associate","age / gender")
    return not any(re.search(r"\b"+re.escape(x)+r"\b",low) for x in blocked)

def _ocr_variants(path):
    """Run several OCR passes and preserve approximate line/column layout.

    Raw OCR text is useful for labels, while image_to_data() gives word
    positions that let us reconstruct thermal-printer rows without assuming
    a particular analyzer or report template.
    """
    if not pytesseract: return []
    img=Image.open(path).convert("L")
    w,h=img.size
    if max(w,h)<2400:
        img=img.resize((w*2,h*2),Image.Resampling.LANCZOS)
    from PIL import ImageOps,ImageFilter
    base=ImageOps.autocontrast(img)
    variants=[
        img,
        base,
        base.filter(ImageFilter.SHARPEN),
    ]
    readings=[]
    for v in variants:
        for psm in (6,4,11):
            try:
                raw=pytesseract.image_to_string(v,config=f"--psm {psm}")
            except Exception:
                raw=""
            if raw and raw.strip():
                readings.append(raw)

            # Preserve positional information. Thermal slips often lose
            # columns when converted to plain OCR text.
            try:
                data=pytesseract.image_to_data(
                    v,
                    config=f"--psm {psm}",
                    output_type=pytesseract.Output.DICT,
                )
                rows={}
                n=len(data.get("text",[]))
                for i in range(n):
                    word=(data["text"][i] or "").strip()
                    try: conf=float(data["conf"][i])
                    except Exception: conf=-1
                    if not word or conf < 0:
                        continue
                    key=(
                        data["block_num"][i],
                        data["par_num"][i],
                        data["line_num"][i],
                    )
                    rows.setdefault(key,[]).append((
                        int(data["left"][i]),
                        int(data["top"][i]),
                        word,
                    ))
                ordered=[]
                for words in rows.values():
                    words.sort(key=lambda x:x[0])
                    ordered.append(words)
                ordered.sort(key=lambda row:(row[0][1],row[0][0]))
                layout_lines=[]
                for words in ordered:
                    parts=[]
                    prev_right=None
                    for left,top,word in words:
                        if prev_right is not None:
                            gap=left-prev_right
                            # A large horizontal gap is probably a column
                            # boundary. Keep it visible for the parser.
                            parts.append("|" if gap >= 45 else " ")
                        parts.append(word)
                        prev_right=left+max(8,len(word)*8)
                    line="".join(parts).strip()
                    if line:
                        layout_lines.append(line)
                if layout_lines:
                    readings.append("\n".join(layout_lines))
            except Exception:
                pass
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
    """Recover labelled patient/header fields, including values on the next OCR line."""
    fields={k:[] for k in ("name","age","sex","phone","code","uhid","referred_by","received_on","reported_on")}
    patterns={
      "name":[r"\bpatient\s*(?:name|nm)?\s*[:#=-]?\s*(.+)$",r"^name\s*[:#=-]?\s*(.+)$",r"^patient\s+([A-Za-z][A-Za-z .,'-]{1,80})$"],
      "age":[r"\bage\s*[/,:#=-]?\s*(\d{1,3})(?:\s*(?:years?|yrs?))?\b"],
      "sex":[r"\b(?:sex|gender)\s*[/,:#=-]?\s*(male|female|m|f)\b"],
      "phone":[r"\b(?:phone|mobile|mob|contact|whatsapp)\s*(?:no\.?|number)?\s*[:#=-]?\s*(\+?\d[\d\s().-]{8,})"],
      "code":[r"\b(?:patient\s*(?:id|code|no\.?)|sample\s*(?:id|no\.?|number)|specimen\s*(?:id|no\.?|number)|accession\s*(?:id|no\.?|number)|lab\s*(?:id|no\.?)|id)\s*[:#=-]?\s*([A-Za-z0-9_./-]{2,})\b"],
      "uhid":[r"\b(?:uhid|uhid\s*no\.?)\s*[:#=-]?\s*([A-Za-z0-9_./-]{2,})\b"],
      "referred_by":[r"\b(?:referred\s*by|ref\.?\s*by|referrer)\s*[:#=-]?\s*(.+)$"],
      "received_on":[r"\b(?:received\s*on|sample\s*(?:received|collection)\s*(?:date|on)?|collection\s*date)\s*[:#=-]?\s*([0-9A-Za-z ./:-]{6,})$"],
      "reported_on":[r"\b(?:reported\s*on|report\s*date)\s*[:#=-]?\s*([0-9A-Za-z ./:-]{6,})$"]
    }
    lines=[]
    for reading in readings:
        for raw in reading.splitlines():
            line=_clean_line(raw)
            if line: lines.append(line)

    for i,line in enumerate(lines):
        for key,ps in patterns.items():
            for p in ps:
                m=re.search(p,line,re.I)
                if m:
                    v=_clean_line(m.group(1))
                    if v and len(v)<120: fields[key].append(v)
        # Handle a label occupying one OCR line and its value the next line.
        if i+1<len(lines):
            nxt=lines[i+1]
            if re.fullmatch(r"(?:patient\s*)?(?:name|nm)\s*[:#=-]?",line,re.I) and re.fullmatch(r"[A-Za-z][A-Za-z .,'-]{1,80}",nxt):
                fields["name"].append(nxt)
            if re.fullmatch(r"(?:age)\s*[:#=-]?",line,re.I) and re.fullmatch(r"\d{1,3}",nxt):
                fields["age"].append(nxt)
            if re.fullmatch(r"(?:sex|gender)\s*[:#=-]?",line,re.I) and re.fullmatch(r"(?:male|female|m|f)",nxt,re.I):
                fields["sex"].append(nxt)
            if re.fullmatch(r"(?:mobile|mob|phone|contact|whatsapp)\s*(?:no\.?|number)?\s*[:#=-]?",line,re.I) and re.fullmatch(r"\+?\d[\d\s().-]{8,}",nxt):
                fields["phone"].append(nxt)
            if re.fullmatch(r"(?:patient\s*(?:id|code|no\.?)|sample\s*(?:id|no\.?|number)|specimen\s*(?:id|no\.?|number)|accession\s*(?:id|no\.?|number)|lab\s*(?:id|no\.?)|uhid)\s*[:#=-]?",line,re.I) and re.fullmatch(r"[A-Za-z0-9_./-]{2,}",nxt):
                fields["code" if "uhid" not in line.lower() else "uhid"].append(nxt)
            if re.fullmatch(r"(?:referred\s*by|ref\.?\s*by|referrer)\s*[:#=-]?",line,re.I) and re.fullmatch(r"[A-Za-z][A-Za-z .,'-]{1,80}",nxt):
                fields["referred_by"].append(nxt)

    out={}
    for key,vals in fields.items():
        if not vals: out[key]=""; continue
        counts={}
        for v in vals:
            k=re.sub(r"[^a-z0-9]+","",v.lower()); counts[k]=counts.get(k,0)+1
        out[key]=max(vals,key=lambda v:(counts[re.sub(r"[^a-z0-9]+","",v.lower())],len(v)))
    return out

def _parse_tests(readings):
    """Format-agnostic clinical result parser with layout recovery.

    The parser treats OCR as noisy evidence rather than clean columns. It
    accepts positional rows, conventional one-line rows, and partial rows;
    then normalizes units, removes instrument metadata, merges duplicates,
    and keeps uncertain fields editable by the technician.
    """
    tests=[]
    current_section="Examination Results"
    scalar=r"[<>]?\d+(?:[.,]\d+)?"
    range_re=rf"[<>]?\d+(?:[.,]\d+)?(?:\s*[-–]\s*[<>]?\d+(?:[.,]\d+)?)?"
    qualitative=(r"(?:positive|negative|normal|reactive|non-reactive|nil|none|absent|present(?:\s*"
                 r"\([+-]\))?|not seen|brownish|yellowish|yellow|greenish|black|soft|formed|"
                 r"semi[- ]formed|acidic|alkaline)")
    unit_re=UNIT_RE
    metadata=re.compile(
        r"^(?:calibration(?:\s+status)?|qc|quality\s+control|reagent\s+lot|reagent\s+no|"
        r"cuvette\s+lot|cuvette\s+no|serial\s+(?:no|number)?|instrument|analyzer|"
        r"machine\s+(?:id|no|number)?|lot\s+(?:no|number)?|control|operator|"
        r"reference\s+range|normal\s+range|method|run\s*(?:no|number)|run)$",re.I)
    headerish=re.compile(
        r"^(?:test|tests|investigation|investigations|examination|parameter|"
        r"result|results|value|unit|units|reference|range|remarks?)$",re.I)
    section_pattern=re.compile(
        r"^(?:physical|chemical|microscopical|microscopic|macroscopic|hematological|haematological|"
        r"biochemical|serological|urine|stool|blood|hormone|lipid|liver|kidney|renal|thyroid|"
        r"coagulation|immunology|cytology|clinical pathology)(?:\s+.{0,45})?$",re.I)

    def norm_unit(unit):
        unit=_clean_line(unit)
        if not unit: return ""
        u=unit.replace("µ","u").strip()
        if re.search(r"mg\s*/\s*d[lI1]|\bmgd[lI1]\b|\bma\s*/\s*dl\b|\bmg\b",u,re.I):
            return "mg/dL"
        if re.search(r"g\s*/\s*d[lI1]|\bgm\s*/\s*dl\b|\bgml\b",u,re.I):
            return "g/dL"
        if re.search(r"m?iu\s*/\s*l",u,re.I):
            return "mIU/L"
        if re.search(r"uiu\s*/\s*ml",u,re.I):
            return "uIU/mL"
        return re.sub(r"\s+"," ",u).strip()

    def normalize_name(name):
        name=_clean_line(name).strip(" :-|")
        name=re.sub(r"\s+"," ",name)
        # Remove obvious OCR column debris from the end, but preserve
        # meaningful alphanumeric test names such as T3/T4.
        name=re.sub(r"\s+(?:[|IiLl1]{1,3}|[A-Za-z]\s*[:;]?[<>]\s*)$","",name)
        name=re.sub(r"\s+\d{1,2}$","",name)
        return name.strip()

    def add_test(name,value,unit="",reference="",section=None):
        name=normalize_name(name)
        value=_clean_line(value)
        # Remove result/column bleed from the test name. Keep compact names
        # such as T3, T4 and B12 intact; only remove a separated numeric tail.
        name=re.sub(r"\s+\d+(?:[.,]\d+)?(?:\s+.*)?$","",name).strip(" :-|")
        unit=norm_unit(unit)
        reference=_clean_line(reference)
        if not _looks_like_test_name(name) or len(name.split())>14:
            return False
        if len(name.split())>5:
            return False
        if metadata.match(name) or headerish.match(name):
            return False
        # A test name should not contain an entire result/unit column.
        if re.search(unit_re,name,re.I) and re.search(r"\d",name):
            # Keep the portion before the first result-like token.
            m=re.search(rf"\s+{scalar}(?:\s+|$)",name,re.I)
            if m:
                name=name[:m.start()].strip()
        if not name or not _looks_like_test_name(name):
            return False
        if re.fullmatch(r"[<>]\s*\d+(?:[.,]\d+)?",value) and not unit and not reference:
            return False
        tests.append({
            "name":name,
            "value":value,
            "unit":unit,
            "reference_range":reference,
            "section":section or current_section
        })
        return True

    def parse_remainder(rest):
        rest=_clean_line(rest).strip(" |,:;-")
        if not rest:
            return "", ""
        reference=""
        # Normalize a few OCR forms of inequality symbols before matching.
        ref=re.search(r"(?:^|\s)(?:[HLN]|FLAG)?\s*:?\s*([<>]?\d+(?:[.,]\d+)?(?:\s*[-–]\s*[<>]?\d+(?:[.,]\d+)?)?)\s*$",rest,re.I)
        if ref:
            reference=ref.group(1).replace(" ","")
            rest=rest[:ref.start()].strip(" |,:;-")
        unit=""
        um=re.search(unit_re,rest,re.I)
        if um:
            unit=um.group(0)
            rest=(rest[:um.start()]+" "+rest[um.end():]).strip(" |,:;-")
        # Some OCR passes return junk after a valid unit. Ignore that junk;
        # the clinical result itself remains usable for verification.
        return norm_unit(unit),reference

    for text in readings:
        for raw in text.splitlines():
            line=_clean_line(raw)
            if not line: continue
            line=line.replace("¦","|")
            line=re.sub(r"\s+"," ",line).strip(" :-")
            if not line: continue

            if section_pattern.match(line) and not re.search(r"[:=]",line):
                current_section=line
                continue
            if metadata.match(line):
                continue
            if headerish.match(line):
                continue

            # Layout-aware row: TEST | RESULT | UNIT | REFERENCE
            cols=[_clean_line(x) for x in line.split("|") if _clean_line(x)]
            if len(cols)>=2:
                result_idx=None
                for i,c in enumerate(cols[1:],1):
                    if re.fullmatch(rf"({scalar}|{qualitative})",c,re.I):
                        result_idx=i
                        break
                if result_idx is not None:
                    name=cols[0]
                    result=cols[result_idx]
                    unit=""
                    reference=""
                    for c in cols[result_idx+1:]:
                        refc=re.sub(r"^(?:[HLN]|L:|H:|N:|FLAG:?)\s*[:=-]?\s*", "", c, flags=re.I)
                        if not reference and re.fullmatch(range_re,refc,re.I):
                            reference=refc.replace(" ","")
                        elif not unit:
                            unit=norm_unit(c)
                    if add_test(name,result,unit,reference):
                        continue

            # Standalone reference range.
            ref_only=re.match(
                rf"^(?:reference(?:\s+range)?|normal(?:\s+range)?|ref\.?)"
                rf"\s*[:=-]\s*({range_re})$",line,re.I)
            if ref_only and tests:
                tests[-1]["reference_range"]=ref_only.group(1)
                continue

            # Clean conventional rows first.
            patterns=[
                rf"^(.{{2,80}}?)\s*[:=]\s*({scalar}|{qualitative})\s+({unit_re})(?:\s+({range_re}))?$",
                rf"^(.{{2,80}}?)\s+({scalar}|{qualitative})\s+({unit_re})\s+({range_re})$",
                rf"^(.{{2,80}}?)\s+({scalar}|{qualitative})\s+({range_re})\s+({unit_re})$",
                rf"^(.{{2,80}}?)\s*[:=]\s*({scalar}|{qualitative})(?:\s+({unit_re}))?$",
                rf"^(.{{2,80}}?)\s+({scalar}|{qualitative})\s+({unit_re})$",
                rf"^(.{{2,80}}?)\s+({scalar}|{qualitative})$",
            ]
            matched=False
            for idx,p in enumerate(patterns):
                m=re.match(p,line,re.I)
                if not m: continue
                if len(m.groups())==4:
                    add_test(m.group(1),m.group(2),m.group(3),m.group(4) or "")
                elif len(m.groups())==3:
                    add_test(m.group(1),m.group(2),m.group(3) or "")
                else:
                    add_test(m.group(1),m.group(2))
                matched=True
                break
            if matched:
                continue

            # Recovery path: if OCR inserted garbage after a numeric result,
            # still recover TEST + RESULT + any recognizable unit/reference.
            m=re.match(rf"^(.{{2,70}}?)\s+({scalar}|{qualitative})\s+(.+)$",line,re.I)
            if m:
                name=m.group(1)
                result=m.group(2)
                unit,reference=parse_remainder(m.group(3))
                add_test(name,result,unit,reference)

    # Normalize analyzer flag prefixes that may survive OCR parsing.
    for t in tests:
        rr=_clean_line(t.get("reference_range",""))
        rr=re.sub(r"^(?:[HLN]|FLAG)\s*:\s*", "", rr, flags=re.I)
        t["reference_range"]=rr.replace(" ","")

    # Merge OCR variants by normalized test name. Prefer the candidate
    # with a clean numeric result, recognizable unit and reference range.
    def quality(t):
        q=0
        n=t["name"]; v=t["value"]; u=t["unit"]; r=t["reference_range"]
        if re.fullmatch(r"[<>]?\d+(?:[.,]\d+)?",v): q+=3
        if r and re.fullmatch(r"[<>]?\d+(?:[.,]\d+)?(?:\s*[-–]\s*[<>]?\d+(?:[.,]\d+)?)?",r): q+=2
        if u in ("mg/dL","g/dL","mIU/L","uIU/mL","U/L","IU/L","IU/mL","fL","pg","sec","mmHg","%","/HPF","/hpf"): q+=2
        if u and u not in ("mg/dL","g/dL","mIU/L","uIU/mL","U/L","IU/L","IU/mL","fL","pg","sec","mmHg","%","/HPF","/hpf") and not re.search(r"/",u):
            q-=1
        if re.search(r"\s+\d+(?:[.,]\d+)?(?:\s|$)",n): q-=5
        if re.search(r"[‘’“”]",n): q-=3
        if len(n.split())>8: q-=2
        return q
    merged=[]
    for t in tests:
        tn=re.sub(r"[^a-z0-9]+","",t["name"].lower())
        found=None
        for existing in merged:
            en=re.sub(r"[^a-z0-9]+","",existing["name"].lower())
            if tn==en or (len(tn)>=4 and SequenceMatcher(None,tn,en).ratio()>=0.88):
                found=existing
                break
        if found:
            if quality(t)>quality(found):
                winner,other=t,found
            else:
                winner,other=found,t
            if not winner["unit"] and other["unit"]: winner["unit"]=other["unit"]
            if not winner["reference_range"] and other["reference_range"]:
                winner["reference_range"]=other["reference_range"]
            found.update(winner)
        else:
            merged.append(t)
    return merged

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

def _pdfme_input_value(schema, data):
    """Map verified report data onto a saved pdfme schema without changing geometry."""
    patient=data.get("patient") or {}
    report=data.get("report") or {}
    key=str(schema.get("name") or "").strip().lower()
    compact=re.sub(r"[^a-z0-9]+","_",key).strip("_")

    def age_gender():
        age=str(patient.get("age") or "").strip()
        sex=str(patient.get("sex") or "").strip()
        return " / ".join(x for x in (age, sex.upper()) if x)

    values={
        "patient_name":str(patient.get("name") or ""),
        "patient_age":str(patient.get("age") or ""),
        "patient_sex":str(patient.get("sex") or ""),
        "patient_gender":str(patient.get("sex") or ""),
        "patient_age_gender":age_gender(),
        "patient_id":str(patient.get("code") or ""),
        "patient_code":str(patient.get("code") or ""),
        "patient_uhid":str(patient.get("uhid") or ""),
        "patient_referred_by":str(patient.get("referred_by") or ""),
        "patient_received_on":str(patient.get("received_on") or ""),
        "patient_reported_on":str(patient.get("reported_on") or ""),
        "patient_phone":str(patient.get("phone") or ""),
        "report_date":str(patient.get("reported_on") or ""),
        "department":str(report.get("department") or ""),
        "report_department":str(report.get("department") or ""),
        "report_title":str(report.get("title") or ""),
        "title":str(report.get("title") or ""),
    }

    if compact in values:
        value=values[compact]
        # The starter template uses the schema content as the field label.
        # Keep that label inline so the saved schema remains the visual source
        # of truth while the value becomes dynamic.
        if schema.get("type") == "text" and str(schema.get("content") or "").strip():
            label=str(schema.get("content") or "").strip()
            if label and label.lower() != value.lower():
                return f"{label} : {value}" if value else label
        return value

    if compact in {"results_table","result_table","laboratory_results","examination_results","tests_table"}:
        return json.dumps(_pdfme_result_matrix(data))

    content=str(schema.get("content") or "")
    # Support simple explicit placeholders in text schemas while preserving
    # every other saved character and property.
    replacements={
        "{{patient.name}}":str(patient.get("name") or ""),
        "{{patient.age}}":str(patient.get("age") or ""),
        "{{patient.sex}}":str(patient.get("sex") or ""),
        "{{patient.phone}}":str(patient.get("phone") or ""),
        "{{patient.id}}":str(patient.get("code") or ""),
        "{{patient.code}}":str(patient.get("code") or ""),
        "{{patient.uhid}}":str(patient.get("uhid") or ""),
        "{{patient.referred_by}}":str(patient.get("referred_by") or ""),
        "{{patient.received_on}}":str(patient.get("received_on") or ""),
        "{{patient.reported_on}}":str(patient.get("reported_on") or ""),
        "{{report.department}}":str(report.get("department") or ""),
        "{{report.title}}":str(report.get("title") or ""),
    }
    for token,value in replacements.items():
        content=content.replace(token,value)
    return content


def _pdfme_result_matrix(data):
    rows=data.get("tests") or []
    matrix=[["TEST","RESULT","UNIT","REFERENCE"]]
    for row in rows:
        matrix.append([
            str(row.get("name") or ""),
            str(row.get("value") or ""),
            str(row.get("unit") or ""),
            str(row.get("reference_range") or ""),
        ])
    return matrix


def _render_pdfme(centre, data, out, pdfme_template):
    if not centre.template_path or not Path(centre.template_path).exists():
        raise ValueError("PDFMe master template requires an uploaded centre PDF letterhead")

    node=shutil.which("node")
    if not node:
        raise RuntimeError("PDFMe server renderer is not installed: Node.js is required on the server")

    base_bytes=Path(centre.template_path).read_bytes()
    base_b64=base64.b64encode(base_bytes).decode("ascii")

    # pdfme's saved schema coordinates are already in millimetres. Do not
    # convert, clamp, scale, reflow, or otherwise reinterpret them.
    schemas=pdfme_template.get("schemas") or []
    inputs=[]
    for page_schemas in schemas:
        page_input={}
        for schema in page_schemas or []:
            name=str(schema.get("name") or "")
            if not name:
                continue
            page_input[name]=_pdfme_input_value(schema,data)
        inputs.append(page_input)

    if not inputs:
        inputs=[{}]

    job={
        "template":{"schemas":schemas},
        "basePdf":base_b64,
        "inputs":inputs,
        "output":str(out),
    }

    root=Path(__file__).resolve().parent.parent
    runtime=root/"pdfme"
    result=subprocess.run(
        [node,str(runtime/"render.mjs")],
        input=json.dumps(job),
        text=True,
        capture_output=True,
        timeout=90,
    )
    if result.returncode != 0:
        detail=(result.stderr or result.stdout or "PDFMe generation failed").strip()
        raise RuntimeError(f"PDFMe generation failed: {detail[-1200:]}")


def make_pdf(centre,report,data,out):
    """Generate the report through Aarogyam's custom ReportLab renderer.

    The current product uses the lightweight custom Report Design editor.
    Saved layout coordinates are rendered by report_renderer.py; no PDFMe or
    Node.js runtime is involved in report approval.
    """
    try:
        layout=json.loads(centre.report_layout or "{}")
    except Exception:
        layout={}

    # The custom renderer is the single authoritative report-generation path.
    # Never route approval through legacy PDFMe data, even if an old layout
    # record still contains a stale pdfme_template key.
    make_pdf_body_on_template(centre.template_path, data, out, layout)

def report_dict(r):
    return {
        "id":r.id,"patient_name":r.patient_name,"patient_age":r.patient_age,
        "patient_sex":r.patient_sex,"patient_phone":r.patient_phone,"patient_code":r.patient_code,
        "status":r.status,"payment":r.payment,"charge":r.charge,"pdf_path":r.pdf_path,
        "verified_data":json.loads(r.verified_data or "{}"),"created_at":r.created_at.isoformat()
    }
