Okay, boss. Here's the updated `pages/dashboard.py` file with the email functionality integrated.

**Key Changes:**

1.  **Email Input:** Added `st.text_input` for the recipient's email address under the "Generate Report" subheader.
2.  **State Management:** Added session state variables (`pdf_report_bytes`, `excel_report_bytes`, `report_generated`) to store the generated files and track if generation was successful.
3.  **Generate Button:** Renamed the PDF button to "Generate Reports for Email/Download". Clicking this now:
      * Generates *both* the PDF and Excel bytes.
      * Stores them in `st.session_state`.
      * Sets `st.session_state.report_generated = True`.
4.  **Conditional Buttons:**
      * The individual **Download** buttons (PDF and Excel) now appear *only after* the "Generate Reports" button is clicked successfully (`st.session_state.report_generated is True`).
      * A new **"Email Generated Reports"** button also appears *only after* generation.
5.  **Email Logic:** Clicking the "Email Generated Reports" button:
      * Checks if an email address was entered.
      * Bundles the stored PDF and Excel bytes into the `attachments` list.
      * Calls `servicenow_integration.send_report_email_with_attachments`.
      * Shows success or error messages.
6.  **Reset State:** The "Run Analysis" button now resets the report generation state variables.

-----

### `pages/dashboard.py` (Updated with Email Sending)

