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
    "Ayta Sözeri",
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

CITY_NAMES = [
    "İstanbul", "Ankara", "İzmir", "Antalya", "Bursa", "Eskişehir",
    "Konya", "Adana", "Mersin", "Kocaeli", "Samsun", "Trabzon",
    "Kayseri", "Gaziantep", "Diyarbakır", "Muğla", "Aydın", "Denizli"
]

KNOWN_VENUES = [
    "Volkswagen Arena",
    "Harbiye Cemil Topuzlu Açıkhava Tiyatrosu",
    "KüçükÇiftlik Park",
    "Maximum Uniq Açıkhava",
    "Maximum Uniq Hall",
    "Zorlu PSM",
    "Jolly Joker",
    "IF Performance Hall",
    "CerModern",
    "Kültürpark Açıkhava Tiyatrosu",
    "Antalya Açıkhava",
    "VakıfBank Spor Sarayı",
    "Ülker Spor ve Etkinlik Salonu",
]

DATE_PATTERNS = [
    r"\b\d{1,2}\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4}\b",
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b",
]

TIME_PATTERNS = [
    r"\b\d{1,2}[:.]\d{2}\b"
]

STATE_FILE = "seen_items.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

SEARCH_PAGES = [
    "https://biletinial.com/tr-tr",
    "https://www.bubilet.com.tr",
    "https://www.biletix.com",
    "https://www.passo.com.tr/tr",
    "https://www.passo.com.tr/tr/kategori/muzik-konser-festival-biletleri/8615",
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
        "https://www.biletix.com/etkinlik-grup/270304422/TURKIYE/tr/{slug}",
        "https://www.biletix.com/artist/54/TURKIYE/tr/{slug}",
    ],
    "passo": [
        "https://www.passo.com.tr/tr/etkinlik/{slug}",
        "https://www.passo.com.tr/en/event/{slug}",
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
            r"\bbilet al\b",
            r"\bsepete ekle\b",
            r"\bsepet\b",
            r"\bsepetim\b",
            r"\bşimdi satışta\b",
            r"\bhemen satışta\b",
            r"\b₺\b",
            r"\btl\b",
        ],
        "upcoming_patterns": [
            r"\byakında satışta\b",
            r"\byakında\b",
            r"\bçok yakında\b",
            r"\bsatış yakında\b",
            r"\b\d{1,2}:\d{2}.*satışta\b",
            r"\bsaat \d{1,2}:\d{2}.*satışta\b",
        ],
        "off_sale_patterns": [
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
            r"\bhemen al\b",
            r"\bson \d+ bilet\b",
            r"\b₺\b",
            r"\btl\b",
            r"\bden başlayan fiyatlarla\b",
        ],
        "upcoming_patterns": [
            r"\byakında\b",
            r"\bçok yakında\b",
            r"\bsatış yakında\b",
        ],
        "off_sale_patterns": [
            r"\btükendi\b",
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
            r"\bbilet\b",
            r"\bsatın al\b",
            r"\bbuy\b",
            r"\bavailable\b",
            r"\b₺\b",
            r"\btl\b",
            r"\betkinlik takvimi\b",
        ],
        "upcoming_patterns": [
            r"\byakında\b",
            r"\bçok yakında\b",
            r"\bsatış yakında\b",
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
    "passo": {
        "on_sale_patterns": [
            r"\bsatışta\b",
            r"\bbiletleri passo'da satışta\b",
            r"\bbiletleri satışta\b",
            r"\bbilet\b",
            r"\bsatın al\b",
            r"\bgenel satış\b",
            r"\bdetaylı incele\b",
            r"\b₺\b",
            r"\btl\b",
            r"\betkinlik takvimi\b",
        ],
        "upcoming_patterns": [
            r"\byakında\b",
            r"\bçok yakında\b",
            r"\bsatış yakında\b",
            r"\b\d{1,2}[.:]\d{2}'?da satışta\b",
            r"\bgenel satış .* başlar\b",
            r"\bcuma \d{1,2}[.:]\d{2}'?da satışta\b",
        ],
        "off_sale_patterns": [
            r"\btükendi\b",
            r"\bsold out\b",
            r"\bcurrently unavailable\b",
        ],
        "event_link_hints": [
            "/tr/etkinlik/",
            "/en/event/",
            "/tr/mekan/",
            "/tr/kategori/",
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


def clean_key_part(value):
    value = value or "bilinmiyor"
    value = slugify(str(value))
    return value or "bilinmiyor"


def normalize_text(text):
    return " ".join(text.split()).strip()


def detect_site(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "bubilet.com.tr" in host:
        return "bubilet"
    if "biletinial.com" in host:
        return "biletinial"
    if "biletix.com" in host:
        return "biletix"
    if "passo.com.tr" in host:
        return "passo"
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
        for _, patterns in ARTIST_PAGE_PATTERNS.items():
            for pattern in patterns:
                urls.append(pattern.format(slug=slug))
    return urls


def base_and_artist_pages():
    return SEARCH_PAGES + artist_seed_urls()


def extract_city(text, url=""):
    combined = f"{text} {url}".lower()

    for city in CITY_NAMES:
        if city.lower() in combined:
            return city

    for city in CITY_NAMES:
        city_slug = slugify(city)
        if f"/{city_slug}/" in combined or f"-{city_slug}" in combined:
            return city

    return "Bilinmiyor"


def extract_date(text):
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return "Bilinmiyor"


def extract_time(text):
    for pattern in TIME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return "Bilinmiyor"


def extract_venue(text):
    text_lower = text.lower()

    for venue in KNOWN_VENUES:
        if venue.lower() in text_lower:
            return venue

    return "Bilinmiyor"


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
    upcoming_patterns = rules.get("upcoming_patterns", [])
    off_patterns = rules.get("off_sale_patterns", [])

    on_hit = any(re.search(p, text, re.IGNORECASE) for p in on_patterns)
    upcoming_hit = any(re.search(p, text, re.IGNORECASE) for p in upcoming_patterns)
    off_hit = any(re.search(p, text, re.IGNORECASE) for p in off_patterns)

    if off_hit and not on_hit:
        return "off_sale"

    if upcoming_hit:
        return "upcoming"

    if on_hit:
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

    city = extract_city(page_text, candidate["url"])
    date = extract_date(page_text)
    time_value = extract_time(page_text)
    venue = extract_venue(page_text)

    return {
        "title": title,
        "url": candidate["url"],
        "category": category,
        "matched_names": matched_names,
        "sale_status": sale_status,
        "site": site,
        "source_page": candidate["source_page"],
        "city": city,
        "date": date,
        "time": time_value,
        "venue": venue,
    }


def build_key(item):
    names = "-".join([clean_key_part(x) for x in item.get("matched_names", [])])
    category = clean_key_part(item.get("category", "unknown"))
    city = clean_key_part(item.get("city", "unknown"))
    venue = clean_key_part(item.get("venue", "unknown"))
    date = clean_key_part(item.get("date", "unknown"))
    title = clean_key_part(item.get("title", "unknown"))

    return f"{category}|{names}|{city}|{venue}|{date}|{title}"


def should_notify_upcoming(old_record, new_record):
    if new_record["sale_status"] != "upcoming":
        return False

    if old_record is None:
        return True

    already_notified = old_record.get("notified_upcoming", False)
    old_status = old_record.get("sale_status", "unknown")

    if already_notified:
        return False

    return old_status != "upcoming"


def should_notify_on_sale(old_record, new_record):
    if new_record["sale_status"] != "on_sale":
        return False

    if old_record is None:
        return True

    old_status = old_record.get("sale_status", "unknown")
    already_notified = old_record.get("notified_on_sale", False)

    if old_status != "on_sale" and not already_notified:
        return True

    return False


def group_notifications(items):
    concerts = []
    sports = []

    for item in items:
        if item["category"] == "concert":
            concerts.append(item)
        elif item["category"] == "sports":
            sports.append(item)

    return concerts, sports


def build_mail_body(items, label):
    lines = [f"{label} için bildirim:\n"]

    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. Başlık: {item['title']}")
        lines.append(f"Eşleşen isimler: {', '.join(item['matched_names'])}")
        lines.append(f"Şehir: {item.get('city', 'Bilinmiyor')}")
        lines.append(f"Mekan: {item.get('venue', 'Bilinmiyor')}")
        lines.append(f"Tarih: {item.get('date', 'Bilinmiyor')}")
        lines.append(f"Saat: {item.get('time', 'Bilinmiyor')}")
        lines.append(f"Site: {item['site']}")
        lines.append(f"Durum: {item['sale_status']}")
        lines.append(f"Link: {item['url']}")
        lines.append("")

    return "\n".join(lines)


def main():
    previous_state = load_state()
    current_state = {}
    upcoming_notifications = []
    on_sale_notifications = []

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
        old_record = previous_state.get(key, {})

        notify_upcoming = should_notify_upcoming(old_record, inspected)
        notify_on_sale = should_notify_on_sale(old_record, inspected)

        current_state[key] = {
            "title": inspected["title"],
            "url": inspected["url"],
            "category": inspected["category"],
            "matched_names": inspected["matched_names"],
            "sale_status": inspected["sale_status"],
            "site": inspected["site"],
            "city": inspected["city"],
            "date": inspected["date"],
            "time": inspected["time"],
            "venue": inspected["venue"],
            "notified_upcoming": old_record.get("notified_upcoming", False),
            "notified_on_sale": old_record.get("notified_on_sale", False),
        }

        if notify_upcoming:
            upcoming_notifications.append(inspected)
            current_state[key]["notified_upcoming"] = True

        if notify_on_sale:
            on_sale_notifications.append(inspected)
            current_state[key]["notified_on_sale"] = True

    save_state(current_state)

    if upcoming_notifications:
        concerts, sports = group_notifications(upcoming_notifications)

        if concerts:
            send_email(
                "Yakında satışta olan konser bulundu",
                build_mail_body(concerts, "Konser / Yakında Satışta")
            )
        if sports:
            send_email(
                "Yakında satışta olan spor etkinliği bulundu",
                build_mail_body(sports, "Spor / Yakında Satışta")
            )

    if on_sale_notifications:
        concerts, sports = group_notifications(on_sale_notifications)

        if concerts:
            send_email(
                "Yeni konser bileti satışta",
                build_mail_body(concerts, "Konser / Satışta")
            )
        if sports:
            send_email(
                "Yeni spor bileti satışta",
                build_mail_body(sports, "Spor / Voleybol / Satışta")
            )

    if not upcoming_notifications and not on_sale_notifications:
        print("Yeni bildirim yok.")
    else:
        print(
            f"Yakında satışta: {len(upcoming_notifications)} | "
            f"Satışta: {len(on_sale_notifications)}"
        )


if __name__ == "__main__":
    main()
