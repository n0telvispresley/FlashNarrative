# dashboard.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import traceback

from flashnarrative import analysis, report_gen

st.set_page_config(page_title="Flash Narrative Dashboard", layout="wide")

st.title("Flash Narrative Dashboard")

# ----------------- User Inputs -----------------
st.sidebar.header("Inputs")
brand = st.sidebar.text_input("Your Brand Name", "BrandX")
competitors_input = st.sidebar.text_area("Competitor Brands (comma-separated)", "")
competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]

campaign_input = st.sidebar.text_area("Campaign Messages (comma-separated)", "")
campaign_messages = [c.strip() for c in campaign_input.split(",") if c.strip()]

hours = st.sidebar.number_input("Lookback Hours", min_value=1, max_value=168, value=24, step=1)

uploaded_file = st.sidebar.file_uploader("Upload brand mentions CSV", type=["csv"])

# ----------------- Data Loading -----------------
full_data = []
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        required_columns = ['text', 'date', 'source', 'mentioned_brands', 'authority', 'likes', 'comments', 'reach']
        for col in required_columns:
            if col not in df.columns:
                st.error(f"CSV missing required column: {col}")
        full_data = df.to_dict(orient="records")
    except Exception as e:
        st.error(f"Failed to load CSV: {e}")

# ----------------- Compute Analysis -----------------
kpis = {}
tones = []
try:
    if full_data:
        # Analyze sentiment
        mentions_text = [item['text'] for item in full_data]
        counts, tones = analysis.analyze_sentiment(mentions_text)

        # Compute KPIs
        kpis = analysis.compute_kpis(full_data, tones, campaign_messages, industry=None, hours=hours, brand=brand)

        # Extract top keywords
        all_text = " ".join(mentions_text)
        top_keywords = analysis.extract_keywords(all_text)
    else:
        top_keywords = []
except Exception:
    st.error("Analysis error:\n" + traceback.format_exc())
    kpis = {}
    top_keywords = []

# ----------------- KPIs Display -----------------
if kpis:
    st.subheader("Key Performance Indicators (KPIs)")
    kpi_cols = st.columns(4)
    kpi_cols[0].metric("MIS", kpis.get("mis", 0))
    kpi_cols[1].metric("MPI", round(kpis.get("mpi", 0), 2))
    kpi_cols[2].metric("Engagement Rate", round(kpis.get("engagement_rate", 0), 2))
    kpi_cols[3].metric("Reach", kpis.get("reach", 0))

# ----------------- SOV Table -----------------
all_brands = [brand] + competitors
sov_values = kpis.get("sov", [0]*len(all_brands))
if len(sov_values) < len(all_brands):
    sov_values += [0]*(len(all_brands)-len(sov_values))

sov_df = pd.DataFrame({'Brand': all_brands, 'SOV (%)': sov_values})
st.subheader("Share of Voice (SOV)")
st.dataframe(sov_df)

# ----------------- Sentiment Pie Chart -----------------
sentiment_ratio = kpis.get("sentiment_ratio", {})
if sentiment_ratio:
    labels = list(sentiment_ratio.keys())
    sizes = list(sentiment_ratio.values())
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.0f%%', startangle=90)
    ax.axis('equal')
    st.subheader("Sentiment Distribution")
    st.pyplot(fig)

# ----------------- Top Keywords -----------------
if top_keywords:
    st.subheader("Top Keywords / Themes")
    for w, f in top_keywords:
        st.write(f"- {w}: {f}")

# ----------------- Recommendations -----------------
if kpis:
    st.subheader("Recommendations")
    neg_pct = sentiment_ratio.get("negative", 0)
    pos_pct = sentiment_ratio.get("positive", 0)
    recs = []
    if neg_pct > 50:
        recs.append("High negative sentiment — escalate to PR and prioritize sentiment remediation plans.")
    elif neg_pct > 30:
        recs.append("Moderate negative sentiment — investigate top negative sources and respond where necessary.")
    elif pos_pct > 60:
        recs.append("Strong positive sentiment — capitalize on momentum with promotional pushes.")
    else:
        recs.append("Mixed sentiment — monitor trending keywords and refine messaging to increase MPI.")

    if top_keywords:
        top_kw = top_keywords[0][0]
        recs.append(f"Consider content or campaign ideas around **{top_kw}**, which is trending in recent coverage.")

    for r in recs:
        st.write(f"- {r}")

# ----------------- Hyperlinks Section -----------------
if full_data:
    st.subheader("Top Mentions Links")
    link_data = []
    for item in full_data:
        source = item.get("source", "").lower()
        text = item.get("text", "")
        link = item.get("link", "#")  # Optional column in CSV
        if link != "#":
            link_data.append((source, text, link))

    if link_data:
        for src, txt, lnk in link_data:
            st.markdown(f"- [{src.upper()}]({lnk}): {txt[:100]}{'...' if len(txt)>100 else ''}")
    else:
        st.write("No links available in uploaded data.")

# ----------------- Report Generation -----------------
st.subheader("Generate PDF Report")
if st.button("Generate Report"):
    if full_data:
        try:
            md, pdf_bytes, _ = report_gen.generate_report(
                kpis=kpis,
                top_keywords=top_keywords,
                brand=brand,
                competitors=competitors,
                timeframe_hours=hours,
                include_json=True
            )
            st.download_button(
                label="Download PDF",
                data=pdf_bytes,
                file_name=f"flash_narrative_report_{brand}.pdf",
                mime="application/pdf"
            )
        except Exception:
            st.error("Report generation failed:\n" + traceback.format_exc())
    else:
        st.warning("Upload brand mentions CSV to generate report.")
