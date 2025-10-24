# analysis.py
import nltk
from nltk.probability import FreqDist
from collections import Counter
import re # Make sure re is imported
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
from nltk.collocations import BigramAssocMeasures, BigramCollocationFinder # <-- Import for bigrams

# Ensure necessary NLTK data is available
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True) # <-- Need stopwords for filtering phrases

# Use NLTK's English stopwords list and add our custom ones
stop_words = set(nltk.corpus.stopwords.words('english'))
stop_words.update(['com', 'www', 'http', 'https', 'co', 'uk', 'amp', 'rt', 'via']) # Add common web/social junk


# --- ADD THIS FUNCTION BACK ---
def analyze_sentiment_keywords(text):
    """
    Analyzes sentiment based on keywords and simple synonyms.
    Returns a single sentiment string ('positive', 'negative', etc.). Used as fallback.
    """
    if not text: # Handle empty input
        return 'neutral'
    text_lower = text.lower()

    # Define keywords and basic synonyms
    positive_kws = ['good', 'great', 'excellent', 'positive', 'love', 'awesome', 'best', 'happy', 'like', 'amazing', 'superb', 'fantastic', 'recommend', 'perfect']
    negative_kws = ['bad', 'poor', 'terrible', 'negative', 'hate', 'awful', 'worst', 'sad', 'dislike', 'broken', 'fail', 'issue', 'problem', 'disappointed', 'avoid']
    anger_kws = ['angry', 'furious', 'rage', 'mad', 'outrage', 'pissed', 'fuming', 'livid']
    appreciation_kws = ['thank', 'appreciate', 'grateful', 'thanks', 'kudos', 'cheers', 'props', 'helpful']
    mixed_kws = ['but', 'however', 'although', 'yet', 'still', 'despite'] # Conjunctions

    # Count keyword occurrences using regex for whole words
    pos_count = sum(1 for k in positive_kws if re.search(r'\b' + re.escape(k) + r'\b', text_lower))
    neg_count = sum(1 for k in negative_kws if re.search(r'\b' + re.escape(k) + r'\b', text_lower))
    anger_count = sum(1 for k in anger_kws if re.search(r'\b' + re.escape(k) + r'\b', text_lower))
    app_count = sum(1 for k in appreciation_kws if re.search(r'\b' + re.escape(k) + r'\b', text_lower))
    has_mixed = any(re.search(r'\b' + re.escape(k) + r'\b', text_lower) for k in mixed_kws)

    # Determine sentiment based on counts (prioritize stronger emotions)
    if anger_count > 0:
        return 'anger'
    # Check for both pos/neg keywords OR a conjunction indicating mixed feelings
    if (pos_count > 0 and neg_count > 0) or (has_mixed and (pos_count > 0 or neg_count > 0)):
        return 'mixed'
    if neg_count > 0:
        return 'negative'
    # Consider appreciation as positive unless it stands alone
    if pos_count > 0:
         return 'positive'
    if app_count > 0: # If only appreciation keywords are found
         return 'appreciation'

    return 'neutral' # Default if no strong keywords found
# --- END OF FUNCTION ---


def extract_keywords(all_text, top_n=10):
    """
    Extracts top single keywords and two-word phrases (bigrams).
    """
    # Tokenize the text
    tokens = nltk.word_tokenize(all_text.lower())

    # Filter tokens: keep words longer than 2 chars, alphabetic, and not in stop_words
    filtered_tokens = [
        t for t in tokens
        if len(t) > 2 and t.isalpha() and t not in stop_words
    ]

    # --- Single Word Frequency ---
    unigram_freq = FreqDist(filtered_tokens)

    # --- Phrase (Bigram) Frequency ---
    finder = BigramCollocationFinder.from_words(filtered_tokens)
    bigram_measures = BigramAssocMeasures()
    bigram_freq = finder.ngram_fd

    # --- Combine Frequencies ---
    combined_freq = Counter()

    # Add single words
    for word, freq in unigram_freq.items():
        combined_freq[word] += freq

    # Add phrases (format them as strings)
    for phrase_tuple, freq in bigram_freq.items():
        # Only add phrases that occur more than once to filter noise
        if freq > 1:
            phrase_str = " ".join(phrase_tuple)
            combined_freq[phrase_str] += freq

    # Return the top N most common items (words or phrases)
    return combined_freq.most_common(top_n)


