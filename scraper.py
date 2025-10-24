"""
scraper.py
Mixed scraper:
- NewsAPI (key rotation) -> primary, strict hour-based filter
- RSS feeds (hardcoded, industry-aware) -> supplement
- Google News HTML scraping -> fallback
- Dummy social scrapers for FB/IG/Threads (existing behavior)
- Caching to cache/scraper_cache.json (TTL from .env or default 15 min)

Main public function:
    fetch_all(brand, time_frame_hours, competitors, industry=None)

Returns:
    {'mentions': [...texts...], 'full_data': [...article dicts...]}
"""

import os
import json
import time
import requests
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import feedparser
from dateutil import parser as dateparser
from urllib.parse import quote_plus

# Optional: create cache dir
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, 'scraper_cache.json')

# Load env variables
NEWSAPI_KEYS = []
if os.getenv("NEWSAPI_KEYS"):
    NEWSAPI_KEYS = [k.strip() for k in os.getenv("NEWSAPI_KEYS").split(",") if k.strip()]

try:
    CACHE_TTL_MINUTES = int(os.getenv("SCRAPER_CACHE_TTL_MINUTES", "15"))
except Exception:
    CACHE_TTL_MINUTES = 15

# Hardcoded authority & reach (can be expanded)
AUTHORITY_DICT = {
    'nytimes.com': 10,
    'washingtonpost.com': 9,
    'cnn.com': 8,
    'bbc.com': 9,
    'reuters.com': 9,
    'techcrunch.com': 7,
    'theverge.com': 7,
    # defaults used if not present
}

REACH_DICT = {
    'nytimes.com': 1000000,
    'washingtonpost.com': 800000,
    'cnn.com': 700000,
    'bbc.com': 900000,
    'reuters.com': 600000,
    'techcrunch.com': 200000,
    # defaults to 10000
}

# Industry-aware RSS feeds (hardcoded; extend as needed)
RSS_FEEDS_BY_INDUSTRY = {
    'default': [
        'http://feeds.bbci.co.uk/news/rss.xml',
        'http://rss.cnn.com/rss/edition.rss',
        'http://feeds.reuters.com/reuters/topNews',
        'http://feeds.feedburner.com/TechCrunch/'
    ],
    'tech': [
        'http://feeds.feedburner.com/TechCrunch/',
        'https://www.theverge.com/rss/index.xml',
        'https://www.wired.com/feed/rss'
    ],
    'finance': [
        'https://www.ft.com/?format=rss',
        'https://www.bloomberg.com/feed/podcast/etf.xml',  # example
        'https://www.cnbc.com/id/100003114/device/rss/rss.html'
    ],
    'healthcare': [
        'https://www.statnews.com/feed/',
        'https://www.medicalnewstoday.com/rss'
    ],
    'retail': [
        'https://www.retaildive.com/rss/all/',
        'https://www.forbes.com/retail/feed2/'
    ],
    # more industries...
}

# Utils
def _cache_read():
    try:
        if not os.path.exists(CACHE_FILE):
            return {}
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def _cache_write(data):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass

def _get_cache_key(brand, hours, competitors):
    comps = ",".join(sorted(competitors)) if competitors else ""
    key = f"{brand.lower()}|{hours}|{comps}"
    return key

def _is_cache_valid(entry_ts):
    return (time.time() - entry_ts) <= CACHE_TTL_MINUTES * 60

def _parse_date_to_dt(datestr):
    # attempts to parse many date formats; returns timezone-naive UTC-like datetime
    try:
        dt = dateparser.parse(datestr)
        if dt is None:
            return None
        # make timezone-naive (compare in UTC-like manner)
        if dt.tzinfo:
            dt = dt.astimezone(tz=None).replace(tzinfo=None)
        return dt
    except Exception:
        return None

def _simple_domain_from_url(url):
    try:
        # crude domain extraction
        parts = url.split("//")[-1].split("/")[0].lower()
        return parts.replace('www.', '')
    except Exception:
        return url

