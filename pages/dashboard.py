# pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import traceback
from dotenv import load_dotenv
import io # <-- IMPORT IO FOR EXCEL
from collections import Counter # Import Counter for SOV recalc

# --- IMPORTANT: Use relative imports from the root ---
# Load .env first, *then* import other modules
load_dotenv()

# --- ADD CUSTOM CSS HERE ---
# Define your brand colors (adjust hex codes as needed)
GOLD = "#FFD700"
BLACK = "#000000"
BEIGE = "#F5F5DC"
DARK_BG = "#1E1E1E"
LIGHT_TEXT = "#EAEAEA"
# --- Add Threshold Colors ---
GREEN_BG = "#28a745"; RED_BG = "#dc3545"

custom_css = f"""
<style>
    /* Main App Background */
    .stApp {{ background-color: {DARK_BG}; color: {LIGHT_TEXT}; }}
    /* Sidebar */
    [data-testid="stSidebar"] > div:first-child {{ background-color: {BLACK}; border-right: 1px solid {GOLD}; }}
    [data-testid="stSidebar"] .st-emotion-cache-16txtl3 {{ color: {BEIGE}; }} /* Sidebar text */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {GOLD}; }} /* Sidebar headers */
    /* Main Content Headers */
    .stApp h1, .stApp h2, .stApp h3 {{ color: {GOLD}; }}
    /* Buttons */
    .stButton>button {{ background-color: {GOLD}; color: {BLACK}; border: 1px solid {GOLD}; border-radius: 5px; padding: 0.5em 1em; }}
    .stButton>button:hover {{ background-color: {BLACK}; color: {GOLD}; border: 1px solid {GOLD}; }}
    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {{ background-color: {DARK_BG}; color: {LIGHT_TEXT}; border: 1px solid {BEIGE}; border-radius: 5px; }}
    /* Selectbox */
    .stSelectbox div[data-baseweb="select"] > div {{ background-color: {DARK_BG}; color: {LIGHT_TEXT}; border: 1px solid {BEIGE}; }}
    /* Dataframes */
    .stDataFrame {{ border: 1px solid {BEIGE}; border-radius: 5px; }}
    .stDataFrame thead th {{ background-color: {BLACK}; color: {GOLD}; }}
    .stDataFrame tbody tr {{ background-color: {DARK_BG}; color: {LIGHT_TEXT}; }}
    .stDataFrame tbody tr:nth-child(even) {{ background-color: #2a2a2a; }}
    /* Expander */
    .streamlit-expanderHeader {{ background-color: {BLACK}; color: {GOLD}; border: 1px solid {GOLD}; border-radius: 5px; }}

    /* --- CSS for KPI Boxes --- */
    .kpi-box {{
        border: 1px solid {BEIGE};
        border-radius: 5px;
        padding: 15px;
        text-align: center;
        margin-bottom: 10px;
        background-color: {DARK_BG};
    }}
    .kpi-box .label {{
        font-size: 0.9em; color: {BEIGE}; margin-bottom: 5px; text-transform: uppercase;
        line-height: 1.2; height: 2.4em; display: flex; align-items: center; justify-content: center;
    }}
    .kpi-box .value {{ font-size: 1.5em; font-weight: bold; color: {LIGHT_TEXT}; }}
    .kpi-box.good {{ background-color: {GREEN_BG}; border-color: {GREEN_BG}; }}
    .kpi-box.good .label, .kpi-box.good .value {{ color: {BLACK}; }} /* Dark text on green */
    .kpi-box.bad {{ background-color: {RED_BG}; border-color: {RED_BG}; }}
    .kpi-box.bad .label, .kpi-box.bad .value {{ color: {LIGHT_TEXT}; }} /* Light text on red */
    /* --- END KPI Box CSS --- */
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


try:
    from .. import analysis
    from .. import report_gen
    from .. import scraper
    from .. import bedrock as bedrock_llm # Use alias for clarity
    from .. import servicenow_integration
except ImportError:
    import analysis, report_gen, scraper, bedrock as bedrock_llm, servicenow_integration


def run_analysis(brand, time_range_text, hours, competitors, industry, campaign_messages):
    """ Runs scraping, AI sentiment (with keyword fallback), and KPIs. """
    try:
        # 1. Scrape Data
        with st.spinner(f"Scraping the web for '{brand}' ({time_range_text})..."):
            scraped_data = scraper.fetch_all(brand=brand, time_frame=hours, competitors=competitors, industry=industry)
        if not scraped_data['full_data']:
            st.warning("No mentions found. Try a broader timeframe or different keywords."); st.stop()

        # 2. Sentiment Analysis with Fallback
        st.write("🧠 Performing Sentiment Analysis...")
        temp_data = scraped_data['full_data']
        progress_bar = st.progress(0, text="Analyzing sentiment (0%)...")
        llm_failed_count = 0
        for i, item in enumerate(temp_data):
            llm_sentiment = bedrock_llm.get_llm_sentiment(item.get('text', ''))
            item['sentiment'] = llm_sentiment if llm_sentiment is not None else analysis.analyze_sentiment_keywords(item.get('text', ''))
            if llm_sentiment is None: llm_failed_count += 1
            progress_percent = ((i + 1) / len(temp_data))
            progress_text = f"Analyzing sentiment ({progress_percent * 100:.0f}%)..." + (f" (LLM errors: {llm_failed_count})" if llm_failed_count > 0 else "")
            progress_bar.progress(progress_percent, text=progress_text)
        progress_bar.empty(); st.session_state.full_data = temp_data
        if llm_failed_count > 0: st.warning(f"⚠️ AI connection failed for {llm_failed_count}/{len(temp_data)} items. Used keyword fallback.")

        # 3. Compute KPIs
        with st.spinner("Calculating KPIs..."):
            st.session_state.kpis = analysis.compute_kpis(full_data=st.session_state.full_data, campaign_messages=campaign_messages, industry=industry, hours=hours, brand=brand)

        # 4. Extract Keywords/Phrases
        all_text = " ".join([item["text"] for item in st.session_state.full_data])
        if hasattr(analysis, 'stop_words') and isinstance(analysis.stop_words, set):
            analysis.stop_words.add(brand.lower()); [analysis.stop_words.add(c.lower()) for c in competitors]
        st.session_state.top_keywords = analysis.extract_keywords(all_text, top_n=10)

        st.success("Analysis complete!")

        # 5. Check for Alerts
        sentiment_ratio = st.session_state.kpis.get('sentiment_ratio', {})
        neg_pct = sentiment_ratio.get('negative', 0) + sentiment_ratio.get('anger', 0)
        if neg_pct > 30:
            alert_msg = f"CRISIS ALERT: High negative sentiment ({neg_pct:.1f}%) detected for {brand}."
            st.error(alert_msg)
            alert_email = os.getenv("ALERT_EMAIL", 'alerts@yourcompany.com') # Get alert email from .env or default
            servicenow_integration.send_alert(alert_msg, channel='#alerts', to_email=alert_email)
            servicenow_integration.create_servicenow_ticket(f"PR Crisis Alert: {brand}", alert_msg, urgency='1', impact='1')
    except Exception: st.error(f"An error occurred during analysis:\n{traceback.format_exc()}")


def display_dashboard(brand, competitors, time_range_text, thresholds): # <-- Added thresholds param
    """ Displays KPIs with conditional styling, charts, tables, and reports. """
    if not st.session_state.kpis:
        st.info("Click 'Run Analysis' to load your brand data."); return

    # --- Display KPIs with Threshold Styling ---
    st.subheader("Key Performance Indicators")
    kpis = st.session_state.kpis
    mis_val = kpis.get('mis', 0); mpi_val = kpis.get('mpi', 0)
    eng_val = kpis.get('engagement_rate', 0); reach_val = kpis.get('reach', 0)
    mpi_threshold = thresholds.get('mpi_good', 20); eng_threshold = thresholds.get('eng_good', 1.0)
    mpi_class = "good" if mpi_val >= mpi_threshold else "bad"
    eng_class = "good" if eng_val >= eng_threshold else "bad"
    mis_class = ""; reach_class = ""

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f'<div class="kpi-box {mis_class}"><div class="label">Media Impact (MIS)</div><div class="value">{mis_val:.0f}</div></div>', unsafe_allow_html=True)
    with col2: st.markdown(f'<div class="kpi-box {mpi_class}"><div class="label">Msg Penetration (MPI)</div><div class="value">{mpi_val:.1f}%</div></div>', unsafe_allow_html=True)
    with col3: st.markdown(f'<div class="kpi-box {eng_class}"><div class="label">Avg Social Engagement</div><div class="value">{eng_val:.1f}</div></div>', unsafe_allow_html=True)
    with col4: st.markdown(f'<div class="kpi-box {reach_class}"><div class="label">Total Reach</div><div class="value">{reach_val:,}</div></div>', unsafe_allow_html=True)
    st.caption(f"Thresholds (Good ≥) MPI: {mpi_threshold}% | Engagement: {eng_threshold}")

    # --- Charts (Vertical Layout) ---
    st.subheader("Visual Analysis")
    sentiment_ratio = kpis.get("sentiment_ratio", {})
    if sentiment_ratio:
        pie_data = pd.DataFrame({'Sentiment': list(sentiment_ratio.keys()), 'Percent': list(sentiment_ratio.values())})
        color_map = {'positive': 'green', 'appreciation': 'blue', 'neutral': 'grey', 'mixed': 'orange', 'negative': 'red', 'anger': 'darkred'}
        fig = px.pie(pie_data, names='Sentiment', values='Percent', title="AI Sentiment Distribution", color='Sentiment', color_discrete_map=color_map, hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else: st.write("No sentiment data.")

    all_brands = kpis.get("all_brands", [brand] + competitors)
    sov_values = kpis.get("sov", [])
    if len(sov_values) != len(all_brands): # Recalculate SOV mapping if needed
        brand_counts = Counter()
        for item in st.session_state.full_data:
             mentioned = item.get('mentioned_brands', []); present_brands = set()
             if isinstance(mentioned, list): present_brands.update(b for b in mentioned if b in all_brands)
             elif isinstance(mentioned, str) and mentioned in all_brands: present_brands.add(mentioned)
             for b in present_brands: brand_counts[b] += 1
        total_sov_mentions = sum(brand_counts.values())
        sov_values = [(brand_counts[b] / total_sov_mentions * 100) if total_sov_mentions > 0 else 0 for b in all_brands]
    sov_df = pd.DataFrame({'Brand': all_brands, 'Share of Voice (%)': sov_values})
    fig_sov = px.bar(sov_df, x='Brand', y='Share of Voice (%)', title="Share of Voice (SOV)", color='Brand')
    st.plotly_chart(fig_sov, use_container_width=True)

    # --- Data Tables (Vertical Layout) ---
    st.subheader("Detailed Mentions")
    st.markdown("**Top Keywords & Phrases**")
    top_keywords = st.session_state.top_keywords
    if top_keywords: st.dataframe(pd.DataFrame(top_keywords, columns=['Keyword/Phrase', 'Frequency']), use_container_width=True)
    else: st.write("- No keywords/phrases.")

    st.markdown("**Recent Mentions (All Brands)**")
    if st.session_state.full_data:
        display_data = [{'Sentiment': item.get('sentiment', 'N/A'), 'Source': item.get('source', 'N/A'), 'Mention': item.get('text', '')[:150]+"...", 'Link': item.get('link', '#')} for item in st.session_state.full_data[:30]]
        st.dataframe(pd.DataFrame(display_data), column_config={"Link": st.column_config.LinkColumn("Link", display_text="Source Link")}, use_container_width=True, hide_index=True)
    else: st.write("No mentions.")

    # --- Report Generation & Sending ---
    st.subheader("Generate & Send Report")
    recipient_email = st.text_input("Enter Email to Send Reports To:", placeholder="your.email@example.com", key="recipient_email_input")

    if st.button("Generate Reports for Email/Download", use_container_width=True, key="generate_reports"):
        if not st.session_state.kpis or not st.session_state.full_data:
            st.warning("Please run analysis first."); st.session_state.report_generated = False
        else:
            st.session_state.report_generated = False; pdf_generated = False; excel_generated = False; ai_summary = ""
            with st.spinner("Building PDF report..."):
                try:
                    # Pass competitors list to AI summary
                    ai_summary = bedrock_llm.generate_llm_report_summary(st.session_state.kpis, st.session_state.top_keywords, st.session_state.full_data, brand, competitors) # <-- Pass competitors
                    st.session_state.ai_summary_text = ai_summary
                    md, pdf_bytes = report_gen.generate_report(kpis=st.session_state.kpis, top_keywords=st.session_state.top_keywords, full_articles_data=st.session_state.full_data, brand=brand, competitors=competitors, timeframe_hours=time_range_text, include_json=False)
                    st.session_state.pdf_report_bytes = pdf_bytes; pdf_generated = True
                except Exception as e: st.error(f"Failed PDF: {e}\n{traceback.format_exc()}")
            with st.spinner("Building Excel mentions file..."):
                try:
                    excel_data = [{'Date': item.get('date', 'N/A'), 'Sentiment': item.get('sentiment', 'N/A'), 'Source': item.get('source', 'N/A'), 'Mention Text': item.get('text', ''), 'Link': item.get('link', '#'), 'Likes': item.get('likes', 0), 'Comments': item.get('comments', 0)} for item in st.session_state.full_data]
                    df_excel = pd.DataFrame(excel_data); output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer: df_excel.to_excel(writer, index=False, sheet_name='Mentions')
                    st.session_state.excel_report_bytes = output.getvalue(); excel_generated = True
                except Exception as e: st.error(f"Failed Excel: {e}")
            if pdf_generated and excel_generated:
                st.session_state.report_generated = True; st.success("Reports Generated!")
                with st.expander("View AI Summary & Recommendations", expanded=True): st.markdown(st.session_state.ai_summary_text)
            else: st.error("Report generation failed.")

    # Conditional Display of Download & Email Buttons
    if st.session_state.get('report_generated', False):
        st.markdown("---")
        col_dl_pdf, col_dl_excel, col_email = st.columns(3)
        with col_dl_pdf:
            if st.session_state.get('pdf_report_bytes'): st.download_button("Download PDF", st.session_state.pdf_report_bytes, f"{brand}_Report.pdf", "application/pdf", use_container_width=True, key="pdf_dl")
            else: st.button("Download PDF", disabled=True, use_container_width=True, help="PDF failed.")
        with col_dl_excel:
            if st.session_state.get('excel_report_bytes'): st.download_button("Download Excel", st.session_state.excel_report_bytes, f"{brand}_Mentions.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="excel_dl")
            else: st.button("Download Excel", disabled=True, use_container_width=True, help="Excel failed.")
        with col_email:
            email_to_send = st.session_state.get("recipient_email_input", "")
            files_ready = st.session_state.get('pdf_report_bytes') and st.session_state.get('excel_report_bytes')
            if not email_to_send: st.button("Email Reports", disabled=True, use_container_width=True, help="Enter email.")
            elif not files_ready: st.button("Email Reports", disabled=True, use_container_width=True, help="Files not ready.")
            elif st.button("Email Reports", use_container_width=True, key="email_reports"):
                with st.spinner(f"Sending to {email_to_send}..."):
                    attachments = [(f"{brand}_Report.pdf", st.session_state.pdf_report_bytes, 'application/pdf'), (f"{brand}_Mentions.xlsx", st.session_state.excel_report_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')]
                    subject = f"FlashNarrative Report: {brand} ({time_range_text})"
                    ai_summary_body = st.session_state.get("ai_summary_text", "(AI Summary failed)")
                    body = f"Attached: FlashNarrative reports for {brand} ({time_range_text}).\n\nAI Summary:\n{ai_summary_body}"
                    sent = servicenow_integration.send_report_email_with_attachments(email_to_send, subject, body, attachments)
                    # Add Notification
                    if sent: st.toast(f"✅ Reports emailed to {email_to_send}!", icon="🎉"); st.success(f"Emailed to {email_to_send}!")
                    else: st.toast("❌ Email failed. Check logs/settings.", icon="🔥"); st.error("Email failed. Check logs & .env (Use App Password?).")


def main():
    """ Main function to run the Streamlit app. """
    st.set_page_config(page_title="FlashNarrative Dashboard", layout="wide")

    if not st.session_state.get('logged_in', False):
        st.error("You must be logged in..."); st.page_link("app.py", label="Login", icon="🔒"); st.stop()

    st.title("FlashNarrative AI Dashboard")
    st.markdown("Monitor brand perception in real-time.")

    # Init State
    if 'full_data' not in st.session_state: st.session_state.full_data = []
    if 'kpis' not in st.session_state: st.session_state.kpis = {}
    if 'top_keywords' not in st.session_state: st.session_state.top_keywords = []
    if 'report_generated' not in st.session_state: st.session_state.report_generated = False
    if 'pdf_report_bytes' not in st.session_state: st.session_state.pdf_report_bytes = None
    if 'excel_report_bytes' not in st.session_state: st.session_state.excel_report_bytes = None
    if 'ai_summary_text' not in st.session_state: st.session_state.ai_summary_text = ""

    # --- KPI Threshold Inputs ---
    with st.sidebar:
        st.header("⚙️ Settings")
        st.subheader("KPI Thresholds (Good ≥)")
        # Use keys for number inputs to retain state
        mpi_thresh = st.number_input("Message Penetration (%)", min_value=0, max_value=100, value=20, step=5, key="mpi_thresh_input")
        eng_thresh = st.number_input("Avg. Social Engagement", min_value=0.0, value=1.0, step=0.1, format="%.1f", key="eng_thresh_input")
        thresholds = {"mpi_good": mpi_thresh, "eng_good": eng_thresh}

    # Inputs
    st.subheader("Monitoring Setup")
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1: brand = st.text_input("Brand Name", value="Nike", key="brand_input")
    with col_i2:
        competitors_input = st.text_input("Competitors (comma-separated)", value="Adidas, Puma", key="comp_input")
        competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]
    with col_i3: industry = st.selectbox("Industry", ['default', 'Personal Brand', 'tech', 'finance', 'healthcare', 'retail'], index=0, help="Affects RSS feed selection.", key="industry_select")

    campaign_input = st.text_area("Campaign Messages (one per line)", value="Just Do It\nAir Max Launch", height=100, key="campaign_input")
    campaign_messages = [c.strip() for c in campaign_input.split("\n") if c.strip()]
    time_range_text = st.selectbox("Time Frame", ["Last 24 hours", "Last 48 hours", "Last 7 days", "Last 30 days (Max)"], index=0, help="Max history depends on data sources.", key="time_select")
    time_map = {"Last 24 hours": 24, "Last 48 hours": 48, "Last 7 days": 168, "Last 30 days (Max)": 720}
    hours = time_map[time_range_text]

    # Run Button
    if st.button("Run Analysis", type="primary", use_container_width=True, key="run_analysis_button"):
        st.session_state.full_data = []; st.session_state.kpis = {}; st.session_state.top_keywords = []
        st.session_state.report_generated = False; st.session_state.pdf_report_bytes = None
        st.session_state.excel_report_bytes = None; st.session_state.ai_summary_text = ""
        run_analysis(brand, time_range_text, hours, competitors, industry, campaign_messages)

    # Display Results - Pass thresholds dictionary
    display_dashboard(brand, competitors, time_range_text, thresholds) # <-- Pass thresholds

if __name__ == "__main__":
    main()
