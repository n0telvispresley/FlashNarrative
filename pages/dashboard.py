# dashboard.py
import streamlit as st
import pandas as pd
import traceback
from flashnarrative import analysis, report_gen

st.set_page_config(page_title="Flash Narrative Dashboard", layout="wide")

st.title("Flash Narrative Dashboard")

# --- User Inputs ---
brand = st.text_input("Enter your brand name", "BrandX")
competitor_input = st.text_area("Enter competitor brands (comma-separated)", "")
competitors = [b.strip() for b in competitor_input.split(",") if b.strip()]

campaign_input = st.text_area("Enter your campaign messages (one per line)", "")
campaign_messages = [m.strip() for m in campaign_input.split("\n") if m.strip()]

hours = st.number_input("Analyze data from the last N hours", min_value=1, max_value=168, value=24)

# --- Mock / Loaded Data ---
# Replace with your actual data source
full_data = st.session_state.get('full_data', [])  # must be list of dicts with 'text', 'date', 'mentioned_brands', etc.

try:
    # --- Sentiment Analysis ---
    texts = [item.get('text','') for item in full_data]
    _, tones = analysis.analyze_sentiment(texts)

    # --- Compute KPIs ---
    kpis = analysis.compute_kpis(
        full_data=full_data,
        tones=tones,
        campaign_messages=campaign_messages,
        hours=hours,
        brand=brand
    )

    # --- SOV Table ---
    all_brands = [brand] + competitors
    sov_values = []
    for b in all_brands:
        try:
            idx = list(analysis.compute_kpis(full_data, tones, campaign_messages, hours=hours, brand=b)['sov'])
            sov_values.append(idx[0] if idx else 0)
        except Exception:
            sov_values.append(0)

    if len(all_brands) != len(sov_values):
        # fallback to zeros if mismatch
        sov_values = [0]*len(all_brands)

    sov_df = pd.DataFrame({'Brand': all_brands, 'SOV': sov_values})

    # --- Display KPIs ---
    st.subheader("Key Performance Indicators (KPIs)")
    st.write(f"**MIS:** {kpis['mis']}")
    st.write(f"**MPI:** {kpis['mpi']:.2f}")
    st.write(f"**Engagement Rate:** {kpis['engagement_rate']:.2f}")
    st.write(f"**Reach:** {kpis['reach']}")
    st.write(f"**Sentiment Ratio:** {kpis['sentiment_ratio']}")
    st.write(f"**Small Brand Sentiment:** {kpis['small_brand_sentiment']:.2f}")

    # --- SOV Table ---
    st.subheader("Share of Voice (SOV)")
    st.table(sov_df)

    # --- Generate PDF / Markdown Report ---
    if st.button("Generate PDF Report"):
        md, pdf_bytes = report_gen.generate_report(
            kpis=kpis,
            top_keywords=analysis.extract_keywords(" ".join(texts)),
            brand=brand,
            competitors=competitors,
            timeframe_hours=hours
        )
        st.download_button("Download PDF", pdf_bytes, file_name=f"{brand}_report.pdf")
        st.text_area("Markdown Report Preview", md, height=400)

except Exception:
    st.error("An error occurred during analysis:")
    st.error(traceback.format_exc())
