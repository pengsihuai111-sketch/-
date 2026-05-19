"""PDF processing utility — convert PDF pages to images for Claude recognition."""

import io
import logging
from typing import List

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

MAX_PDF_PAGES = 30
PDF_DPI = 300  # Resolution for rendering (increased for better OCR quality)


def pdf_to_images(pdf_bytes: bytes, max_pages: int = MAX_PDF_PAGES) -> List[bytes]:
    """Convert PDF pages to JPEG images.

    Args:
        pdf_bytes: Raw PDF file bytes.
        max_pages: Maximum number of pages to process (0 = unlimited).

    Returns:
        List of JPEG image bytes, one per page.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = min(len(doc), max_pages) if max_pages > 0 else len(doc)

    if total_pages == 0:
        raise ValueError("PDF 文件为空")

    images = []
    for page_num in range(total_pages):
        page = doc[page_num]
        # Render page to pixmap at specified DPI
        mat = fitz.Matrix(PDF_DPI / 72, PDF_DPI / 72)
        pix = page.get_pixmap(matrix=mat)

        # Convert pixmap to PIL Image, then save as JPEG
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95, optimize=True)
        img_bytes = buf.getvalue()
        images.append(img_bytes)

        # Quality check
        if pix.width < 1200 or pix.height < 1200:
            logger.warning(
                f"PDF page {page_num + 1} resolution may be too low: "
                f"{pix.width}x{pix.height}. Consider higher DPI for better recognition."
            )

        logger.info(
            f"PDF page {page_num + 1}/{total_pages}: "
            f"{pix.width}x{pix.height}, {len(img_bytes) / 1024:.0f}KB"
        )

    doc.close()
    return images
