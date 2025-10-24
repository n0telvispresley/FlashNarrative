# app.py
import streamlit as st
import pandas as pd

# App title and configuration
st.set_page_config(page_title="Flash Narrative", layout="wide")

# Initialize session state for authentication
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Function to handle login logic
def handle_login():
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign In")
        
        if submit:
            if username == 'user' and password == 'pass':
                st.session_state['logged_in'] = True
                st.success("Login successful! Redirecting to dashboard...")
                # Use st.rerun() to force the script to check session_state again
                st.rerun()
            else:
                st.error("Invalid username or password.")

# Main app logic
if not st.session_state['logged_in']:
    # Landing page content for non-logged-in users
    st.title("Welcome to Flash Narrative")
    st.markdown("""
    **Your AI-Powered PR Monitoring Solution** Monitor your brand's narrative in real-time, gain actionable insights, and stay ahead of the competition. Tailored for PR agencies.
    """)

    # Core features
    st.header("Core Features")
    st.markdown("""
    - **Real-Time Monitoring**: Track mentions across Google News, FB, IG, and Threads.  
    - **Advanced AI Sentiment Analysis**: Detect tones like mixed, anger, or appreciation using Amazon Bedrock.  
    - **Competitive Tracking**: Monitor competitors for market positioning.  
    - **KPI Dashboard**: Visualize Sentiment Ratio, Share of Voice (SOV), MIS, MPI, Engagement, and Reach.  
    - **Alerts**: Instant email/Slack/ServiceNow notifications for negative sentiment spikes.  
    - **AI-Powered PDF Reports**: Generate on-demand reports with AI-driven summaries.
    """)

    # Pricing tiers (FIXED to match your brief)
    st.header("Pricing Tiers")
    try:
        pricing_data = {
            "Tier": ["Professional", "Agency", "Enterprise"],
            "Price": ["N40,000 / month", "N80,000 / month", "N120,000 / month"],
            "Features": [
                "3 keywords, 10k mentions, 2 users, Basic KPIs",
                "10 keywords, 50k mentions, 10 users, Advanced KPIs, Alerts, PDF Reports",
                "Unlimited, API access, Dedicated support, Custom Audits"
            ]
        }
        pricing_df = pd.DataFrame(pricing_data)
        st.table(pricing_df)
    except Exception as e:
        st.error(f"Error displaying pricing: {e}")

    # Login form
    st.header("Login to Access Dashboard")
    handle_login()
else:
    # User is logged in, show the dashboard
    # We will call the dashboard function from the main app
    # This is a bit of a hack, but simpler than switch_page
    # st.switch_page("pages/dashboard.py")
    
    # A better pattern:
    st.success("Logged in. Redirecting to your dashboard...")
    # Give a moment for the user to see the success message
    import time
    time.sleep(1)
    st.switch_page("pages/dashboard.py")
