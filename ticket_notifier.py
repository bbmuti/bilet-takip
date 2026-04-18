import os
import re
import json
import smtplib
import requests
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from urllib.parse import urljoin

TRACKED_KEYWORDS = [
    "Hadise",
    "Ebru Gündeş",
    "Melike Şahin",
    "Mabel Matiz",
    "Sıla",
    "VakıfBank",
    "Fenerbahçe",
]

SEARCH_PAGES = [
    "https://biletinial.com/tr-tr",
    "https://www.bubilet.com.tr",
    "https://www.biletix.com",
]

STATE_FILE = "seen_items.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

ON_SALE_PATTERNS = [
    r"\bbiletini al\b",
    r"\bsatın al\b",
    r"\bsepete ekle\b",
    r"\bhemen al\b",
    r"\bşimdi al\b",
    r"\bbilet al\b",
    r"\bon sale\b",
    r"\bbuy ticket\b",
    r"\bbuy now\b",
    r"\bget ticket\b",
    r"\bavailable\b",
]

OFF_SALE_PATTERNS = [
    r"\byakında\b",
    r"\bçok yakında\b",
    r"\bsatışta değil\b",
    r"\btükendi\b",
    r"\bsold out\b",
    r"\bcurrently unavailable\b",
    r"\bnot available\b",
]

EVENT_LINK_HINTS = [
    "/etkinlik/",
    "/event/",
    "/muzik/",
    "/music/",
    "/konser/",
    "/tiyatro/",
    "/spor/",
    "/sports/",
]

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def send_email(subject, body):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    mail_to = os.getenv("MAIL_TO")

    if not all([smtp_host, smtp_user, smtp_pass, mail_to]):
        raise ValueError("Mail ayarları eksik.")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = mail_to

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [mail_to], msg.as_string())

def normalize_text(text):
    return " ".join(text.split()).strip()

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        return r.text
    except Exception:
        return ""

def text_matches_keyword(text, keyword):
    return keyword.lower() in text.lower()

def looks_like_event_link(href):
    href_lower = href.lower()
    return any(hint in href_lower for hint in EVENT_LINK_HINTS)

def find_candidate_links(page_url, html):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        text = normalize_text(a.get_text(" ", strip=True))
        if not href or not text:
            continue

        full_url = urljoin(page_url, href)
        combined = f"{text} {href}"

        matched_keywords = [kw for kw in TRACKED_KEYWORDS if text_matches_keyword(combined, kw)]
        if not matched_keywords:
            continue

        if not looks_like_event_link(full_url) and not looks_like_event_link(href):
            # link yolu çok genel olsa bile başlıkta aranan ifade geçiyorsa yine de al
            pass

        results.append({
            "title": text,
            "url": full_url,
            "matched_keywords": matched_keywords,
            "source_page": page_url,
        })

    # aynı URL'leri tekilleştir
    dedup = {}
    for item in results:
        url = item["url"]
        if url not in dedup:
            dedup[url] = item
        else:
            old = dedup[url]
            merged = sorted(set(old["matched_keywords"] + item["matched_keywords"]))
            old["matched_keywords"] = merged

    return list(dedup.values())

def detect_sale_status(html):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    text = normalize_text(text).lower()

    on_hit = any(re.search(p, text, re.IGNORECASE) for p in ON_SALE_PATTERNS)
    off_hit = any(re.search(p, text, re.IGNORECASE) for p in OFF_SALE_PATTERNS)

    if on_hit and not off_hit:
        return "on_sale"
    if off_hit and not on_hit:
        return "off_sale"
    if on_hit and off_hit:
        # satış butonu daha güçlü sayılır
        return "on_sale"
    return "unknown"

def inspect_event(candidate):
    html = fetch(candidate["url"])
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_text(soup.get_text(" ", strip=True))
    sale_status = detect_sale_status(html)

    matched_keywords = [
        kw for kw in TRACKED_KEYWORDS
        if kw.lower() in page_text.lower() or kw in candidate["matched_keywords"]
    ]

    if not matched_keywords:
        return None

    title = candidate["title"]
    if not title or len(title) < 3:
        if soup.title and soup.title.text:
            title = normalize_text(soup.title.text)

    return {
        "title": title,
        "url": candidate["url"],
        "matched_keywords": matched_keywords,
        "sale_status": sale_status,
        "source_page": candidate["source_page"],
    }

def build_key(item):
    return item["url"]

def should_notify(old_status, new_status):
    if new_status != "on_sale":
        return False
    if old_status is None:
        return True
    return old_status != "on_sale"

def main():
    previous_state = load_state()
    current_state = {}
    notifications = []

    all_candidates = []
    for page in SEARCH_PAGES:
        html = fetch(page)
        if not html:
            continue
        all_candidates.extend(find_candidate_links(page, html))

    # aynı URL'leri tekilleştir
    unique_candidates = {}
    for item in all_candidates:
        if item["url"] not in unique_candidates:
            unique_candidates[item["url"]] = item
        else:
            old = unique_candidates[item["url"]]
            old["matched_keywords"] = sorted(set(old["matched_keywords"] + item["matched_keywords"]))

    for candidate in unique_candidates.values():
        inspected = inspect_event(candidate)
        if not inspected:
            continue

        key = build_key(inspected)
        old_status = previous_state.get(key, {}).get("sale_status")
        new_status = inspected["sale_status"]

        current_state[key] = {
            "title": inspected["title"],
            "url": inspected["url"],
            "matched_keywords": inspected["matched_keywords"],
            "sale_status": new_status,
        }

        if should_notify(old_status, new_status):
            notifications.append(inspected)

    save_state(current_state)

    if not notifications:
        print("Yeni satış bildirimi yok.")
        return

    lines = ["Satışta olan yeni bilet / etkinlik bulundu:\n"]

    for i, item in enumerate(notifications, start=1):
        lines.append(f"{i}. Başlık: {item['title']}")
        lines.append(f"Eşleşen isimler: {', '.join(item['matched_keywords'])}")
        lines.append(f"Durum: {item['sale_status']}")
        lines.append(f"Link: {item['url']}")
        lines.append("")

    body = "\n".join(lines)
    send_email("Yeni bilet satış bildirimi", body)
    print(f"Mail gönderildi. Bildirim sayısı: {len(notifications)}")

if __name__ == "__main__":
    main()
