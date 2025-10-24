import streamlit as st
import pandas as pd
import plotly.express as px
import nltk
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import smtplib
from email.mime.text import MIMEText
from slack_sdk import WebClient
import schedule
import time
from scraper import fetch_all
from analysis import analyze_sentiment, compute_kpis
from report_gen import generate_report
from servicenow_integration import create_servicenow_ticket

# Initialize NLTK
try:
    nltk.download('punkt', quiet=True)
except Exception as e:
    st.warning(f"NLTK setup failed: {e}")

# Check login
if not st.session_state.get('logged_in', False):
    st.error("Please log in first.")
    st.switch_page("pages/landing.py")

# Dashboard UI
st.title("Flash Narrative Dashboard")

# Inputs
brand = st.text_input("Brand Name", value="MyBrand")
time_frame = st.slider("Time Frame (hours)", 1, 48, 24)
industry = st.selectbox("Industry", ["Tech", "Finance", "Healthcare", "Retail"])
competitors = st.multiselect("Competitors (up to 3)", ["Competitor1", "Competitor2", "Competitor3"], max_selections=3)
campaign_messages = st.text_area("Campaign Messages for MPI", value="Message1,Message2")

# Session state
if 'data' not in st.session_state:
    st.session_state['data'] = None
if 'kpis' not in st.session_state:
    st.session_state['kpis'] = None

# Analyze button
if st.button("Analyze"):
    try:
        # Fetch data
        data = fetch_all(brand, time_frame, competitors)
        st.session_state['data'] = data
        
        # Analyze sentiment
        sentiments, tones = analyze_sentiment(data['mentions'])
        
        # Extract keywords
        all_text = ' '.join(data['mentions'])
        top_keywords = nltk.FreqDist(nltk.word_tokenize(all_text.lower())).most_common(10)
        
        # Compute KPIs
        kpis = compute_kpis(data['full_data'], tones, campaign_messages.split(','), industry)
        st.session_state['kpis'] = kpis
        
        # Alerts
        if kpis['sentiment_ratio'].get('negative', 0) > 50 or any('nytimes.com' in m['source'] for m in data['full_data'] if m['sentiment'] == 'negative'):
            try:
                create_servicenow_ticket("PR Crisis Alert", "Negative spike or high-priority mention detected.")
                send_alert("Alert: Negative sentiment spike or high-priority mention!")
            except Exception as e:
                st.error(f"Alert failed: {e}")
        
        st.success("Analysis complete!")
    except Exception as e:
        st.error(f"Analysis error: {e}")

# Display KPIs
if st.session_state['kpis']:
    kpis = st.session_state['kpis']
    col1, col2 = st.columns(2)
    
    with col1:
        # Sentiment Pie
        sentiment_df = pd.DataFrame(list(kpis['sentiment_ratio'].items()), columns=['Tone', 'Percentage'])
        fig_pie = px.pie(sentiment_df, values='Percentage', names='Tone', title='Sentiment Ratio')
        st.plotly_chart(fig_pie)
        
        # SOV Bar
        sov_df = pd.DataFrame({'Brand': [brand] + competitors, 'SOV': kpis['sov']})
        fig_bar = px.bar(sov_df, x='Brand', y='SOV', title='Share of Voice')
        st.plotly_chart(fig_bar)
    
    with col2:
        st.subheader("Key Metrics")
        st.metric("MIS", kpis['mis'])
        st.metric("MPI", kpis['mpi'])
        st.metric("Engagement Rate", kpis['engagement_rate'])
        st.metric("Reach/Impressions", kpis['reach'])
        
        st.subheader("Top Keywords")
        st.table(pd.DataFrame(top_keywords, columns=['Keyword', 'Frequency']))
    
    # PDF Report
    if st.button("Generate PDF Report"):
        try:
            md, pdf_bytes = generate_report(kpis, top_keywords, brand, competitors)
            st.download_button("Download Report", pdf_bytes, file_name="report.pdf", mime="application/pdf")
            st.markdown(md)  # Show Markdown preview
        except Exception as e:
            st.error(f"PDF generation failed: {e}")

# Refresh button
if st.button("Refresh"):
    st.rerun()

# Comments:
# - Fixed missing io import for PDF.
# - Simplified imports to specific functions.
# - Robust error-handling for each block.
# - Alerts use servicenow_integration.py.
# - PDF report via generate_report (returns md, pdf_bytes).
# - Under 200 lines, beginner-friendly.
