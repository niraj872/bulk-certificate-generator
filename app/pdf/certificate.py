from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas


def _register_fonts() -> tuple[str, str]:
    # Built-in Helvetica keeps the container image small and avoids external font dependencies.
    return "Helvetica", "Helvetica-Bold"


def generate_certificate_pdf(
    *,
    output_path: Path,
    certificate_title: str,
    event_name: str,
    certificate_date: date,
    issuer_name: str | None,
    recipient_name: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    regular, bold = _register_fonts()
    page_width, page_height = landscape(A4)

    pdf = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
    pdf.setTitle(f"Certificate - {recipient_name}")

    margin = 28
    pdf.setStrokeColor(colors.HexColor("#1F3A5F"))
    pdf.setLineWidth(3)
    pdf.rect(margin, margin, page_width - 2 * margin, page_height - 2 * margin)
    pdf.setStrokeColor(colors.HexColor("#C5A46D"))
    pdf.setLineWidth(1)
    pdf.rect(margin + 10, margin + 10, page_width - 2 * margin - 20, page_height - 2 * margin - 20)

    center_x = page_width / 2
    pdf.setFillColor(colors.HexColor("#1F3A5F"))
    pdf.setFont(bold, 28)
    pdf.drawCentredString(center_x, page_height - 105, certificate_title.upper())

    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.setFont(regular, 13)
    pdf.drawCentredString(center_x, page_height - 145, "This certificate is proudly presented to")

    pdf.setFillColor(colors.HexColor("#111111"))
    pdf.setFont(bold, 30)
    pdf.drawCentredString(center_x, page_height - 205, recipient_name)

    pdf.setFillColor(colors.HexColor("#444444"))
    pdf.setFont(regular, 14)
    pdf.drawCentredString(center_x, page_height - 245, f"for participation in {event_name}")

    pdf.setStrokeColor(colors.HexColor("#C5A46D"))
    pdf.line(center_x - 160, page_height - 270, center_x + 160, page_height - 270)

    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.setFont(regular, 12)
    pdf.drawCentredString(center_x, page_height - 310, f"Date: {certificate_date.strftime('%d %B %Y')}")

    if issuer_name:
        pdf.setFont(bold, 13)
        pdf.setFillColor(colors.HexColor("#1F3A5F"))
        pdf.drawCentredString(center_x, 85, issuer_name)
        pdf.setFont(regular, 10)
        pdf.setFillColor(colors.HexColor("#666666"))
        pdf.drawCentredString(center_x, 68, "Authorized Issuer")

    pdf.showPage()
    pdf.save()