```python
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
    # ... (Error handling and scraping logic remains the same) ...
    try:
        # 1. Scrape Data
        with st.spinner(f"Scraping the web for '{brand}' ({time_range_text})..."):
             scraped_data = scraper.fetch_all(...) # Pass args

        if not scraped_data['full_data']:
             st.warning("No mentions found...")
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
             # Update progress bar logic remains the same
             progress_percent = ((i + 1) / len(temp_data))
             progress_text = f"Analyzing sentiment ({progress_percent * 100:.0f}%)..."
             if llm_failed_count > 0:
                 progress_text += f" (LLM errors: {llm_failed_count})"
             progress_bar.progress(progress_percent, text=progress_text)

        progress_bar.empty()
        st.session_state.full_data = temp_data

        if llm_failed_count > 0:
             st.warning(f"⚠️ Could not connect to the AI...") # Warning message

        # 3. Compute KPIs (remains the same)
        with st.spinner("Calculating KPIs..."):
             st.session_state.kpis = analysis.compute_kpis(...) # Pass args

        # 4. Extract Keywords/Phrases (remains the same)
        all_text = " ".join(...)
        # Stop words logic...
        st.session_state.top_keywords = analysis.extract_keywords(all_text, top_n=10)

        st.success("Analysis complete!")

        # 5. Check for Alerts (remains the same)
        # Alert logic...

    except Exception:
        st.error("An error occurred during analysis:\n" + traceback.format_exc())

def display_dashboard(brand, competitors, time_range_text):
    """
    This function displays KPIs, charts, tables, and report generation/sending options.
    """
    if not st.session_state.kpis:
        st.info("Click 'Run Analysis' to load your brand data.")
        return

    # --- Display KPIs (remains the same) ---
    st.subheader("Key Performance Indicators")
    # ... (KPI display logic) ...

    # --- Charts (Vertical Layout - remains the same) ---
    st.subheader("Visual Analysis")
    # ... (Sentiment Doughnut logic) ...
    # ... (SOV Bar Chart logic) ...

    # --- Data Tables (Vertical Layout - remains the same) ---
    st.subheader("Detailed Mentions")
    # ... (Keywords/Phrases table logic) ...
    # ... (Recent Mentions table logic) ...

    # --- Report Generation & Sending ---
    st.subheader("Generate & Send Report")

    # --- Email Input ---
    recipient_email = st.text_input("Enter Email to Send Reports To:",
                                    placeholder="your.email@example.com",
                                    key="recipient_email_input")

    # --- Generate Button ---
    if st.button("Generate Reports for Email/Download", use_container_width=True, key="generate_reports"):
        if not st.session_state.kpis or not st.session_state.full_data:
             st.warning("Please run analysis first to generate data for the report.")
             st.session_state.report_generated = False # Ensure flag is false
        else:
             st.session_state.report_generated = False # Reset flag initially
             pdf_generated = False
             excel_generated = False

             # Generate PDF
             with st.spinner("Building PDF report..."):
                 try:
                     ai_summary = bedrock_llm.generate_llm_report_summary(
                          st.session_state.kpis,
                          st.session_state.top_keywords,
                          st.session_state.full_data,
                          brand
                     )
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
                     st.session_state.ai_summary_text = ai_summary # Store summary for email body
                     pdf_generated = True
                 except Exception:
                     st.error("Failed to generate PDF report:\n" + traceback.format_exc())

             # Generate Excel
             with st.spinner("Building Excel mentions file..."):
                 try:
                     excel_data = []
                     for item in st.session_state.full_data:
                         excel_data.append({
                             'Date': item.get('date', 'N/A'), 'Sentiment': item.get('sentiment', 'N/A'),
                             'Source': item.get('source', 'N/A'), 'Mention Text': item.get('text', ''),
                             'Link': item.get('link', '#'), 'Likes': item.get('likes', 0),
                             'Comments': item.get('comments', 0)
                         })
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
                      st.markdown(st.session_state.ai_summary_text)
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

        with col_email:
             # Get email from state if it exists, otherwise from input
             email_to_send = st.session_state.get("recipient_email_input", "")
             if not email_to_send:
                 st.button("Email Generated Reports", disabled=True, use_container_width=True, help="Enter recipient email above.")
             elif st.button("Email Generated Reports", use_container_width=True, key="email_reports"):
                 if not st.session_state.get('pdf_report_bytes') or not st.session_state.get('excel_report_bytes'):
                      st.error("Cannot email reports. Generation failed or files missing.")
                 else:
                      with st.spinner(f"Sending reports to {email_to_send}..."):
                           # Prepare attachments list
                           attachments = [
                               (f"{brand}_FlashNarrative_Report.pdf", st.session_state.pdf_report_bytes, 'application/pdf'),
                               (f"{brand}_FlashNarrative_Mentions.xlsx", st.session_state.excel_report_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                           ]
                           subject = f"FlashNarrative Report for {brand} ({time_range_text})"
                           # Use stored AI summary in body
                           ai_summary = st.session_state.get("ai_summary_text", "AI Summary could not be generated.")
                           body = f"Please find attached the FlashNarrative reports for {brand} covering {time_range_text}.\n\nAI Summary:\n{ai_summary}"

                           sent = servicenow_integration.send_report_email_with_attachments(
                               email_to_send, subject, body, attachments
                           )
                           if sent:
                               st.success(f"Reports emailed successfully to {email_to_send}!")
                           else:
                               st.error("Failed to send email. Check logs and .env SMTP settings.")


def main():
    """
    Main function to run the Streamlit app.
    """
    st.set_page_config(page_title="FlashNarrative Dashboard", layout="wide")

    # Auth Check
    if not st.session_state.get('logged_in', False):
        st.error("You must be logged in...")
        st.page_link("app.py", label="Go to Login", icon="🔒")
        st.stop()

    st.title(f"FlashNarrative AI Dashboard")
    st.markdown("Monitor brand perception in real-time.")

    # Initialize Session State
    if 'full_data' not in st.session_state:
        st.session_state.full_data = []
    if 'kpis' not in st.session_state:
        st.session_state.kpis = {}
    if 'top_keywords' not in st.session_state:
        st.session_state.top_keywords = []
    # Add state for report generation/download/email
    if 'report_generated' not in st.session_state:
        st.session_state.report_generated = False
    if 'pdf_report_bytes' not in st.session_state:
        st.session_state.pdf_report_bytes = None
    if 'excel_report_bytes' not in st.session_state:
        st.session_state.excel_report_bytes = None
    if 'ai_summary_text' not in st.session_state:
        st.session_state.ai_summary_text = ""


    # Inputs
    st.subheader("Monitoring Setup")
    col_i1, col_i2, col_i3 = st.columns(3)

    with col_i1:
        brand = st.text_input("Enter your brand name", value="Nike")
    with col_i2:
        competitors_input = st.text_input("Enter competitors (comma-separated)", value="Adidas, Puma")
        competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]
    with col_i3:
        industry = st.selectbox("Select Industry (for better RSS results)",
                                ['default', 'Personal Brand', 'tech', 'finance', 'healthcare', 'retail'], index=0,
                                help="Select 'Personal Brand' or 'default' if searching for a person.")

    campaign_input = st.text_area("Enter campaign messages (one per line, for MPI)",
                                  value="Just Do It\nAir Max Launch", height=100)
    campaign_messages = [c.strip() for c in campaign_input.split("\n") if c.strip()]

    time_range_text = st.selectbox("Select time frame",
                                   options=["Last 24 hours", "Last 48 hours", "Last 7 days", "Last 30 days (Max)"], index=0,
                                   help="News & blog APIs are typically limited to 30 days of history.")
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

# This makes the script runnable
if __name__ == "__main__":
    main()
```
