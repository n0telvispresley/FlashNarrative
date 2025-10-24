import streamlit as st
import sys
import os
import traceback
import pandas as pd
import plotly.express as px
import nltk
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Add FlashNarrative folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from FlashNarrative import analysis, report_gen

# Ensure nltk data is downloaded
nltk.download('punkt', quiet=True)

st.set_page_config(page_title="FlashNarrative Dashboard", layout="wide")

st.title("FlashNarrative Dashboard")

# --------------------
# Inputs
# --------------------
brand = st.text_input("Enter your brand name", value="BrandX")

competitors_input = st.text_area(
    "Enter competitor brands (comma-separated)",
    value="CompetitorA, CompetitorB"
)
competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]

campaign_input = st.text_area(
    "Enter your campaign messages (one per line)",
    value="New Product Launch\nSummer Sale"
)
campaign_messages = [c.strip() for c in campaign_input.split("\n") if c.strip()]

hours = st.slider("Select timeframe (hours)", min_value=1, max_value=168, value=24)

# --------------------
# Load / Mock Data
# --------------------
# For testing; replace with actual data loading
if 'full_data' not in st.session_state:
    st.session_state.full_data = [
        {
            "text": "I love BrandX! It's awesome.",
            "date": "2025-10-24 12:00",
            "authority": 5,
            "likes": 10,
            "comments": 2,
            "reach": 100,
            "source": "fb",
            "mentioned_brands": ["BrandX"]
        },
        {
            "text": "CompetitorA is terrible, I hate it!",
            "date": "2025-10-24 10:00",
            "authority": 3,
            "likes": 5,
            "comments": 1,
            "reach": 50,
            "source": "ig",
            "mentioned_brands": ["CompetitorA"]
        }
    ]

full_data = st.session_state.full_data

# --------------------
# Sentiment Analysis
# --------------------
counts, tones = analysis.analyze_sentiment([item["text"] for item in full_data])

# Compute KPIs
try:
    kpis = analysis.compute_kpis(
        full_data=full_data,
        tones=tones,
        campaign_messages=campaign_messages,
        industry=None,
        hours=hours,
        brand=brand
    )
except Exception:
    st.error("Error computing KPIs:\n" + traceback.format_exc())
    kpis = {'sentiment_ratio': {}, 'sov': [], 'mis': 0, 'mpi': 0,
            'engagement_rate': 0, 'reach': 0, 'small_brand_sentiment': 0}

# --------------------
# Display KPIs
# --------------------
st.subheader("Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)
col1.metric("MIS", kpis.get("mis", 0))
col2.metric("MPI", round(kpis.get("mpi", 0), 2))
col3.metric("Engagement Rate", round(kpis.get("engagement_rate", 0), 2))
col4.metric("Reach", kpis.get("reach", 0))

# --------------------
# Sentiment Pie
# --------------------
sentiment_ratio = kpis.get("sentiment_ratio", {})
if sentiment_ratio:
    pie_data = pd.DataFrame({
        'Sentiment': list(sentiment_ratio.keys()),
        'Percent': list(sentiment_ratio.values())
    })
    fig = px.pie(pie_data, names='Sentiment', values='Percent', title="Sentiment Distribution")
    st.plotly_chart(fig)

# --------------------
# SOV Table
# --------------------
all_brands = [brand] + competitors
sov_values = kpis.get("sov", [])
if len(sov_values) < len(all_brands):
    # pad with zeros if lengths mismatch
    sov_values = sov_values + [0]*(len(all_brands) - len(sov_values))

sov_df = pd.DataFrame({'Brand': all_brands, 'SOV': sov_values})
st.subheader("Share of Voice (SOV)")
st.dataframe(sov_df)

# --------------------
# Top Keywords
# --------------------
st.subheader("Top Keywords / Themes")
top_keywords = analysis.extract_keywords(" ".join([item["text"] for item in full_data]), top_n=10)
if top_keywords:
    for word, freq in top_keywords:
        st.write(f"- {word}: {freq}")
else:
    st.write("- No keywords identified.")

# --------------------
# Competitive Audit
# --------------------
st.subheader("Competitive Audit")
for i, comp in enumerate(competitors):
    comp_sov = sov_values[i+1] if i+1 < len(sov_values) else 0
    st.write(f"- {comp}: SOV {comp_sov}% vs {brand}: {sov_values[0]}%")

# --------------------
# Links to sources
# --------------------
st.subheader("Top Sources / Links")
sources = {}
for item in full_data:
    for b in item["mentioned_brands"]:
        if b not in sources:
            sources[b] = set()
        # Construct dummy URLs for demonstration; replace with actual URLs
        source_url = f"https://{item['source']}.com/{b.replace(' ','')}"
        sources[b].add(source_url)

for b, urls in sources.items():
    st.markdown(f"**{b}**")
    for url in urls:
        st.markdown(f"- [{url}]({url})")

# --------------------
# Report Generation
# --------------------
if st.button("Generate PDF Report"):
    md, pdf_bytes, json_summary = report_gen.generate_report(
        kpis=kpis,
        top_keywords=top_keywords,
        brand=brand,
        competitors=competitors,
        timeframe_hours=hours,
        include_json=True
    )
    st.download_button("Download PDF", data=pdf_bytes, file_name=f"{brand}_report.pdf", mime="application/pdf")
