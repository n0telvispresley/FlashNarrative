import nltk
from nltk.probability import FreqDist
from collections import Counter
import re

# Download NLTK resources if needed
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
        text_lower = text.lower()
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

def extract_keywords(all_text):
    """
    Extract top 10 keywords/themes using NLTK.
    Returns: list of (word, freq) tuples.
    """
    tokens = nltk.word_tokenize(all_text.lower())
    # Filter out short words and punctuation
    tokens = [t for t in tokens if len(t) > 3 and t.isalpha()]
    freq_dist = FreqDist(tokens)
    return freq_dist.most_common(10)

def compute_kpis(full_data, tones, campaign_messages, industry):
    """
    Compute PR KPIs based on scraped data.
    Returns: dict of KPIs.
    Assumes full_data is list of dicts with 'mentioned_brands', 'authority', 'reach', 'likes', 'comments', 'text', 'source'.
    tones: list of sentiments per mention.
    """
    total_mentions = len(full_data)
    if total_mentions == 0:
        return {'sentiment_ratio': {}, 'sov': [], 'mis': 0, 'mpi': 0, 'engagement_rate': 0, 'reach': 0}

    # Add sentiment to full_data for convenience
    for i, item in enumerate(full_data):
        item['sentiment'] = tones[i]

    # Get unique brands (brand + competitors)
    all_brands = set()
    for item in full_data:
        all_brands.update(item['mentioned_brands'])
    all_brands = list(all_brands)

    # SOV: mentions per brand / total mention counts (allowing multi-brand)
    brand_counts = {b: 0 for b in all_brands}
    for item in full_data:
        for b in item['mentioned_brands']:
            brand_counts[b] += 1
    total_brand_mentions = sum(brand_counts.values())
    sov = [brand_counts.get(b, 0) / total_brand_mentions * 100 if total_brand_mentions > 0 else 0 for b in all_brands]

    # Sentiment Ratio: % of each tone overall
    counts = Counter(tones)
    sentiment_ratio = {tone: count / total_mentions * 100 for tone, count in counts.items()}

    # MIS: sum authority for positive mentions
    mis = sum(item['authority'] for item in full_data if item['sentiment'] == 'positive')

    # MPI: average matches of campaign messages in mentions
    matches = 0
    for item in full_data:
        text_lower = item['text'].lower()
        matches += sum(1 for msg in campaign_messages if msg.lower() in text_lower)
    mpi = matches / total_mentions if total_mentions > 0 else 0

    # Engagement Rate: avg (likes + comments) for social sources
    social_sources = ['fb', 'ig', 'threads']
    social_mentions = [item for item in full_data if any(s in item['source'] for s in social_sources)]
    if social_mentions:
        engagement_rate = sum((item['likes'] + item['comments']) for item in social_mentions) / len(social_mentions)
    else:
        engagement_rate = 0

    # Reach/Impressions: sum estimates overall
    reach = sum(item['reach'] for item in full_data)

    return {
        'sentiment_ratio': sentiment_ratio,
        'sov': sov,
        'mis': mis,
        'mpi': mpi,
        'engagement_rate': engagement_rate,
        'reach': reach
    }
