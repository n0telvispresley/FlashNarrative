import nltk
from nltk.probability import FreqDist
from collections import Counter
import re
from datetime import datetime, timedelta

nltk.download('punkt', quiet=True)

def analyze_sentiment(mentions):
    """
    Analyze sentiment for each mention using keyword-based approach.
    Returns: dict of tone counts, list of tones per mention.
    """
    positive_keywords = ['good', 'great', 'excellent', 'positive', 'love', 'awesome', 'best']
    negative_keywords = ['bad', 'poor', 'terrible', 'negative', 'hate', 'awful', 'worst']
    anger_keywords = ['angry', 'furious', 'rage', 'mad', 'outrage']
    appreciation_keywords = ['thank', 'appreciate', 'grateful', 'thanks', 'kudos']
    mixed_keywords = ['but', 'however', 'although', 'yet', 'nonetheless']

    tones = []
    for text in mentions:
        text_lower = str(text).lower()
        has_pos = any(re.search(r'\b' + k + r'\b', text_lower) for k in positive_keywords)
        has_neg = any(re.search(r'\b' + k + r'\b', text_lower) for k in negative_keywords)
        has_anger = any(re.search(r'\b' + k + r'\b', text_lower) for k in anger_keywords)
        has_app = any(re.search(r'\b' + k + r'\b', text_lower) for k in appreciation_keywords)
        has_mixed = any(re.search(r'\b' + k + r'\b', text_lower) for k in mixed_keywords)

        if has_anger:
            tone = 'anger'
        elif has_app:
            tone = 'appreciation'
        elif (has_pos and has_neg) or has_mixed:
            tone = 'mixed'
        elif has_pos:
            tone = 'positive'
        elif has_neg:
            tone = 'negative'
        else:
            tone = 'neutral'
        tones.append(tone)

    counts = Counter(tones)
    return counts, tones

def extract_keywords(all_text, top_n=10):
    """
    Extract top keywords/themes using NLTK.
    Returns: list of (word, freq) tuples.
    """
    tokens = nltk.word_tokenize(str(all_text).lower())
    tokens = [t for t in tokens if len(t) > 3 and t.isalpha()]
    freq_dist = FreqDist(tokens)
    return freq_dist.most_common(top_n)

def filter_by_hours(full_data, hours):
    """
    Strict hour-based filtering.
    Only include mentions within the last `hours` hours.
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    filtered = []
    for item in full_data:
        try:
            item_time = datetime.strptime(item.get('date', ''), "%Y-%m-%d %H:%M")
            if item_time >= cutoff:
                filtered.append(item)
        except Exception:
            # Keep item if date parsing fails
            filtered.append(item)
    return filtered

def compute_kpis(full_data, tones=None, campaign_messages=None, industry=None, hours=None, brand=None):
    """
    Compute PR KPIs safely, defaulting missing data where necessary.
    Returns dict including sentiment_ratio, SOV, MIS, MPI, engagement, reach, small_brand_sentiment.
    """
    if full_data is None:
        full_data = []

    if hours:
        full_data = filter_by_hours(full_data, hours)

    # Ensure every item has 'sentiment'
    if tones is None:
        tones = []
    for item in full_data:
        if 'sentiment' not in item or item['sentiment'] is None:
            # Compute sentiment if text exists
            text = item.get('text', '')
            _, tone = analyze_sentiment([text])
            item['sentiment'] = tone[0] if tone else 'neutral'
        tones.append(item['sentiment'])

    total_mentions = len(full_data)
    if total_mentions == 0:
        return {'sentiment_ratio': {}, 'sov': [], 'mis': 0, 'mpi': 0,
                'engagement_rate': 0, 'reach': 0, 'small_brand_sentiment': 0}

    # Attach sentiment safely
    for i, item in enumerate(full_data):
        item['sentiment'] = tones[i] if i < len(tones) else 'neutral'
        item['mentioned_brands'] = item.get('mentioned_brands', [])
        item['authority'] = item.get('authority', 0)
        item['likes'] = item.get('likes', 0)
        item['comments'] = item.get('comments', 0)
        item['reach'] = item.get('reach', 0)
        item['source'] = item.get('source', '')

    # Gather all brands
    all_brands = set()
    for item in full_data:
        all_brands.update(item.get('mentioned_brands', []))
    all_brands = list(all_brands)

    # SOV
    brand_counts = {b: 0 for b in all_brands}
    for item in full_data:
        for b in item.get('mentioned_brands', []):
            brand_counts[b] += 1
    total_brand_mentions = sum(brand_counts.values())
    sov = [brand_counts.get(b, 0) / total_brand_mentions * 100 if total_brand_mentions > 0 else 0 for b in all_brands]

    # Sentiment ratio
    counts = Counter(tones)
    sentiment_ratio = {tone: count / total_mentions * 100 for tone, count in counts.items()}

    # MIS
    mis = sum(item.get('authority', 0) for item in full_data if item['sentiment'] == 'positive')

    # MPI
    mpi = 0
    if campaign_messages:
        matches = 0
        for item in full_data:
            text_lower = str(item.get('text','')).lower()
            matches += sum(1 for msg in campaign_messages if msg.lower() in text_lower)
        mpi = matches / total_mentions if total_mentions > 0 else 0

    # Engagement rate
    social_sources = ['fb', 'ig', 'threads']
    social_mentions = [item for item in full_data if any(s in item.get('source','') for s in social_sources)]
    engagement_rate = sum((item.get('likes',0) + item.get('comments',0)) for item in social_mentions) / len(social_mentions) if social_mentions else 0

    # Reach
    reach = sum(item.get('reach',0) for item in full_data)

    # Small brand sentiment
    small_brand_sentiment = 0
    if brand and brand in brand_counts:
        pos = sum(1 for item in full_data if brand in item.get('mentioned_brands', []) and item['sentiment'] == 'positive')
        neg = sum(1 for item in full_data if brand in item.get('mentioned_brands', []) and item['sentiment'] == 'negative')
        total = pos + neg
        small_brand_sentiment = (pos / total * 100 - neg / total * 100) if total > 0 else 0

    return {
        'sentiment_ratio': sentiment_ratio,
        'sov': sov,
        'mis': mis,
        'mpi': mpi,
        'engagement_rate': engagement_rate,
        'reach': reach,
        'small_brand_sentiment': small_brand_sentiment
    }
