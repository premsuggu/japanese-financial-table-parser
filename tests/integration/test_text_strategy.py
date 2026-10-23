"""The band-free (words only) strategy: the basis for OCR and for pages without shaded rows."""

from pathlib import Path

import pymupdf
import pytest

from fin_table_parser.evaluate import load_truth, score_against_truth, table_diff
from fin_table_parser.labels import label_key
from fin_table_parser.pipeline import parse_page
from fin_table_parser.triage import UnsupportedPage
from fin_table_parser.validate import summarize, validate_tables

from ..conftest import CORRECTED_PDF, ROOT, TRUTH_JSON

CORPUS = ROOT / "data" / "corpus" / "yamato"


@pytest.fixture(scope="module")
def stripped_pdf(tmp_path_factory) -> Path:
    """The sample page with every drawing removed; the text layer is untouched."""
    path = tmp_path_factory.mktemp("stripped") / "no_graphics.pdf"
    with pymupdf.open(str(CORRECTED_PDF)) as doc:
        page = doc[0]
        page.add_redact_annot(page.rect)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
            text=pymupdf.PDF_REDACT_TEXT_NONE,
        )
        doc.save(str(path))
    return path


def test_banded_strategy_refuses_a_page_without_bands(stripped_pdf):
    with pytest.raises(UnsupportedPage):
        parse_page(stripped_pdf, strategy="banded")


def test_auto_falls_back_to_the_text_strategy(stripped_pdf):
    assert parse_page(stripped_pdf).meta["strategy"] == "text"


def test_stripped_page_matches_ground_truth_except_drawing_flags(stripped_pdf):
    scores = score_against_truth(parse_page(stripped_pdf), load_truth(TRUTH_JSON))
    assert scores.rows_pred == scores.rows_truth == 43
    assert all(r.correct == r.total for r in scores.metrics.values())
    assert scores.cells.fp == scores.cells.fn == 0
    # The only difference: underline flags need drawings, which this page no longer has.
    assert scores.underline.tp == 0 and scores.underline.fn == 2


def test_text_strategy_passes_the_accounting_checks(stripped_pdf):
    counts = summarize(validate_tables([parse_page(stripped_pdf)]))
    assert counts["FAIL"] == counts["WARN"] == 0


def test_page_number_is_not_mistaken_for_a_row(stripped_pdf):
    table = parse_page(stripped_pdf)
    assert table.rows[-1].label == "資産合計"
    assert table.meta["lines_below"] == ["-4-"]


def test_text_strategy_survives_rescaling(tmp_path, stripped_pdf):
    with pymupdf.open(str(stripped_pdf)) as src:
        w, h = src[0].rect.width, src[0].rect.height
        doc = pymupdf.open()
        page = doc.new_page(width=w * 1.6, height=h * 1.6)
        page.show_pdf_page(pymupdf.Rect(0, 0, w * 1.6, h * 1.6), src, 0)
        doc.save(str(tmp_path / "big.pdf"))
    scores = score_against_truth(parse_page(tmp_path / "big.pdf"), load_truth(TRUTH_JSON))
    assert scores.cells.fp == scores.cells.fn == 0
    assert scores.metrics["row.level"].correct == scores.metrics["row.level"].total


def _statement_pages():
    if not CORPUS.exists():
        return []
    pages = []
    for pdf in sorted(CORPUS.glob("*/*.pdf")):
        with pymupdf.open(str(pdf)) as doc:
            for i, page in enumerate(doc):
                text = label_key(page.get_text())
                if ("資産合計" in text and "流動資産" in text) or "負債純資産合計" in text:
                    pages.append((pdf, i))
    return pages


@pytest.mark.skipif(not CORPUS.exists(), reason="corpus not downloaded")
def test_text_and_banded_strategies_agree_on_the_corpus():
    """Same rows, labels, levels, types and printed values on every page both can read."""
    compared, disagreements = 0, []
    for pdf, i in _statement_pages():
        try:
            banded = parse_page(pdf, i, strategy="banded")
        except UnsupportedPage:
            continue  # a grid-ruled page: the banded strategy does not apply
        diffs = table_diff(banded, parse_page(pdf, i, strategy="text"))
        compared += 1
        if diffs:
            disagreements.append((pdf.parent.name, i, diffs[:3]))
    assert compared >= 20
    assert disagreements == []


@pytest.mark.skipif(not CORPUS.exists(), reason="corpus not downloaded")
def test_annual_report_footnote_markers_are_read_not_dropped():
    pdf = CORPUS / "S100YMK7" / "S100YMK7.pdf"
    for strategy in ("banded", "text"):
        table = parse_page(pdf, 42, strategy=strategy)
        building = next(r for r in table.rows if r.label == "建物及び構築物")
        assert building.values[0].number == 2121360
        assert building.values[0].notes == ("※1",)
        assert building.values[0].raw.startswith("※")  # the printed form is kept
        counts = summarize(validate_tables([table]))
        assert counts["FAIL"] == 0, strategy


@pytest.mark.skipif(not CORPUS.exists(), reason="corpus not downloaded")
def test_label_wrapped_over_two_lines_is_one_row():
    pdf = ROOT / "complete_pdf.pdf"
    table = parse_page(pdf, 13, strategy="text")
    wrapped = [
        r for r in table.rows if r.label.startswith("連結の範囲の変更を伴う子会社株式の売却による")
    ]
    assert len(wrapped) == 1
    assert wrapped[0].label.endswith("収入")
    assert wrapped[0].values[1].number == 185770
