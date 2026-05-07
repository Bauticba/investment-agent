import feedparser
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Google News RSS — búsquedas temáticas específicas para el mercado argentino
GOOGLE_NEWS_QUERIES = [
    ("mercado financiero AR", "dolar+bonos+merval+argentina"),
    ("macro argentina",       "inflacion+bcra+economia+argentina"),
    ("geopolitica mercados",  "fed+reserva+federal+aranceles+trump+mercados"),
]

# Feeds RSS directos (solo los que funcionan)
DIRECT_FEEDS = {
    "Ámbito": "https://www.ambito.com/rss/economia.xml",
}

IRRELEVANT_KEYWORDS = [
    "smart tv", "electrodoméstico", "supermercado", "descuento",
    "oferta", "receta", "horóscopo", "deporte", "fútbol",
    "farmacia", "reintegro", "billetera digital", "promocion",
    "compras cotidianas",
]

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _parse_date(entry) -> datetime | None:
    for field in ("published", "updated"):
        val = entry.get(field)
        if val:
            try:
                return parsedate_to_datetime(val)
            except Exception:
                pass
    return None


def _is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return not any(kw in text for kw in IRRELEVANT_KEYWORDS)


def _fetch_google_news(query: str, max_per_query: int = 6) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={query}&hl=es-419&gl=AR&ceid=AR:es-419"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        feed = feedparser.parse(r.text)
        articles = []
        for entry in feed.entries[:max_per_query]:
            title = entry.get("title", "").strip()
            if not title or not _is_relevant(title, ""):
                continue
            # Google News incluye la fuente en el título como "Título - Fuente"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, source = parts[0].strip(), parts[1].strip()
            else:
                source = "Google News"
            pub_date = _parse_date(entry)
            articles.append({
                "source":  source,
                "title":   title,
                "summary": "",
                "date":    pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else "?",
                "_dt":     pub_date or datetime.min.replace(tzinfo=timezone.utc),
            })
        return articles
    except Exception:
        return []


def _fetch_direct_feed(source: str, url: str, max_entries: int = 5) -> list[dict]:
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
        articles = []
        for entry in feed.entries[:max_entries]:
            title   = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            if not title or not _is_relevant(title, summary):
                continue
            pub_date = _parse_date(entry)
            articles.append({
                "source":  source,
                "title":   title,
                "summary": summary[:200] if summary else "",
                "date":    pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else "?",
                "_dt":     pub_date or datetime.min.replace(tzinfo=timezone.utc),
            })
        return articles
    except Exception:
        return []


def get_argentina_news(max_articles: int = 15) -> list[dict]:
    """
    Trae titulares recientes de medios financieros argentinos.
    Fuentes: Google News RSS (búsquedas temáticas) + Ámbito RSS directo.
    """
    articles = []

    for label, query in GOOGLE_NEWS_QUERIES:
        articles.extend(_fetch_google_news(query, max_per_query=5))

    for source, url in DIRECT_FEEDS.items():
        articles.extend(_fetch_direct_feed(source, url, max_entries=5))

    # Deduplicar por título
    seen = set()
    unique = []
    for a in articles:
        key = a["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    unique.sort(key=lambda a: a["_dt"], reverse=True)
    for a in unique:
        a.pop("_dt")

    return unique[:max_articles]


def format_news_for_prompt(articles: list[dict]) -> str:
    if not articles:
        return "No se pudieron obtener noticias recientes."
    lines = []
    for a in articles:
        lines.append(f"- [{a['date']} — {a['source']}] {a['title']}")
        if a.get("summary"):
            lines.append(f"  {a['summary']}")
    return "\n".join(lines)
