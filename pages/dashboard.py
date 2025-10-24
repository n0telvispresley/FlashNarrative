import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
import traceback

from flashnarrative import analysis, report_gen

st.set_page_config(page_title="Flash Narrative Dashboard", layout="wide")
st.title("Flash Narrative Dashboard")

# Sidebar Inputs
st.sidebar.header("Inputs")
brand = st.sidebar.text_input("Your Brand Name", "BrandX")

competitors_input = st.sidebar.text_area("Competitor Brands (comma-separated)", "")
competitors = [c.strip() for c in competitors_input.split(",") if c.strip()]

campaign_input = st.sidebar.text_area("Campaign Messages (comma-separated)", "")
campaign_messages = [c.strip() for c in campaign_input.split(",") if c.strip()]

hours = st.sidebar.number_input("Lookback Hours", min_value=1, max_value=168, value=24, step=1)

uploaded_file = st.sidebar.file_uploader("Upload brand mentions CSV", type=["csv"])

full_data = []

# Load uploaded CSV
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        required_columns = ['text','date','source','mentioned_brands','authority','likes','comments','reach','url']
        for col in required_columns:
            if col not in df.columns:
                st.error(f"CSV missing required column: {col}")
                st.stop()
        # Convert mentioned_brands to lists if stored as string
        df['mentioned_brands'] = df['mentioned_brands'].apply(lambda x: x.split(';') if isinstance(x,str) else [])
        full_data = df.to_dict('records')
    except Exception:
        st.error(traceback.format_exc())
        st.stop()

# Perform analysis if data exists
if full_data:
    mentions_text = [item.get('text','') for item in full_data]
    _, tones = analysis.analyze_sentiment(mentions_text)

    try:
        kpis = analysis.compute_kpis(full_data, tones, campaign_messages, hours=hours, brand=brand)
    except Exception:
        st.error("Analysis error:\n"+traceback.format_exc())
        st.stop()

    # Sidebar Download
    md, pdf_bytes = report_gen.generate_report(kpis, analysis.extract_keywords(" ".join(mentions_text)), brand=brand, competitors=competitors)
    st.sidebar.download_button("Download PDF Report", data=pdf_bytes, file_name=f"{brand}_report.pdf", mime="application/pdf")

    # Display KPIs
    st.subheader("Key Performance Indicators")
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("MIS", kpis.get('mis',0))
    kpi_cols[1].metric("MPI", round(kpis.get('mpi',0),2))
    kpi_cols[2].metric("Engagement Rate", round(kpis.get('engagement_rate',0),2))
    kpi_cols[3].metric("Reach", kpis.get('reach',0))
    kpi_cols[4].metric("Small Brand Sentiment", round(kpis.get('small_brand_sentiment',0),2))

    # SOV Table
    st.subheader("Share of Voice (SOV)")
    all_brands = [brand]+competitors
    sov_values = kpis.get('sov',[0]*len(all_brands))
    if len(sov_values)<len(all_brands): sov_values+=[0]*(len(all_brands)-len(sov_values))
    sov_df = pd.DataFrame({'Brand': all_brands, 'SOV (%)': [round(s,2) for s in sov_values]})
    st.dataframe(sov_df)

    # Sentiment Pie
    st.subheader("Sentiment Distribution")
    sentiment_ratio = kpis.get('sentiment_ratio',{})
    labels, sizes = [], []
    for tone in ['positive','neutral','negative']:
        val = float(sentiment_ratio.get(tone,0))
        if val>0:
            labels.append(f"{tone} ({val:.1f}%)")
            sizes.append(val)
    if not sizes:
        labels=['neutral (100%)']
        sizes=[100]
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.0f%%', startangle=90)
    ax.axis('equal')
    st.pyplot(fig)

    # Top Keywords
    st.subheader("Top Keywords / Themes")
    top_keywords = analysis.extract_keywords(" ".join(mentions_text))
    if top_keywords:
        kw_list = [f"{w}: {f}" for w,f in top_keywords]
        st.write("\n".join(kw_list))
    else:
        st.write("No keywords identified.")

    # Recommendations
    st.subheader("Recommendations")
    recs=[]
    neg_pct = sentiment_ratio.get('negative',0)
    pos_pct = sentiment_ratio.get('positive',0)
    if neg_pct>50: recs.append("High negative sentiment — escalate to PR.")
    elif neg_pct>30: recs.append("Moderate negative sentiment — monitor sources.")
    elif pos_pct>60: recs.append("Strong positive sentiment — capitalize momentum.")
    else: recs.append("Mixed sentiment — monitor trending keywords.")

    if top_keywords:
        recs.append(f"Consider content ideas around **{top_keywords[0][0]}**.")

    st.write("\n".join(recs))

    # Hyperlinks to top sources
    st.subheader("Top Sources / Mentions")
    for item in full_data:
        url = item.get('url','')
        text = item.get('text','')[:100]+"..." if len(item.get('text',''))>100 else item.get('text','')
        if url:
            st.markdown(f"- [{text}]({url})")
        else:
            st.markdown(f"- {text}")

else:
    st.info("Upload a CSV file with brand mentions to see KPIs, SOV, sentiment, and trends.")
