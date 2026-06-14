from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from database import Base
from datetime import datetime


class Email(Base):
    __tablename__ = "emails"

    id         = Column(Integer, primary_key=True, index=True)
    uid        = Column(String, unique=True, index=True)
    subject    = Column(String, default="")
    sender     = Column(String, default="")
    recipient  = Column(String, default="")
    body       = Column(Text, default="")
    folder     = Column(String, default="inbox")
    read       = Column(Boolean, default=False)
    starred    = Column(Boolean, default=False)
    deleted    = Column(Boolean, default=False)
    date       = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":        self.id,
            "uid":       self.uid,
            "subject":   self.subject,
            "sender":    self.sender,
            "recipient": self.recipient,
            "body":      self.body,
            "folder":    self.folder,
            "read":      self.read,
            "starred":   self.starred,
            "deleted":   self.deleted,
            "date":      str(self.date),
        }


class Rule(Base):
    __tablename__ = "rules"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, default="")
    condition  = Column(String, default="")
    value      = Column(String, default="")
    action     = Column(String, default="")
    active     = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":        self.id,
            "name":      self.name,
            "condition": self.condition,
            "value":     self.value,
            "action":    self.action,
            "active":    self.active,
        }


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

    def to_dict(self):
        return {
            "id":        self.id,
            "email":     self.email,
            "imap_host": self.imap_host,
            "smtp_host": self.smtp_host,
            "active":    self.active,
        }
