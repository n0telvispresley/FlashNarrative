# analysis.py
import nltk
from nltk.probability import FreqDist
from collections import Counter
import re
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser # Import this

nltk.download('punkt', quiet=True)

stop_words = set(['the', 'is', 'a', 'to', 'and', 'in', 'it', 'for', 'of', 'i', 's', 'your', 'com', 'www', 'http', 'https', 'co', 'uk'])


def extract_keywords(all_text, top_n=10):
    tokens = nltk.word_tokenize(all_text.lower())
    
    # This line now correctly uses the global 'stop_words' list
    tokens = [t for t in tokens if len(t) > 3 and t.isalpha() and t not in stop_words]
    freq_dist = FreqDist(tokens)
    return freq_dist.most_common(top_n)


def filter_by_hours(full_data, hours):
    """
    FIXED: Uses dateutil.parser to handle ISO strings from scraper.
    """
    # Use timezone.utc for comparison
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered = []
    for item in full_data:
        try:
            # Use dateparser.parse to handle various ISO formats
            item_time = dateparser.parse(item['date'])
            
            # Ensure item_time is offset-aware for correct comparison
            if item_time.tzinfo is None:
                # If naive, assume it's UTC as per scraper.py
                item_time = item_time.replace(tzinfo=timezone.utc) 
                
            if item_time >= cutoff:
                filtered.append(item)
        except Exception:
            # Fallback: if date is bad or missing, just include it
            filtered.append(item)
    return filtered

def compute_kpis(full_data, campaign_messages, industry=None, hours=None, brand=None):
    
    # Filter by time *first*
    if hours:
        full_data = filter_by_hours(full_data, hours)

    # Get tones *from* the data (set by Bedrock in dashboard.py)
    tones = [item.get('sentiment', 'neutral') for item in full_data]

    total_mentions = len(full_data)
    if total_mentions == 0:
        return {'sentiment_ratio': {}, 'sov': [], 'mis': 0, 'mpi': 0,
                'engagement_rate': 0, 'reach': 0, 'all_brands': [brand]}

    # All brands
    all_brands = set()
    if brand:
        all_brands.add(brand)
    for item in full_data:
        mentioned = item.get('mentioned_brands', [])
        all_brands.update(mentioned if isinstance(mentioned, list) else [])
    
    all_brands_list = sorted(list(all_brands))
    if brand and brand not in all_brands_list:
        all_brands_list = [brand] + all_brands_list
    elif not brand and all_brands_list:
        brand = all_brands_list[0] # Assign a default brand if none provided

    # SOV (Share of Voice)
    brand_counts = {b: 0 for b in all_brands_list}
    for item in full_data:
        for b in item.get('mentioned_brands', []):
            if b in brand_counts:
                brand_counts[b] += 1
                
    total_brand_mentions = sum(brand_counts.values())
    sov = [brand_counts.get(b, 0) / total_brand_mentions * 100 if total_brand_mentions > 0 else 0 for b in all_brands_list]

    # Sentiment ratio
    counts = Counter(tones)
    sentiment_ratio = {tone: count / total_mentions * 100 for tone, count in counts.items()}

    # --- THIS IS THE FIX ---
    # MIS (Media Impact Score) - Weighted by authority
    # Now counts 'positive' OR 'appreciation'
    mis = sum(item.get('authority', 0) for item in full_data if item.get('sentiment') in ['positive', 'appreciation'])
    # --- END OF FIX ---

    # MPI (Message Penetration Index)
    matches = 0
    if campaign_messages:
        for item in full_data:
            text_lower = item.get('text', '').lower()
            matches += sum(1 for msg in campaign_messages if msg.lower() in text_lower)
        # Return as a percentage
        mpi = (matches / total_mentions) * 100 if total_mentions > 0 else 0
    else:
        mpi = 0

    # Engagement rate (Social only)
    social_sources = ['fb', 'ig', 'threads', 'twitter', 'x', 'reddit.com'] # Added reddit
    social_mentions = [item for item in full_data if any(s in item.get('source', '').lower() for s in social_sources)]
    total_engagement = sum((item.get('likes', 0) + item.get('comments', 0)) for item in social_mentions)
    engagement_rate = total_engagement / len(social_mentions) if social_mentions else 0

    # Reach
    reach = sum(item.get('reach', 0) for item in full_data)

    return {
        'sentiment_ratio': sentiment_ratio,
        'sov': sov,
        'mis': mis,
        'mpi': mpi,
        'engagement_rate': engagement_rate,
        'reach': reach,
        'all_brands': all_brands_list # Pass this out for the UI
    }
