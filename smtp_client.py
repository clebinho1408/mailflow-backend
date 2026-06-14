import smtplib, os
from email.mime.text      import MIMEText
from email.mime.multipart import MIMEMultipart

class SMTPClient:
    def __init__(self):
        self.host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("SMTP_PORT", 587))
        self.user = os.getenv("EMAIL_USER")
        self.pwd  = os.getenv("EMAIL_PASS")

    def send(self, to, subject, body, cc=None, html=None):
        msg = MIMEMultipart("alternative")
        msg["From"] = self.user; msg["To"] = to; msg["Subject"] = subject
        if cc: msg["Cc"] = cc
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html: msg.attach(MIMEText(html, "html", "utf-8"))
        recipients = [to] + ([cc] if cc else [])
        with smtplib.SMTP(self.host, self.port) as s:
            s.ehlo(); s.starttls(); s.login(self.user, self.pwd)
            s.sendmail(self.user, recipients, msg.as_string())