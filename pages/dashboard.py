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
import smtplib
from email.mime.text import MIMEText
from slack_sdk import WebClient

# Clean sys.path to remove duplicates and add project root
sys.path = list(dict.fromkeys(sys.path))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Debug: Print sys.path and working directory
st.write(f"sys.path: {sys.path}")
st.write(f"Working directory: {os.getcwd()}")
st.write(f"Current file dir: {os.path.abspath(os.path.dirname(__file__))}")

# Debug: List directory structure
st.subheader("Project Directory Structure")
def list_directory(path, indent=""):
    result = []
    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                result.append(f"{indent}📁 {item}/")
                result.extend(list_directory(item_path, indent + "  "))
            else:
                result.append(f"{indent}📄 {item}")
    except Exception as e:
        result.append(f"{indent}Error listing directory {path}: {e}")
    return result

structure = list_directory(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
st.write("\n".join(structure))

# Module import status
module_status = {}
try:
    from scraper import fetch_all
    st.write("scraper.py: fetch_all imported successfully")
    module_status["scraper"] = True
except Exception as e:
    st.error(f"Error importing scraper.py: {e}")
    module_status["scraper"] = False

try:
    from analysis import analyze_sentiment, compute_kpis, extract_keywords
    st.write("analysis.py imported successfully")
    module_status["analysis"] = True
except Exception as e:
    st.error(f"Error importing analysis.py: {e}")
    module_status["analysis"] = False

try:
    from report_gen import generate_report
    st.write("report_gen.py imported successfully")
    module_status["report_gen"] = True
except Exception as e:
    st.error(f"Error importing report_gen.py: {e}")
    module_status["report_gen"] = False

try:
    from servicenow_integration import create_servicenow_ticket
    st.write("servicenow_integration.py imported successfully")
    module_status["servicenow_integration"] = True
except Exception as e:
    st.error(f"Error importing servicenow_integration.py: {e}")
    module_status["servicenow_integration"] = False

# Initialize NLTK
try:
    os.environ['NLTK_DATA'] = '/mount/src/flashnarrative/nltk_data'
    nltk.download('punkt_tab', quiet=True, download_dir='/mount/src/flashnarrative/nltk_data')
except Exception as e:
    st.warning(f"NLTK setup failed: {e}")

# Check login
if not st.session_state.get('logged_in', False):
    st.error("Please log in first.")
    st.switch_page("pages/landing.py")

# Session state
if 'data' not in st.session_state: st.session_state['data'] = None
if 'kpis' not in st.session_state: st.session_state['kpis'] = None
if 'top_keywords' not in st.session_state: st.session_state['top_keywords'] = []
if 'md' not in st.session_state: st.session_state['md'] = ""
if 'pdf_bytes' not in st.session_state: st.session_state['pdf_bytes'] = b""

# Dashboard UI
st.title("Flash Narrative Dashboard")
brand = st.text_input("Brand Name", value="MyBrand")
time_frame = st.slider("Time Frame (hours)", 1, 48, 24)
industry = st.selectbox("Industry", ["Tech", "Finance", "Healthcare", "Retail"])
competitors = st.multiselect("Competitors (up to 3)", ["Competitor1", "Competitor2", "Competitor3"], max_selections=3)
campaign_messages = st.text_area("Campaign Messages for MPI", value="Message1,Message2")

# Analyze button
if st.button("Analyze"):
    if not module_status.get("scraper", False) or not module_status.get("analysis", False):
        st.error("Cannot analyze: scraper.py or analysis.py failed to import.")
    else:
        try:
            data = fetch_all(brand, time_frame, competitors)
            st.session_state['data'] = data
            
            mentions = [item['text'] for item in data['full_data']]
            sentiments, tones = analyze_sentiment(mentions)
            st.session_state['top_keywords'] = extract_keywords(' '.join(mentions))
            
            # Compute KPIs
            kpis = compute_kpis(
                data['full_data'],
                tones,
                [msg.strip() for msg in campaign_messages.split(',')],
                industry,
                hours=time_frame,
                brand=brand
            )
            st.session_state['kpis'] = kpis

            # Alerts
            if module_status.get("servicenow_integration", False):
                neg_ratio = kpis['sentiment_ratio'].get('negative', 0)
                if neg_ratio > 50 or any('nytimes.com' in m['source'] for m in data['full_data'] if m.get('sentiment') == 'negative'):
                    try:
                        create_servicenow_ticket("PR Crisis Alert", "Negative spike or high-priority mention detected.")
                        st.success("Alert sent (check console for mock).")
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
        sentiment_df = pd.DataFrame(list(kpis['sentiment_ratio'].items()), columns=['Tone', 'Percentage'])
        st.plotly_chart(px.pie(sentiment_df, values='Percentage', names='Tone', title='Sentiment Ratio'))

        # Use brand list stored in KPIs
        brands = kpis.get('all_brands', [brand] + competitors)
        sov_values = kpis.get('sov', [0]*len(brands))
        sov_df = pd.DataFrame({'Brand': brands, 'SOV': sov_values})
        st.plotly_chart(px.bar(sov_df, x='Brand', y='SOV', title='Share of Voice'))

    with col2:
        st.subheader("Key Metrics")
        st.metric("MIS", kpis['mis'])
        st.metric("MPI", kpis['mpi'])
        st.metric("Engagement Rate", kpis['engagement_rate'])
        st.metric("Reach/Impressions", kpis['reach'])
        st.metric("Brand Sentiment", f"{kpis['small_brand_sentiment']:.2f}%")

        st.subheader("Top Keywords")
        if st.session_state['top_keywords']:
            st.table(pd.DataFrame(st.session_state['top_keywords'], columns=['Keyword', 'Frequency']))

# PDF Report
if st.button("Generate PDF Report"):
    if not module_status.get("report_gen", False):
        st.error("Cannot generate report: report_gen.py failed to import.")
    else:
        try:
            md, pdf_bytes = generate_report(
                kpis,
                st.session_state['top_keywords'],
                brand,
                competitors
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
    st.session_state['data'] = None
    st.session_state['kpis'] = None
    st.session_state['top_keywords'] = []
    st.session_state['md'] = ""
    st.session_state['pdf_bytes'] = b""
    st.experimental_rerun()
