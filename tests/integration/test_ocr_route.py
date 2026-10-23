"""Hybrid routing with a stand-in OCR engine (no real engine needed)."""

import pymupdf
import pytest

from fin_table_parser.evaluate import load_truth, score_against_truth
from fin_table_parser.ocr import clean_text, ocr_geometry
from fin_table_parser.pdf_io import load_page
from fin_table_parser.pipeline import parse_ocr_words, parse_source
from fin_table_parser.triage import UnsupportedPage
from fin_table_parser.validate import summarize, validate_tables

from ..conftest import CORRECTED_PDF, TRUTH_JSON
from ..ocr_sim import SimulatedOcr


@pytest.fixture(scope="module")
def scanned_pdf(tmp_path_factory):
    """The sample page as a picture only: no text layer, like a scan."""
    path = tmp_path_factory.mktemp("scan") / "scan.pdf"
    with pymupdf.open(str(CORRECTED_PDF)) as src:
        png = src[0].get_pixmap(dpi=150).tobytes("png")
        w, h = src[0].rect.width, src[0].rect.height
    doc = pymupdf.open()
    doc.new_page(width=w, height=h).insert_image(pymupdf.Rect(0, 0, w, h), stream=png)
    doc.save(str(path))
    return path


@pytest.fixture(scope="module")
def truth():
    return load_truth(TRUTH_JSON)


@pytest.fixture(scope="module")
def sim():
    return SimulatedOcr(load_page(CORRECTED_PDF, 0))


def test_scan_has_no_text_layer_and_needs_ocr(scanned_pdf):
    assert load_page(scanned_pdf, 0).words == []
    with pytest.raises(UnsupportedPage, match="text layer"):
        parse_source(scanned_pdf)  # no engine available


def test_scan_is_parsed_through_ocr(scanned_pdf, sim, truth):
    table = parse_source(scanned_pdf, ocr=sim)
    assert table.meta["route"] == "ocr:simulated"
    scores = score_against_truth(table, truth)
    assert scores.cells.fp == scores.cells.fn == 0
    assert all(r.correct == r.total for r in scores.metrics.values())
    assert summarize(validate_tables([table]))["FAIL"] == 0


def test_healthy_text_layer_never_calls_ocr():
    engine = SimulatedOcr(load_page(CORRECTED_PDF, 0))
    table = parse_source(CORRECTED_PDF, ocr=engine)
    assert table.meta["route"] == "text-layer"
    assert engine.calls == []


def test_ocr_is_not_used_to_second_guess_a_healthy_page_with_no_table(complete_pdf):
    engine = SimulatedOcr(load_page(complete_pdf, 4))
    with pytest.raises(UnsupportedPage):
        parse_source(complete_pdf, 4, ocr=engine)  # a prose page: no table, text layer is fine
    assert engine.calls == []


def test_force_ocr_runs_the_engine_even_with_a_text_layer(truth):
    engine = SimulatedOcr(load_page(CORRECTED_PDF, 0))
    table = parse_source(CORRECTED_PDF, ocr=engine, force_ocr=True)
    assert table.meta["route"] == "ocr:simulated" and len(engine.calls) == 1
    assert score_against_truth(table, truth).cells.fn == 0


@pytest.mark.parametrize("jitter", [0.0, 1.0, 2.0])
@pytest.mark.parametrize("split_signs", [False, True])
def test_text_strategy_tolerates_ocr_like_noise(truth, jitter, split_signs):
    engine = SimulatedOcr(load_page(CORRECTED_PDF, 0), jitter_pt=jitter, split_signs=split_signs)
    geom = ocr_geometry(CORRECTED_PDF, 0, engine)
    scores = score_against_truth(parse_ocr_words(geom, "x"), truth)
    assert scores.cells.fp == scores.cells.fn == 0
    assert all(r.correct == r.total for r in scores.metrics.values())


@pytest.mark.parametrize("skew", [-2.0, -1.0, 0.5, 1.0, 2.0])
def test_a_rotated_scan_is_straightened_before_extraction(truth, skew):
    engine = SimulatedOcr(load_page(CORRECTED_PDF, 0), skew_deg=skew, split_signs=True)
    table = parse_ocr_words(ocr_geometry(CORRECTED_PDF, 0, engine), "x")
    assert abs(table.meta["skew_degrees"] - skew) < 0.3  # the estimate is close to the truth
    scores = score_against_truth(table, truth)
    assert scores.cells.fp == scores.cells.fn == 0
    assert all(r.correct == r.total for r in scores.metrics.values())


def test_a_straight_page_is_not_rotated(truth):
    engine = SimulatedOcr(load_page(CORRECTED_PDF, 0))
    table = parse_ocr_words(ocr_geometry(CORRECTED_PDF, 0, engine), "x")
    assert table.meta["skew_degrees"] == 0.0


def test_table_pasted_as_a_picture_on_a_text_page_goes_to_ocr(tmp_path, truth):
    """The page has a text layer (a caption) but the table is an image: no table in the words."""
    with pymupdf.open(str(CORRECTED_PDF)) as src:
        png = src[0].get_pixmap(dpi=150).tobytes("png")
        w, h = src[0].rect.width, src[0].rect.height
    doc = pymupdf.open()
    page = doc.new_page(width=w, height=h)
    page.insert_image(pymupdf.Rect(0, 0, w, h), stream=png)
    # a caption large enough to give the page a healthy text layer
    for i in range(30):  # 30 separate Japanese words: a healthy text layer with no table in it
        page.insert_text(
            (20 + (i % 6) * 80, 12 + (i // 6) * 9), "参考資料", fontsize=6, fontname="japan"
        )
    path = tmp_path / "pasted.pdf"
    doc.save(str(path))
    with pytest.raises(UnsupportedPage, match="no table found"):
        parse_source(path)  # no engine: the reason is reported
    sim = SimulatedOcr(load_page(CORRECTED_PDF, 0))
    table = parse_source(path, ocr=sim)
    assert table.meta["route"] == "ocr:simulated"
    assert score_against_truth(table, truth).cells.fn == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("リース資産", "リース資産"),  # the long-vowel mark inside a word is untouched
        ("ー", "－"),
        ("—", "－"),
        ("Δ2,979", "△2,979"),
        ("▲1,000", "△1,000"),
        ("  608,281 ", "608,281"),
        ("Δ", "△"),
    ],
)
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


def test_verify_two_reads_of_a_scan_agree_and_are_recorded(scanned_pdf, sim):
    table = parse_source(scanned_pdf, ocr=sim, verify=True)
    assert table.meta["reads"] == 2 and table.meta["read_findings"] == []
    checks = {f.check: f.status for f in validate_tables([table])}
    assert checks["read_agreement"] == "PASS"


def test_verify_flags_a_digit_the_second_read_got_wrong(scanned_pdf):
    first = load_page(CORRECTED_PDF, 0)
    amount = next(
        w.text for w in first.words if w.text.replace(",", "").isdigit() and len(w.text) > 5
    )
    engine = SimulatedOcr(first, wrong_on_call={2: (amount, "9" + amount[1:])})
    table = parse_source(scanned_pdf, ocr=engine, verify=True)
    findings = table.meta["read_findings"]
    assert len(findings) == 1 and findings[0].status == "WARN"
    assert summarize(validate_tables([table]))["WARN"] >= 1


def test_verify_compares_the_text_layer_with_ocr():
    engine = SimulatedOcr(load_page(CORRECTED_PDF, 0))
    table = parse_source(CORRECTED_PDF, ocr=engine, verify=True)
    assert table.meta["route"] == "text-layer" and table.meta["read_findings"] == []
    assert len(engine.calls) == 1
