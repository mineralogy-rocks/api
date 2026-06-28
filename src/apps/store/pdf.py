# -*- coding: UTF-8 -*-
"""Server-side PDF + QR export for gemological reports.

Uses reportlab only: the QR codes are drawn with reportlab's built-in
``barcode.qr`` widget, so no external QR/imaging service is required. Report
images are embedded on a best-effort basis (fetched from their short-lived
signed URLs); a failed fetch is skipped rather than aborting the whole export.
"""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.files.storage import storages
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .storage import STORE_PRIVATE_STORAGE_ALIAS
from .storage import signed_url

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm
BRAND = "GemsLabé"

REPORT_LEFT = 50
REPORT_RIGHT = PAGE_WIDTH - 50
REPORT_GOLD = (0.75, 0.65, 0.5)
REPORT_GRAY = (0.4, 0.4, 0.4)
REPORT_LIGHT_GRAY = (0.5, 0.5, 0.5)
REPORT_EXPERT = "MSc Olena Rybnikova, PhD"
REPORT_WARNING = "(colors may be distorted)"
FOOTER_COMPANY = "Rutheniai s.r.o."
FOOTER_ADDRESS = "Karpatske namestie 7770/10A, Bratislava – Rača, 831 06, Slovakia"
FOOTER_CONTACT = "www.gemsla.be  |  olena.rybnikova@gemsla.be  |  @olena_rybnikova"

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"
_REPORT_FONTS_READY = False


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
    if not image_url:
        return None

    storage_name = _private_storage_name(image_url)
    if storage_name:
        try:
            storage = storages[STORE_PRIVATE_STORAGE_ALIAS]
            with storage.open(storage_name, "rb") as image_file:
                return ImageReader(BytesIO(image_file.read()))
        except Exception:
            pass

    try:
        url = image_url if str(image_url).startswith(("http://", "https://")) else signed_url(image_url)
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return ImageReader(BytesIO(response.content))
    except Exception:
        return None


def _private_storage_name(image_url):
    value = str(image_url)
    if not value.startswith(("http://", "https://")):
        return value

    local_media_url = getattr(settings, "STORE_LOCAL_MEDIA_URL", "")
    if local_media_url:
        private_base = f"{local_media_url.rstrip('/')}/store_private/"
        if value.startswith(private_base):
            return unquote(value.removeprefix(private_base))

    parsed = urlparse(value)
    marker = "/store_private/"
    if marker in parsed.path:
        return unquote(parsed.path.split(marker, 1)[1])
    return None


def _draw_image(pdf, reader, x, top, max_width, max_height, center=False):
    try:
        iw, ih = reader.getSize()
    except Exception:
        return 0, 0
    if not iw or not ih:
        return 0, 0
    scale = min(max_width / iw, max_height / ih)
    width = iw * scale
    height = ih * scale
    draw_x = x + ((max_width - width) / 2 if center else 0)
    pdf.drawImage(reader, draw_x, top - height, width=width, height=height, preserveAspectRatio=True, mask="auto")
    return width, height


def _register_report_fonts():
    global FONT_REGULAR, FONT_BOLD, FONT_ITALIC, _REPORT_FONTS_READY
    if _REPORT_FONTS_READY:
        return

    base_dir = Path(getattr(settings, "BASE_DIR", "") or ".")
    candidate_dirs = [
        Path(value)
        for value in (
            Path(__file__).resolve().parent / "fonts",
            getattr(settings, "REPORT_FONT_DIR", None),
            base_dir.parent / "gems-labe" / "public" / "fonts",
            base_dir.parent.parent / "gems-labe" / "public" / "fonts",
        )
        if value
    ]
    for font_dir in candidate_dirs:
        regular = font_dir / "Lora-Regular.ttf"
        bold = font_dir / "Lora-Bold.ttf"
        italic = font_dir / "Lora-Italic.ttf"
        if not regular.exists() or not bold.exists() or not italic.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("LoraReportRegular", str(regular)))
            pdfmetrics.registerFont(TTFont("LoraReportBold", str(bold)))
            pdfmetrics.registerFont(TTFont("LoraReportItalic", str(italic)))
        except Exception:
            continue
        FONT_REGULAR = "LoraReportRegular"
        FONT_BOLD = "LoraReportBold"
        FONT_ITALIC = "LoraReportItalic"
        break

    _REPORT_FONTS_READY = True


def _set_fill(pdf, color):
    pdf.setFillColorRGB(*color)


def _draw_text(pdf, text, x, y, font_name, size, color=(0, 0, 0), align="left"):
    if text in (None, ""):
        return
    value = str(text)
    pdf.setFont(font_name, size)
    _set_fill(pdf, color)
    if align == "center":
        pdf.drawCentredString(x, y, value)
    elif align == "right":
        pdf.drawRightString(x, y, value)
    else:
        pdf.drawString(x, y, value)


