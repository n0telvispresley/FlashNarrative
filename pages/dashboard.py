```python
import streamlit as st
import pandas as pd
import plotly.express as px
import nltk
from nltk.probability import FreqDist
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import smtplib
from email.mime.text import MIMEText
from slack_sdk import WebClient
import schedule
import time
from scraper import fetch_all  # Assumes this fetches data from sources with dummy fallback
from analysis import analyze_sentiment, compute_kpis  # Sentiment and KPI functions
from report_gen import generate_report_template  # Returns report text/template
from servicenow_integration import create_servicenow_ticket  # For crisis integration

# Ensure NLTK resources are downloaded (for MVP, assume local)
try:
    nltk.download('punkt', quiet=True)
except Exception as e:
    st.warning(f"NLTK download failed: {e}")

# Check if logged in, else redirect
if not st.session_state.get('logged_in', False):
    st.switch_page("pages/landing.py")

# Dashboard title
st.title("Flash Narrative Dashboard")

# UI Inputs
brand = st.text_input("Brand Name", value="MyBrand")
time_frame = st.slider("Time Frame (hours)", 1, 48, 24)
industry = st.selectbox("Industry", options=["Tech", "Finance", "Healthcare", "Retail"])
competitors = st.multiselect("Competitors (up to 3)", options=["Competitor1", "Competitor2", "Competitor3"], max_selections=3)
campaign_messages = st.text_area("Campaign Messages for MPI (comma-separated)", value="Message1,Message2")

# Session state for data persistence
if 'data' not in st.session_state:
    st.session_state['data'] = None
if 'kpis' not in st.session_state:
    st.session_state['kpis'] = None

# Analyze button
if st.button("Analyze"):
    try:
        # Fetch data
        data = fetch_all(brand, time_frame, competitors)  # Returns dict or DF; dummy if no data
        st.session_state['data'] = data
        
        # Analyze sentiment (keyword-based with tones: positive, negative, neutral, mixed, anger, appreciation)
        sentiments = analyze_sentiment(data['mentions'])  # Returns dict like {'positive': count, ...}
        
        # Extract keywords/themes with NLTK
        all_text = ' '.join(data['mentions'])
        tokens = nltk.word_tokenize(all_text.lower())
        freq_dist = FreqDist(tokens)
        top_keywords = freq_dist.most_common(10)
        
        # Compute KPIs
        kpis = compute_kpis(data, sentiments, campaign_messages.split(','), industry)  # Custom function
        st.session_state['kpis'] = kpis
        
        # Trigger alerts
        if kpis['sentiment_ratio']['negative'] > 50 or any('NYT' in m for m in data['mentions'] if sentiments[m] == 'negative'):
            # Email alert
            try:
                msg = MIMEText("Alert: Negative sentiment spike or high-priority mention!")
                msg['Subject'] = 'PR Alert'
                msg['From'] = 'alert@flashnarrative.com'
                msg['To'] = 'user@email.com'
                with smtplib.SMTP('localhost') as server:  # MVP local; replace with real SMTP
                    server.send_message(msg)
            except Exception as e:
                st.error(f"Email alert failed: {e}")
            
            # Slack alert
            try:
                client = WebClient(token="your-slack-token")  # Replace with env var
                client.chat_postMessage(channel="#pr-alerts", text="Alert: Negative sentiment spike!")
            except Exception as e:
                st.error(f"Slack alert failed: {e}")
            
            # ServiceNow for crises
            try:
                create_servicenow_ticket("PR Crisis Alert", "Negative spike detected")
            except Exception as e:
                st.error(f"ServiceNow integration failed: {e}")
        
        st.success("Analysis complete!")
    except Exception as e:
        st.error(f"Analysis error: {e}")

# Display KPIs if available
if st.session_state['kpis']:
    kpis = st.session_state['kpis']
    
    # Visualize in one-place dashboard
    col1, col2 = st.columns(2)
    
    with col1:
        # Sentiment Ratio Pie
        sentiment_df = pd.DataFrame(list(kpis['sentiment_ratio'].items()), columns=['Tone', 'Percentage'])
        fig_pie = px.pie(sentiment_df, values='Percentage', names='Tone', title='Sentiment Ratio')
        st.plotly_chart(fig_pie)
        
        # SOV Bar
        sov_df = pd.DataFrame({'Brand': [brand] + competitors, 'SOV': kpis['sov']})
        fig_bar_sov = px.bar(sov_df, x='Brand', y='SOV', title='Share of Voice')
        st.plotly_chart(fig_bar_sov)
    
    with col2:
        # Other KPIs
        st.subheader("Key Metrics")
        st.metric("MIS (Media Impact Score)", kpis['mis'])
        st.metric("MPI (Message Penetration Index)", kpis['mpi'])
        st.metric("Engagement Rate", kpis['engagement_rate'])
        st.metric("Reach/Impressions", kpis['reach'])
        
        # Keywords
        st.subheader("Top Keywords/Themes")
        keywords_df = pd.DataFrame(top_keywords, columns=['Keyword', 'Frequency'])
        st.table(keywords_df)
    
    # Generate PDF Report
    if st.button("Generate PDF Report"):
        try:
            report_text = generate_report_template(kpis, top_keywords)  # Returns string template
            pdf_buffer = io.BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=letter)
            c.drawString(100, 750, "Flash Narrative Report")
            textobject = c.beginText(100, 700)
            textobject.setFont("Helvetica", 12)
            for line in report_text.split('\n'):
                textobject.textLine(line)
            c.drawText(textobject)
            c.save()
            pdf_buffer.seek(0)
            st.download_button("Download PDF", pdf_buffer, file_name="report.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"PDF generation failed: {e}")

# Refresh button for real-time simulation
if st.button("Refresh"):
    st.rerun()  # Simulates real-time by rerunning app

# Scheduling for auto-refresh (MVP: run in loop, but Streamlit limits; use button for now)
# For production, use schedule in a thread
def auto_refresh():
    st.rerun()

# Comments for beginners:
# - This dashboard.py handles the main PR features post-login.
# - Inputs collect user params; Analyze fetches and processes data.
# - Use try/except for error-handling to make it robust.
# - Visuals use Plotly for interactive charts; KPIs computed in analysis.py (assume implemented).
# - Alerts trigger on conditions using email/Slack/ServiceNow.
# - PDF uses ReportLab for simple reports; download via buffer.
# - Dummy data in scraper ensures MVP works without real scraping.
# - Keep code modular; expand functions in separate files.
# - Total lines under 200 for focus on core.
```
