# report_gen.py
import io
import textwrap
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.colors import navy, black, gray
import matplotlib.pyplot as plt
from bedrock import generate_llm_report_summary as generate_ai_summary

# --- Helper to create sentiment pie chart (no changes needed) ---
def _create_sentiment_pie(sentiment_ratio):
    # ... (Keep existing code) ...
    labels, sizes, colors = [], [], []
    color_map = {
        'positive': 'green', 'appreciation': 'blue',
        'neutral': 'grey', 'mixed': 'orange',
        'negative': 'red', 'anger': 'darkred'
    }
    sentiment_order = ['positive', 'appreciation', 'neutral', 'mixed', 'negative', 'anger']
    for tone in sentiment_order:
        val = float(sentiment_ratio.get(tone, 0))
        if val > 0.1:
            labels.append(f"{tone.capitalize()} ({val:.1f}%)")
            sizes.append(val)
            colors.append(color_map.get(tone, 'grey'))
    if not sizes:
        labels = ['Neutral (100.0%)']; sizes = [100.0]; colors = ['grey']

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, labels=None, colors=colors, autopct='%1.1f%%', startangle=90, pctdistance=0.85)
    ax.axis('equal')
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


# --- Helper function to draw a section (UPDATED SIGNATURE) ---
def _draw_mention_section(c, y, title, mentions, width, margin_x, height): # <-- Added height
    """Draws a titled section with mentions (headline, source, link)."""
    styles = getSampleStyleSheet()
    max_y = y # Store starting y for checking space

    # Draw Section Title
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(navy)
    c.drawString(margin_x, y, title)
    y -= 20
    c.setFillColor(black)

    mention_count = 0
    max_mentions_per_section = 15

    for item in mentions:
        if mention_count >= max_mentions_per_section:
            break

        headline = item.get('text', 'No Headline')[:200]
        source = item.get('source', 'Unknown Source')
        link = item.get('link', None)

        # Estimate height needed
        headline_lines = textwrap.wrap(headline, width=80)
        estimated_height = len(headline_lines) * 14 + 14 + 10
        if y < estimated_height + 60: # Check page break
            c.showPage()
            y = height - 60 # <-- Use the passed height variable HERE
            # Optional: Redraw title on new page
            c.setFont("Helvetica-Bold", 14); c.setFillColor(navy)
            c.drawString(margin_x, y, title + " (cont.)"); y -= 20
            c.setFillColor(black)


        # Draw Headline
        c.setFont("Helvetica-Bold", 10)
        lines = textwrap.wrap(headline, width=80)
        for line in lines:
            # Re-check y position for each line in case headline is long
            if y < 60: # Check bottom margin
                 c.showPage(); y = height - 60
                 c.setFont("Helvetica-Bold", 10) # Reset font
            c.drawString(margin_x, y, line)
            y -= 12

        # Draw Source and Link
        c.setFont("Helvetica", 9)
        c.setFillColor(gray)
        source_text = f"Source: {source}"
        # Check if source line needs page break
        if y < 60: c.showPage(); y = height - 60; c.setFont("Helvetica", 9); c.setFillColor(gray)
        c.drawString(margin_x, y, source_text)

        # Draw Link
        if link:
             link_text = " (Link)"
             text_width = c.stringWidth(source_text, "Helvetica", 9)
             link_x = margin_x + text_width
             c.setFillColor(navy)
             # Add try-except for linkURL just in case
             try:
                 c.linkURL(link, (link_x, y - 2, link_x + c.stringWidth(link_text, "Helvetica", 9), y + 10), relative=1)
             except Exception as link_e:
                 print(f"Warning: Could not create PDF link for {link}: {link_e}")
             c.drawString(link_x, y, link_text)
             c.line(link_x, y - 1, link_x + c.stringWidth(link_text, "Helvetica", 9), y-1)

        y -= 14 # Space after source/link
        c.setFillColor(black) # Reset color

        y -= 10 # Space between mentions
        mention_count += 1

    if mention_count == 0:
         # Check page break before drawing "No mentions"
         if y < 60: c.showPage(); y = height - 60
         c.setFont("Helvetica-Oblique", 10)
         c.drawString(margin_x, y, "No specific mentions found in this category.")
         y -= 20

    return y


