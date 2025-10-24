# pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import traceback
from dotenv import load_dotenv
import io # <-- IMPORT IO FOR EXCEL

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

custom_css = f"""
<style>
    /* ... (Your full CSS string) ... */
    .stApp {{ background-color: {DARK_BG}; color: {LIGHT_TEXT}; }}
    [data-testid="stSidebar"] > div:first-child {{ background-color: {BLACK}; border-right: 1px solid {GOLD}; }}
    [data-testid="stSidebar"] .st-emotion-cache-16txtl3 {{ color: {BEIGE}; }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {GOLD}; }}
    .stApp h1, .stApp h2, .stApp h3 {{ color: {GOLD}; }}
    .stButton>button {{ background-color: {GOLD}; color: {BLACK}; border: 1px solid {GOLD}; border-radius: 5px; padding: 0.5em 1em; }}
    .stButton>button:hover {{ background-color: {BLACK}; color: {GOLD}; border: 1px solid {GOLD}; }}
    .stTextInput input, .stTextArea textarea {{ background-color: {DARK_BG}; color: {LIGHT_TEXT}; border: 1px solid {BEIGE}; border-radius: 5px; }}
    .stSelectbox div[data-baseweb="select"] > div {{ background-color: {DARK_BG}; color: {LIGHT_TEXT}; border: 1px solid {BEIGE}; }}
    .stDataFrame {{ border: 1px solid {BEIGE}; border-radius: 5px; }}
    .stDataFrame thead th {{ background-color: {BLACK}; color: {GOLD}; }}
    .stDataFrame tbody tr {{ background-color: {DARK_BG}; color: {LIGHT_TEXT}; }}
    .stDataFrame tbody tr:nth-child(even) {{ background-color: #2a2a2a; }}
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{ color: {LIGHT_TEXT}; }}
    [data-testid="stMetricLabel"] {{ color: {BEIGE}; }}
    .streamlit-expanderHeader {{ background-color: {BLACK}; color: {GOLD}; border: 1px solid {GOLD}; border-radius: 5px; }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)
# --- END OF CSS INJECTION ---


try:
    from .. import analysis
    from .. import report_gen
    from .. import scraper
    from .. import bedrock as bedrock_llm # Use alias for clarity
    from .. import servicenow_integration
except ImportError:
    # Fallback for when script is run directly (less ideal)
    import analysis
    import report_gen
    import scraper
    import bedrock as bedrock_llm # Use alias for clarity
    import servicenow_integration


def run_analysis(brand, time_range_text, hours, competitors, industry, campaign_messages):
    """
    This function runs scraping, AI sentiment (with keyword fallback), and KPIs.
    """
    try:
        # 1. Scrape Data
        with st.spinner(f"Scraping the web for '{brand}' ({time_range_text})..."):
            scraped_data = scraper.fetch_all(
                brand=brand,
                time_frame=hours,
                competitors=competitors,
                industry=industry
            )

        if not scraped_data['full_data']:
            st.warning("No mentions found. Try a broader timeframe or different keywords.")
            st.stop()

        # 2. Sentiment Analysis with Fallback
        st.write("🧠 Performing Sentiment Analysis...")
        temp_data = scraped_data['full_data']
        progress_bar = st.progress(0, text="Analyzing sentiment (0%)...")
        llm_failed_count = 0

        for i, item in enumerate(temp_data):
            llm_sentiment = bedrock_llm.get_llm_sentiment(item.get('text', ''))
            if llm_sentiment is not None:
                item['sentiment'] = llm_sentiment
            else:
                item['sentiment'] = analysis.analyze_sentiment_keywords(item.get('text', ''))
                llm_failed_count += 1
            progress_percent = ((i + 1) / len(temp_data))
            progress_text = f"Analyzing sentiment ({progress_percent * 100:.0f}%)..."
            if llm_failed_count > 0:
                progress_text += f" (LLM errors: {llm_failed_count})"
            progress_bar.progress(progress_percent, text=progress_text)

        progress_bar.empty()
        st.session_state.full_data = temp_data

        if llm_failed_count > 0:
            st.warning(f"⚠️ Could not connect to the AI for {llm_failed_count}/{len(temp_data)} items. Used basic keyword analysis as a fallback.")

        # 3. Compute KPIs
        with st.spinner("Calculating KPIs..."):
            st.session_state.kpis = analysis.compute_kpis(
                full_data=st.session_state.full_data,
                campaign_messages=campaign_messages,
                industry=industry,
                hours=hours,
                brand=brand
            )

        # 4. Extract Keywords/Phrases
        all_text = " ".join([item["text"] for item in st.session_state.full_data])
        if hasattr(analysis, 'stop_words') and isinstance(analysis.stop_words, set):
            analysis.stop_words.add(brand.lower())
            for c in competitors:
                analysis.stop_words.add(c.lower())
        st.session_state.top_keywords = analysis.extract_keywords(all_text, top_n=10)

        st.success("Analysis complete!")

        # 5. Check for Alerts
        sentiment_ratio = st.session_state.kpis.get('sentiment_ratio', {})
        neg_pct = sentiment_ratio.get('negative', 0) + sentiment_ratio.get('anger', 0)
        if neg_pct > 30:
            alert_msg = f"CRISIS ALERT: High negative sentiment ({neg_pct:.1f}%) detected for {brand}."
            st.error(alert_msg)
            servicenow_integration.send_alert(alert_msg, channel='#alerts', to_email='alerts@yourcompany.com')
            servicenow_integration.create_servicenow_ticket(f"PR Crisis Alert: {brand}", alert_msg, urgency='1', impact='1')

    except Exception:
        st.error("An error occurred during analysis:\n" + traceback.format_exc())

def display_dashboard(brand, competitors, time_range_text):
    """
    Displays KPIs, charts, tables, and report generation/sending options.
    """
    if not st.session_state.kpis:
        st.info("Click 'Run Analysis' to load your brand data.")
        return

    # Display KPIs
    st.subheader("Key Performance Indicators")
    kpis = st.session_state.kpis
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Media Impact (MIS)", f"{kpis.get('mis', 0):.0f}")
    col2.metric("Message Penetration (MPI)", f"{kpis.get('mpi', 0):.1f}%")
    col3.metric("Avg. Social Engagement", f"{kpis.get('engagement_rate', 0):.1f}")
    col4.metric("Total Reach", f"{kpis.get('reach', 0):,}")

    # Charts (Vertical Layout)
    st.subheader("Visual Analysis")
    sentiment_ratio = kpis.get("sentiment_ratio", {})
    if sentiment_ratio:
        pie_data = pd.DataFrame({'Sentiment': list(sentiment_ratio.keys()), 'Percent': list(sentiment_ratio.values())})
        color_map = {'positive': 'green', 'appreciation': 'blue', 'neutral': 'grey', 'mixed': 'orange', 'negative': 'red', 'anger': 'darkred'}
        fig = px.pie(pie_data, names='Sentiment', values='Percent', title="AI Sentiment Distribution", color='Sentiment', color_discrete_map=color_map, hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No sentiment data to display.")

    all_brands = kpis.get("all_brands", [brand] + competitors)
    sov_values = kpis.get("sov", [0] * len(all_brands))
    sov_df = pd.DataFrame({'Brand': all_brands, 'Share of Voice (%)': sov_values})
    fig_sov = px.bar(sov_df, x='Brand', y='Share of Voice (%)', title="Share of Voice (SOV)", color='Brand')
    st.plotly_chart(fig_sov, use_container_width=True)

    # Data Tables (Vertical Layout)
    st.subheader("Detailed Mentions")
    st.markdown("**Top Keywords & Phrases**")
    top_keywords = st.session_state.top_keywords
    if top_keywords:
        kw_df = pd.DataFrame(top_keywords, columns=['Keyword/Phrase', 'Frequency'])
        st.dataframe(kw_df, use_container_width=True)
    else:
        st.write("- No keywords or phrases identified.")

    st.markdown("**Recent Mentions (All Brands)**")
    if st.session_state.full_data:
        display_data = [{'Sentiment': item.get('sentiment', 'N/A'), 'Source': item.get('source', 'N/A'), 'Mention': item.get('text', '')[:150] + "...", 'Link': item.get('link', '#')} for item in st.session_state.full_data[:30]]
        st.dataframe(pd.DataFrame(display_data), column_config={"Link": st.column_config.LinkColumn("Link", display_text="Source Link")}, use_container_width=True, hide_index=True)
    else:
        st.write("No mentions to display.")

    # --- Report Generation & Sending ---
    st.subheader("Generate & Send Report")
    recipient_email = st.text_input("Enter Email to Send Reports To:",
                                    placeholder="your.email@example.com",
                                    key="recipient_email_input") # Key helps retain value

    # Generate Button
    if st.button("Generate Reports for Email/Download", use_container_width=True, key="generate_reports"):
        if not st.session_state.kpis or not st.session_state.full_data:
            st.warning("Please run analysis first to generate data for the report.")
            st.session_state.report_generated = False # Ensure flag is false if no data
        else:
            st.session_state.report_generated = False # Reset flag initially
            pdf_generated = False
            excel_generated = False
            ai_summary = "" # Initialize ai_summary variable

            # Generate PDF
            with st.spinner("Building PDF report..."):
                try:
                    # Generate AI summary first
                    ai_summary = bedrock_llm.generate_llm_report_summary(
                         st.session_state.kpis,
                         st.session_state.top_keywords,
                         st.session_state.full_data,
                         brand
                    )
                    st.session_state.ai_summary_text = ai_summary # Store for later use

                    # Generate the PDF content
                    md, pdf_bytes = report_gen.generate_report(
                        kpis=st.session_state.kpis,
                        top_keywords=st.session_state.top_keywords,
                        full_articles_data=st.session_state.full_data,
                        brand=brand,
                        competitors=competitors,
                        timeframe_hours=time_range_text,
                        include_json=False
                    )
                    st.session_state.pdf_report_bytes = pdf_bytes
                    pdf_generated = True
                except Exception as e:
                    st.error(f"Failed to generate PDF report: {e}\n{traceback.format_exc()}")

            # Generate Excel
            with st.spinner("Building Excel mentions file..."):
                try:
                    excel_data = [{'Date': item.get('date', 'N/A'), 'Sentiment': item.get('sentiment', 'N/A'),
                                   'Source': item.get('source', 'N/A'), 'Mention Text': item.get('text', ''),
                                   'Link': item.get('link', '#'), 'Likes': item.get('likes', 0),
                                   'Comments': item.get('comments', 0)} for item in st.session_state.full_data]
                    df_excel = pd.DataFrame(excel_data)
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_excel.to_excel(writer, index=False, sheet_name='Mentions')
                    st.session_state.excel_report_bytes = output.getvalue()
                    excel_generated = True
                except Exception as e:
                    st.error(f"Failed to generate Excel file: {e}")

            # Set flag only if BOTH files generated successfully
            if pdf_generated and excel_generated:
                st.session_state.report_generated = True
                st.success("Reports Generated Successfully!")
                # Show AI summary immediately
                with st.expander("View AI Summary & Recommendations", expanded=True):
                    st.markdown(st.session_state.ai_summary_text) # Display stored summary
            else:
                st.error("Report generation failed. Please check errors above.")

    # --- Conditional Display of Download & Email Buttons ---
    if st.session_state.get('report_generated', False):
        st.markdown("---") # Separator
        col_dl_pdf, col_dl_excel, col_email = st.columns(3)

        with col_dl_pdf:
            if st.session_state.get('pdf_report_bytes'):
                st.download_button(
                    label="Download PDF Summary",
                    data=st.session_state.pdf_report_bytes,
                    file_name=f"{brand}_FlashNarrative_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_download"
                )
            else: # Disable if bytes aren't there
                 st.button("Download PDF Summary", disabled=True, use_container_width=True)


        with col_dl_excel:
            if st.session_state.get('excel_report_bytes'):
                st.download_button(
                    label="Download Mentions (Excel)",
                    data=st.session_state.excel_report_bytes,
                    file_name=f"{brand}_FlashNarrative_Mentions.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="excel_download"
                )
            else: # Disable if bytes aren't there
                 st.button("Download Mentions (Excel)", disabled=True, use_container_width=True)

        with col_email:
            # Use the value directly from the input field state
            email_to_send = st.session_state.get("recipient_email_input", "")
            if not email_to_send:
                st.button("Email Generated Reports", disabled=True, use_container_width=True, help="Enter recipient email above.")
            # Check if bytes exist before enabling email button
            elif not st.session_state.get('pdf_report_bytes') or not st.session_state.get('excel_report_bytes'):
                 st.button("Email Generated Reports", disabled=True, use_container_width=True, help="Report generation failed or files missing.")
            elif st.button("Email Generated Reports", use_container_width=True, key="email_reports"):
                 with st.spinner(f"Sending reports to {email_to_send}..."):
                     # Prepare attachments list
                     attachments = [
                         (f"{brand}_FlashNarrative_Report.pdf", st.session_state.pdf_report_bytes, 'application/pdf'),
                         (f"{brand}_FlashNarrative_Mentions.xlsx", st.session_state.excel_report_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                     ]
                     subject = f"FlashNarrative Report for {brand} ({time_range_text})"
                     # Use stored AI summary in body
                     ai_summary_body = st.session_state.get("ai_summary_text", "AI Summary could not be generated.")
                     body = f"Please find attached the FlashNarrative reports for {brand} covering {time_range_text}.\n\nAI Summary:\n{ai_summary_body}"

                     # Call the function and check its return value
                     sent = servicenow_integration.send_report_email_with_attachments(
                         email_to_send, subject, body, attachments
                     )
                     # Display success or error message *based on the return value*
                     if sent:
                         st.success(f"Reports emailed successfully to {email_to_send}!")
                     else:
                         # Use st.error HERE in the dashboard script
                         st.error("Failed to send email. Check logs and .env SMTP settings (use App Password for Gmail).")


def main():
    """ Main function to run the Streamlit app. """
    st.set_page_config(page_title="FlashNarrative Dashboard", layout="wide")

    if not st.session_state.get('logged_in', False):
        st.error("You must be logged in...")
        st.page_link("app.py", label="Go to Login", icon="🔒")
        st.stop()

    st.title("FlashNarrative AI Dashboard")
    st.markdown("Monitor brand perception in real-time.")

    # Initialize Session State
    if 'full_data' not in st.session_state: st.session_state.full_data = []
    if 'kpis' not in st.session_state: st.session_state.kpis = {}
    if 'top_keywords' not in st.session_state: st.session_state.top_keywords = []
    # Initialize report states
    if 'report_generated' not in st.session_state: st.session_state.report_generated = False
    if 'pdf_report_bytes' not in st.session_state: st.session_state.pdf_report_bytes = None
    if 'excel_report_bytes' not in st.session_state: st.session_state.excel_report_bytes = None
    if 'ai_summary_text' not in st.session_state: st.session_state.ai_summary_text = ""

    # Inputs
    st.subheader("Monitoring Setup")
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1: brand = st.text_input("Brand Name", value="Nike")
    with col_i2:
        competitors_input = st.text_input("Competitors (comma-separated)", value="Adidas, Puma")
        competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]
    with col_i3: industry = st.selectbox("Industry", ['default', 'Personal Brand', 'tech', 'finance', 'healthcare', 'retail'], index=0, help="Affects RSS feed selection.")

    campaign_input = st.text_area("Campaign Messages (one per line)", value="Just Do It\nAir Max Launch", height=100)
    campaign_messages = [c.strip() for c in campaign_input.split("\n") if c.strip()]
    time_range_text = st.selectbox("Time Frame", ["Last 24 hours", "Last 48 hours", "Last 7 days", "Last 30 days (Max)"], index=0, help="Max history depends on data sources.")
    time_map = {"Last 24 hours": 24, "Last 48 hours": 48, "Last 7 days": 168, "Last 30 days (Max)": 720}
    hours = time_map[time_range_text]

    # Run Button
    if st.button("Run Analysis", type="primary", use_container_width=True):
        # Clear old data AND report generation state
        st.session_state.full_data = []
        st.session_state.kpis = {}
        st.session_state.top_keywords = []
        st.session_state.report_generated = False # Reset flag
        st.session_state.pdf_report_bytes = None
        st.session_state.excel_report_bytes = None
        st.session_state.ai_summary_text = ""
        run_analysis(brand, time_range_text, hours, competitors, industry, campaign_messages)

    # Display Results
    display_dashboard(brand, competitors, time_range_text)

if __name__ == "__main__":
    main()

