import base64,hashlib,hmac,json,time
from fastapi import HTTPException,Request
from .config import SECRET_KEY
def hash_password(p):
    salt=hashlib.sha256((SECRET_KEY+p).encode()).hexdigest()[:32]
    return hashlib.scrypt(p.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def check_password(p,h): return hmac.compare_digest(hash_password(p),h)
def token_for(cid):
    payload={"cid":cid,"exp":int(time.time())+86400}
    raw=json.dumps(payload,separators=(",",":")).encode()
    sig=hmac.new(SECRET_KEY.encode(),raw,hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw+b"."+sig).decode()
def centre_id(request:Request):
    t=request.headers.get("Authorization","")
    if not t.startswith("Bearer "): raise HTTPException(401,"Login required")
    try:
        raw=base64.urlsafe_b64decode(t[7:].encode()); body,sig=raw.rsplit(b".",1)
        if not hmac.compare_digest(sig,hmac.new(SECRET_KEY.encode(),body,hashlib.sha256).digest()): raise ValueError()
        p=json.loads(body)
        if p["exp"]<time.time(): raise ValueError()
        return int(p["cid"])
    except Exception: raise HTTPException(401,"Invalid or expired session")