def _string_width(text, font_name, size):
    return pdfmetrics.stringWidth(str(text), font_name, size)


def _wrap_text(text, font_name, size, max_width):
    if text in (None, ""):
        return []
    wrapped = []
    for raw_line in str(text).splitlines() or [""]:
        words = raw_line.split()
        if not words:
            wrapped.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if _string_width(candidate, font_name, size) <= max_width:
                line = candidate
            else:
                wrapped.append(line)
                line = word
        wrapped.append(line)
    return wrapped


def _draw_wrapped_text(pdf, text, x, y, max_width, font_name, size, color=(0, 0, 0), line_height=13):
    lines = _wrap_text(text, font_name, size, max_width)
    for index, line in enumerate(lines):
        _draw_text(pdf, line, x, y - index * line_height, font_name, size, color)
    return len(lines)


def _draw_header(pdf, report, include_qr=False):
    _draw_text(pdf, BRAND, REPORT_LEFT, 791.89, FONT_REGULAR, 14)
    _draw_text(pdf, "Gemological Expertise and Consultancy", REPORT_LEFT, 775.89, FONT_ITALIC, 9, REPORT_GRAY)
    _draw_text(pdf, report.title or "Gemstone Identification Report", REPORT_LEFT, 755.89, FONT_BOLD, 14)

    if include_qr:
        qr_size = 60
        qr = _qr_drawing(report_share_url(report), qr_size)
        renderPDF.draw(qr, pdf, REPORT_RIGHT - qr_size, 731.89)
        _draw_text(pdf, REPORT_EXPERT, REPORT_LEFT, 737.69, FONT_ITALIC, 9, REPORT_GRAY)
        line_y = 721.99
    else:
        line_y = 733.69

    pdf.setStrokeColorRGB(*REPORT_GOLD)
    pdf.setLineWidth(1)
    pdf.line(REPORT_LEFT, line_y, REPORT_RIGHT, line_y)
    return line_y


def _draw_footer(pdf):
    pdf.setStrokeColorRGB(*REPORT_GOLD)
    pdf.setLineWidth(1)
    pdf.line(REPORT_LEFT, 55, REPORT_RIGHT, 55)

    center = PAGE_WIDTH / 2
    _draw_text(pdf, FOOTER_COMPANY, center, 41, FONT_BOLD, 7, align="center")
    _draw_text(pdf, FOOTER_ADDRESS, center, 31, FONT_REGULAR, 6.5, align="center")
    _draw_text(pdf, FOOTER_CONTACT, center, 21, FONT_REGULAR, 6.5, align="center")


def _format_decimal(value):
    if value in (None, ""):
        return None
    text = f"{value}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _format_carat_weight(value):
    if value in (None, ""):
        return None
    carats = _format_decimal(value)
    try:
        grams = Decimal(str(value)) * Decimal("0.2")
        grams_text = f"{grams:.4f}"
    except Exception:
        grams_text = None
    if grams_text:
        return f"{carats} ct ({grams_text} g)"
    return f"{carats} ct"


def _draw_field(pdf, label, value, x, label_y, width):
    if value in (None, ""):
        return 0
    _draw_text(pdf, label.upper(), x, label_y, FONT_REGULAR, 8, REPORT_GRAY)
    line_count = _draw_wrapped_text(pdf, value, x, label_y - 12.4, width, FONT_REGULAR, 10)
    return 12.4 + line_count * 13


def _draw_two_column_row(pdf, left, right, label_y):
    left_height = _draw_field(pdf, left[0], left[1], REPORT_LEFT, label_y, 230) if left else 0
    right_height = _draw_field(pdf, right[0], right[1], 315.28, label_y, 230) if right else 0
    if not left_height and not right_height:
        return label_y
    line_count_height = max(left_height, right_height)
    return label_y - line_count_height - 6


def _report_fields(report):
    return {
        "stone": report.stone,
        "shape_cutting_style": report.shape_cutting_style,
        "measurements": report.measurements,
        "carat_weight": _format_carat_weight(report.carat_weight),
        "specific_gravity": report.specific_gravity,
        "refractive_index": report.refractive_index,
        "double_refraction": report.double_refraction,
        "polariscope": report.polariscope,
        "pleochroism": report.pleochroism,
        "chelsea_color_filter": report.chelsea_color_filter,
        "microscope": report.microscope,
        "fluorescence_sw": report.fluorescence_sw,
        "fluorescence_lw": report.fluorescence_lw,
        "treatment": report.treatment,
        "origin": report.origin,
    }


