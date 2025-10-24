# report_gen.py
"""
Enhanced report generator for Flash Narrative.

Public function:
    generate_report(kpis, top_keywords, brand="Brand", competitors=None,
                    timeframe_hours=24, include_json=False)

Returns:
    - By default: (md: str, pdf_bytes: bytes)
    - If include_json=True: (md: str, pdf_bytes: bytes, json_summary: dict)

Notes:
- Keeps default return (md, pdf_bytes) to preserve compatibility with existing dashboard code.
- Embeds a sentiment pie chart into the PDF.
- Requires: reportlab, matplotlib
"""

import io
import json
import textwrap
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import matplotlib.pyplot as plt

# Helpers
def _safe_get(d, key, default=None):
    try:
        return d.get(key, default)
    except Exception:
        return default

def _short_kpi_table(kpis):
    lines = []
    # prefer stable ordering for readability
    keys = [k for k in ['mis', 'mpi', 'engagement_rate', 'reach'] if k in kpis] + \
           [k for k in kpis.keys() if k not in ('mis','mpi','engagement_rate','reach','sov','sentiment_ratio')]
    for k in keys:
        try:
            lines.append(f"- **{k}**: {kpis[k]}")
        except Exception:
            lines.append(f"- **{k}**: {kpis.get(k,'-')}")
    return "\n".join(lines)

def _wrap_text(text, width=90):
    # wrap preserving existing paragraphs
    wrapped = []
    for para in str(text).split("\n"):
        if not para.strip():
            wrapped.append("")
            continue
        for line in textwrap.wrap(para, width=width):
            wrapped.append(line)
    return "\n".join(wrapped)

def _create_sentiment_pie(sentiment_ratio):
    """
    Create a matplotlib pie chart from sentiment_ratio dict and return BytesIO PNG.
    """
    labels = []
    sizes = []
    for tone in ['positive', 'neutral', 'negative']:
        val = float(sentiment_ratio.get(tone, 0)) if sentiment_ratio else 0.0
        if val > 0:
            labels.append(f"{tone} ({val}%)")
            sizes.append(val)
    # fallback if empty
    if not sizes:
        labels = ['neutral (100%)']
        sizes = [100.0]

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, labels=labels, autopct='%1.0f%%', startangle=90)
    ax.axis('equal')  # equal aspect ratio ensures pie is drawn as a circle
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

def _draw_wrapped_text(c, x, y, text, max_width, leading=14, font="Helvetica", font_size=10):
    """
    Draw wrapped text on the canvas starting at (x, y) downward.
    Returns the new y position after drawing.
    """
    c.setFont(font, font_size)
    lines = []
    for paragraph in str(text).split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        wrapped = textwrap.wrap(paragraph, width=max_width)
        lines.extend(wrapped if wrapped else [""])
    for line in lines:
        if y < 60:  # start a new page if we near bottom margin
            c.showPage()
            _draw_header_footer(c, page_num=None, brand=None)  # header/footer optional per page
            y = letter[1] - 70
            c.setFont(font, font_size)
        c.drawString(x, y, line)
        y -= leading
    return y

def _draw_header_footer(c, page_num=None, brand=None):
    width, height = letter
    # Header
    c.setFont("Helvetica-Bold", 10)
    header_text = f"{brand or ''} - Flash Narrative Report"
    c.drawString(50, height - 40, header_text)
    # Footer
    c.setFont("Helvetica", 8)
    footer_text = f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    if page_num is not None:
        footer_text = f"{footer_text}   |   Page {page_num}"
    c.drawString(50, 30, footer_text)

