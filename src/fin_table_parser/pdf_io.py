"""PDF reading. This is the only module that imports PyMuPDF.

Swapping the PDF library (for example to pdfplumber, MIT licensed) means rewriting only this file.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from .models import PageGeometry, Rect, Word

_BLACK = (0.0, 0.0, 0.0)


def _round_color(color: tuple[float, ...]) -> tuple[float, float, float]:
    r, g, b = (round(c, 2) for c in color[:3])
    return (r, g, b)


PdfSource = str | Path | bytes


def _open(source: PdfSource) -> pymupdf.Document:
    """Open a PDF from a path or from bytes (an upload held in memory)."""
    if isinstance(source, bytes):
        return pymupdf.open(stream=source, filetype="pdf")
    return pymupdf.open(str(source))


def page_count(source: PdfSource) -> int:
    with _open(source) as doc:
        return int(doc.page_count)


def page_texts(source: PdfSource) -> list[str]:
    """Plain text of every page (for cheap page-level searches)."""
    with _open(source) as doc:
        return [str(page.get_text()) for page in doc]


def image_coverage(source: PdfSource, page_no: int) -> float:
    """Share of the page area covered by embedded images (0..1): high for a scan or a pasted table."""
    with _open(source) as doc:
        page = doc[page_no]
        area = page.rect.width * page.rect.height
        covered = 0.0
        for info in page.get_image_info():
            box = pymupdf.Rect(info["bbox"]) & page.rect
            covered += box.width * box.height
        return min(1.0, covered / area) if area else 0.0


def page_size(source: PdfSource, page_no: int) -> tuple[float, float]:
    with _open(source) as doc:
        rect = doc[page_no].rect
        return float(rect.width), float(rect.height)


def render_page(
    source: PdfSource,
    page_no: int,
    dpi: int = 110,
    rotate_deg: float = 0.0,
    jpeg_quality: int | None = None,
) -> bytes:
    """PNG (or JPEG when ``jpeg_quality`` is set) bytes of one page.

    ``rotate_deg`` and ``jpeg_quality`` exist to simulate imperfect scans when evaluating OCR.
    """
    with _open(source) as doc:
        page = doc[page_no]
        matrix = pymupdf.Matrix(dpi / 72, dpi / 72).prerotate(rotate_deg)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        if jpeg_quality is not None:
            return bytes(pix.tobytes("jpeg", jpg_quality=jpeg_quality))
        return bytes(pix.tobytes("png"))


def baseline_find_tables(pdf_path: str | Path, page_no: int = 0) -> list[list[str]]:
    """Rows from PyMuPDF's built-in ``find_tables()`` (used only as an evaluation baseline)."""
    with pymupdf.open(str(pdf_path)) as doc:
        tables = doc[page_no].find_tables().tables
        return [[c or "" for c in row] for t in tables for row in t.extract()]


def load_page(pdf_path: PdfSource, page_no: int = 0) -> PageGeometry:
    """Read words and filled rectangles of one page (0-based ``page_no``)."""
    with _open(pdf_path) as doc:
        page = doc[page_no]
        words = [Word(w[4], w[0], w[1], w[2], w[3]) for w in page.get_text("words")]
        fills: list[Rect] = []
        rules: list[Rect] = []
        for drawing in page.get_drawings():
            r = drawing["rect"]
            color = drawing.get("fill")
            if color is not None:
                fill = _round_color(color)
                rect = Rect(r.x0, r.y0, r.x1, r.y1, fill)
                (rules if fill == _BLACK else fills).append(rect)
                continue
            stroke = drawing.get("color")
            # Some producers draw table rules as stroked horizontal lines instead of thin filled
            # rectangles; normalise them to the same Rect form (centred on the line).
            if stroke is not None and r.height < 0.01 and sum(stroke[:3]) < 0.3:
                half = (drawing.get("width") or 0.5) / 2
                rules.append(Rect(r.x0, r.y0 - half, r.x1, r.y0 + half, _BLACK))
        return PageGeometry(
            page_no=page_no,
            width=page.rect.width,
            height=page.rect.height,
            words=words,
            fills=fills,
            rules=rules,
        )
