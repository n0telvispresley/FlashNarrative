# Flash Narrative ✨

**AI-Powered Real-Time Public Relations Monitoring & Analysis**

Flash Narrative is an intelligent dashboard built to empower PR agencies and brand managers with immediate insights into their online reputation. It leverages AI to monitor news, blogs, and social media, analyze sentiment, track competitors, and generate actionable reports.

**(Optional: Add a Screenshot/GIF here!)**
---

## 🚀 Key Features

* **Real-Time Monitoring:** Scans **NewsAPI**, **RSS Feeds** (industry-specific), **Google News**, and **Reddit** for brand and competitor mentions within user-defined timeframes (up to 30 days). Includes fallback dummy data for other social platforms.
* **AI-Powered Sentiment Analysis:** Utilizes **Amazon Bedrock** (Anthropic Claude models with sequential fallback) to analyze mentions, classifying them beyond simple positive/negative into nuanced tones like `mixed`, `anger`, and `appreciation`. Keyword analysis serves as a robust fallback.
* **Comprehensive KPI Dashboard:** Visualizes key metrics crucial for PR success:
    * **Media Impact Score (MIS):** Weighted score based on source authority.
    * **Message Penetration Index (MPI):** Tracks how well campaign messages appear in mentions.
    * **Sentiment Ratio:** Detailed breakdown of sentiment tones.
    * **Share of Voice (SOV):** Compares brand visibility against competitors.
    * **Average Social Engagement:** Tracks likes/comments/upvotes from social sources (Reddit & dummy data).
    * **Total Reach:** Estimated audience size based on source reach.
    * *(Thresholds for MPI & Engagement are user-configurable in the sidebar)*.
* **Competitive Tracking:** Allows monitoring of the primary brand alongside user-defined competitors.
* **Keyword & Phrase Extraction:** Identifies trending topics and themes associated with mentions using NLTK.
* **Automated Reporting:** Generates professional **PDF summary reports** (including AI-generated executive summaries & recommendations) and detailed **Excel (.xlsx) files** containing all mention data with source links.
* **Intelligent Alert System:** Configurable alerts (via **Email** and **Slack**) and **ServiceNow** incident creation for significant spikes in negative sentiment.
* **Customizable Styling:** Features a custom dark theme with brand colors (Gold, Black, Beige).

---

## 🛠️ Technology Stack

* **Backend:** Python
* **Frontend:** Streamlit
* **AI / LLM:** Amazon Bedrock (Anthropic Claude Opus/Sonnet/Haiku, Meta Llama3, Cohere Command R+, Mistral Large, Amazon Titan - with sequential fallback)
* **Data Sources:** NewsAPI, RSS Feeds, Google News (Scraping), Reddit API (.json endpoint)
* **Data Analysis:** NLTK, Pandas
* **Report Generation:** ReportLab (PDF), Openpyxl (Excel)
* **Notifications:** SMTPlib (Email), Slack SDK, ServiceNow REST API
* **Core Libraries:** Requests, BeautifulSoup4, Feedparser, python-dotenv, Plotly Express

---

## ⚙️ Setup & Installation

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/your-username/flash-narrative.git](https://github.com/your-username/flash-narrative.git)
    cd flash-narrative
    ```

2.  **Create Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: `playwright` might be listed but isn't actively used by the current scrapers. `facebook-scraper` is also listed but only dummy data is generated.)*

4.  **Configure Environment Variables:**
    * Create a file named `.env` in the root directory.
    * Copy the contents of `.env.example` (if provided) or add the following, replacing placeholders with your actual keys/credentials:

        ```dotenv
        # NewsAPI (REQUIRED for real news data)
        NEWSAPI_KEYS=YOUR_NEWSAPI_KEY_1,YOUR_NEWSAPI_KEY_2 # Comma-separated if multiple

        # AWS Bedrock (REQUIRED for AI analysis)
        AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY
        AWS_SECRET_KEY=YOUR_AWS_SECRET_KEY
        AWS_REGION=us-east-1 # Or your preferred Bedrock-enabled region

        # Email for Reports/Alerts (REQUIRED for email features)
        SMTP_SERVER=smtp.gmail.com # Or smtp.office365.com, etc.
        SMTP_PORT=587
        SMTP_USER=your_email@example.com
        SMTP_PASS=your_app_password # Use Google/Outlook App Password if 2FA is enabled

        # Slack Alerts (Optional)
        SLACK_TOKEN=xoxb-your-slack-bot-token

        # ServiceNow Integration (Optional)
        SERVICENOW_INSTANCE=your_instance_name # e.g., dev12345
        SERVICENOW_USER=your_servicenow_user
        SERVICENOW_PASSWORD=your_servicenow_password

        # Other Settings
        SCRAPER_CACHE_TTL_MINUTES=15
        ALERT_EMAIL=email_for_crisis_alerts@yourcompany.com # Email used by send_alert
        ```
    * **IMPORTANT:** Ensure you have enabled model access in the AWS Bedrock console for the models listed in `bedrock.py` within your specified `AWS_REGION`.

5.  **Run the Application:**
    ```bash
    streamlit run app.py
    ```

6.  **Login:** Use the default credentials `user` / `pass` (defined in `app.py`).

---

## 📖 How It Works

1.  **Input:** User enters Brand Name, Competitors, Industry, Campaign Messages, and Time Frame on the Streamlit dashboard.
2.  **Scraping:** The `scraper.py` module fetches mentions from NewsAPI, RSS feeds, Google News, and Reddit based on the inputs. Dummy data is generated for other social platforms.
3.  **AI Analysis:** For each mention, `bedrock.py` calls the Amazon Bedrock API (trying models sequentially) to determine sentiment (`get_llm_sentiment`). If all Bedrock models fail, `analysis.py` uses keyword matching (`analyze_sentiment_keywords`) as a fallback.
4.  **KPI Calculation:** `analysis.py` processes the raw data and sentiments to calculate MIS, MPI, SOV, Engagement Rate, Reach, and Sentiment Ratios (`compute_kpis`), and extracts top keywords/phrases (`extract_keywords`).
5.  **Display:** `pages/dashboard.py` renders the KPIs (with threshold styling), interactive charts (Plotly), and data tables (Pandas DataFrames).
6.  **Reporting:** On request, `report_gen.py` creates a PDF summary using ReportLab (including an AI-generated summary from Bedrock via `generate_llm_report_summary`) and an Excel file of all mentions using Pandas/Openpyxl.
7.  **Alerting:** If negative sentiment exceeds a threshold, `servicenow_integration.py` sends alerts via Slack/Email and creates a ServiceNow ticket. Email functionality is also used for sending generated reports.

---

## 🏆 Hackathon Goals Achieved

* Real-time (on-demand refresh) monitoring of multiple online sources.
* Advanced AI sentiment analysis using a leading LLM service (Bedrock) with robust fallback.
* Comprehensive PR KPI tracking and visualization.
* Competitor analysis (SOV).
* Automated, professional report generation (PDF & Excel).
* Configurable alerting system integration (Email, Slack, ServiceNow).

---
