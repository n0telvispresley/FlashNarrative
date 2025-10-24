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
    /* ... (Copy the full CSS string from above here) ... */
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
    This function runs when the user clicks the 'Run Analysis' button.
    It handles all scraping, AI analysis, and KPI calculation.
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

        # 2. AI Sentiment Analysis
        with st.spinner("Running AI sentiment analysis on results..."):
            temp_data = scraped_data['full_data']
            progress_bar = st.progress(0, text="Analyzing sentiment...")

            for i, item in enumerate(temp_data):
                # Use bedrock_llm alias here
                item['sentiment'] = bedrock_llm.get_llm_sentiment(item.get('text', ''))
                progress_bar.progress((i + 1) / len(temp_data), text=f"Analyzing: {item['text'][:50]}...")

            progress_bar.empty()
            st.session_state.full_data = temp_data # Save processed data

        # 3. Compute KPIs
        with st.spinner("Calculating KPIs..."):
            st.session_state.kpis = analysis.compute_kpis(
                full_data=st.session_state.full_data,
                campaign_messages=campaign_messages,
                industry=industry,
                hours=hours,
                brand=brand
            )

        # 4. Extract Keywords
        all_text = " ".join([item["text"] for item in st.session_state.full_data])
        # Ensure stop_words exists before adding
        if hasattr(analysis, 'stop_words') and isinstance(analysis.stop_words, set):
             analysis.stop_words.add(brand.lower())
             for c in competitors:
                 analysis.stop_words.add(c.lower())

        st.session_state.top_keywords = analysis.extract_keywords(all_text, top_n=10)

        st.success("Analysis complete!")

        # 5. Check for Alerts
        sentiment_ratio = st.session_state.kpis.get('sentiment_ratio', {})
        neg_pct = sentiment_ratio.get('negative', 0) + sentiment_ratio.get('anger', 0)
        if neg_pct > 30: # Crisis alert threshold
            alert_msg = f"CRISIS ALERT: High negative sentiment ({neg_pct:.1f}%) detected for {brand}."
            st.error(alert_msg)
            servicenow_integration.send_alert(alert_msg, channel='#alerts', to_email='alerts@yourcompany.com')
            servicenow_integration.create_servicenow_ticket(f"PR Crisis Alert: {brand}", alert_msg, urgency='1', impact='1')

    except Exception:
        st.error("An error occurred during analysis:\n" + traceback.format_exc())

