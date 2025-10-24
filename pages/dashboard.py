import streamlit as st
import sys
import os
import traceback
import pandas as pd
import plotly.express as px
import nltk
from analysis import analyze_sentiment, compute_kpis, extract_keywords
from scraper import fetch_all
from report_gen import generate_report
from servicenow_integration import create_servicenow_ticket

# Clean sys.path
sys.path = list(dict.fromkeys(sys.path))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# NLTK setup
os.environ['NLTK_DATA'] = '/mount/src/flashnarrative/nltk_data'
nltk.download('punkt_tab', quiet=True, download_dir='/mount/src/flashnarrative/nltk_data')

# Check login
if not st.session_state.get('logged_in', False):
    st.error("Please log in first.")
    st.switch_page("pages/landing.py")

# Initialize session state
for key in ['data', 'kpis', 'top_keywords', 'md', 'pdf_bytes']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'top_keywords' else []

st.title("Flash Narrative Dashboard")

# Inputs
brand = st.text_input("Brand Name", value="MyBrand")
time_frame = st.slider("Time Frame (hours)", 1, 48, 24)
industry = st.selectbox("Industry", ["Tech", "Finance", "Healthcare", "Retail"])
competitors_input = st.text_area("Competitor Brands (comma-separated)", value="Competitor1,Competitor2")
competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]
campaign_messages_input = st.text_area("Campaign Messages (comma-separated)", value="Message1,Message2")
campaign_messages = [m.strip() for m in campaign_messages_input.split(",") if m.strip()]

# Analyze button
if st.button("Analyze"):
    try:
        # Fetch data
        data = fetch_all(brand, time_frame, competitors)
        full_data = data.get('full_data', [])
        st.session_state['data'] = full_data

        # Analyze sentiment
        mentions = [item.get('text', '') for item in full_data]
        sentiments, tones = analyze_sentiment(mentions)

        # Add sentiment to each item to prevent KeyError
        for i, item in enumerate(full_data):
            item['sentiment'] = tones[i] if i < len(tones) else 'neutral'

        # Extract keywords
        all_text = ' '.join(mentions)
        st.session_state['top_keywords'] = extract_keywords(all_text)

        # Compute KPIs
        kpis = compute_kpis(
            full_data,
            tones,
            campaign_messages,
            industry,
            hours=time_frame,
            brand=brand
        )
        st.session_state['kpis'] = kpis

        # Alerts
        if (kpis['sentiment_ratio'].get('negative', 0) > 50 and create_servicenow_ticket):
            create_servicenow_ticket("PR Crisis Alert", "Negative spike detected.")

        st.success("Analysis complete!")

    except Exception as e:
        st.error(f"Analysis error: {e}")
        st.exception(traceback.format_exc())

# Display KPIs
if st.session_state['kpis']:
    kpis = st.session_state['kpis']
    all_brands = kpis.get('all_brands', [brand] + competitors)
    sov_values = kpis.get('sov', [0]*len(all_brands))
    
    # Ensure lengths match
    if len(all_brands) != len(sov_values):
        min_len = min(len(all_brands), len(sov_values))
        all_brands = all_brands[:min_len]
        sov_values = sov_values[:min_len]

    col1, col2 = st.columns(2)
    with col1:
        # Sentiment Pie
        sentiment_df = pd.DataFrame(list(kpis['sentiment_ratio'].items()), columns=['Tone', 'Percentage'])
        fig_pie = px.pie(sentiment_df, values='Percentage', names='Tone', title='Sentiment Ratio')
        st.plotly_chart(fig_pie)

        # SOV Bar
        sov_df = pd.DataFrame({'Brand': all_brands, 'SOV': sov_values})
        fig_bar = px.bar(sov_df, x='Brand', y='SOV', title='Share of Voice')
        st.plotly_chart(fig_bar)

    with col2:
        st.subheader("Key Metrics")
        st.metric("MIS", kpis.get('mis', 0))
        st.metric("MPI", kpis.get('mpi', 0))
        st.metric("Engagement Rate", kpis.get('engagement_rate', 0))
        st.metric("Reach/Impressions", kpis.get('reach', 0))
        st.metric("Brand Sentiment", f"{kpis.get('small_brand_sentiment', 0):.2f}%")

        st.subheader("Top Keywords")
        if st.session_state['top_keywords']:
            st.table(pd.DataFrame(st.session_state['top_keywords'], columns=['Keyword', 'Frequency']))

# PDF Report
if st.button("Generate PDF Report"):
    try:
        md, pdf_bytes = generate_report(kpis, st.session_state['top_keywords'], brand, competitors)
        st.session_state['md'] = md
        st.session_state['pdf_bytes'] = pdf_bytes
        st.download_button(
            label="Download Report",
            data=st.session_state['pdf_bytes'],
            file_name=f"{brand}_report.pdf",
            mime="application/pdf"
        )
        st.markdown(st.session_state['md'])
    except Exception as e:
        st.error(f"PDF generation failed: {e}")
        st.exception(traceback.format_exc())

# Refresh button
if st.button("Refresh"):
    for key in ['data', 'kpis', 'top_keywords', 'md', 'pdf_bytes']:
        st.session_state[key] = None if key != 'top_keywords' else []
    st.experimental_rerun()
