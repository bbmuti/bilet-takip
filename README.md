# Bilet Takip

Bilet Takip; çeşitli etkinlik platformlarındaki konser ve spor bileti duyurularını izlemek, eşleşen etkinlikleri sınıflandırmak ve e-posta bildirimi oluşturmak amacıyla geliştirilmiş Python tabanlı bir takip aracıdır.

> **Durum:** Zamanlanmış GitHub Actions otomasyonu devre dışıdır. Proje şu anda otomatik olarak çalışmaz ve e-posta göndermez.

## Özellikler

- Biletinial, Bubilet, Biletix ve Passo sayfalarını tarama
- Sanatçı ve takım anahtar kelimelerine göre etkinlik eşleştirme
- Satışta, yakında satışta ve tükenmiş durumlarını ayırt etme
- Şehir, tarih, saat ve mekân bilgilerini çıkarma
- Daha önce görülen etkinlikleri JSON tabanlı durum kaydıyla takip etme
- SMTP üzerinden e-posta bildirimi oluşturma

## Kullanılan Teknolojiler

- Python 3.11
- Requests
- Beautiful Soup
- SMTP
- GitHub Actions (isteğe bağlı; mevcut repoda devre dışı)

## Proje Yapısı

- `ticket_notifier.py`: Tarama, eşleştirme ve bildirim işlemleri
- `requirements.txt`: Python bağımlılıkları
- `seen_items.json`: İlk çalıştırmada yerel olarak oluşturulan ve Git tarafından takip edilmeyen durum kaydı

## Yerel Kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell kullanıyorsanız sanal ortamı şu komutla etkinleştirebilirsiniz:

```powershell
.venv\Scripts\Activate.ps1
```

Çalıştırmadan önce aşağıdaki ortam değişkenleri tanımlanmalıdır:

| Değişken | Açıklama |
|---|---|
| `SMTP_HOST` | SMTP sunucusu |
| `SMTP_PORT` | SMTP portu |
| `SMTP_USER` | Gönderen e-posta adresi |
| `SMTP_PASS` | Uygulama şifresi veya SMTP parolası |
| `MAIL_TO` | Bildirimin gönderileceği adres |

Ardından:

```bash
python ticket_notifier.py
```

`seen_items.json` ilk çalıştırmada otomatik oluşturulur. Bu çalışma zamanı dosyası `.gitignore` kapsamında tutulur.

## Güvenlik

Kimlik bilgileri kaynak koduna yazılmamalıdır. SMTP bilgileri yalnızca ortam değişkenleri veya güvenli secret yönetimi üzerinden sağlanmalıdır.
