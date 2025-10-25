# report_gen.py
import io
import textwrap
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.colors import navy, black, gray # Import colors
import matplotlib.pyplot as plt
# Use alias for clarity
from bedrock import generate_llm_report_summary as generate_ai_summary

# --- Helper to create sentiment pie chart (no changes needed) ---
def _create_sentiment_pie(sentiment_ratio):
    # ... (Keep the existing _create_sentiment_pie function code) ...
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


# --- NEW Helper function to draw a section of mentions in the PDF ---
def _draw_mention_section(c, y, title, mentions, width, margin_x):
    """Draws a titled section with mentions (headline, source, link)."""
    styles = getSampleStyleSheet()
    max_y = y # Store starting y for checking space

    # Draw Section Title
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(navy) # Use a color for section titles
    c.drawString(margin_x, y, title)
    y -= 20 # Space after title
    c.setFillColor(black) # Reset color

    mention_count = 0
    max_mentions_per_section = 15 # Limit mentions per category to avoid huge PDFs

    for item in mentions:
        if mention_count >= max_mentions_per_section:
            break

        headline = item.get('text', 'No Headline')[:200] # Truncate headline
        source = item.get('source', 'Unknown Source')
        link = item.get('link', None)

        # Check for page break BEFORE drawing the item
        # Estimate height needed (headline lines + source line + padding)
        headline_lines = textwrap.wrap(headline, width=80)
        estimated_height = len(headline_lines) * 14 + 14 + 10 # Approx height needed
        if y < estimated_height + 60: # Check if enough space remains + bottom margin
            c.showPage()
            y = height - 60 # Reset Y for new page
            # Redraw title on new page if needed (optional)
            # c.setFont("Helvetica-Bold", 14); c.setFillColor(navy)
            # c.drawString(margin_x, y, title + " (cont.)"); y -= 20
            # c.setFillColor(black)

        # Draw Headline (using Paragraph for potential wrapping)
        c.setFont("Helvetica-Bold", 10)
        # Wrap headline text manually
        lines = textwrap.wrap(headline, width=80)
        for line in lines:
            c.drawString(margin_x, y, line)
            y -= 12 # Line spacing

        # Draw Source and Link
        c.setFont("Helvetica", 9)
        c.setFillColor(gray)
        source_text = f"Source: {source}"
        c.drawString(margin_x, y, source_text)

        # If link exists, draw it next to the source
        if link:
            # Simple link drawing - assumes it fits on one line
             link_text = " (Link)"
             text_width = c.stringWidth(source_text, "Helvetica", 9)
             link_x = margin_x + text_width
             # Draw the blue underlined link text
             c.setFillColor(navy)
             c.linkURL(link, (link_x, y - 2, link_x + c.stringWidth(link_text, "Helvetica", 9), y + 10), relative=1)
             c.drawString(link_x, y, link_text)
             # Draw underline for the link text
             c.line(link_x, y - 1, link_x + c.stringWidth(link_text, "Helvetica", 9), y-1)

        y -= 14 # Space after source/link
        c.setFillColor(black) # Reset color

        y -= 10 # Space between mentions
        mention_count += 1

    if mention_count == 0:
         c.setFont("Helvetica-Oblique", 10)
         c.drawString(margin_x, y, "No specific mentions found in this category.")
         y -= 20

    # Return the updated Y position
    return y


