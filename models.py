from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Email(Base):
    __tablename__ = "emails"
    id          = Column(Integer, primary_key=True)
    message_id  = Column(String, unique=True, index=True)
    sender      = Column(String); email_from = Column(String)
    recipient   = Column(String); subject    = Column(String)
    body        = Column(Text);   date       = Column(DateTime, default=datetime.utcnow)
    read        = Column(Boolean, default=False)
    starred     = Column(Boolean, default=False)
    folder      = Column(String,  default="inbox")
    labels      = Column(JSON,    default=list)
    attachments = Column(JSON,    default=list)
    deleted     = Column(Boolean, default=False)
    account     = Column(String,  default="main")

    def to_dict(self):
        return {
            "id": self.id, "message_id": self.message_id,
            "sender": self.sender, "email": self.email_from,
            "subject": self.subject, "body": self.body,
            "preview": (self.body or "")[:120],
            "date": self.date.isoformat() if self.date else None,
            "read": self.read, "starred": self.starred,
            "folder": self.folder, "labels": self.labels or [],
            "attachments": self.attachments or [], "account": self.account,
        }

class Rule(Base):
class Account(Base):
    __tablename__ = "accounts"
    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String, unique=True, nullable=False, index=True)
    password   = Column(String, nullable=False)
    imap_host  = Column(String, default="imap.gmail.com")
    imap_port  = Column(Integer, default=993)
    smtp_host  = Column(String, default="smtp.gmail.com")
    smtp_port  = Column(Integer, default=587)
    active     = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


    __tablename__ = "rules"
    id         = Column(Integer, primary_key=True)
    name       = Column(String); conditions = Column(JSON)
    actions    = Column(JSON);   active     = Column(Boolean, default=True)
    applied    = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id":self.id,"name":self.name,"conditions":self.conditions,
                "actions":self.actions,"active":self.active,"applied":self.applied}