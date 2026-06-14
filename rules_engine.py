from models import Rule, Email
from smtp_client import SMTPClient

def check(email, cond):
    val = (getattr(email, cond.get("field",""),"") or "").lower()
    return cond.get("value","").lower() in val

def act(db, email, action):
    t, v = action.get("type"), action.get("value","")
    if   t == "label"     : email.labels = (email.labels or []) + ([v] if v not in (email.labels or []) else [])
    elif t == "move"      : email.folder = v
    elif t == "mark_read": email.read = True
    elif t == "star"      : email.starred = True
    elif t == "delete"   : email.folder = "trash"; email.deleted = True
    elif t == "auto_reply":
        try: SMTPClient().send(email.email_from, f"Re: {email.subject}", v)
        except: pass

def apply_rules(db, email):
    for r in db.query(Rule).filter_by(active=True).all():
        if all(check(email, c) for c in (r.conditions or [])):
            for a in (r.actions or []): act(db, email, a)
            r.applied += 1