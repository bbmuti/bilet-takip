import os
import re
import json
import smtplib
import requests
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from urllib.parse import urljoin

ARTIST_KEYWORDS = [
    "Hadise",
    "Ebru Gündeş",
    "Melike Şahin",
    "Mabel Matiz",
    "Sıla",
    "Derya Bedavacı",
]

TEAM_KEYWORDS = [
    "VakıfBank",
    "Fenerbahçe",
]

VOLLEYBALL_HINTS = [
    "voleybol",
    "volleyball",
    "sultanlar ligi",
    "cev",
    "challenge cup",
    "champions league",
    "kadın voleybol",
    "erkek voleybol",
    "axa sigorta efeler ligi",
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
    r"\bbook now\b",
]

OFF_SALE_PATTERNS = [
    r"\byakında\b",
    r"\bçok yakında\b",
    r"\bsatışta değil\b",
    r"\btükendi\b",
    r"\bsold out\b",
    r"\bcurrently unavailable\b",
    r"\bnot available\b",
    r"\byakında satışta\b",
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
    "/artist/",
    "/sanatci/",
]

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
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

        matched_artists = [kw for kw in ARTIST_KEYWORDS if kw.lower() in combined.lower()]
        matched_teams = [kw for kw in TEAM_KEYWORDS if kw.lower() in combined.lower()]

        if not matched_artists and not matched_teams:
            continue

        if not looks_like_event_link(full_url) and not looks_like_event_link(href):
            pass

        results.append({
            "title": text,
            "url": full_url,
            "matched_artists": matched_artists,
            "matched_teams": matched_teams,
            "source_page": page_url,
        })

    dedup = {}
    for item in results:
        url = item["url"]
        if url not in dedup:
            dedup[url] = item
        else:
            old = dedup[url]
            old["matched_artists"] = sorted(set(old["matched_artists"] + item["matched_artists"]))
            old["matched_teams"] = sorted(set(old["matched_teams"] + item["matched_teams"]))

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
        return "on_sale"
    return "unknown"

def detect_category(page_text, candidate):
    text_lower = page_text.lower()

    matched_artists = sorted(set([
        kw for kw in ARTIST_KEYWORDS
        if kw.lower() in text_lower or kw in candidate["matched_artists"]
    ]))

    matched_teams = sorted(set([
        kw for kw in TEAM_KEYWORDS
        if kw.lower() in text_lower or kw in candidate["matched_teams"]
    ]))

    volleyball_hit = any(hint.lower() in text_lower for hint in VOLLEYBALL_HINTS)

    if matched_artists:
        return "concert", matched_artists

    if matched_teams and volleyball_hit:
        return "sports", matched_teams

    return None, []

def inspect_event(candidate):
    html = fetch(candidate["url"])
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_text(soup.get_text(" ", strip=True))
    sale_status = detect_sale_status(html)

    category, matched_names = detect_category(page_text, candidate)
    if not category or not matched_names:
        return None

    title = candidate["title"]
    if not title or len(title) < 3:
        if soup.title and soup.title.text:
            title = normalize_text(soup.title.text)

    return {
        "title": title,
        "url": candidate["url"],
        "category": category,
        "matched_names": matched_names,
        "sale_status": sale_status,
        "source_page": candidate["source_page"],
    }

def build_key(item):
    return item["url"]

def should_notify(old_record, new_record):
    if new_record["sale_status"] != "on_sale":
        return False

    if old_record is None:
        return True

    if old_record.get("notified", False):
        return False

    old_status = old_record.get("sale_status", "unknown")
    return old_status != "on_sale"

def group_notifications(notifications):
    concerts = []
    sports = []

    for item in notifications:
        if item["category"] == "concert":
            concerts.append(item)
        elif item["category"] == "sports":
            sports.append(item)

    return concerts, sports

def build_mail_body(items, label):
    lines = [f"{label} için yeni satış bildirimi:\n"]

    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. Başlık: {item['title']}")
        lines.append(f"Eşleşen isimler: {', '.join(item['matched_names'])}")
        lines.append(f"Durum: {item['sale_status']}")
        lines.append(f"Link: {item['url']}")
        lines.append("")

    return "\n".join(lines)

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

    unique_candidates = {}
    for item in all_candidates:
        if item["url"] not in unique_candidates:
            unique_candidates[item["url"]] = item
        else:
            old = unique_candidates[item["url"]]
            old["matched_artists"] = sorted(set(old["matched_artists"] + item["matched_artists"]))
            old["matched_teams"] = sorted(set(old["matched_teams"] + item["matched_teams"]))

    for candidate in unique_candidates.values():
        inspected = inspect_event(candidate)
        if not inspected:
            continue

        key = build_key(inspected)
        old_record = previous_state.get(key)

        notify_now = should_notify(old_record, inspected)

        current_state[key] = {
            "title": inspected["title"],
            "url": inspected["url"],
            "category": inspected["category"],
            "matched_names": inspected["matched_names"],
            "sale_status": inspected["sale_status"],
            "notified": bool(old_record.get("notified")) if old_record else False,
        }

        if notify_now:
            notifications.append(inspected)
            current_state[key]["notified"] = True

    save_state(current_state)

    if not notifications:
        print("Yeni satış bildirimi yok.")
        return

    concerts, sports = group_notifications(notifications)

    if concerts:
        send_email(
            "Yeni konser bileti satışta",
            build_mail_body(concerts, "Konser")
        )

    if sports:
        send_email(
            "Yeni spor bileti satışta",
            build_mail_body(sports, "Spor / Voleybol")
        )

    print(f"Mail gönderildi. Toplam bildirim: {len(notifications)}")

if __name__ == "__main__":
    main()
