import os
import re
import json
import smtplib
import requests
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

ARTIST_KEYWORDS = [
    "Hadise",
    "Ebru Gündeş",
    "Melike Şahin",
    "Mabel Matiz",
    "Sıla",
    "Derya Bedavacı",
    "Mor ve Ötesi",
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
    "champions league",
    "kadın voleybol",
    "erkek voleybol",
    "axa sigorta efeler ligi",
    "efeler ligi",
]

STATE_FILE = "seen_items.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

SEARCH_PAGES = [
    "https://biletinial.com/tr-tr",
    "https://www.bubilet.com.tr",
    "https://www.biletix.com",
]

ARTIST_PAGE_PATTERNS = {
    "bubilet": [
        "https://www.bubilet.com.tr/sanatci/{slug}",
    ],
    "biletinial": [
        "https://biletinial.com/tr-tr/profile/{slug}",
        "https://biletinial.com/tr-tr/muzik/{slug}",
    ],
    "biletix": [
        "https://www.biletix.com/artist/54/TURKIYE/tr/{slug}",
        "https://www.biletix.com/etkinlik-grup/270304422/TURKIYE/tr/{slug}",
    ],
}

SITE_RULES = {
    "bubilet": {
        "on_sale_patterns": [
            r"\bbiletler\b",
            r"\bbilet\b",
            r"\bbiletler satışta\b",
            r"\bbiletleri satışta\b",
            r"\bsatışta\b",
            r"\bsepet\b",
            r"\bsepetim\b",
            r"\bşimdi satışta\b",
            r"\bhemen satışta\b",
            r"\b₺\b.*\bbilet",
        ],
        "off_sale_patterns": [
            r"\byakında satışta\b",
            r"\byakında\b",
            r"\btükendi\b",
            r"\bsold out\b",
            r"\bnot available\b",
        ],
        "event_link_hints": [
            "/etkinlik/",
            "/seans/",
            "/sanatci/",
        ],
    },
    "biletinial": {
        "on_sale_patterns": [
            r"\bbiletini al\b",
            r"\bbilet fiyatları\b",
            r"\bbilet al\b",
            r"\bsatın al\b",
            r"\bsepete ekle\b",
            r"\bson \d+ bilet\b",
            r"\b\d+[.,]?\d*\s*₺.*bilet",
            r"\bden başlayan fiyatlarla\b",
        ],
        "off_sale_patterns": [
            r"\btükendi\b",
            r"\byakında\b",
            r"\bsatışta değil\b",
            r"\bcurrently unavailable\b",
        ],
        "event_link_hints": [
            "/tr-tr/muzik/",
            "/tr-tr/profile/",
            "/tr-tr/etkinlik/",
            "/tr-tr/spor/",
            "/tr-tr/mekan/",
        ],
    },
    "biletix": {
        "on_sale_patterns": [
            r"\bbiletix\b.*\betkinlik",
            r"\betkinlik takvimi\b",
            r"\bbilet\b",
            r"\bsatın al\b",
            r"\bbuy\b",
        ],
        "off_sale_patterns": [
            r"\btükendi\b",
            r"\bsold out\b",
            r"\bcurrently unavailable\b",
        ],
        "event_link_hints": [
            "/etkinlik/",
            "/artist/",
            "/etkinlik-grup/",
        ],
    },
}

def slugify(name: str) -> str:
    repl = {
        "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g",
        "ı": "i", "İ": "i",
        "ö": "o", "Ö": "o",
        "ş": "s", "Ş": "s",
        "ü": "u", "Ü": "u",
        "&": "ve",
    }
    for k, v in repl.items():
        name = name.replace(k, v)
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")

def detect_site(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "bubilet.com.tr" in host:
        return "bubilet"
    if "biletinial.com" in host:
        return "biletinial"
    if "biletix.com" in host:
        return "biletix"
    return "unknown"

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

def site_event_link_hints(site: str):
    return SITE_RULES.get(site, {}).get("event_link_hints", [])

def looks_like_event_link(url: str, site: str) -> bool:
    url_lower = url.lower()
    return any(h in url_lower for h in site_event_link_hints(site))

def artist_seed_urls():
    urls = []
    for artist in ARTIST_KEYWORDS:
        slug = slugify(artist)
        for site, patterns in ARTIST_PAGE_PATTERNS.items():
            for pattern in patterns:
                urls.append(pattern.format(slug=slug))
    return urls

def base_and_artist_pages():
    return SEARCH_PAGES + artist_seed_urls()

def find_candidate_links(page_url, html):
    site = detect_site(page_url)
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        text = normalize_text(a.get_text(" ", strip=True))
        if not href:
            continue

        full_url = urljoin(page_url, href)
        combined = f"{text} {href}"

        matched_artists = [kw for kw in ARTIST_KEYWORDS if kw.lower() in combined.lower()]
        matched_teams = [kw for kw in TEAM_KEYWORDS if kw.lower() in combined.lower()]

        if not matched_artists and not matched_teams:
            continue

        if not looks_like_event_link(full_url, site):
            # başlıkta birebir eşleşme varsa yine al
            if not text:
                continue

        results.append({
            "title": text,
            "url": full_url,
            "matched_artists": matched_artists,
            "matched_teams": matched_teams,
            "source_page": page_url,
            "site": site,
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

def detect_sale_status(html, site):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    text = normalize_text(text).lower()

    rules = SITE_RULES.get(site, {})
    on_patterns = rules.get("on_sale_patterns", [])
    off_patterns = rules.get("off_sale_patterns", [])

    on_hit = any(re.search(p, text, re.IGNORECASE) for p in on_patterns)
    off_hit = any(re.search(p, text, re.IGNORECASE) for p in off_patterns)

    if on_hit and not off_hit:
        return "on_sale"
    if off_hit and not on_hit:
        return "off_sale"
    if on_hit and off_hit:
        # satış ifadesi varsa satışta kabul et
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

    volleyball_hit = any(h.lower() in text_lower for h in VOLLEYBALL_HINTS)

    if matched_artists:
        return "concert", matched_artists

    if matched_teams and volleyball_hit:
        return "sports", matched_teams

    return None, []

def inspect_event(candidate):
    html = fetch(candidate["url"])
    if not html:
        return None

    site = candidate["site"] if candidate["site"] != "unknown" else detect_site(candidate["url"])
    soup = BeautifulSoup(html, "html.parser")
    page_text = normalize_text(soup.get_text(" ", strip=True))
    sale_status = detect_sale_status(html, site)

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
        "site": site,
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
        lines.append(f"Site: {item['site']}")
        lines.append(f"Durum: {item['sale_status']}")
        lines.append(f"Link: {item['url']}")
        lines.append("")

    return "\n".join(lines)

def main():
    previous_state = load_state()
    current_state = {}
    notifications = []

    all_candidates = []
    for page in base_and_artist_pages():
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
            "site": inspected["site"],
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
