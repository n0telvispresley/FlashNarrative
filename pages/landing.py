import streamlit as st
import pandas as pd

# Page configuration
st.set_page_config(page_title="Flash Narrative - Landing", layout="wide")

# Welcome section
st.title("Welcome to Flash Narrative")
st.markdown("""
**Your AI-Powered PR Monitoring Solution**  
Monitor your brand's narrative in real-time, gain actionable insights, and stay ahead of the competition. Tailored for PR agencies.
""")

# Core features
st.header("Core Features")
st.markdown("""
- **Real-Time Monitoring**: Track mentions across Google News, FB, IG, and Threads.  
- **Advanced Sentiment Analysis**: Detect tones like mixed, anger, or appreciation using keyword-based NLP.  
- **Competitive Tracking**: Monitor up to 3 competitors for market positioning.  
- **KPI Dashboard**: Visualize Sentiment Ratio, Share of Voice (SOV), MIS, MPI, Engagement Rate, and Reach/Impressions.  
- **Alerts**: Instant email/Slack notifications for negative sentiment spikes or high-priority events.  
- **PDF Reports**: Generate on-demand reports with ReportLab for stakeholders.  
- **Keyword Extraction**: Identify trending themes with NLTK FreqDist.
""")

# Key Performance Indicators
st.header("Key Performance Indicators")
st.markdown("""
- **Sentiment Ratio**: Measure positive vs. negative sentiment.  
- **Share of Voice (SOV)**: Compare brand visibility against competitors.  
- **MIS/MPI**: Monitor media impact and performance indices.  
- **Engagement Rate**: Track audience interaction metrics.  
- **Reach/Impressions**: Quantify your brand's exposure.
""")

# Deliverables
st.header("Deliverables")
st.markdown("""
- **Live Dashboard**: Real-time insights for instant decision-making.  
- **Monthly PDF Reports**: Comprehensive analytics for stakeholders.  
- **Quarterly Audits**: Deep-dive performance reviews.  
- **Crisis Alerts**: Immediate notifications for urgent PR issues.
""")

# Pricing tiers
st.header("Pricing Tiers")
tiers_data = {
    "Tier": ["Professional", "Agency", "Enterprise"],
    "Price": ["N40,000/mo", "N80,000/mo", "N120,000/mo"],
    "Features": [
        "Real-time monitoring, basic sentiment, 1 competitor",
        "Advanced sentiment, 2 competitors, email alerts, PDF reports",
        "Full KPIs, 3 competitors, Slack alerts, custom audits"
    ]
}
st.table(pd.DataFrame(tiers_data))

# Login form
st.header("Sign In to Start Monitoring")
with st.form("login_form"):
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    submit = st.form_submit_button("Sign In")
    if submit:
        try:
            if username == "user" and password == "pass":
                st.session_state['logged_in'] = True
                st.success("Login successful! Redirecting...")
                st.switch_page("pages/dashboard.py")
            else:
                st.error("Invalid credentials")
        except Exception as e:
            st.error(f"Login error: {e}")

# Call-to-action
st.markdown("**Ready to transform your PR strategy? Sign in now!**")
