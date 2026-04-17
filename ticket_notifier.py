
import os
import smtplib
import datetime
from email.mime.text import MIMEText

ARTISTS = [
    "Hadise",
    "Ebru Gündeş",
    "Melike Şahin",
    "Mabel Matiz",
    "Sıla"
]

def send_email(subject, body):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    mail_to = os.getenv("MAIL_TO")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = mail_to

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [mail_to], msg.as_string())

def check_events():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = "Bilet Takip Sistemi Çalışıyor"
    body = f"Sistem çalışıyor. Kontrol zamanı: {now}"
    send_email(subject, body)

if __name__ == "__main__":
    check_events()
