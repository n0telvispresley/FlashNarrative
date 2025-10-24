# pages/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import traceback
from dotenv import load_dotenv

# Load .env variables at the top
load_dotenv() 

# --- IMPORTANT: Use relative imports from the root ---
# This assumes app.py is in the root and this is in pages/
# Remove the sys.path hack
import analysis
import report_gen
import scraper
import bedrock # <-- IMPORT YOUR AI
import servicenow_integration # For alerts

# --- Page Config & Auth Check ---
st.set_page_config(page_title="FlashNarrative Dashboard", layout="wide")

# Check login status
if not st.session_state.get('logged_in', False):
    st.error("You must be logged in to view this page.")
    st.page_link("app.py", label="Go to Login", icon="🔒")
    st.stop() # Stop execution if not logged in

st.title(f"FlashNarrative AI Dashboard")
st.markdown("Monitor brand perception in real-time.")

# --- Initialize Session State ---
# This holds our data between reruns
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
        ['default', 'tech', 'finance', 'healthcare', 'retail', 'personal brand'],
        index=0
    )

campaign_input = st.text_area(
    "Enter campaign messages (one per line, for MPI)",
    value="Just Do It\nAir Max Launch",
    height=100
)
campaign_messages = [c.strip() for c in campaign_input.split("\n") if c.strip()]

hours = st.slider("Select timeframe (hours)", min_value=1, max_value=48, value=24)

# --- The "Run" Button ---
if st.button("Run Analysis", type="primary", use_container_width=True):
    try:
        # 1. Scrape Data
        with st.spinner(f"Scraping the web for '{brand}' and competitors..."):
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
                # Call Bedrock for each item
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
        # Add brand to stop list
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
            # Send alerts
            servicenow_integration.send_alert(alert_msg, channel='#alerts', to_email='alerts@yourcompany.com')
            servicenow_integration.create_servicenow_ticket(f"PR Crisis Alert: {brand}", alert_msg, urgency='1', impact='1')

    except Exception:
        st.error("An error occurred during analysis:\n" + traceback.format_exc())

# --- Display KPIs (Only if data exists) ---
if st.session_state.kpis:
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
            # Define color map for AI tones
            color_map = {
                'positive': 'green',
                'appreciation': 'blue',
                'neutral': 'grey',
                'mixed': 'orange',
                'negative': 'red',
                'anger': 'darkred'
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

    # pages/dashboard.py

    # ... (inside the 'data_col2' block) ...
    with data_col2:
        # --- CHANGE THE TITLE ---
        st.markdown(f"**Recent Mentions (for {brand})**")
        
        if st.session_state.full_data:
            
            # --- ADD THIS FILTER ---
            # Filter the list to only show mentions of the main brand
            brand_mentions_only = [
                item for item in st.session_state.full_data 
                if brand.lower() in (mb.lower() for mb in item.get('mentioned_brands', []))
            ]
            
            display_data = []
            
            # --- CHANGE THIS LINE to use the new filtered list ---
            for item in brand_mentions_only[:20]: # Show top 20 of *brand* mentions
                display_data.append({
                    'Sentiment': item.get('sentiment', 'N/A'),
                    'Source': item.get('source', 'N/A'),
                    'Mention': item.get('text', '')[:100] + "...",
                    'Link': item.get('link', '#')
                })
            
            st.dataframe(
                pd.DataFrame(display_data),
    # ... (rest of the file is unchanged) ...,
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
                    full_articles_data=st.session_state.full_data, # <-- PASS FULL DATA
                    brand=brand,
                    competitors=competitors,
                    timeframe_hours=hours,
                    include_json=False # We don't need the JSON output here
                )
                
                st.download_button(
                    "Download PDF Report", 
                    data=pdf_bytes, 
                    file_name=f"{brand}_FlashNarrative_Report.pdf", 
                    mime="application/pdf",
                    use_container_width=True
                )
                
                # Show AI recommendations in an expander
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

else:
    st.info("Click 'Run Analysis' to load your brand data.")
