
BU DOSYALAR NE YAPAR

Bu proje GitHub Actions üzerinde çalışır.
Bilgisayarınız kapalı olsa bile sistem 5 dakikada bir çalışır ve mail gönderir.

Kurulum:
1) Bu dosyaları GitHub reposuna yükle
2) Settings → Secrets and variables → Actions bölümüne şu değerleri ekle:

SMTP_HOST = smtp.gmail.com
SMTP_PORT = 465
SMTP_USER = mail adresin
SMTP_PASS = Gmail App Password
MAIL_TO = mail adresin

Sonra Actions sekmesinde sistem otomatik çalışır.
