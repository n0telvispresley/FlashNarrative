import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def generate_report(kpis, top_keywords, brand="Brand", competitors=[]):
    """
    Generate Markdown report and PDF bytes for download.
    Includes overview, KPIs, trends (simple), keywords, recommendations, competitive audit.
    """
    all_brands = [brand] + competitors  # Assume sov order: brand first, then competitors
    sov_values = kpis.get('sov', [0] * len(all_brands))

    # Markdown generation
    md = f"# Flash Narrative Report for {brand}\n\n"

    md += "## Overview\n"
    md += "This report provides insights into your brand's PR performance, including sentiment, visibility, and engagement.\n\n"

    md += "## Key Performance Indicators (KPIs)\n"
    md += f"- Sentiment Ratio: {kpis['sentiment_ratio']}\n"
    md += f"- Share of Voice (SOV): {dict(zip(all_brands, sov_values))}\n"
    md += f"- Media Impact Score (MIS): {kpis['mis']}\n"
    md += f"- Message Penetration Index (MPI): {kpis['mpi']}\n"
    md += f"- Engagement Rate: {kpis['engagement_rate']}\n"
    md += f"- Reach/Impressions: {kpis['reach']}\n\n"

    md += "## Trends\n"
    md += "Sentiment trends show a mix of tones; monitor for spikes in negative or anger sentiments.\n\n"  # MVP simple; expand with data grouping

    md += "## Top Keywords/Themes\n"
    for word, freq in top_keywords:
        md += f"- {word}: {freq}\n"
    md += "\n"

    md += "## Recommendations\n"
    if kpis['sentiment_ratio'].get('negative', 0) > 30:
        md += "- Address negative sentiment drivers urgently.\n"
    if kpis['mpi'] < 0.5:
        md += "- Improve campaign message penetration through targeted PR.\n"
    md += "- Leverage top keywords in future content.\n\n"

    md += "## Competitive Audit\n"
    for i, comp in enumerate(competitors):
        md += f"- {comp} SOV: {sov_values[i+1]}% (vs. {brand}: {sov_values[0]}%)\n"
    md += "\n"

    # PDF generation
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter
    y = height - 50  # Start position

    def draw_section(title, content, y_pos):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_pos, title)
        y_pos -= 20
        c.setFont("Helvetica", 12)
        for line in content.split('\n'):
            if line.strip():
                c.drawString(60, y_pos, line)
                y_pos -= 15
        return y_pos - 10

    y = draw_section("Flash Narrative Report", f"For {brand}", y)
    y = draw_section("Overview", "This report provides insights into your brand's PR performance.", y)
    
    kpi_text = "\n".join([f"{k}: {v}" for k, v in kpis.items() if k != 'sov' and k != 'sentiment_ratio'])
    kpi_text += f"\nSentiment Ratio: {kpis['sentiment_ratio']}"
    kpi_text += f"\nSOV: {dict(zip(all_brands, sov_values))}"
    y = draw_section("KPIs", kpi_text, y)
    
    y = draw_section("Trends", "Sentiment trends show a mix of tones.", y)
    
    keywords_text = "\n".join([f"{w}: {f}" for w, f in top_keywords])
    y = draw_section("Top Keywords", keywords_text, y)
    
    rec_text = "Recommendations based on data:\n" + "\n".join(md.split("## Recommendations\n")[1].split("\n")[1:-3])
    y = draw_section("Recommendations", rec_text, y)
    
    audit_text = "\n".join([f"{comp}: {sov_values[i+1]}%" for i, comp in enumerate(competitors)])
    y = draw_section("Competitive Audit", audit_text, y)
    
    c.save()
    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.close()

    return md, pdf_bytes
