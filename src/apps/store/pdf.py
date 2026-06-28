# -*- coding: UTF-8 -*-
"""Server-side PDF + QR export for gemological reports.

Uses reportlab only: the QR codes are drawn with reportlab's built-in
``barcode.qr`` widget, so no external QR/imaging service is required. Report
images are embedded on a best-effort basis (fetched from their short-lived
signed URLs); a failed fetch is skipped rather than aborting the whole export.
"""

from io import BytesIO

import requests
from django.conf import settings
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .storage import signed_url

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm
BRAND = "GemsLabé"


def report_share_url(report):
    base = getattr(settings, "GEMS_SITE_URL", "https://gemsla.be").rstrip("/")
    return f"{base}/reports/{report.id}"


def _qr_drawing(data, size):
    widget = QrCodeWidget(data)
    widget.barLevel = "M"
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    return drawing


def _fetch_image(image_url):
    try:
        url = signed_url(image_url)
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return ImageReader(BytesIO(response.content))
    except Exception:
        return None


def _draw_image(pdf, reader, x, top, max_width, max_height):
    try:
        iw, ih = reader.getSize()
    except Exception:
        return 0
    if not iw or not ih:
        return 0
    scale = min(max_width / iw, max_height / ih)
    width = iw * scale
    height = ih * scale
    pdf.drawImage(reader, x, top - height, width=width, height=height, preserveAspectRatio=True, mask="auto")
    return height


def build_report_pdf(report, include_admin_fields=False):
    """Render a single report (with QR code + images) to PDF bytes."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(report.title or "report")

    content_width = PAGE_WIDTH - 2 * MARGIN
    y = PAGE_HEIGHT - MARGIN

    qr_size = 28 * mm
    qr = _qr_drawing(report_share_url(report), qr_size)
    renderPDF.draw(qr, pdf, PAGE_WIDTH - MARGIN - qr_size, y - qr_size)

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(MARGIN, y - 14, BRAND)
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(MARGIN, y - 28, "Gemological Report")

    y -= qr_size + 8 * mm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(MARGIN, y, report.title or "")
    y -= 8 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(MARGIN, y, "Olena Rybnikova, PhD.")
    y -= 10 * mm

    rows = [("Stone", report.stone)]
    rows += [
        ("Shape / cutting style", report.shape_cutting_style),
        ("Measurements", report.measurements),
        ("Carat weight", report.carat_weight),
        ("Specific gravity", report.specific_gravity),
        ("Refractive index", report.refractive_index),
        ("Double refraction", report.double_refraction),
        ("Polariscope", report.polariscope),
        ("Pleochroism", report.pleochroism),
        ("Chelsea color filter", report.chelsea_color_filter),
        ("Fluorescence (SW)", report.fluorescence_sw),
        ("Fluorescence (LW)", report.fluorescence_lw),
        ("Microscope", report.microscope),
        ("Treatment", report.treatment),
        ("Origin", report.origin),
    ]
    if include_admin_fields:
        price = None
        if report.price is not None:
            price = f"{report.price} {report.currency or ''}".strip()
        rows += [
            ("Customer", " ".join(filter(None, [report.first_name, report.last_name])) or None),
            ("Email", report.owner_email),
            ("Telephone", report.owner_telephone),
            ("Price", price),
            ("Note", report.note),
        ]

    label_x = MARGIN
    value_x = MARGIN + 55 * mm
    for label, value in rows:
        if value in (None, ""):
            continue
        if y < MARGIN + 20 * mm:
            pdf.showPage()
            y = PAGE_HEIGHT - MARGIN
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(label_x, y, f"{label}:")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(value_x, y, str(value)[:80])
        y -= 6 * mm

    for image in report.images.all():
        reader = _fetch_image(image.image_url)
        if reader is None:
            continue
        pdf.showPage()
        top = PAGE_HEIGHT - MARGIN
        if image.title:
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(MARGIN, top, image.title)
            top -= 8 * mm
        drawn = _draw_image(pdf, reader, MARGIN, top, content_width, PAGE_HEIGHT - 2 * MARGIN - 30 * mm)
        if image.caption:
            pdf.setFont("Helvetica-Oblique", 9)
            pdf.drawString(MARGIN, top - drawn - 6 * mm, str(image.caption)[:120])

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def build_qr_sheet_pdf(reports):
    """Render a printable A4 grid of QR-code labels for the given reports."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    cols = 4
    rows = 8
    per_page = cols * rows
    cell_w = (PAGE_WIDTH - 2 * MARGIN) / cols
    cell_h = (PAGE_HEIGHT - 2 * MARGIN) / rows
    qr_size = min(cell_w, cell_h) - 16 * mm

    reports = list(reports)
    for index, report in enumerate(reports):
        position = index % per_page
        if position == 0 and index > 0:
            pdf.showPage()
        col = position % cols
        row = position // cols
        x = MARGIN + col * cell_w
        top = PAGE_HEIGHT - MARGIN - row * cell_h

        qr = _qr_drawing(report_share_url(report), qr_size)
        renderPDF.draw(qr, pdf, x + (cell_w - qr_size) / 2, top - qr_size - 4 * mm)

        text_y = top - qr_size - 9 * mm
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawCentredString(x + cell_w / 2, text_y, (report.title or "")[:28])
        pdf.setFont("Helvetica", 6)
        pdf.drawCentredString(x + cell_w / 2, text_y - 4 * mm, (report.stone or "")[:30])

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
