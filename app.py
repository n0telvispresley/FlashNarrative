import streamlit as st
import pandas as pd
import plotly.express as px
from pages import *  # Import page modules if needed; features implemented in respective pages

# App title and configuration
st.set_page_config(page_title="Flash Narrative", layout="wide")

# Initialize session state for authentication
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Function to handle login logic
def handle_login():
    try:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username == 'user' and password == 'pass':
                st.session_state['logged_in'] = True
                st.success("Login successful! Redirecting to dashboard...")
                st.switch_page("pages/dashboard.py")  # Redirect to dashboard page
            else:
                st.error("Invalid username or password.")
    except Exception as e:
        st.error(f"An error occurred during login: {e}")

# Main app logic
if not st.session_state['logged_in']:
    # Landing page content for non-logged-in users
    st.title("Flash Narrative - AI-Powered PR Monitoring Tool")
    st.write("Monitor your brand's narrative in real-time with advanced analytics. Built for PR pros.")

    # Integrate pricing tiers
    st.header("Pricing Tiers")
    try:
        pricing_data = {
            "Tier": ["Basic", "Pro", "Enterprise"],
            "Price": ["Free", "$49/month", "Custom"],
            "Features": [
                "Basic monitoring, dummy data fallback",
                "Advanced sentiment, competitive tracking, alerts",
                "Full KPI dashboard, PDF reports, custom integrations"
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
    # Redirect logged-in users to dashboard
    st.switch_page("pages/dashboard.py")

# Comments for beginners:
# - This app.py serves as the entry point and landing page.
# - Authentication uses st.session_state for persistence across reruns.
# - On successful login, we switch to dashboard.py in the pages/ folder.
# - dashboard.py should include checks like: if not st.session_state.get('logged_in', False): st.switch_page("../app.py")
# - Features like monitoring, sentiment, etc., are implemented in dashboard.py for modularity.
# - Use try/except for robustness in production.
# - For real scraping, use requests + BeautifulSoup in dashboard.py with dummy fallbacks.
# - Keep under 150 lines: Focus on core auth and redirect first, expand pages as needed.
