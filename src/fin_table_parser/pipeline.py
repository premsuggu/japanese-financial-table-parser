"""High-level entry points: PDF page -> Table (-> workbook)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Literal

from .crosscheck import compare_reads
from .models import Finding, PageGeometry, Table
from .ocr import OcrEngine, ocr_geometry
from .pdf_io import PdfSource, image_coverage, load_page
from .strategies.banded import extract_banded
from .strategies.deskew import deskew_words
from .strategies.textgeom import NoTableFound, extract_text
from .triage import MIN_BANDS, UnsupportedPage, check_banded, check_text_layer, count_bands

Strategy = Literal["auto", "banded", "text"]


def parse_geometry(geom: PageGeometry, source: str = "", strategy: Strategy = "auto") -> Table:
    """Parse one page's geometry. ``auto`` uses row bands when the page has them, else words only."""
    if strategy == "banded" or (strategy == "auto" and count_bands(geom) >= MIN_BANDS):
        check_banded(geom)
        try:
            return extract_banded(geom, source=source)
        except ValueError as exc:  # bands that do not form columns: not a table this strategy reads
            raise UnsupportedPage(f"banded layout not usable: {exc}") from exc
    check_text_layer(geom)
    return _extract_text(geom, source)


def _extract_text(geom: PageGeometry, source: str) -> Table:
    try:
        table = extract_text(geom, source=source)
    except NoTableFound as exc:
        raise UnsupportedPage(f"no table found in the words: {exc}") from exc
    return table


def parse_ocr_words(geom: PageGeometry, source: str = "") -> Table:
    """Table from OCR words: straighten the page, then the words-only strategy.

    The one function both ``parse_source`` and the OCR bake-off use, so what is measured is what runs.
    There is no text-layer health gate here: that gate exists to catch garbled PDF text, and OCR
    output is judged by the accounting checks instead.
    """
    words, angle = deskew_words(geom.words)
    table = _extract_text(replace(geom, words=words), source)
    table.meta["skew_degrees"] = round(angle, 2)
    return table


def parse_source(
    pdf: PdfSource,
    page_no: int = 0,
    strategy: Strategy = "auto",
    ocr: OcrEngine | None = None,
    force_ocr: bool = False,
    verify: bool = False,
) -> Table:
    """Parse one page, using the text layer when it is usable and OCR otherwise.

    The route is recorded in ``table.meta["route"]`` ("text-layer" or "ocr:<engine>").
    With ``verify`` the page is read a second time (OCR against the text layer, or OCR at another
    pixel size) and the differences are kept in ``table.meta["read_findings"]``.
    """
    name = Path(pdf).name if isinstance(pdf, str | Path) else "upload.pdf"
    if not force_ocr:
        try:
            table = parse_geometry(load_page(pdf, page_no), name, strategy)
            table.meta["route"] = "text-layer"
            if verify and ocr is not None:
                _second_read(table, pdf, page_no, ocr, name, rescale=1.0)
            return table
        except UnsupportedPage as exc:
            if ocr is None or not _needs_ocr(str(exc), lambda: image_coverage(pdf, page_no)):
                raise
    if ocr is None:
        raise UnsupportedPage("OCR requested but no OCR engine is available")
    table = parse_ocr_words(ocr_geometry(pdf, page_no, ocr), name)
    table.meta["route"] = f"ocr:{ocr.name}"
    if verify:
        _second_read(table, pdf, page_no, ocr, name, rescale=SECOND_READ_SCALE)
    return table


# The second read of a scan is the same picture at another pixel size: a different input for the
# engine, so its random mistakes tend to differ from the first read's.
SECOND_READ_SCALE = 0.75


def _second_read(
    table: Table, pdf: PdfSource, page_no: int, ocr: OcrEngine, name: str, rescale: float
) -> None:
    """Read the page again and record every disagreement with ``table`` (never raises)."""
    try:
        second = parse_ocr_words(ocr_geometry(pdf, page_no, ocr, rescale=rescale), name)
        findings = compare_reads(table, second)
    except UnsupportedPage as exc:
        findings = [
            Finding(
                "read_agreement",
                "WARN",
                table.statement,
                "",
                "",
                detail=f"second read failed: {exc}",
            )
        ]
    table.meta["reads"] = 2
    table.meta["read_findings"] = findings


IMAGE_PAGE_SHARE = 0.5  # an image covering this much of the page may hold the table


def _needs_ocr(reason: str, coverage: Callable[[], float]) -> bool:
    """OCR is justified by an unusable text layer, or by 'no table' on a page that is mostly a picture.

    'No table' on an ordinary text page is not a reason: OCR would only read the same prose again.
    """
    if "text layer" in reason:
        return True
    return "no table found" in reason and coverage() >= IMAGE_PAGE_SHARE


def parse_page(pdf_path: str | Path, page_no: int = 0, strategy: Strategy = "auto") -> Table:
    """Parse one page of a file with its text layer. Raises ``UnsupportedPage`` if impossible."""
    return parse_source(pdf_path, page_no, strategy)