def _headline_image(images):
    for image in images:
        if image.is_headline:
            return image
    return images[0] if images else None


def _draw_headline_image(pdf, image):
    if image is None:
        return
    reader = _fetch_image(image.image_url)
    if reader is None:
        return
    width, height = _draw_image(pdf, reader, 330, 701.99, 215, 220)
    if not height:
        return
    caption = image.caption or REPORT_WARNING
    _draw_text(pdf, caption, 330 + width / 2, 701.99 - height - 12, FONT_ITALIC, 7, REPORT_LIGHT_GRAY, align="center")


def _draw_first_page(pdf, report, images):
    _draw_header(pdf, report, include_qr=True)

    fields = _report_fields(report)
    headline = _headline_image(images)
    _draw_headline_image(pdf, headline)

    top_rows = [
        ("Stone identification", fields["stone"]),
        ("Shape / cutting style", fields["shape_cutting_style"]),
        ("Measurements", fields["measurements"]),
        ("Carat weight", fields["carat_weight"]),
        ("Specific gravity", fields["specific_gravity"]),
    ]
    for (label, value), y in zip(top_rows, [701.99, 670.59, 639.19, 607.79, 576.39], strict=True):
        _draw_field(pdf, label, value, REPORT_LEFT, y, 250)

    y = 447.99
    y = _draw_two_column_row(
        pdf, ("Refractive index", fields["refractive_index"]), ("Double refraction", fields["double_refraction"]), y
    )
    y = _draw_two_column_row(pdf, ("Polariscope", fields["polariscope"]), ("Pleochroism", fields["pleochroism"]), y)
    y = _draw_two_column_row(
        pdf,
        ("Chelsea color filter", fields["chelsea_color_filter"]),
        ("Microscope", fields["microscope"]),
        y,
    )
    y = _draw_two_column_row(
        pdf, ("Fluorescence SW", fields["fluorescence_sw"]), ("Fluorescence LW", fields["fluorescence_lw"]), y
    )
    y = _draw_two_column_row(pdf, ("Treatment", fields["treatment"]), ("Origin", fields["origin"]), y)

    return headline, y


def _draw_admin_fields(pdf, report, y):
    rows = []
    customer = " ".join(filter(None, [report.first_name, report.last_name]))
    if customer:
        rows.append(("Customer", customer))
    rows += [
        ("Email", report.owner_email),
        ("Telephone", report.owner_telephone),
        ("Price", f"{report.price} {report.currency or ''}".strip() if report.price is not None else None),
        ("Note", report.note),
    ]
    rows = [(label, value) for label, value in rows if value not in (None, "")]
    if not rows:
        return

    y -= 8
    if y < 110:
        _draw_footer(pdf)
        pdf.showPage()
        _draw_header(pdf, report)
        y = 705
    pdf.setStrokeColorRGB(*REPORT_GOLD)
    pdf.setLineWidth(1)
    pdf.line(REPORT_LEFT, y, REPORT_RIGHT, y)
    y -= 20
    for label, value in rows:
        if y < 95:
            _draw_footer(pdf)
            pdf.showPage()
            _draw_header(pdf, report)
            y = 705
        consumed = _draw_field(pdf, label, value, REPORT_LEFT, y, REPORT_RIGHT - REPORT_LEFT)
        y -= consumed + 6


def _draw_extra_images(pdf, report, images, headline):
    extra_images = []
    for image in images:
        if image == headline:
            continue
        reader = _fetch_image(image.image_url)
        if reader is not None:
            extra_images.append((image, reader))
    if not extra_images:
        return False

    pdf.showPage()
    _draw_header(pdf, report)
    top = 713.69
    for image, reader in extra_images:
        if top - 280 < 90:
            _draw_footer(pdf)
            pdf.showPage()
            _draw_header(pdf, report)
            top = 713.69

        width, height = _draw_image(pdf, reader, REPORT_LEFT, top, REPORT_RIGHT - REPORT_LEFT, 280, center=True)
        if not height:
            continue
        title = image.title or image.caption
        if title:
            _draw_text(pdf, title, PAGE_WIDTH / 2, top - height - 10, FONT_BOLD, 9, align="center")
        top = top - height - 32
    return True


def build_report_pdf(report, include_admin_fields=False):
    """Render a single report (with QR code + images) to PDF bytes."""
    _register_report_fonts()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(report.title or "report")

    images = list(report.images.all())
    headline, y = _draw_first_page(pdf, report, images)
    if include_admin_fields:
        _draw_admin_fields(pdf, report, y)
    _draw_footer(pdf)
    if _draw_extra_images(pdf, report, images, headline):
        _draw_footer(pdf)

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