# --- Main Report Generation Function ---
def generate_report(kpis, top_keywords, full_articles_data, brand="Brand", competitors=None, timeframe_hours=24, include_json=False):
    if competitors is None: competitors = []

    # --- Categorize Mentions ---
    main_brand_mentions = []
    competitor_mentions = []
    related_mentions = []
    lower_brand = brand.lower()
    lower_competitors = {c.lower() for c in competitors}
    for item in full_articles_data:
        mentioned_brands_lower = {mb.lower() for mb in item.get('mentioned_brands', [])}
        mentions_main = lower_brand in mentioned_brands_lower
        mentions_comp = any(comp in mentioned_brands_lower for comp in lower_competitors)
        if mentions_main and not mentions_comp: main_brand_mentions.append(item)
        elif not mentions_main and mentions_comp: competitor_mentions.append(item)
        else: related_mentions.append(item)

    # --- Get KPI data (remains the same) ---
    sentiment_ratio = kpis.get('sentiment_ratio', {})
    # ... (other kpis) ...
    generated_on = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(timeframe_hours, int): time_text = f"the last {timeframe_hours} hours"
    else: time_text = timeframe_hours

    # --- Generate AI Summary (remains the same) ---
    ai_summary = "AI Summary generation failed."
    try:
        ai_summary = generate_ai_summary(kpis, top_keywords, full_articles_data, brand)
    except Exception as ai_e: print(f"Error generating AI summary: {ai_e}")

    # ---- 1. Markdown Generation (remains the same) ----
    # ... (code to build md_lines list) ...
    md = "\n".join(md_lines)


    # ---- 2. PDF Generation ----
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter # Get page dimensions HERE
    margin_x = 50
    margin_y = 60
    content_width = width - 2 * margin_x

    # --- Page 1 ---
    y = height - margin_y

    # Title and Date (remains the same)
    c.setFont("Helvetica-Bold", 18); c.drawString(margin_x, y, f"Flash Narrative Report: {brand}"); y -= 20
    c.setFont("Helvetica", 10); c.drawString(margin_x, y, f"Period: {time_text} | Generated: {generated_on}"); y -= 25

    # KPIs (remains the same)
    c.setFont("Helvetica-Bold", 12); c.drawString(margin_x, y, "Key Performance Indicators"); y -= 16
    c.setFont("Helvetica", 10)
    kpi_text = f"MIS: {kpis.get('mis', 0):.0f} | MPI: {kpis.get('mpi', 0):.1f}% | Avg. Engagement: {kpis.get('engagement_rate', 0):.1f} | Reach: {kpis.get('reach', 0):,}"
    lines = textwrap.wrap(kpi_text, width=70)
    kpi_block_height = 0
    for line in lines: c.drawString(margin_x, y, line); y -= 14; kpi_block_height += 14

    # Sentiment Pie Chart (remains the same)
    pie_buf = _create_sentiment_pie(sentiment_ratio)
    try:
        img = ImageReader(pie_buf)
        img_width = 150; img_height = 150
        img_x = width - margin_x - img_width - 20
        img_y = height - margin_y - 20 - img_height
        c.drawImage(img, img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')
        y = min(y, img_y - 20)
    except Exception as pie_e:
        print(f"Error drawing pie chart: {pie_e}")
        # Placeholder text if chart fails
        img_x = width - margin_x - 150 - 20; img_y = height - margin_y - 20 - 150
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(img_x, img_y + 150 / 2, "(Sentiment chart failed to load)")
        y -= 20

    # AI Summary Section (remains the same)
    y -= 10
    c.setFont("Helvetica-Bold", 12); c.drawString(margin_x, y, "AI Summary & Recommendations"); y -= 16
    ai_lines = ai_summary.split('\n')
    for r in ai_lines:
         # ... (code to draw AI summary with page breaks) ...
         r = r.strip()
         if not r: y -= 6; continue
         is_bold = r.startswith("**")
         if is_bold: c.setFont("Helvetica-Bold", 10); r = r.replace("**", "")
         else: c.setFont("Helvetica", 10)
         lines = textwrap.wrap(r, width=85)
         for line in lines:
             if y < margin_y + 20:
                 c.showPage(); y = height - margin_y
                 c.setFont("Helvetica-Bold", 12)
                 c.drawString(margin_x, y, "AI Summary & Recommendations (cont.)"); y -= 16
                 if is_bold: c.setFont("Helvetica-Bold", 10)
                 else: c.setFont("Helvetica", 10)
             c.drawString(margin_x, y, line); y -= 12
    y -= 15 # Space after AI summary


    # --- Mention Sections (UPDATED CALLS) ---
    if y < height / 2: c.showPage(); y = height - margin_y
    # Pass 'height' to the helper function
    y = _draw_mention_section(c, y, f"{brand} News Mentions", main_brand_mentions, content_width, margin_x, height)
    y = _draw_mention_section(c, y, "Competition News Mentions", competitor_mentions, content_width, margin_x, height)
    y = _draw_mention_section(c, y, "Related News / Passive Mentions", related_mentions, content_width, margin_x, height)
    # --- END UPDATED CALLS ---

    # Keywords Section (remains the same)
    if y < 150: c.showPage(); y = height - margin_y
    c.setFont("Helvetica-Bold", 12); c.drawString(margin_x, y, "Top Keywords & Phrases"); y -= 16
    c.setFont("Helvetica", 10)
    kw_count = 0
    for w, f in top_keywords:
        text = f"- {w}: {f}"
        if y < margin_y + 10:
             c.showPage(); y = height - margin_y
             c.setFont("Helvetica-Bold", 12); c.drawString(margin_x, y, "Top Keywords & Phrases (cont.)"); y -= 16
             c.setFont("Helvetica", 10)
        c.drawString(margin_x, y, text); y -= 12
        kw_count += 1
    if kw_count == 0:
        c.setFont("Helvetica-Oblique", 10); c.drawString(margin_x, y, "No keywords identified."); y -= 20

    # --- Finalize PDF ---
    c.save()
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    # ---- 3. Return Values ----
    json_summary = {"brand": brand, "competitors": competitors, "kpis": kpis, "top_keywords": top_keywords, "generated_on": generated_on, "ai_summary": ai_summary}

    if include_json:
        return md, pdf_bytes, json_summary
    return md, pdf_bytes
