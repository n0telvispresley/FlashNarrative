import io
import textwrap
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import matplotlib.pyplot as plt

def _create_sentiment_pie(sentiment_ratio):
    labels, sizes = [], []
    for tone in ['positive','neutral','negative']:
        val = float(sentiment_ratio.get(tone,0))
        if val>0:
            labels.append(f"{tone} ({val:.1f}%)")
            sizes.append(val)
    if not sizes:
        labels=['neutral (100%)']
        sizes=[100.0]
    fig, ax = plt.subplots(figsize=(4,4))
    ax.pie(sizes, labels=labels, autopct='%1.0f%%', startangle=90)
    ax.axis('equal')
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_report(kpis, top_keywords, brand="Brand", competitors=None, timeframe_hours=24, include_json=False):
    if competitors is None: competitors=[]
    sentiment_ratio = kpis.get('sentiment_ratio', {})
    sov = kpis.get('sov', [0]*(len(competitors)+1))
    mis = kpis.get('mis',0)
    mpi = kpis.get('mpi',0)
    engagement = kpis.get('engagement_rate',0)
    reach = kpis.get('reach',0)
    generated_on = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Markdown
    md_lines = [f"# Flash Narrative Report for {brand}",
                f"*This report covers the last {timeframe_hours} hours.*",
                f"**Generated on:** {generated_on}",
                "\n## Key Performance Indicators",
                f"- MIS: {mis}", f"- MPI: {mpi}", f"- Engagement Rate: {engagement}", f"- Reach: {reach}",
                f"- Sentiment Ratio: {sentiment_ratio}"]

    all_brands = [brand]+competitors
    if len(sov)<len(all_brands): sov+=[0]*(len(all_brands)-len(sov))
    md_lines.append("\n### Share of Voice (SOV)")
    md_lines.append("| Brand | SOV (%) |"); md_lines.append("|---|---|")
    for b,s in zip(all_brands,sov):
        md_lines.append(f"| {b} | {s:.1f} |")

    md_lines.append("\n## Top Keywords / Themes")
    if top_keywords:
        for w,f in top_keywords:
            md_lines.append(f"- {w}: {f}")
    else: md_lines.append("- No keywords identified.")

    # Recommendations
    recs=[]
    neg_pct = sentiment_ratio.get('negative',0)
    pos_pct = sentiment_ratio.get('positive',0)
    if neg_pct>50: recs.append("High negative sentiment — escalate to PR.")
    elif neg_pct>30: recs.append("Moderate negative sentiment — monitor sources.")
    elif pos_pct>60: recs.append("Strong positive sentiment — capitalize momentum.")
    else: recs.append("Mixed sentiment — monitor trending keywords.")

    if top_keywords:
        recs.append(f"Consider content ideas around **{top_keywords[0][0]}**.")

    md_lines.append("\n## Recommendations")
    for r in recs: md_lines.append(f"- {r}")

    md = "\n".join(md_lines)

    # PDF
    pdf_buffer=io.BytesIO()
    c=canvas.Canvas(pdf_buffer,pagesize=letter)
    width,height=letter
    margin_x=50
    y=height-60
    c.setFont("Helvetica-Bold",18)
    c.drawString(margin_x,y,f"Flash Narrative Report — {brand}")
    y-=28
    c.setFont("Helvetica",10)
    c.drawString(margin_x,y,f"This report covers the last {timeframe_hours} hours. Generated on {generated_on}")
    y-=24

    # KPI block
    c.setFont("Helvetica-Bold",12)
    c.drawString(margin_x,y,"Key Performance Indicators"); y-=16
    kpi_text=f"MIS: {mis} | MPI: {mpi} | Engagement: {engagement} | Reach: {reach}"
    lines = textwrap.wrap(kpi_text,width=90)
    for line in lines:
        c.drawString(margin_x,y,line); y-=14

    # Sentiment pie
    pie_buf=_create_sentiment_pie(sentiment_ratio)
    img=ImageReader(pie_buf)
    c.drawImage(img,width-margin_x-150,height-140,width=150,height=150,preserveAspectRatio=True,mask='auto')

    # Keywords
    y-=20
    c.setFont("Helvetica-Bold",12)
    c.drawString(margin_x,y,"Top Keywords / Themes"); y-=16
    for w,f in top_keywords:
        text=f"{w}: {f}"
        for line in textwrap.wrap(text,width=90):
            c.drawString(margin_x,y,line); y-=12

    # Recommendations
    y-=10
    c.setFont("Helvetica-Bold",12)
    c.drawString(margin_x,y,"Recommendations"); y-=16
    for r in recs:
        for line in textwrap.wrap(r,width=90):
            c.drawString(margin_x,y,line); y-=12

    c.showPage()
    c.save()
    pdf_bytes=pdf_buffer.getvalue()
    pdf_buffer.close()

    json_summary={"brand":brand,"competitors":competitors,"kpis":kpis,"top_keywords":top_keywords,"generated_on":generated_on}

    if include_json: return md,pdf_bytes,json_summary
    return md,pdf_bytes