# --- Main Report Generation Function (UPDATED STRUCTURE) ---
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

        if mentions_main and not mentions_comp:
            main_brand_mentions.append(item)
        elif not mentions_main and mentions_comp:
            competitor_mentions.append(item)
        else: # Includes mentions of both, or mentions of neither
            related_mentions.append(item)

    # --- Get KPI data ---
    sentiment_ratio = kpis.get('sentiment_ratio', {})
    sov = kpis.get('sov', [])
    all_brands = kpis.get('all_brands', [brand] + competitors)
    mis = kpis.get('mis', 0)
    mpi = kpis.get('mpi', 0)
    engagement = kpis.get('engagement_rate', 0)
    reach = kpis.get('reach', 0)
    generated_on = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if isinstance(timeframe_hours, int):
        time_text = f"the last {timeframe_hours} hours"
    else:
        time_text = timeframe_hours

    # --- Generate AI Summary ---
    # Ensure this runs even if PDF generation fails later
    ai_summary = "AI Summary generation failed." # Default text
    try:
        ai_summary = generate_ai_summary(kpis, top_keywords, full_articles_data, brand)
    except Exception as ai_e:
        print(f"Error generating AI summary: {ai_e}")


    # ---- 1. Markdown Generation (Updated Structure) ----
    md_lines = [f"# Flash Narrative Report: {brand}",
                f"**Period:** {time_text}",
                f"**Generated:** {generated_on}",
                "\n## Executive Summary", # Placeholder if needed
                ai_summary, # Add AI summary early on
                "\n## Key Performance Indicators",
                f"- **Media Impact Score (MIS):** {mis:.0f}",
                f"- **Message Penetration (MPI):** {mpi:.1f}%",
                f"- **Avg. Social Engagement:** {engagement:.1f}",
                f"- **Total Reach:** {reach:,}",
                f"- **Sentiment Ratio:** " + ", ".join([f"{k.capitalize()}: {v:.1f}%" for k, v in sentiment_ratio.items()]),
                "\n### Share of Voice (SOV)",
                "| Brand | SOV (%) |", "|---|---|"]
    if len(sov) < len(all_brands): sov += [0] * (len(all_brands) - len(sov))
    for b, s in zip(all_brands, sov): md_lines.append(f"| {b} | {s:.1f} |")

    # Add Mention Categories to Markdown
    md_lines.append(f"\n## {brand} News Mentions")
    if main_brand_mentions:
        for item in main_brand_mentions[:10]: # Limit in markdown too
             md_lines.append(f"- **{item.get('text','No Headline')[:150]}...** ([{item.get('source','Source')}]({item.get('link','#')}))")
    else: md_lines.append("_No specific mentions found._")

    md_lines.append("\n## Competition News Mentions")
    if competitor_mentions:
         for item in competitor_mentions[:10]:
              md_lines.append(f"- **{item.get('text','No Headline')[:150]}...** ([{item.get('source','Source')}]({item.get('link','#')}))")
    else: md_lines.append("_No competitor mentions found._")

    md_lines.append("\n## Related News / Passive Mentions")
    if related_mentions:
         for item in related_mentions[:10]:
              md_lines.append(f"- **{item.get('text','No Headline')[:150]}...** ([{item.get('source','Source')}]({item.get('link','#')}))")
    else: md_lines.append("_No related mentions found._")


    md_lines.append("\n## Top Keywords & Phrases")
    if top_keywords:
        for w, f in top_keywords: md_lines.append(f"- {w}: {f}")
    else: md_lines.append("- No keywords identified.")

    md = "\n".join(md_lines)


    # ---- 2. PDF Generation (Updated Structure) ----
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter # Get page dimensions
    margin_x = 50
    margin_y = 60 # Define top/bottom margin
    content_width = width - 2 * margin_x

    # --- Page 1 ---
    y = height - margin_y # Start Y position

    # Title and Date
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin_x, y, f"Flash Narrative Report: {brand}")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(margin_x, y, f"Period: {time_text} | Generated: {generated_on}")
    y -= 25

    # KPIs
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Key Performance Indicators"); y -= 16
    c.setFont("Helvetica", 10)
    kpi_text = f"MIS: {mis:.0f} | MPI: {mpi:.1f}% | Avg. Engagement: {engagement:.1f} | Reach: {reach:,}"
    lines = textwrap.wrap(kpi_text, width=70) # Adjust wrap width if needed
    kpi_block_height = 0
    for line in lines:
        c.drawString(margin_x, y, line); y -= 14
        kpi_block_height += 14

    # Sentiment Pie Chart (Position relative to KPIs)
    pie_buf = _create_sentiment_pie(sentiment_ratio)
    try:
        img = ImageReader(pie_buf)
        img_width = 150 # Smaller chart?
        img_height = 150
        img_x = width - margin_x - img_width - 20 # Position right
        img_y = height - margin_y - 20 - img_height # Position below title, align top with KPIs?
        c.drawImage(img, img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')
        # Ensure 'y' doesn't go above the bottom of the chart if KPIs are short
        y = min(y, img_y - 20)
    except Exception as pie_e:
        print(f"Error drawing pie chart: {pie_e}")
        # Draw placeholder text if chart fails
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(img_x, img_y + img_height / 2, "(Sentiment chart failed to load)")
        y -= 20 # Add some space anyway

    # AI Summary Section (Below KPIs/Chart)
    y -= 10 # Space before AI summary
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "AI Summary & Recommendations"); y -= 16
    c.setFont("Helvetica", 10)
    ai_lines = ai_summary.split('\n')
    for r in ai_lines:
        r = r.strip()
        if not r: y -= 6; continue
        is_bold = r.startswith("**")
        if is_bold:
            c.setFont("Helvetica-Bold", 10)
            r = r.replace("**", "")
        else:
            c.setFont("Helvetica", 10)
        lines = textwrap.wrap(r, width=85) # Wrap AI summary text
        for line in lines:
            if y < margin_y + 20: # Check for page break
                c.showPage(); y = height - margin_y
                c.setFont("Helvetica-Bold", 12) # Maybe add section title continuation?
                c.drawString(margin_x, y, "AI Summary & Recommendations (cont.)"); y -= 16
                if is_bold: c.setFont("Helvetica-Bold", 10)
                else: c.setFont("Helvetica", 10)
            c.drawString(margin_x, y, line); y -= 12
    y -= 15 # Space after AI summary

    # --- Mention Sections ---
    # Check if a new page is needed before starting mentions
    if y < height / 2: # Arbitrary check, if less than half page left
         c.showPage(); y = height - margin_y

    y = _draw_mention_section(c, y, f"{brand} News Mentions", main_brand_mentions, content_width, margin_x)
    y = _draw_mention_section(c, y, "Competition News Mentions", competitor_mentions, content_width, margin_x)
    y = _draw_mention_section(c, y, "Related News / Passive Mentions", related_mentions, content_width, margin_x)

    # Keywords Section (Maybe start on new page if little space left)
    if y < 150: # Check space before keywords
        c.showPage(); y = height - margin_y

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Top Keywords & Phrases"); y -= 16
    c.setFont("Helvetica", 10)
    kw_count = 0
    for w, f in top_keywords: # Show all top N keywords
        text = f"- {w}: {f}"
        if y < margin_y + 10: # Check page break
            c.showPage(); y = height - margin_y
            c.setFont("Helvetica-Bold", 12) # Redraw title?
            c.drawString(margin_x, y, "Top Keywords & Phrases (cont.)"); y -= 16
            c.setFont("Helvetica", 10)
        c.drawString(margin_x, y, text); y -= 12
        kw_count += 1
    if kw_count == 0:
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(margin_x, y, "No keywords identified.")
        y -= 20

    # --- Finalize PDF ---
    c.save() # Save the PDF to the buffer
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    # ---- 3. Return Values ----
    json_summary = {"brand": brand, "competitors": competitors, "kpis": kpis, "top_keywords": top_keywords, "generated_on": generated_on, "ai_summary": ai_summary}

    if include_json:
        return md, pdf_bytes, json_summary
    return md, pdf_bytes