def filter_by_hours(full_data, hours):
    """
    Uses dateutil.parser to handle ISO strings from scraper.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered = []
    for item in full_data:
        try:
            item_time = dateparser.parse(item['date'])
            if item_time.tzinfo is None:
                item_time = item_time.replace(tzinfo=timezone.utc)
            if item_time >= cutoff:
                filtered.append(item)
        except Exception:
            # Fallback: if date is bad or missing, just include it
            filtered.append(item)
    return filtered

def compute_kpis(full_data, campaign_messages, industry=None, hours=None, brand=None):
    """
    Calculates all KPIs based on the provided data.
    """
    if hours:
        full_data = filter_by_hours(full_data, hours)

    tones = [item.get('sentiment', 'neutral') for item in full_data]
    total_mentions = len(full_data)
    if total_mentions == 0:
        return {'sentiment_ratio': {}, 'sov': [], 'mis': 0, 'mpi': 0,
                'engagement_rate': 0, 'reach': 0, 'all_brands': [brand] if brand else []}

    # --- All Brands Calculation ---
    all_brands = set()
    if brand:
        all_brands.add(brand)
    for item in full_data:
        mentioned = item.get('mentioned_brands', [])
        # Ensure mentioned is always treated as a list
        if isinstance(mentioned, list):
             all_brands.update(mentioned)
        elif isinstance(mentioned, str): # Handle if it's just a single string
             all_brands.add(mentioned)

    all_brands_list = sorted(list(all_brands))
    if brand and brand not in all_brands_list:
        all_brands_list.insert(0, brand) # Put main brand first
    elif not brand and all_brands_list:
        brand = all_brands_list[0] # Assign a default if none provided but mentions exist

    # --- SOV Calculation ---
    brand_counts = Counter()
    for item in full_data:
        mentioned = item.get('mentioned_brands', [])
        # Count each brand mentioned in the item
        present_brands = set()
        if isinstance(mentioned, list):
            present_brands.update(b for b in mentioned if b in all_brands_list)
        elif isinstance(mentioned, str) and mentioned in all_brands_list:
            present_brands.add(mentioned)
        # Increment count for each unique brand present in this mention
        for b in present_brands:
             brand_counts[b] += 1

    # Total mentions contributing to SOV
    total_sov_mentions = sum(brand_counts.values())
    sov = [(brand_counts[b] / total_sov_mentions * 100) if total_sov_mentions > 0 else 0 for b in all_brands_list]

    # --- Sentiment Ratio ---
    sentiment_counts = Counter(tones)
    sentiment_ratio = {tone: count / total_mentions * 100 for tone, count in sentiment_counts.items()}

    # --- MIS ---
    mis = sum(item.get('authority', 0) for item in full_data if item.get('sentiment') in ['positive', 'appreciation'])

    # --- MPI ---
    matches = 0
    if campaign_messages:
        # Prepare messages for efficient checking (lowercase)
        lower_campaign_messages = [msg.lower() for msg in campaign_messages]
        for item in full_data:
            text_lower = item.get('text', '').lower()
            # Check if any campaign message is present
            if any(msg in text_lower for msg in lower_campaign_messages):
                matches += 1
        mpi = (matches / total_mentions) * 100 if total_mentions > 0 else 0
    else:
        mpi = 0

    # --- Engagement Rate ---
    social_sources = ['fb', 'ig', 'threads', 'twitter', 'x', 'reddit.com'] # Include dummy and real social
    social_mentions_data = [
        (item.get('likes', 0), item.get('comments', 0))
        for item in full_data
        # Check if source contains any of the social platform names
        if any(s in item.get('source', '').lower() for s in social_sources)
    ]

    total_engagement = sum(likes + comments for likes, comments in social_mentions_data)
    num_social_mentions = len(social_mentions_data)
    engagement_rate = total_engagement / num_social_mentions if num_social_mentions > 0 else 0

    # --- Reach ---
    reach = sum(item.get('reach', 0) for item in full_data)

    return {
        'sentiment_ratio': sentiment_ratio,
        'sov': sov,
        'mis': mis,
        'mpi': mpi,
        'engagement_rate': engagement_rate,
        'reach': reach,
        'all_brands': all_brands_list # Pass the final list out
    }
