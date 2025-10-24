# report_gen.py
import io
import textwrap
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import matplotlib.pyplot as plt
# Use alias for clarity if bedrock is imported elsewhere too
from bedrock import generate_llm_report_summary

def _create_sentiment_pie(sentiment_ratio):
    labels, sizes, colors = [], [], []
    color_map = {
        'positive': 'green', 'appreciation': 'blue',
        'neutral': 'grey', 'mixed': 'orange',
        'negative': 'red', 'anger': 'darkred'
    }

    # Order sentiments for consistency in the chart
    sentiment_order = ['positive', 'appreciation', 'neutral', 'mixed', 'negative', 'anger']
    for tone in sentiment_order:
        val = float(sentiment_ratio.get(tone, 0))
        if val > 0.1: # Threshold to avoid tiny slices
            # Format label, ensure percentage sign is included correctly
            labels.append(f"{tone.capitalize()} ({val:.1f}%)")
            sizes.append(val)
            colors.append(color_map.get(tone, 'grey')) # Use get for safety

    if not sizes:
        labels = ['Neutral (100.0%)']
        sizes = [100.0]
        colors = ['grey']

    # Create the plot
    fig, ax = plt.subplots(figsize=(4, 4)) # Adjust figure size if needed
    # Use autopct to format percentages on slices
    ax.pie(sizes, labels=None, colors=colors, autopct='%1.1f%%', startangle=90, pctdistance=0.85)
    ax.axis('equal') # Equal aspect ratio ensures a circular pie chart

    # Add a legend instead of labels on slices if there are many slices
    # ax.legend(labels, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

    buf = io.BytesIO()
    plt.tight_layout() # Adjust layout
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight') # Use bbox_inches
    plt.close(fig)
    buf.seek(0)
    return buf

# timeframe_hours can now be an int or a string
def generate_report(kpis, top_keywords, full_articles_data, brand="Brand", competitors=None, timeframe_hours=24, include_json=False):
    if competitors is None: competitors = []

    sentiment_ratio = kpis.get('sentiment_ratio', {})
    sov = kpis.get('sov', [])
    all_brands = kpis.get('all_brands', [brand] + competitors)
    mis = kpis.get('mis', 0)
    mpi = kpis.get('mpi', 0)
    engagement = kpis.get('engagement_rate', 0)
    reach = kpis.get('reach', 0)
    generated_on = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Smartly format the time text
    if isinstance(timeframe_hours, int):
        time_text = f"the last {timeframe_hours} hours"
    else:
        time_text = timeframe_hours # It's already a string like "Last 30 days (Max)"

    # ---- Markdown Generation ----
    md_lines = [f"# Flash Narrative Report for {brand}",
                f"*This report covers {time_text}.*",
                f"**Generated on:** {generated_on}",
                "\n## Key Performance Indicators",
                f"- **Media Impact Score (MIS):** {mis:.0f}", # Format MIS
                f"- **Message Penetration (MPI):** {mpi:.1f}%",
                f"- **Avg. Social Engagement:** {engagement:.1f}",
                f"- **Total Reach:** {reach:,}",
                # Format sentiment ratio nicely
                f"- **Sentiment Ratio:** " + ", ".join([f"{k.capitalize()}: {v:.1f}%" for k, v in sentiment_ratio.items()])]

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
    articles_with_sentiment = [a for a in full_articles_data if 'sentiment' in a]
    # Ensure bedrock call uses the correct alias if needed elsewhere
    ai_recommendations = generate_llm_report_summary(kpis, top_keywords, articles_with_sentiment, brand)
    md_lines.append(ai_recommendations)

    md = "\n".join(md_lines)

    # ---- PDF Generation ----
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter
    margin_x = 50
    y = height - 60 # Start Y position

    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin_x, y, f"Flash Narrative Report — {brand}")
    y -= 28
    c.setFont("Helvetica", 10)
    c.drawString(margin_x, y, f"This report covers {time_text}. Generated on {generated_on}")
    y -= 24

    # KPI block
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Key Performance Indicators"); y -= 16
    c.setFont("Helvetica", 10)
    # Format KPIs consistently
    kpi_text = f"MIS: {mis:.0f} | MPI: {mpi:.1f}% | Avg. Engagement: {engagement:.1f} | Reach: {reach:,}"
    for line in textwrap.wrap(kpi_text, width=90):
        c.drawString(margin_x, y, line); y -= 14

    # --- THIS IS THE FIX ---
    # Sentiment pie
    pie_buf = _create_sentiment_pie(sentiment_ratio)
    img = ImageReader(pie_buf) # <<< THIS LINE WAS MISSING
    # --- END OF FIX ---

    # Position pie chart (adjust x, y, width, height as needed)
    img_width = 200
    img_height = 200
    img_x = width - margin_x - img_width
    img_y = height - 60 - img_height # Align top near title? Or adjust based on KPI block height
    c.drawImage(img, img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')

    # Adjust Y position to be below the KPI block before drawing keywords
    y = img_y - 20 # Start keywords below the chart

    # Keywords
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Top Keywords / Themes"); y -= 16
    c.setFont("Helvetica", 10)
    for w, f in top_keywords[:10]: # Limit to top 10
        text = f"- {w}: {f}"
        c.drawString(margin_x, y, text); y -= 12
        if y < 100: # Page break logic
            c.showPage(); y = height - 60 # Reset Y after page break
            c.setFont("Helvetica", 10) # Reset font

    # AI Recommendations
    y -= 20 # Space before recommendations
    if y < 200: # Check if enough space before starting section
        c.showPage(); y = height - 60

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "AI Summary & Recommendations"); y -= 16

    recs = ai_recommendations.split('\n')
    for r in recs:
        r = r.strip()
        if not r: # Skip empty lines but add a small space
            y -= 6
            continue

        if r.startswith("**"):
            c.setFont("Helvetica-Bold", 10)
            r = r.replace("**", "") # Remove markdown bold
        else:
            c.setFont("Helvetica", 10)

        # Wrap text and draw line by line
        lines = textwrap.wrap(r, width=90)
        for line in lines:
            c.drawString(margin_x, y, line); y -= 12
            if y < 60: # Check for page break after drawing each line
                c.showPage(); y = height - 60
                # Reset font after page break if needed
                if r.startswith("**"): c.setFont("Helvetica-Bold", 10)
                else: c.setFont("Helvetica", 10)


    c.showPage() # Finish the last page
    c.save() # Save the PDF to the buffer
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    json_summary = {"brand": brand, "competitors": competitors, "kpis": kpis, "top_keywords": top_keywords, "generated_on": generated_on}

    if include_json:
        return md, pdf_bytes, json_summary
    return md, pdf_bytes
