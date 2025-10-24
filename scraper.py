import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import random
import schedule
import time
import threading

# Hardcoded authority for MIS (1-10 scale)
AUTHORITY_DICT = {
    'nytimes.com': 10,
    'washingtonpost.com': 9,
    'cnn.com': 8,
    'bbc.com': 9,
    # Add more as needed
}

# Hardcoded reach estimates (impressions)
REACH_DICT = {
    'nytimes.com': 1000000,
    'washingtonpost.com': 800000,
    'cnn.com': 700000,
    'bbc.com': 900000,
    # Defaults to 10000 if not found
}

def fetch_google_news(brand, time_frame, competitors):
    """Fetch from Google News; prioritize for high-impact PR monitoring."""
    try:
        query = f"{brand} OR {' OR '.join(competitors)}"
        since = datetime.now() - timedelta(hours=time_frame)
        since_str = since.strftime("%m/%d/%Y")
        until_str = datetime.now().strftime("%m/%d/%Y")
        url = f"https://www.google.com/search?q={query}&tbm=nws&tbs=cdr:1,cd_min:{since_str},cd_max:{until_str}&num=50&hl=en&gl=us"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        mentions = []
        
        for el in soup.select("div.SoaBEf"):
            try:
                link = el.find("a")["href"]
                title = el.select_one("div.MBeuO").get_text()
                snippet = el.select_one(".GI74Re").get_text()
                date = el.select_one(".LfVVr").get_text()
                source = el.select_one(".NUnG9d span").get_text().lower()
                
                # Check which brands are mentioned
                mentioned_brands = [b for b in [brand] + competitors if b.lower() in (title + snippet).lower()]
                if mentioned_brands:
                    authority = AUTHORITY_DICT.get(source, 5)
                    reach = REACH_DICT.get(source, 10000)
                    mentions.append({
                        'text': title + ' ' + snippet,
                        'source': source,
                        'date': date,
                        'link': link,
                        'mentioned_brands': mentioned_brands,
                        'authority': authority,
                        'reach': reach,
                        'likes': 0,  # No engagement in news
                        'comments': 0
                    })
            except Exception:
                pass
        
        return mentions
    except Exception as e:
        # Dummy fallback
        return generate_dummy_mentions(brand, competitors, time_frame, 'news')

def fetch_fb(brand, time_frame, competitors):
    """Fetch from FB; use dummy for MVP as public scraping without login is limited."""
    return generate_dummy_mentions(brand, competitors, time_frame, 'fb')

def fetch_ig(brand, time_frame, competitors):
    """Fetch from IG; dummy fallback due to auth requirements."""
    return generate_dummy_mentions(brand, competitors, time_frame, 'ig')

def fetch_threads(brand, time_frame, competitors):
    """Fetch from Threads; dummy for MVP."""
    return generate_dummy_mentions(brand, competitors, time_frame, 'threads')

def generate_dummy_mentions(brand, competitors, time_frame, source_type):
    """Generate dummy data if scraping fails; include engagement for social."""
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

def fetch_all(brand, time_frame, competitors):
    """Combine fetches from all sources; prioritize news for high-impact."""
    mentions = []
    mentions.extend(fetch_google_news(brand, time_frame, competitors))
    mentions.extend(fetch_fb(brand, time_frame, competitors))
    mentions.extend(fetch_ig(brand, time_frame, competitors))
    mentions.extend(fetch_threads(brand, time_frame, competitors))
    return {'mentions': [m['text'] for m in mentions], 'full_data': mentions}

# Schedule integration for periodic fetch (use in thread for production)
def run_periodic_fetch(brand, time_frame, competitors, interval_minutes=5):
    def job():
        fetch_all(brand, time_frame, competitors)
    
    schedule.every(interval_minutes).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

# Comments:
# - Prioritize Google News scraping for real high-impact data; social uses dummy to avoid auth/block issues in hackathon.
# - Filter by time via tbs=cdr in URL; extract mentions for SOV (count per brand), Reach (sum per source).
# - Add engagement (likes/comments) in dummy for social tracking.
# - Robust with try/except and dummy fallback.
# - Under 150 lines: Focus on core functions.
