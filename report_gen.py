# report_gen.py
import io
import textwrap
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import matplotlib.pyplot as plt
from bedrock import generate_llm_report_summary # <-- IMPORT THE AI

def _create_sentiment_pie(sentiment_ratio):
    labels, sizes, colors = [], [], []
    color_map = {
        'positive': 'green',
        'appreciation': 'blue',
        'neutral': 'grey',
        'mixed': 'orange',
        'negative': 'red',
        'anger': 'darkred'
    }
    
    # Ensure consistent order
    for tone in ['positive', 'appreciation', 'neutral', 'mixed', 'negative', 'anger']:
        val = float(sentiment_ratio.get(tone, 0))
        if val > 0:
            labels.append(f"{tone} ({val:.1f}%)")
            sizes.append(val)
            colors.append(color_map[tone])
            
    if not sizes:
        labels = ['neutral (100%)']
        sizes = [100.0]
        colors = ['grey']
        
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%', startangle=90)
    ax.axis('equal')
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

# UPDATED function signature
# report_gen.py

# ... (imports) ...

# ... (_create_sentiment_pie function) ...

# timeframe_hours can now be an int (like 24) or a string (like "Last 7 days")
def generate_report(kpis, top_keywords, full_articles_data, brand="Brand", competitors=None, timeframe_hours=24, include_json=False):
    
    # ... (KPI setup) ...
    generated_on = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # --- THIS IS THE CHANGE ---
    # Smartly format the time text
    if isinstance(timeframe_hours, int):
        time_text = f"the last {timeframe_hours} hours"
    else:
        time_text = timeframe_hours # It's already a string like "Last 30 days (Max)"
    # --- END OF CHANGE ---


    # ---- Markdown Generation ----
    md_lines = [f"# Flash Narrative Report for {brand}",
                f"*This report covers {time_text}.*", ,
                f"**Generated on:** {generated_on}",
                "\n## Key Performance Indicators",
                f"- **Media Impact Score (MIS):** {mis}",
                f"- **Message Penetration (MPI):** {mpi:.1f}%",
                f"- **Avg. Social Engagement:** {engagement:.1f}",
                f"- **Total Reach:** {reach:,}",
                f"- **Sentiment Ratio:** {sentiment_ratio}"]

    md_lines.append("\n### Share of Voice (SOV)")
    md_lines.append("| Brand | SOV (%) |"); md_lines.append("|---|---|")
    if len(sov) < len(all_brands): 
        sov += [0] * (len(all_brands) - len(sov))
    for b, s in zip(all_brands, sov):
        md_lines.append(f"| {b} | {s:.1f} |")

    md_lines.append("\n## Top Keywords / Themes")
    if top_keywords:
        for w, f in top_keywords:
            md_lines.append(f"- {w}: {f}")
    else: 
        md_lines.append("- No keywords identified.")

    # ---- AI Recommendations ----
    md_lines.append("\n## AI-Powered Summary & Recommendations")
    
    # Filter articles to only include those with sentiment
    articles_with_sentiment = [a for a in full_articles_data if 'sentiment' in a]
    ai_recommendations = generate_llm_report_summary(kpis, top_keywords, articles_with_sentiment, brand)
    md_lines.append(ai_recommendations)

    md = "\n".join(md_lines)

 # ---- PDF Generation ----
    # ... (canvas setup) ...
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin_x, y, f"Flash Narrative Report — {brand}")
    y -= 28
    c.setFont("Helvetica", 10)
    # --- USE THE NEW time_text VARIABLE ---
    c.drawString(margin_x, y, f"This report covers {time_text}. Generated on {generated_on}") # <-- UPDATED
    y -= 24

    # KPI block
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Key Performance Indicators"); y -= 16
    c.setFont("Helvetica", 10)
    kpi_text = f"MIS: {mis} | MPI: {mpi:.1f}% | Avg. Engagement: {engagement:.1f} | Reach: {reach:,}"
    for line in textwrap.wrap(kpi_text, width=90):
        c.drawString(margin_x, y, line); y -= 14

    # Sentiment pie
    pie_buf = _create_sentiment_pie(sentiment_ratio)
    img = ImageReader(pie_buf)
    # Position pie chart
    c.drawImage(img, width - margin_x - 200, height - 200, width=200, height=200, preserveAspectRatio=True, mask='auto')

    # Keywords
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Top Keywords / Themes"); y -= 16
    c.setFont("Helvetica", 10)
    for w, f in top_keywords[:10]: # Limit to top 10
        text = f"- {w}: {f}"
        c.drawString(margin_x, y, text); y -= 12
        if y < 100: # Page break logic
            c.showPage(); y = height - 60
            c.setFont("Helvetica", 10)

    # AI Recommendations
    y -= 20
    if y < 200: # Check for page break before starting section
        c.showPage(); y = height - 60
        
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "AI Summary & Recommendations"); y -= 16
    
    # Use textwrap for the new AI recommendations
    recs = ai_recommendations.split('\n') 
    for r in recs:
        r = r.strip()
        if not r: # Skip empty lines
            y -= 6
            continue
            
        if r.startswith("**"):
            c.setFont("Helvetica-Bold", 10)
            r = r.replace("**", "") # Remove markdown
        else:
            c.setFont("Helvetica", 10)
             
        for line in textwrap.wrap(r, width=90):
            c.drawString(margin_x, y, line); y -= 12
            if y < 60: # Page break
                c.showPage(); y = height - 60
                c.setFont("Helvetica", 10)

    c.showPage()
    c.save()
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    json_summary = {"brand": brand, "competitors": competitors, "kpis": kpis, "top_keywords": top_keywords, "generated_on": generated_on}

    if include_json: 
        return md, pdf_bytes, json_summary
    return md, pdf_bytes