# Dummy fallback generator (keeps your old behavior for social)
def generate_dummy_mentions(brand, competitors, time_frame, source_type):
    mentions = []
    all_brands = [brand] + competitors
    for _ in range(random.randint(5, 15)):
        mentioned = random.choice(all_brands)
        text = f"Dummy mention of {mentioned} in {source_type}."
        source = f"dummy.{source_type}.com"
        date = (datetime.now() - timedelta(hours=random.randint(1, time_frame))).strftime("%Y-%m-%d %H:%M")
        likes = random.randint(10, 1000) if source_type != 'news' else 0
        comments = random.randint(1, 100) if source_type != 'news' else 0
        authority = random.randint(1, 10)
        reach = random.randint(1000, 100000)
        mentions.append({
            'text': text,
            'source': source,
            'date': date,
            'link': '',
            'mentioned_brands': [mentioned],
            'authority': authority,
            'reach': reach,
            'likes': likes,
            'comments': comments
        })
    return mentions

# NewsAPI integration with key rotation
def fetch_newsapi(brand, time_frame_hours, competitors, newsapi_keys=None):
    if newsapi_keys is None:
        newsapi_keys = NEWSAPI_KEYS
    if not newsapi_keys:
        return []
    # Prepare time window (strict hour-based)
    to_dt = datetime.utcnow()
    from_dt = to_dt - timedelta(hours=time_frame_hours)
    # NewsAPI expects ISO format
    from_iso = from_dt.isoformat(timespec='seconds') + 'Z'
    to_iso = to_dt.isoformat(timespec='seconds') + 'Z'

    query_terms = [brand] + (competitors or [])
    q = " OR ".join([f'"{t}"' for t in query_terms if t])

    # endpoints and params
    url = "https://newsapi.org/v2/everything"
    params = {
        'q': q,
        'from': from_iso,
        'to': to_iso,
        'language': 'en',
        'pageSize': 100,
        'sortBy': 'publishedAt'
    }

    # Try keys in rotation
    errors = []
    for key in newsapi_keys:
        headers = {'Authorization': key}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                payload = resp.json()
                articles = payload.get('articles', [])
                results = []
                for art in articles:
                    published = art.get('publishedAt') or art.get('published_at') or ''
                    dt = _parse_date_to_dt(published)
                    if dt is None:
                        continue
                    # strict hour check
                    if dt < from_dt:
                        continue
                    source_name = (art.get('source') or {}).get('name') or art.get('source') or 'newsapi'
                    domain = _simple_domain_from_url(art.get('url') or source_name)
                    text = (art.get('title') or '') + ' ' + (art.get('description') or '')
                    mentioned_brands = [b for b in [brand] + (competitors or []) if b.lower() in text.lower()]
                    results.append({
                        'text': text.strip(),
                        'source': domain,
                        'date': dt.isoformat(),
                        'link': art.get('url') or '',
                        'mentioned_brands': mentioned_brands,
                        'authority': AUTHORITY_DICT.get(domain, 5),
                        'reach': REACH_DICT.get(domain, 10000),
                        'likes': 0,
                        'comments': 0
                    })
                return results
            else:
                # handle known rate limit or auth errors
                errors.append({'key': key, 'status': resp.status_code, 'text': resp.text})
                # try next key
        except Exception as e:
            errors.append({'key': key, 'exception': str(e)})
            continue
    # If all keys failed, return empty and let caller fallback to RSS/Google
    return []

# RSS fetcher
def fetch_rss_for_industry(industry, brand, time_frame_hours, competitors):
    feeds = RSS_FEEDS_BY_INDUSTRY.get(industry, None) or RSS_FEEDS_BY_INDUSTRY.get(industry.lower(), None)
    if not feeds:
        feeds = RSS_FEEDS_BY_INDUSTRY.get('default', [])
    mentions = []
    cutoff = datetime.now() - timedelta(hours=time_frame_hours)
    for feed_url in feeds:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                datestr = entry.get('published') or entry.get('pubDate') or entry.get('updated') or entry.get('updated_parsed')
                dt = _parse_date_to_dt(datestr) if datestr else None
                if dt is None:
                    # skip if no parseable date
                    continue
                if dt < cutoff:
                    continue
                title = entry.get('title', '')
                summary = entry.get('summary', '') or entry.get('description', '')
                link = entry.get('link', '') or ''
                text = (title + ' ' + BeautifulSoup(summary, 'html.parser').get_text()).strip()
                domain = _simple_domain_from_url(link or feed_url)
                mentioned_brands = [b for b in [brand] + (competitors or []) if b.lower() in text.lower()]
                mentions.append({
                    'text': text,
                    'source': domain,
                    'date': dt.isoformat(),
                    'link': link,
                    'mentioned_brands': mentioned_brands,
                    'authority': AUTHORITY_DICT.get(domain, 5),
                    'reach': REACH_DICT.get(domain, 10000),
                    'likes': 0,
                    'comments': 0
                })
        except Exception:
            continue
    return mentions

