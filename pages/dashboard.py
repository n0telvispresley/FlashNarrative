# pages/dashboard.py
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

# Add flashnarrative folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import analysis
import report_gen

nltk.download('punkt', quiet=True)

# --- Session state setup ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.error("Please log in first.")
    st.stop()

for key in ['data', 'kpis', 'top_keywords', 'md', 'pdf_bytes']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'top_keywords' else []

# --- Dashboard UI ---
st.title("Flash Narrative Dashboard")

brand = st.text_input("Brand Name", value="MyBrand")
competitors_input = st.text_area("Competitor Brands (comma-separated)", value="Competitor1,Competitor2")
competitors = [c.strip() for c in competitors_input.split(',') if c.strip()]

campaign_input = st.text_area("Campaign Messages (comma-separated)", value="Message1,Message2")
campaign_messages = [m.strip() for m in campaign_input.split(',') if m.strip()]

time_frame = st.slider("Time Frame (hours)", 1, 48, 24)
industry = st.selectbox("Industry", ["Tech", "Finance", "Healthcare", "Retail"])

# --- Analyze Button ---
if st.button("Analyze"):
    try:
        # Fetch data
        from scraper import fetch_all
        data = fetch_all(brand, time_frame, competitors)
        st.session_state['data'] = data

        mentions = [item.get('text', '') for item in data.get('full_data', [])]
        sentiment_counts, tones = analysis.analyze_sentiment(mentions)
        top_keywords = analysis.extract_keywords(' '.join(mentions))
        st.session_state['top_keywords'] = top_keywords

        kpis = analysis.compute_kpis(
            full_data=data.get('full_data', []),
            tones=tones,
            campaign_messages=campaign_messages,
            industry=industry,
            hours=time_frame,
            brand=brand
        )
        st.session_state['kpis'] = kpis
        st.success("Analysis complete!")

    except Exception as e:
        st.error("Analysis error:")
        st.error(traceback.format_exc())

# --- Display KPIs & Charts ---
if st.session_state['kpis']:
    kpis = st.session_state['kpis']
    st.subheader("Key Metrics")
    col1, col2 = st.columns(2)

    with col1:
        st.metric("MIS", kpis['mis'])
        st.metric("MPI", round(kpis['mpi'], 2))
        st.metric("Engagement Rate", round(kpis['engagement_rate'], 2))
        st.metric("Reach/Impressions", kpis['reach'])
        st.metric("Brand Sentiment (%)", round(kpis['small_brand_sentiment'], 2))

        # Sentiment Pie Chart
        sentiment_df = pd.DataFrame(list(kpis['sentiment_ratio'].items()), columns=['Tone', 'Percentage'])
        fig_pie = px.pie(sentiment_df, names='Tone', values='Percentage', title='Sentiment Ratio')
        st.plotly_chart(fig_pie)

    with col2:
        # Share of Voice (SOV)
        all_brands = [brand] + competitors
        sov_values = kpis.get('sov', [0]*len(all_brands))
        # Ensure length match
        if len(sov_values) < len(all_brands):
            sov_values += [0]*(len(all_brands)-len(sov_values))
        sov_df = pd.DataFrame({'Brand': all_brands, 'SOV': sov_values})
        st.subheader("Share of Voice")
        st.table(sov_df)

        # Top Keywords
        st.subheader("Top Keywords / Themes")
        if top_keywords:
            kw_df = pd.DataFrame(top_keywords, columns=['Keyword', 'Frequency'])
            st.table(kw_df)

# --- PDF Report ---
if st.session_state['kpis'] and st.button("Generate PDF Report"):
    try:
        md, pdf_bytes = report_gen.generate_report(
            kpis=kpis,
            top_keywords=st.session_state['top_keywords'],
            brand=brand,
            competitors=competitors,
            timeframe_hours=time_frame
        )
        st.session_state['md'] = md
        st.session_state['pdf_bytes'] = pdf_bytes
        st.download_button(
            label="Download PDF Report",
            data=st.session_state['pdf_bytes'],
            file_name=f"{brand}_report.pdf",
            mime="application/pdf"
        )
        st.markdown(md)
    except Exception as e:
        st.error(f"PDF generation failed: {e}")

# --- Refresh Button ---
if st.button("Refresh"):
    st.session_state['data'] = None
    st.session_state['kpis'] = None
    st.session_state['top_keywords'] = []
    st.session_state['md'] = ""
    st.session_state['pdf_bytes'] = b""
    st.experimental_rerun()
