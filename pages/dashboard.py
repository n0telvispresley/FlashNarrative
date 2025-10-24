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

# Import your modules
try:
    from scraper import fetch_all
except Exception as e:
    st.error(f"Error importing scraper.py: {e}")

try:
    from analysis import analyze_sentiment, compute_kpis, extract_keywords
except Exception as e:
    st.error(f"Error importing analysis.py: {e}")

try:
    from report_gen import generate_report
except Exception as e:
    st.error(f"Error importing report_gen.py: {e}")

# Initialize NLTK
try:
    nltk.download('punkt', quiet=True)
except Exception as e:
    st.warning(f"NLTK setup failed: {e}")

# Check login
if not st.session_state.get('logged_in', False):
    st.error("Please log in first.")
    st.stop()

# Initialize session state
for key in ['data', 'kpis', 'top_keywords', 'md', 'pdf_bytes']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'top_keywords' else []

# Dashboard UI
st.title("Flash Narrative Dashboard")

# Inputs
brand = st.text_input("Brand Name", value="MyBrand")
competitors_input = st.text_area("Competitor Brands (comma separated)")
competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]
campaign_messages_input = st.text_area("Campaign Messages (comma separated)")
campaign_messages = [m.strip() for m in campaign_messages_input.split(",") if m.strip()]
time_frame = st.slider("Time Frame (hours)", 1, 48, 24)
industry = st.selectbox("Industry", ["Tech", "Finance", "Healthcare", "Retail"])
enable_llm = st.checkbox("Enable AI Summary in Report")

# Dummy LLM summarizer for demo purposes
def llm_summarizer(kpis, top_keywords, competitors):
    summary = "This AI summary highlights key trends based on sentiment, engagement, and competitive analysis."
    neg_pct = kpis.get('sentiment_ratio', {}).get('negative', 0)
    if neg_pct > 50:
        summary += " High negative sentiment detected. Immediate PR action recommended."
    elif neg_pct > 30:
        summary += " Moderate negative sentiment observed. Monitor sources closely."
    return summary

# Analyze button
if st.button("Analyze"):
    try:
        # Fetch data
        data = fetch_all(brand, time_frame, competitors)
        st.session_state['data'] = data

        mentions = [item.get('text', '') for item in data.get('full_data', [])]
        sentiments, tones = analyze_sentiment(mentions)
        st.session_state['top_keywords'] = extract_keywords(" ".join(mentions))

        st.session_state['kpis'] = compute_kpis(
            data.get('full_data', []),
            tones,
            campaign_messages,
            industry,
            hours=time_frame,
            brand=brand
        )
        st.success("Analysis complete!")

    except Exception as e:
        st.error(f"Analysis failed: {e}")
        st.error(traceback.format_exc())

# Display KPIs and charts
if st.session_state['kpis']:
    kpis = st.session_state['kpis']
    col1, col2 = st.columns(2)

    with col1:
        sentiment_df = pd.DataFrame(list(kpis.get('sentiment_ratio', {}).items()), columns=['Tone', 'Percentage'])
        fig_pie = px.pie(sentiment_df, values='Percentage', names='Tone', title='Sentiment Ratio')
        st.plotly_chart(fig_pie)

        all_brands = [brand] + competitors
        sov_values = kpis.get('sov', [])
        if len(sov_values) < len(all_brands):
            sov_values += [0]*(len(all_brands)-len(sov_values))
        sov_df = pd.DataFrame({'Brand': all_brands, 'SOV': sov_values})
        fig_bar = px.bar(sov_df, x='Brand', y='SOV', title='Share of Voice')
        st.plotly_chart(fig_bar)

    with col2:
        st.subheader("Key Metrics")
        st.metric("MIS", kpis.get('mis', '-'))
        st.metric("MPI", kpis.get('mpi', '-'))
        st.metric("Engagement Rate", kpis.get('engagement_rate', '-'))
        st.metric("Reach/Impressions", kpis.get('reach', '-'))
        st.metric("Brand Sentiment", f"{kpis.get('small_brand_sentiment', 0):.2f}%")

        st.subheader("Top Keywords")
        if st.session_state['top_keywords']:
            st.table(pd.DataFrame(st.session_state['top_keywords'], columns=['Keyword', 'Frequency']))

# PDF Report
if st.button("Generate PDF Report"):
    if not st.session_state['kpis']:
        st.error("No KPIs available. Please run analysis first.")
    else:
        try:
            md, pdf_bytes = generate_report(
                st.session_state['kpis'],
                st.session_state['top_keywords'],
                brand=brand,
                competitors=competitors,
                timeframe_hours=time_frame,
                llm_summarizer=llm_summarizer if enable_llm else None
            )
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

# Refresh button
if st.button("Refresh"):
    for key in ['data', 'kpis', 'top_keywords', 'md', 'pdf_bytes']:
        st.session_state[key] = None if key != 'top_keywords' else []
    st.experimental_rerun()