# Google News HTML fallback (keeps older approach; may be brittle)
def fetch_google_news_html(brand, time_frame_hours, competitors):
    try:
        query = f"{brand} OR {' OR '.join(competitors)}" if competitors else brand
        # Use the last N days window via parameters; we'll do strict hour filtering after parsing
        url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=nws&hl=en"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        mentions = []
        # heuristic selectors (may change)
        items = soup.select("div.dbsr") or soup.select("g-card")
        cutoff_dt = datetime.now() - timedelta(hours=time_frame_hours)
        for el in items:
            try:
                a = el.find('a')
                link = a['href'] if a else ''
                title = el.get_text(separator=' ').strip()
                # Google often doesn't provide easy dates in HTML results; skip strict check here
                domain = _simple_domain_from_url(link or 'news.google')
                mentioned_brands = [b for b in [brand] + (competitors or []) if b.lower() in title.lower()]
                if mentioned_brands:
                    mentions.append({
                        'text': title,
                        'source': domain,
                        'date': datetime.now().isoformat(),  # best-effort
                        'link': link,
                        'mentioned_brands': mentioned_brands,
                        'authority': AUTHORITY_DICT.get(domain, 5),
                        'reach': REACH_DICT.get(domain, 10000),
                        'likes': 0,
                        'comments': 0
                    })
            except Exception:
                continue
        return mentions
    except Exception:
        return []

# Public interface
def fetch_all(brand, time_frame, competitors=None, industry='default'):
    """
    fetch_all(brand, time_frame(hours), competitors:list, industry:str) -> dict
    Maintains compatibility with the dashboard: returns {'mentions': [texts], 'full_data': [...]}
    """
    if competitors is None:
        competitors = []

    cache = _cache_read()
    cache_key = _get_cache_key(brand, time_frame, competitors)
    cached_entry = cache.get(cache_key)
    if cached_entry and _is_cache_valid(cached_entry.get('ts', 0)):
        try:
            return cached_entry['value']
        except Exception:
            pass  # continue to fresh fetch

    aggregated = []
    # 1) Primary: NewsAPI
    try:
        newsapi_results = fetch_newsapi(brand, time_frame, competitors, NEWSAPI_KEYS)
        if newsapi_results:
            aggregated.extend(newsapi_results)
    except Exception:
        pass

    # 2) RSS (industry-aware)
    try:
        rss_results = fetch_rss_for_industry(industry or 'default', brand, time_frame, competitors)
        if rss_results:
            aggregated.extend(rss_results)
    except Exception:
        pass

    # 3) Google News HTML fallback if still few results
    if len(aggregated) < 5:
        try:
            google_results = fetch_google_news_html(brand, time_frame, competitors)
            if google_results:
                aggregated.extend(google_results)
        except Exception:
            pass

    # 4) Social sources (dummy for now)
    try:
        fb = generate_dummy_mentions(brand, competitors, time_frame, 'fb')
        ig = generate_dummy_mentions(brand, competitors, time_frame, 'ig')
        threads = generate_dummy_mentions(brand, competitors, time_frame, 'threads')
        aggregated.extend(fb + ig + threads)
    except Exception:
        pass

    # Normalize unique by link+text to avoid duplicates
    seen = set()
    normalized = []
    for a in aggregated:
        signature = (a.get('link') or '') + '||' + (a.get('text') or '')[:200]
        if signature in seen:
            continue
        seen.add(signature)
        normalized.append(a)

    out = {'mentions': [m['text'] for m in normalized], 'full_data': normalized}

    # write to cache
    try:
        cache[cache_key] = {'ts': time.time(), 'value': out}
        _cache_write(cache)
    except Exception:
        pass

    return out

# If module run directly for quick test
if __name__ == "__main__":
    # quick smoke test (replace with actual keys in .env)
    test = fetch_all("MyBrand", 24, ["Competitor1", "Competitor2"], industry='tech')
    print(f"Found {len(test['full_data'])} mentions")
