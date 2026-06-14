from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
from database import SessionLocal, engine
from models import Base, Email, Rule
from imap_client import IMAPClient
from smtp_client import SMTPClient
from rules_engine import apply_rules
import os

load_dotenv()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MailFlow API", version="1.0.0")

# CORS — coloque o domínio do seu Cloudflare Pages aqui
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health ────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

# ── Sync ──────────────────────────────────────
@app.post("/api/sync")
async def sync_emails():
    try:
        client = IMAPClient()
        new_emails = client.fetch_new_emails(limit=50)
        db = SessionLocal()
        saved = 0
        for e in new_emails:
            exists = db.query(Email).filter(
                Email.message_id == e["message_id"]
            ).first()
            if not exists:
                obj = Email(**e)
                db.add(obj)
                apply_rules(db, obj)
                saved += 1
        db.commit(); db.close()
        return {"synced": saved}
    except Exception as ex:
        raise HTTPException(500, str(ex))

# ── List emails ───────────────────────────────
@app.get("/api/emails")
async def list_emails(
    folder: str = "inbox", page: int = 1,
    limit: int = 20, q: Optional[str] = None,
    label: Optional[str] = None, unread: Optional[bool] = None
):
    db = SessionLocal()
    qr = db.query(Email).filter(Email.folder==folder, Email.deleted==False)
    if q: qr = qr.filter(Email.subject.ilike(f"%{q}%")|Email.sender.ilike(f"%{q}%"))
    if label: qr = qr.filter(Email.labels.contains([label]))
    if unread is not None: qr = qr.filter(Email.read==(not unread))
    total = qr.count()
    emails = qr.order_by(Email.date.desc()).offset((page-1)*limit).limit(limit).all()
    db.close()
    return {"emails": [e.to_dict() for e in emails], "total": total}

# ── Get one email ─────────────────────────────
@app.get("/api/emails/{eid}")
async def get_email(eid: int):
    db = SessionLocal()
    e = db.query(Email).filter(Email.id==eid).first()
    db.close()
    if not e: raise HTTPException(404, "Não encontrado")
    return e.to_dict()

# ── Actions ───────────────────────────────────
@app.patch("/api/emails/{eid}/read")
async def mark_read(eid: int, read: bool = True):
    db = SessionLocal(); e = db.query(Email).filter(Email.id==eid).first()
    if not e: raise HTTPException(404,"Não encontrado")
    e.read = read; db.commit(); db.close()
    return {"ok": True}

@app.patch("/api/emails/{eid}/star")
async def star(eid: int, starred: bool = True):
    db = SessionLocal(); e = db.query(Email).filter(Email.id==eid).first()
    if not e: raise HTTPException(404,"Não encontrado")
    e.starred = starred; db.commit(); db.close()
    return {"ok": True}

@app.patch("/api/emails/{eid}/folder")
async def move(eid: int, folder: str):
    db = SessionLocal(); e = db.query(Email).filter(Email.id==eid).first()
    if not e: raise HTTPException(404,"Não encontrado")
    e.folder = folder; db.commit(); db.close()
    return {"ok": True}

@app.delete("/api/emails/{eid}")
async def delete_email(eid: int):
    db = SessionLocal(); e = db.query(Email).filter(Email.id==eid).first()
    if not e: raise HTTPException(404,"Não encontrado")
    e.deleted = True; e.folder = "trash"; db.commit(); db.close()
    return {"ok": True}

# ── Send ──────────────────────────────────────
class SendReq(BaseModel):
    to: str; subject: str; body: str
    cc: Optional[str] = None

@app.post("/api/emails/send")
async def send_email(req: SendReq):
    try:
        SMTPClient().send(req.to, req.subject, req.body, req.cc)
        return {"ok": True}
    except Exception as ex:
        raise HTTPException(500, str(ex))

# ── Stats ─────────────────────────────────────
@app.get("/api/stats")
async def stats():
    db = SessionLocal()
    def count(**kw): return db.query(Email).filter_by(**kw).count()
    data = {
        "total"  : count(folder="inbox", deleted=False),
        "unread" : count(folder="inbox", read=False, deleted=False),
        "sent"   : count(folder="sent"),
        "starred": count(starred=True, deleted=False),
        "spam"   : count(folder="spam"),
    }
    db.close(); return data

# ── Rules ─────────────────────────────────────
class RuleReq(BaseModel):
    name: str; conditions: List[dict]; actions: List[dict]; active: bool = True

@app.get("/api/rules")
async def list_rules():
    db = SessionLocal(); r = [x.to_dict() for x in db.query(Rule).all()]; db.close(); return r

@app.post("/api/rules")
async def create_rule(req: RuleReq):
    db = SessionLocal(); r = Rule(**req.dict()); db.add(r); db.commit(); db.refresh(r); db.close(); return r.to_dict()

@app.delete("/api/rules/{rid}")
async def del_rule(rid: int):
    db = SessionLocal(); r = db.query(Rule).filter(Rule.id==rid).first()
    if not r: raise HTTPException(404,"Não encontrada")
    db.delete(r); db.commit(); db.close(); return {"ok": True}