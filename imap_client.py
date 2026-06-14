import imaplib, email, os
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime

class IMAPClient:
    def __init__(self):
        self.host = os.getenv("IMAP_HOST", "imap.gmail.com")
        self.user = os.getenv("EMAIL_USER")
        self.pwd  = os.getenv("EMAIL_PASS")
        self.port = int(os.getenv("IMAP_PORT", 993))

    def connect(self):
        m = imaplib.IMAP4_SSL(self.host, self.port)
        m.login(self.user, self.pwd)
        return m

    def _dec(self, v):
        if not v: return ""
        d, enc = decode_header(v)[0]
        return d.decode(enc or "utf-8", errors="replace") if isinstance(d, bytes) else (d or "")

    def _body(self, msg):
        if msg.is_multipart():
            for p in msg.walk():
                if p.get_content_type() == "text/plain" and "attachment" not in str(p.get("Content-Disposition")):
                    cs = p.get_content_charset() or "utf-8"
                    return p.get_payload(decode=True).decode(cs, errors="replace").strip()
        cs = msg.get_content_charset() or "utf-8"
        raw = msg.get_payload(decode=True)
        return raw.decode(cs, errors="replace").strip() if raw else ""

    def _attachments(self, msg):
        out = []
        for p in msg.walk():
            if "attachment" in str(p.get("Content-Disposition")):
                fn = p.get_filename()
                if fn: out.append({"name": self._dec(fn), "type": p.get_content_type()})
        return out

    def fetch_new_emails(self, folder="INBOX", limit=50):
        mail = self.connect(); mail.select(folder)
        _, data = mail.search(None, "ALL")
        ids = data[0].split()[-limit:]
        result = []
        for eid in reversed(ids):
            try:
                _, md = mail.fetch(eid, "(RFC822 FLAGS)")
                flags = imaplib.ParseFlags(md[0][0])
                msg   = email.message_from_bytes(md[0][1])
                try: date = parsedate_to_datetime(msg.get("Date",""))
                except: date = datetime.now()
                result.append({
                    "message_id": msg.get("Message-ID", eid.decode()),
                    "sender"    : self._dec(msg.get("From","")),
                    "email_from": msg.get("From",""),
                    "recipient" : msg.get("To",""),
                    "subject"   : self._dec(msg.get("Subject","(sem assunto)")),
                    "body"      : self._body(msg),
                    "date"      : date,
                    "read"      : b"\\Seen" in flags,
                    "starred"   : b"\\Flagged" in flags,
                    "folder"    : "inbox",
                    "attachments": self._attachments(msg),
                    "labels"    : [],
                })
            except Exception as ex: print(f"Skip {eid}: {ex}")
        mail.logout(); return result