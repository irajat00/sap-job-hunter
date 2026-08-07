"""
Exports a list of jobs (by job_url, from frontend bookmarks) to
CSV/Excel/PDF. Pure formatting -- no DB writes, no schema involvement.
"""
import csv
import io

FIELDS = ["title", "company", "location", "salary", "source", "posted_date", "job_url"]


def export_csv(jobs: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    writer.writeheader()
    for j in jobs:
        writer.writerow(j)
    return buf.getvalue().encode("utf-8")


def export_excel(jobs: list[dict]) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Bookmarked Jobs"
    ws.append(FIELDS)
    for j in jobs:
        ws.append([j.get(f, "") or "" for f in FIELDS])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_pdf(jobs: list[dict]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Bookmarked Jobs — AI Job Hunter", styles["Title"])]

    data = [["Title", "Company", "Location", "Source", "URL"]]
    for j in jobs:
        data.append([j.get("title", ""), j.get("company", ""), j.get("location", ""),
                     j.get("source", ""), j.get("job_url", "")])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(table)
    doc.build(elements)
    return buf.getvalue()


EXPORTERS = {"csv": export_csv, "excel": export_excel, "pdf": export_pdf}
