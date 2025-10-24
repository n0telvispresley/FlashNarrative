# report_gen.py
"""
Enhanced report generator for Flash Narrative with optional LLM summary.

Public function:
    generate_report(kpis, top_keywords, brand="Brand", competitors=None,
                    timeframe_hours=24, include_json=False, llm_summarizer=None)

Returns:
    - By default: (md: str, pdf_bytes: bytes)
    - If include_json=True: (md: str, pdf_bytes: bytes, json_summary: dict)

Notes:
- llm_summarizer: optional callable that takes (kpis, top_keywords, competitors) and returns a string summary.
- Keeps default return (md, pdf_bytes) to preserve compatibility.
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

def _wrap_text(text, width=90):
    wrapped = []
    for para in str(text).split("\n"):
        if not para.strip():
            wrapped.append("")
            continue
        for line in textwrap.wrap(para, width=width):
            wrapped.append(line)
    return "\n".join(wrapped)

def _create_sentiment_pie(sentiment_ratio):
    labels, sizes = [], []
    for tone in ['positive', 'neutral', 'negative']:
        val = float(sentiment_ratio.get(tone, 0)) if sentiment_ratio else 0.0
        if val > 0:
            labels.append(f"{tone} ({val}%)")
            sizes.append(val)
    if not sizes:
        labels = ['neutral (100%)']
        sizes = [100.0]
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, labels=labels, autopct='%1.0f%%', startangle=90)
    ax.axis('equal')
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

def _draw_wrapped_text(c, x, y, text, max_width, leading=14, font="Helvetica", font_size=10):
    c.setFont(font, font_size)
    lines = []
    for paragraph in str(text).split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        wrapped = textwrap.wrap(paragraph, width=max_width)
        lines.extend(wrapped if wrapped else [""])
    for line in lines:
        if y < 60:
            c.showPage()
            _draw_header_footer(c)
            y = letter[1] - 70
            c.setFont(font, font_size)
        c.drawString(x, y, line)
        y -= leading
    return y

def _draw_header_footer(c, page_num=None, brand=None):
    width, height = letter
    c.setFont("Helvetica-Bold", 10)
    header_text = f"{brand or ''} - Flash Narrative Report"
    c.drawString(50, height - 40, header_text)
    c.setFont("Helvetica", 8)
    footer_text = f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    if page_num is not None:
        footer_text = f"{footer_text}   |   Page {page_num}"
    c.drawString(50, 30, footer_text)

# Main function
def generate_report(
    kpis, top_keywords, brand="Brand", competitors=None,
    timeframe_hours=24, include_json=False, llm_summarizer=None
):
    if competitors is None:
        competitors = []

    sentiment_ratio = _safe_get(kpis, 'sentiment_ratio', {})
    sov = _safe_get(kpis, 'sov', [])
    mis = _safe_get(kpis, 'mis', '-')
    mpi = _safe_get(kpis, 'mpi', '-')
    engagement = _safe_get(kpis, 'engagement_rate', '-')
    reach = _safe_get(kpis, 'reach', '-')

    generated_on = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Markdown
    md_lines = [
        f"# Flash Narrative Report for {brand}\n",
        f"*This report covers the last {int(timeframe_hours)} hours.*\n",
        f"**Generated on:** {generated_on}\n",
        "## Overview\n",
        "This report provides insights into your brand's PR performance, including sentiment, visibility, and engagement.\n",
        "## Key Performance Indicators (KPIs)\n",
        f"- **MIS**: {mis}",
        f"- **MPI**: {mpi}",
        f"- **Engagement Rate**: {engagement}",
        f"- **Reach/Impressions**: {reach}",
        f"- **Sentiment Ratio**: {sentiment_ratio}"
    ]

    # SOV table
    all_brands = [brand] + competitors
    if sov and len(sov) >= len(all_brands):
        md_lines.append("\n### Share of Voice (SOV)\n| Brand | SOV (%) |\n|---|---|")
        for b, s in zip(all_brands, sov):
            md_lines.append(f"| {b} | {s} |")
    else:
        md_lines.append(f"- **SOV**: {sov}")

    # Trends / keywords
    md_lines.append("\n## Top Keywords / Themes\n")
    if top_keywords:
        for w, f in top_keywords:
            md_lines.append(f"- {w}: {f}")
    else:
        md_lines.append("- No keywords identified.")

    # LLM summary integration
    if llm_summarizer:
        try:
            llm_summary = llm_summarizer(kpis, top_keywords, competitors)
            md_lines.append("\n## AI Summary\n")
            md_lines.append(_wrap_text(llm_summary))
        except Exception as e:
            md_lines.append("\n## AI Summary\nFailed to generate LLM summary: " + str(e))

    md = "\n".join(md_lines)

    # JSON summary
    json_summary = {
        "generated_on": generated_on,
        "brand": brand,
        "timeframe_hours": timeframe_hours,
        "kpis": kpis,
        "top_keywords": top_keywords,
        "competitors": competitors,
        "llm_summary": llm_summary if llm_summarizer else None
    }

    # PDF
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter
    margin_x = 50
    y = height - 60

    _draw_header_footer(c, page_num=1, brand=brand)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin_x, y, f"Flash Narrative Report — {brand}")
    y -= 28
    c.setFont("Helvetica", 10)
    c.drawString(margin_x, y, f"This report covers the last {int(timeframe_hours)} hours. Generated on {generated_on}")
    y -= 24

    # KPI block
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Key Performance Indicators")
    y -= 16
    kpi_text = f"MIS: {mis}   |   MPI: {mpi}   |   Engagement: {engagement}   |   Reach: {reach}"
    y = _draw_wrapped_text(c, margin_x, y, kpi_text, max_width=90, leading=14, font_size=10)

    # Sentiment pie
    pie_buf = _create_sentiment_pie(sentiment_ratio)
    try:
        img = ImageReader(pie_buf)
        c.drawImage(img, width - margin_x - 150, height - 140, width=150, height=150, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass

    # Top keywords
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin_x, y, "Top Keywords / Themes")
    y -= 16
    kw_lines = [f"{w}: {f}" for w, f in top_keywords] if top_keywords else ["No keywords identified."]
    y = _draw_wrapped_text(c, margin_x, y, "\n".join(kw_lines), max_width=90, leading=12, font_size=10)

    # LLM summary in PDF
    if llm_summarizer:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_x, y, "AI Summary")
        y -= 16
        y = _draw_wrapped_text(c, margin_x, y, llm_summary, max_width=90, leading=12, font_size=10)

    c.showPage()
    _draw_header_footer(c, page_num=2, brand=brand)
    c.save()
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    if include_json:
        return md, pdf_bytes, json_summary
    return md, pdf_bytes
