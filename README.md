# Flash Narrative
AI-powered PR monitoring tool for real-time insights. No APIs (except ServiceNow); scrapes Google News, FB, IG, Threads with dummy fallback. Features:
- Real-time monitoring (button refresh)
- Advanced sentiment (positive/negative/mixed/anger/appreciation)
- KPIs: Sentiment Ratio, SOV, MIS, MPI, Engagement, Reach
- Competitive tracking (1-3 competitors)
- PDF reports (on-demand, white-label)
- Alerts (email/Slack/ServiceNow for negative spikes)
- Keyword extraction (NLTK)
- Landing page with pricing (N40k-N120k/mo)

## Setup
1. Clone repo: `git clone <repo>`
2. Install: `pip install -r requirements.txt; playwright install`
3. Add `.env` (optional for mock mode)
4. Run: `streamlit run app.py`

Login: user/pass. Demo: Input "Nike," analyze, download PDF.