def display_dashboard(brand, competitors, time_range_text):
    """
    This function displays all the KPIs, charts, and tables
    if the data exists in st.session_state.
    """
    if not st.session_state.kpis:
        st.info("Click 'Run Analysis' to load your brand data.")
        return

    # --- Display KPIs ---
    st.subheader("Key Performance Indicators")
    kpis = st.session_state.kpis

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Media Impact (MIS)", f"{kpis.get('mis', 0):.0f}")
    col2.metric("Message Penetration (MPI)", f"{kpis.get('mpi', 0):.1f}%")
    col3.metric("Avg. Social Engagement", f"{kpis.get('engagement_rate', 0):.1f}")
    col4.metric("Total Reach", f"{kpis.get('reach', 0):,}")

    # --- Charts ---
    st.subheader("Visual Analysis")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # Sentiment Pie (Doughnut)
        sentiment_ratio = kpis.get("sentiment_ratio", {})
        if sentiment_ratio:
            pie_data = pd.DataFrame({
                'Sentiment': list(sentiment_ratio.keys()),
                'Percent': list(sentiment_ratio.values())
            })
            color_map = {
                'positive': 'green', 'appreciation': 'blue',
                'neutral': 'grey', 'mixed': 'orange',
                'negative': 'red', 'anger': 'darkred'
            }
            fig = px.pie(pie_data, names='Sentiment', values='Percent', title="AI Sentiment Distribution",
                         color='Sentiment', color_discrete_map=color_map, hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No sentiment data to display.")

    with chart_col2:
        # SOV Bar Chart
        all_brands = kpis.get("all_brands", [brand] + competitors)
        sov_values = kpis.get("sov", [0] * len(all_brands))

        sov_df = pd.DataFrame({'Brand': all_brands, 'Share of Voice (%)': sov_values})
        fig_sov = px.bar(sov_df, x='Brand', y='Share of Voice (%)', title="Share of Voice (SOV)",
                         color='Brand')
        st.plotly_chart(fig_sov, use_container_width=True)

    # --- Data Tables ---
    st.subheader("Detailed Mentions")
    data_col1, data_col2 = st.columns(2)

    with data_col1:
        # Top Keywords
        st.markdown("**Top Keywords / Themes**")
        top_keywords = st.session_state.top_keywords
        if top_keywords:
            kw_df = pd.DataFrame(top_keywords, columns=['Keyword', 'Frequency'])
            st.dataframe(kw_df, use_container_width=True)
        else:
            st.write("- No keywords identified.")

    with data_col2:
        # Recent Mentions
        st.markdown("**Recent Mentions (All Brands)**")
        if st.session_state.full_data:
            display_data = []
            for item in st.session_state.full_data[:20]:
                display_data.append({
                    'Sentiment': item.get('sentiment', 'N/A'),
                    'Source': item.get('source', 'N/A'),
                    'Mention': item.get('text', '')[:100] + "...",
                    'Link': item.get('link', '#')
                })

            st.dataframe(
                pd.DataFrame(display_data),
                column_config={
                    "Link": st.column_config.LinkColumn("Link", display_text="Source Link")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.write("No mentions to display.")

    # --- Report Generation ---
    st.subheader("Generate Report")
    # Use columns for side-by-side download buttons
    pdf_col, excel_col = st.columns(2)

    with pdf_col:
        # Button to generate PDF (triggers the process)
        if st.button("Generate PDF Summary Report", use_container_width=True, key="generate_pdf"):
            with st.spinner("Building your PDF report..."):
                try:
                    # Check if data exists before generating
                    if not st.session_state.kpis or not st.session_state.full_data:
                        st.warning("Please run analysis first to generate data for the report.")
                    else:
                        md, pdf_bytes = report_gen.generate_report(
                            kpis=st.session_state.kpis,
                            top_keywords=st.session_state.top_keywords,
                            full_articles_data=st.session_state.full_data,
                            brand=brand,
                            competitors=competitors,
                            timeframe_hours=time_range_text,
                            include_json=False
                        )

                        # Store PDF bytes in session state to enable download later
                        st.session_state.pdf_report_bytes = pdf_bytes
                        st.session_state.show_pdf_download = True

                        # Display AI Summary immediately after generation
                        with st.expander("View AI Summary & Recommendations", expanded=True):
                            ai_summary = bedrock_llm.generate_llm_report_summary(
                                 st.session_state.kpis,
                                 st.session_state.top_keywords,
                                 st.session_state.full_data,
                                 brand
                            )
                            st.markdown(ai_summary)
                        st.success("PDF Report Ready!")

                except Exception:
                    st.error("Failed to generate PDF report:\n" + traceback.format_exc())
                    st.session_state.show_pdf_download = False # Hide button on error

    # --- NEW: Excel File Generation & Download ---
    with excel_col:
        # Check if there's data to export
        if st.session_state.full_data:
            try:
                # Prepare data for Excel
                excel_data = []
                for item in st.session_state.full_data:
                    excel_data.append({
                        'Date': item.get('date', 'N/A'), # Add Date
                        'Sentiment': item.get('sentiment', 'N/A'),
                        'Source': item.get('source', 'N/A'),
                        'Mention Text': item.get('text', ''),
                        'Link': item.get('link', '#'),
                        'Likes': item.get('likes', 0), # Add Likes
                        'Comments': item.get('comments', 0) # Add Comments
                    })
                df_excel = pd.DataFrame(excel_data)

                # Convert DataFrame to Excel in memory
                output = io.BytesIO()
                # Requires: pip install openpyxl
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                     df_excel.to_excel(writer, index=False, sheet_name='Mentions')
                excel_bytes = output.getvalue()

                # Excel Download Button
                st.download_button(
                    label="Download All Mentions (Excel)",
                    data=excel_bytes,
                    file_name=f"{brand}_FlashNarrative_Mentions.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="excel_download"
                )
            except Exception as e:
                 st.error(f"Failed to generate Excel file: {e}")
                 st.button("Download All Mentions (Excel)", disabled=True, use_container_width=True, help="Error generating file.")

        else:
             # Disable button if no data
             st.button("Download All Mentions (Excel)", disabled=True, use_container_width=True, help="Run analysis first to generate data.")

    # --- Conditionally show PDF download button ---
    if st.session_state.get('show_pdf_download', False) and st.session_state.get('pdf_report_bytes'):
         st.download_button(
             label="Download PDF Summary Report",
             data=st.session_state.pdf_report_bytes,
             file_name=f"{brand}_FlashNarrative_Report.pdf",
             mime="application/pdf",
             use_container_width=True,
             key="pdf_download_final" # Use a different key
         )

def main():
    """
    Main function to run the Streamlit app.
    """
    st.set_page_config(page_title="FlashNarrative Dashboard", layout="wide")

    # --- Auth Check ---
    if not st.session_state.get('logged_in', False):
        st.error("You must be logged in to view this page.")
        st.page_link("app.py", label="Go to Login", icon="🔒")
        st.stop()

    st.title(f"FlashNarrative AI Dashboard")
    st.markdown("Monitor brand perception in real-time.")

    # --- Initialize Session State ---
    if 'full_data' not in st.session_state:
        st.session_state.full_data = []
    if 'kpis' not in st.session_state:
        st.session_state.kpis = {}
    if 'top_keywords' not in st.session_state:
        st.session_state.top_keywords = []
    # Add state for PDF download button visibility
    if 'show_pdf_download' not in st.session_state:
        st.session_state.show_pdf_download = False
    if 'pdf_report_bytes' not in st.session_state:
        st.session_state.pdf_report_bytes = None


    # --- Inputs ---
    st.subheader("Monitoring Setup")
    col_i1, col_i2, col_i3 = st.columns(3)

    with col_i1:
        brand = st.text_input("Enter your brand name", value="Nike")

    with col_i2:
        competitors_input = st.text_input(
            "Enter competitors (comma-separated)",
            value="Adidas, Puma"
        )
        competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]

    with col_i3:
        industry = st.selectbox(
            "Select Industry (for better RSS results)",
            ['default', 'Personal Brand', 'tech', 'finance', 'healthcare', 'retail'],
            index=0,
            help="Select 'Personal Brand' or 'default' if searching for a person."
        )

    campaign_input = st.text_area(
        "Enter campaign messages (one per line, for MPI)",
        value="Just Do It\nAir Max Launch",
        height=100
    )
    campaign_messages = [c.strip() for c in campaign_input.split("\n") if c.strip()]

    time_range_text = st.selectbox(
        "Select time frame",
        options=["Last 24 hours", "Last 48 hours", "Last 7 days", "Last 30 days (Max)"],
        index=0,
        help="News & blog APIs are typically limited to 30 days of history."
    )
    time_map = {
        "Last 24 hours": 24,
        "Last 48 hours": 48,
        "Last 7 days": 168,
        "Last 30 days (Max)": 720
    }
    hours = time_map[time_range_text]

    # --- Run Button ---
    if st.button("Run Analysis", type="primary", use_container_width=True):
        # Clear old data before running a new analysis
        st.session_state.full_data = []
        st.session_state.kpis = {}
        st.session_state.top_keywords = []
        st.session_state.show_pdf_download = False # Hide download button on new run
        st.session_state.pdf_report_bytes = None

        run_analysis(brand, time_range_text, hours, competitors, industry, campaign_messages)

    # --- Display Results ---
    # This will now show the dashboard *after* the button is pressed and data is loaded
    display_dashboard(brand, competitors, time_range_text)

# This makes the script runnable
if __name__ == "__main__":
    main()
