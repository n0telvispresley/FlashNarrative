import re
# utils.py
def mock_alert(msg):
    """Mock alert for demo if no creds."""
    print(f"Mock Alert: {msg}")


def clean_text(text):
    """
    Clean input text by removing extra spaces, special characters.
    """
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)  # collapse whitespace
    text = re.sub(r'[^\w\s]', '', text)  # remove punctuation
    return text.strip()

def safe_get(d, key, default=None):
    """
    Safely get value from dict; returns default if key missing.
    """
    try:
        return d.get(key, default)
    except Exception:
        return default

def ensure_sentiment(full_data, default='neutral'):
    """
    Ensure each mention in full_data has a 'sentiment' key.
    """
    for item in full_data:
        if 'sentiment' not in item:
            item['sentiment'] = default
    return full_data
