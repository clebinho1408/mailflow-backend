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
# ── Account Models & Endpoints ───────────────────────────
class AccountReq(BaseModel):
    email: str
    password: str
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

@app.post("/api/accounts/test")
async def test_account(req: AccountReq):
    import imaplib, smtplib, ssl
    errors = []
    try:
        ctx = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(req.imap_host, req.imap_port, ssl_context=ctx)
        imap.login(req.email, req.password)
        imap.logout()
    except Exception as e:
        errors.append(f"IMAP: {str(e)}")
    try:
        with smtplib.SMTP(req.smtp_host, req.smtp_port, timeout=10) as s:
            s.ehlo()
            s.starttls()
            s.login(req.email, req.password)
    except Exception as e:
        errors.append(f"SMTP: {str(e)}")
    if errors:
        raise HTTPException(status_code=400, detail=" | ".join(errors))
    return {"ok": True, "message": f"Conexao com {req.email} bem-sucedida!"}

@app.post("/api/accounts")
async def add_account(req: AccountReq):
    from sqlalchemy import text
    db = SessionLocal()
    try:
        existing = db.execute(text("SELECT id FROM accounts WHERE email = :e"), {"e": req.email}).fetchone()
        if existing:
            db.execute(text("UPDATE accounts SET password=:pw, imap_host=:ih, imap_port=:ip, smtp_host=:sh, smtp_port=:sp WHERE email=:e"),
                {"pw": req.password, "ih": req.imap_host, "ip": req.imap_port, "sh": req.smtp_host, "sp": req.smtp_port, "e": req.email})
            msg = f"Conta {req.email} atualizada."
        else:
            db.execute(text("INSERT INTO accounts (email, password, imap_host, imap_port, smtp_host, smtp_port) VALUES (:e, :pw, :ih, :ip, :sh, :sp)"),
                {"e": req.email, "pw": req.password, "ih": req.imap_host, "ip": req.imap_port, "sh": req.smtp_host, "sp": req.smtp_port})
            msg = f"Conta {req.email} adicionada."
        db.commit()
        return {"ok": True, "message": msg, "email": req.email}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/accounts")
async def list_accounts():
    from sqlalchemy import text
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, email, imap_host, smtp_host FROM accounts ORDER BY id")).fetchall()
        return [{"id": r[0], "email": r[1], "imap_host": r[2], "smtp_host": r[3]} for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
