"""Whole-document parsing: which pages hold a statement table, and why the others do not.

This is the layer the UI and any batch job use. It never raises for a bad page; each page gets a
``PageResult`` that carries either a table or the reason there is none.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .models import Finding, Table
from .ocr import OcrEngine
from .pdf_io import PdfSource, page_count
from .pipeline import Strategy, parse_source
from .triage import UnsupportedPage
from .validate import validate_tables

MIN_VALUED_ROWS = 4  # fewer amount rows than this is not a statement table
MIN_LABELLED_SHARE = 0.6  # most amount rows must carry a label


@dataclass
class PageResult:
    page_no: int  # 0-based
    table: Table | None = None
    reason: str = ""  # why there is no table
    route: str = ""  # how it was read: "banded", "text" ...


def looks_like_statement(table: Table) -> bool:
    """Reject accidental 'tables' found in prose pages (a few figures in running text)."""
    valued = [r for r in table.rows if any(v is not None and v.kind != "text" for v in r.values)]
    if len(valued) < MIN_VALUED_ROWS:
        return False
    labelled = sum(1 for r in valued if r.label)
    return labelled / len(valued) >= MIN_LABELLED_SHARE


def parse_document(
    source: PdfSource,
    pages: Sequence[int] | None = None,
    strategy: Strategy = "auto",
    progress: Callable[[int, int], None] | None = None,
    ocr: OcrEngine | None = None,
    force_ocr: bool = False,
    verify: bool = False,
) -> list[PageResult]:
    """Parse the given pages (default: all) and report a result for each.

    With an OCR engine, a page whose text layer is unusable (a scan) is read through OCR;
    ``force_ocr`` sends every page through OCR. ``verify`` reads each page a second time and records
    where the two reads differ.
    """
    total = page_count(source)
    wanted = list(range(total)) if pages is None else [p for p in pages if 0 <= p < total]
    results: list[PageResult] = []
    for done, page_no in enumerate(wanted, start=1):
        try:
            table = parse_source(
                source, page_no, strategy, ocr=ocr, force_ocr=force_ocr, verify=verify
            )
            if looks_like_statement(table):
                results.append(PageResult(page_no, table, route=str(table.meta.get("route", ""))))
            else:
                results.append(PageResult(page_no, None, "no statement table on this page"))
        except UnsupportedPage as exc:
            results.append(PageResult(page_no, None, str(exc)))
        except Exception as exc:  # noqa: BLE001 - one bad page must not stop the document
            results.append(PageResult(page_no, None, f"error: {type(exc).__name__}: {exc}"))
        if progress is not None:
            progress(done, len(wanted))
    return results


def validate_results(results: Sequence[PageResult]) -> list[Finding]:
    """Accounting checks over every table found, so cross-page rules (balance identity) can run."""
    return validate_tables([r.table for r in results if r.table is not None])
