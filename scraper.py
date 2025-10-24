# scraper.py
"""
scraper.py
Mixed scraper:
- NewsAPI (key rotation) -> primary, strict hour-based filter
- RSS feeds (hardcoded, industry-aware) -> supplement
- Google News HTML scraping -> fallback
- Reddit search -> real-time social
- Dummy social scrapers for FB/IG/Threads (existing behavior)

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
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import feedparser
from dateutil import parser as dateparser
from urllib.parse import quote_plus

# --- Data for dummy mentions ---
DUMMY_FIRST_NAMES = ['John', 'Sarah', 'Mike', 'Emily', 'David', 'Jessica', 'Chris', 'Amanda', 'Matt', 'Laura', 'James', 'Anna']
DUMMY_LAST_INITIALS = ['K.', 'S.', 'D.', 'M.', 'P.', 'R.', 'W.', 'B.', 'G.', 'T.']

DUMMY_TEMPLATES = {
    'positive': [
        "Just got the new {brand} and I'm obsessed! Best purchase all year. 🔥",
        "Shoutout to {brand} for their amazing customer service. 10/10!",
        "I love my {brand}! It's awesome and works perfectly.",
        "Honestly, {brand} is the best in the game. Highly recommend.",
        # --- THIS IS THE FIX ---
        "The new {brand} Air Max Launch is fire! Just Do It! 🚀"
        # --- END OF FIX ---
    ],
    'negative': [
        "My {brand} broke after just one week. So disappointed.",
        "Ugh, {brand} is terrible. I hate it. Worst experience ever.",
        "Avoid {brand} at all costs. It's an awful product.",
        "I'm so mad at {brand} right now. Their new update is the worst."
    ],
    'neutral': [
        "Just saw an ad for {brand}.",
        "Thinking about buying a {brand} later today.",
        "My friend has a {brand}.",
        "The {brand} headquarters is downtown."
    ],
    'mixed': [
        "I like the new {brand}, but the battery life is pretty bad.",
        "The {brand} is great, although it's way too expensive for what it is.",
        "It's a decent product, however, the old {brand} was better.",
        "The design is awesome, yet the software feels unfinished."
    ],
    'appreciation': [
        "Thanks {brand} for making such a great product!",
        "Big appreciation post for the {brand} team. You guys rock!",
        "So grateful for {brand}. You saved me so much time.",
        "Kudos to {brand} for their new eco-friendly packaging."
    ],
    'anger': [
        "I'm furious with {brand}! My order is a month late!",
        "This is an outrage! {brand} completely scammed me.",
        "Absolutely mad at {brand}. Never buying from them again.",
        "The rage I feel towards {brand} is unreal. What a terrible company."
    ]
}

# --- Cache Setup ---
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, 'scraper_cache.json')

# --- Load env variables ---
NEWSAPI_KEYS = []
if os.getenv("NEWSAPI_KEYS"):
    NEWSAPI_KEYS = [k.strip() for k in os.getenv("NEWSAPI_KEYS").split(",") if k.strip()]

try:
    CACHE_TTL_MINUTES = int(os.getenv("SCRAPER_CACHE_TTL_MINUTES", "15"))
except Exception:
    CACHE_TTL_MINUTES = 15

# --- Hardcoded Metrics ---
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

# --- Industry RSS Feeds ---
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
        'https://www.bloomberg.com/feed/podcast/etf.xml', # example
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
    # 'Personal Brand' will use 'default'
}

# --- Utils ---
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
    # attempts to parse many date formats; returns timezone-aware datetime
    try:
        dt = dateparser.parse(datestr)
        if dt is None:
            return None
        # make timezone-aware (assume UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
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

# --- Scraper Functions ---

def generate_dummy_mentions(brand, competitors, time_frame, source_type):
    """
    Generates realistic dummy social media mentions.
    """
    mentions = []
    all_brands = [brand] + (competitors or [])
    
    for _ in range(random.randint(5, 15)):
        # Pick a random brand and user
        mentioned = random.choice(all_brands)
        user = f"{random.choice(DUMMY_FIRST_NAMES)} {random.choice(DUMMY_LAST_INITIALS)}"
        
        # Pick a random sentiment and create the text
        sentiment_type = random.choice(list(DUMMY_TEMPLATES.keys()))
        template = random.choice(DUMMY_TEMPLATES[sentiment_type])
        
        text = f"{template.format(brand=mentioned)}"

        # Define source and link as requested
        social_links = {
            'fb': 'https://www.facebook.com',
            'ig': 'https://www.instagram.com',
            'threads': 'https://www.threads.net'
        }
        source = f"{user} ({source_type})"
        link = social_links.get(source_type, 'https://socialmedia.com')

        date_dt = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, time_frame))
        date = date_dt.isoformat()
        
        likes = random.randint(10, 1000)
        comments = random.randint(1, 100)
        authority = random.randint(1, 3) # Low authority for dummy social
        reach = random.randint(1000, 100000)
        
        mentions.append({
            'text': text,
            'source': source,
            'date': date,
            'link': link,
            'mentioned_brands': [mentioned],
            'authority': authority,
            'reach': reach,
            'likes': likes,
            'comments': comments
        })
    return mentions

def fetch_newsapi(brand, time_frame_hours, competitors, newsapi_keys=None):
    """
    Fetches news from NewsAPI with key rotation.
    """
    if newsapi_keys is None:
        newsapi_keys = NEWSAPI_KEYS
    if not newsapi_keys:
        return []
        
    to_dt = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(hours=time_frame_hours)
    
    # NewsAPI free plan (on 'everything') only supports up to 30 days
    # And on dev plan, 'from' can't be more than 30 days ago
    max_from_dt = to_dt - timedelta(days=29)
    if from_dt < max_from_dt:
        from_dt = max_from_dt # Cap at 29-30 days ago

    from_iso = from_dt.isoformat()
    # to_iso = to_dt.isoformat() # 'to' is optional, defaults to now

    query_terms = [brand] + (competitors or [])
    q = " OR ".join([f'"{t}"' for t in query_terms if t])

    url = "https://newsapi.org/v2/everything"
    params = {
        'q': q,
        'from': from_iso,
        'language': 'en',
        'pageSize': 100,
        'sortBy': 'publishedAt'
    }

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
                    published = art.get('publishedAt') or ''
                    dt = _parse_date_to_dt(published)
                    if dt is None:
                        continue
                        
                    # We must re-check the date here b/c NewsAPI 'from' is not always exact
                    if dt < from_dt:
                        continue
                        
                    source_name = (art.get('source') or {}).get('name') or 'newsapi'
                    domain = _simple_domain_from_url(art.get('url') or source_name)
                    text = (art.get('title') or '') + ' ' + (art.get('description') or '')
                    mentioned_brands = [b for b in [brand] + (competitors or []) if b.lower() in text.lower()]
                    
                    if not mentioned_brands: # Skip if no brand is mentioned
                        continue

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
                errors.append({'key': key, 'status': resp.status_code, 'text': resp.text})
        except Exception as e:
            errors.append({'key': key, 'exception': str(e)})
            continue
    print(f"[NewsAPI Errors] {errors}")
    return []

def fetch_rss_for_industry(industry, brand, time_frame_hours, competitors):
    """
    Fetches news from industry-specific RSS feeds.
    """
    feeds = RSS_FEEDS_BY_INDUSTRY.get(industry, None) or RSS_FEEDS_BY_INDUSTRY.get(industry.lower(), None)
    if not feeds:
        feeds = RSS_FEEDS_BY_INDUSTRY.get('default', [])
        
    mentions = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=time_frame_hours)
    
    for feed_url in feeds:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                datestr = entry.get('published') or entry.get('pubDate') or entry.get('updated')
                dt = _parse_date_to_dt(datestr) if datestr else None
                
                if dt is None:
                    continue
                if dt < cutoff:
                    continue
                    
                title = entry.get('title', '')
                summary = entry.get('summary', '') or entry.get('description', '')
                link = entry.get('link', '') or ''
                text = (title + ' ' + BeautifulSoup(summary, 'html.parser').get_text()).strip()
                domain = _simple_domain_from_url(link or feed_url)
                
                mentioned_brands = [b for b in [brand] + (competitors or []) if b.lower() in text.lower()]
                if not mentioned_brands:
                    continue
                    
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
        except Exception as e:
            print(f"[RSS Error] {feed_url} failed: {e}")
            continue
    return mentions

def fetch_google_news_html(brand, time_frame_hours, competitors):
    """
    Fetches news from Google News HTML scrape as a fallback.
    """
    try:
        query = f"{brand} OR {' OR '.join(competitors)}" if competitors else brand
        
        # Map hours to Google's 'tbs' parameter (tbs=qdr:...)
        time_filter = ""
        try:
            h = int(time_frame_hours)
            if h <= 1:
                time_filter = "qdr:h" # Last hour
            elif h <= 72: # Use hour precision up to 3 days
                time_filter = f"qdr:h{h}"
            else: # Otherwise use day precision
                days = max(1, int(h / 24))
                time_filter = f"qdr:d{days}"
        except Exception:
            time_filter = "qdr:d" # Default to last 24 hours
        
        url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=nws&hl=en&tbs={time_filter}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        mentions = []
        
        items = soup.select("div.dbsr") or soup.select("g-card") or soup.select("div.SoaBEf")
        
        for el in items:
            try:
                a_tag = el.find('a')
                if not a_tag: continue
                
                link = a_tag['href']
                title_el = el.find('div', role='heading')
                title = title_el.get_text(separator=' ').strip() if title_el else a_tag.get_text(separator=' ').strip()

                date_el = el.find('div', role='text')
                date_str = date_el.get_text().split('·')[-1].strip() if date_el else None
                
                dt = _parse_date_to_dt(date_str) if date_str else datetime.now(timezone.utc)
                
                domain = _simple_domain_from_url(link or 'news.google')
                mentioned_brands = [b for b in [brand] + (competitors or []) if b.lower() in title.lower()]
                
                if mentioned_brands:
                    mentions.append({
                        'text': title,
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
    except Exception as e:
        print(f"[Google News HTML Error] {e}")
        return []

def fetch_reddit(brand, time_frame_hours, competitors):
    """
    Fetches real-time social mentions from Reddit.
    """
    try:
        query = f"{brand} OR {' OR '.join(competitors)}" if competitors else brand
        
        h = int(time_frame_hours)
        if h <= 2:
            time_filter = 'hour'
        elif h <= 24:
            time_filter = 'day'
        elif h <= 168:
            time_filter = 'week'
        elif h <= 720:
            time_filter = 'month'
        else:
            time_filter = 'year'

        url = f"https://www.reddit.com/search.json?q={quote_plus(query)}&sort=new&t={time_filter}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        payload = resp.json()
        mentions = []
        
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=time_frame_hours)

        for post in payload.get('data', {}).get('children', []):
            data = post.get('data', {})
            
            created_utc = data.get('created_utc')
            if not created_utc:
                continue
            dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            
            if dt < cutoff_dt:
                continue
            
            title = data.get('title', '')
            selftext = data.get('selftext', '')
            text = (title + ' ' + selftext).strip()
            link = "https://www.reddit.com" + data.get('permalink', '')
            domain = f"reddit.com/r/{data.get('subreddit', 'all')}"

            mentioned_brands = [b for b in [brand] + (competitors or []) if b.lower() in text.lower()]
            
            if not mentioned_brands:
                continue

            mentions.append({
                'text': text,
                'source': domain,
                'date': dt.isoformat(),
                'link': link,
                'mentioned_brands': mentioned_brands,
                'authority': 4, 
                'reach': data.get('score', 0) * 10,
                'likes': data.get('score', 0),
                'comments': data.get('num_comments', 0)
            })
        return mentions
    except Exception as e:
        print(f"[Reddit Scraper Error] {e}")
        return []

# --- Public Interface ---

def fetch_all(brand, time_frame, competitors=None, industry='default'):
    """
    Fetches all mentions from all sources.
    Returns: {'mentions': [texts], 'full_data': [dicts]}
    """
    if competitors is None:
        competitors = []
    
    # Use 'default' for 'Personal Brand'
    if industry.lower() == 'personal brand':
        industry = 'default'

    cache = _cache_read()
    cache_key = _get_cache_key(brand, time_frame, competitors)
    cached_entry = cache.get(cache_key)
    if cached_entry and _is_cache_valid(cached_entry.get('ts', 0)):
        try:
            return cached_entry['value']
        except Exception:
            pass 

    aggregated = []
    
    # 1) Primary: NewsAPI
    try:
        newsapi_results = fetch_newsapi(brand, time_frame, competitors, NEWSAPI_KEYS)
        if newsapi_results:
            aggregated.extend(newsapi_results)
    except Exception as e:
        print(f"[fetch_all NewsAPI Error] {e}")

    # 2) RSS (industry-aware)
    try:
        rss_results = fetch_rss_for_industry(industry or 'default', brand, time_frame, competitors)
        if rss_results:
            aggregated.extend(rss_results)
    except Exception as e:
        print(f"[fetch_all RSS Error] {e}")

    # 3) Google News HTML fallback
    if len(aggregated) < 5:
        try:
            google_results = fetch_google_news_html(brand, time_frame, competitors)
            if google_results:
                aggregated.extend(google_results)
        except Exception as e:
            print(f"[fetch_all Google News Error] {e}")

    # 4) Reddit Search
    try:
        reddit_results = fetch_reddit(brand, time_frame, competitors)
        if reddit_results:
            aggregated.extend(reddit_results)
    except Exception as e:
        print(f"[fetch_all Reddit Error] {e}")

    # 5) Social sources (dummy)
    try:
        fb = generate_dummy_mentions(brand, competitors, time_frame, 'fb')
        ig = generate_dummy_mentions(brand, competitors, time_frame, 'ig')
        threads = generate_dummy_mentions(brand, competitors, time_frame, 'threads')
        aggregated.extend(fb + ig + threads)
    except Exception as e:
        print(f"[fetch_all Dummy Error] {e}")

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
    print("Running scraper.py smoke test...")
    # quick smoke test (replace with actual keys in .env)
    test = fetch_all("Nike", 24, ["Adidas", "Puma"], industry='tech')
    print(f"Found {len(test['full_data'])} total mentions.")
    for item in test['full_data']:
        print(f" - [{item['source']}] {item['text'][:50]}...")