# Main function
def generate_report(kpis, top_keywords, brand="Brand", competitors=None, timeframe_hours=24, include_json=False):
    """
    Generate markdown and PDF report. Optionally return json summary.
    - kpis: dict (must include 'sentiment_ratio' and optionally 'sov','mis','mpi','engagement_rate','reach')
    - top_keywords: list of tuples [(keyword, freq), ...]
    - brand: primary brand name
    - competitors: list of competitor names
    - timeframe_hours: number (used in report header text)
    - include_json: bool -> if True, returns (md, pdf_bytes, json_summary)
    """
    if competitors is None:
        competitors = []

    # Prepare basic data
    sentiment_ratio = _safe_get(kpis, 'sentiment_ratio', {})
    sov = _safe_get(kpis, 'sov', [])
    mis = _safe_get(kpis, 'mis', '-')
    mpi = _safe_get(kpis, 'mpi', '-')
    engagement = _safe_get(kpis, 'engagement_rate', '-')
    reach = _safe_get(kpis, 'reach', '-')

    generated_on = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Markdown generation
    md_lines = []
    md_lines.append(f"# Flash Narrative Report for {brand}\n")
    md_lines.append(f"*This report covers the last {int(timeframe_hours)} hours.*\n")
    md_lines.append(f"**Generated on:** {generated_on}\n")

    md_lines.append("## Overview\n")
    md_lines.append("This report provides insights into your brand's PR performance, including sentiment, visibility, and engagement.\n")

    md_lines.append("## Key Performance Indicators (KPIs)\n")
    md_lines.append(f"- **MIS**: {mis}")
    md_lines.append(f"- **MPI**: {mpi}")
    md_lines.append(f"- **Engagement Rate**: {engagement}")
    md_lines.append(f"- **Reach/Impressions**: {reach}")
    md_lines.append(f"- **Sentiment Ratio**: {sentiment_ratio}")
    # SOV table
    all_brands = [brand] + competitors
    if sov and len(sov) >= len(all_brands):
        md_lines.append("\n### Share of Voice (SOV)\n")
        md_lines.append("| Brand | SOV (%) |")
        md_lines.append("|---|---|")
        for b, s in zip(all_brands, sov):
            md_lines.append(f"| {b} | {s} |")
    else:
        md_lines.append(f"- **SOV**: {sov}")

    md_lines.append("\n## Trends\n")
    md_lines.append("Sentiment trends show a mix of tones; monitor for spikes in negative mentions and identify driving keywords.\n")

    md_lines.append("## Top Keywords/Themes\n")
    if top_keywords:
        for w, f in top_keywords:
            md_lines.append(f"- {w}: {f}")
    else:
        md_lines.append("- No keywords identified.")

    # recommendations (richer)
    md_lines.append("\n## Recommendations\n")
    neg_pct = float(sentiment_ratio.get('negative', 0)) if sentiment_ratio else 0
    pos_pct = float(sentiment_ratio.get('positive', 0)) if sentiment_ratio else 0

    recs = []
    if neg_pct > 50:
        recs.append("High negative sentiment — escalate to PR and prioritize sentiment remediation plans.")
    elif neg_pct > 30:
        recs.append("Moderate negative sentiment — investigate top negative sources and respond where necessary.")
    elif pos_pct > 60:
        recs.append("Strong positive sentiment — capitalize on momentum with promotional pushes.")
    else:
        recs.append("Mixed sentiment — monitor trending keywords and refine messaging to increase MPI.")

    # Keyword-driven recommendation
    if top_keywords:
        top_kw = top_keywords[0][0]
        recs.append(f"Consider content or campaign ideas around **{top_kw}**, which is trending in recent coverage.")

    for r in recs:
        md_lines.append(f"- {r}")

    md_lines.append("\n## Competitive Audit\n")
    if competitors:
        for i, comp in enumerate(competitors):
            comp_sov = sov[i+1] if (isinstance(sov, (list,tuple)) and len(sov) > i+1) else "-"
            brand_sov = sov[0] if (isinstance(sov, (list,tuple)) and len(sov) > 0) else "-"
            md_lines.append(f"- {comp} SOV: {comp_sov} (vs. {brand}: {brand_sov})")
    else:
        md_lines.append("- No competitors provided.")

    md = "\n".join(md_lines)

    # JSON summary (for API use)
    json_summary = {
        "generated_on": generated_on,
        "brand": brand,
        "timeframe_hours": timeframe_hours,
        "kpis": kpis,
        "top_keywords": top_keywords,
        "competitors": competitors
    }

    # PDF generation with ReportLab + embedded pie chart from matplotlib
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter
    margin_x = 50
    y = height - 60

    # Header
    _draw_header_footer(c, page_num=1, brand=brand)

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin_x, y, f"Flash Narrative Report — {brand}")
    y -= 28
    c.setFont("Helvetica", 10)
    c.drawString(margin_x, y, f"This report covers the last {int(timeframe_hours)} hours. Generated on {generated_on}")
    y -= 24

    # KPI block (left) and Sentiment pie (right)
    # Draw KPI text
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Key Performance Indicators")
    y -= 16
    kpi_text = f"MIS: {mis}   |   MPI: {mpi}   |   Engagement: {engagement}   |   Reach: {reach}"
    y = _draw_wrapped_text(c, margin_x, y, kpi_text, max_width=90, leading=14, font_size=10)

    # Insert sentiment pie chart to the right of current y
    pie_buf = _create_sentiment_pie(sentiment_ratio)
    try:
        img = ImageReader(pie_buf)
        # position image to the right column area
        img_w = 150
        img_h = 150
        img_x = width - margin_x - img_w
        img_y = height - 140  # a bit below title area
        c.drawImage(img, img_x, img_y, width=img_w, height=img_h, preserveAspectRatio=True, mask='auto')
    except Exception:
        # If image insertion fails, ignore
        pass

    # Move down below pie if required
    if y < (height - 300):
        y = height - 300

    # Trends / Keywords
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Top Keywords / Themes")
    y -= 16
    kw_lines = [f"{w}: {f}" for w, f in top_keywords] if top_keywords else ["No keywords identified."]
    y = _draw_wrapped_text(c, margin_x, y, "\n".join(kw_lines), max_width=90, leading=12, font_size=10)

    # Recommendations
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Recommendations")
    y -= 16
    y = _draw_wrapped_text(c, margin_x, y, "\n".join(recs), max_width=90, leading=12, font_size=10)

    # Competitive audit
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Competitive Audit")
    y -= 16
    audit_lines = []
    if competitors:
        for i, comp in enumerate(competitors):
            comp_sov = sov[i+1] if (isinstance(sov, (list,tuple)) and len(sov) > i+1) else "-"
            audit_lines.append(f"{comp}: SOV {comp_sov}")
    else:
        audit_lines = ["No competitors provided."]
    y = _draw_wrapped_text(c, margin_x, y, "\n".join(audit_lines), max_width=90, leading=12, font_size=10)

    c.showPage()  # finalize first page
    # Footer for last page
    _draw_header_footer(c, page_num=2, brand=brand)
    c.save()

    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    # Return values: default keep backward compatibility (md, pdf_bytes)
    if include_json:
        return md, pdf_bytes, json_summary
    return md, pdf_bytes
