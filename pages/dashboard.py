# pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import traceback
from dotenv import load_dotenv

# --- IMPORTANT: Use relative imports from the root ---
# Load .env first, *then* import other modules
load_dotenv() 
import analysis
import report_gen
import bedrock 
import servicenow_integration

import scraper

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
                item['sentiment'] = bedrock.get_llm_sentiment(item.get('text', ''))
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
        # Sentiment Pie
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
                         color='Sentiment', color_discrete_map=color_map)
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
    if st.button("Generate PDF Report", use_container_width=True):
        with st.spinner("Building your PDF report..."):
            try:
                md, pdf_bytes = report_gen.generate_report(
                    kpis=st.session_state.kpis,
                    top_keywords=st.session_state.top_keywords,
                    full_articles_data=st.session_state.full_data,
                    brand=brand,
                    competitors=competitors,
                    timeframe_hours=time_range_text, # Pass "Last 7 days"
                    include_json=False
                )
                
                st.download_button(
                    "Download PDF Report", 
                    data=pdf_bytes, 
                    file_name=f"{brand}_FlashNarrative_Report.pdf", 
                    mime="application/pdf",
                    use_container_width=True
                )
                
                with st.expander("View AI Summary & Recommendations", expanded=True):
                    ai_summary = bedrock.generate_llm_report_summary(
                        st.session_state.kpis, 
                        st.session_state.top_keywords, 
                        st.session_state.full_data, 
                        brand
                    )
                    st.markdown(ai_summary)

            except Exception:
                st.error("Failed to generate PDF report:\n" + traceback.format_exc())

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
        
        run_analysis(brand, time_range_text, hours, competitors, industry, campaign_messages)

    # --- Display Results ---
    # This will now show the dashboard *after* the button is pressed and data is loaded
    display_dashboard(brand, competitors, time_range_text)

# This makes the script runnable
if __name__ == "__main__":
    main()
