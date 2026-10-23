"""Whole-document parsing and the Streamlit page, driven end to end."""

import textwrap

import pytest
from streamlit.testing.v1 import AppTest

from fin_table_parser import validate_tables
from fin_table_parser.document import parse_document, validate_results
from fin_table_parser.export import workbook_bytes
from fin_table_parser.validate import summarize
from fin_table_parser.xlsx_reader import read_workbook

from ..conftest import COMPLETE_PDF, CORRECTED_PDF, ROOT

APP = ROOT / "src" / "fin_table_parser" / "app.py"
SUPPORTED = ("balance_sheet", "income_statement", "comprehensive_income", "cash_flow")


def test_parse_document_finds_the_statement_pages(complete_pdf):
    results = parse_document(complete_pdf)
    found = {r.page_no + 1: r.table.kind for r in results if r.table}
    expected = {
        8: "balance_sheet",
        9: "balance_sheet",
        10: "income_statement",
        11: "comprehensive_income",
        14: "cash_flow",
        15: "cash_flow",
    }
    for page, kind in expected.items():
        assert found[page] == kind
    assert all(not r.reason.startswith("error") for r in results)


def test_prose_pages_do_not_become_tables(complete_pdf):
    results = parse_document(complete_pdf)
    prose = [r for r in results if r.page_no in (3, 4, 5, 6)]  # contents and commentary pages
    assert all(r.table is None for r in prose)


def test_whole_filing_checks_pass_for_the_supported_statements(complete_pdf):
    results = [
        r
        for r in parse_document(complete_pdf)
        if r.table and r.table.kind in SUPPORTED and r.page_no + 1 in (8, 9, 10, 11, 14, 15)
    ]
    counts = summarize(validate_results(results))
    assert counts["FAIL"] == 0 and counts["SKIP"] == 0


def test_workbook_bytes_round_trip(complete_pdf, tmp_path):
    results = [r for r in parse_document(complete_pdf) if r.table and r.page_no + 1 in (8, 9)]
    path = tmp_path / "out.xlsx"
    path.write_bytes(workbook_bytes([r.table for r in results], validate_results(results)))
    reread = read_workbook(path)
    assert [len(t.rows) for t in reread] == [43, 36]
    assert reread[1].statement == ""  # untitled continuation page
    assert summarize(validate_tables(reread))["FAIL"] == 0


# ---------------------------------------------------------------- the Streamlit page


def run_app_with_upload(tmp_path, pdf):
    """Run the real app script, replacing the file picker by a stand-in holding ``pdf``."""
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(
        textwrap.dedent(
            f"""
            import runpy
            from pathlib import Path
            import streamlit as st

            class FakeUpload:
                name = {pdf.name!r}
                def getvalue(self):
                    return Path({str(pdf)!r}).read_bytes()

            st.file_uploader = lambda *a, **k: FakeUpload()
            runpy.run_path({str(APP)!r})
            """
        ),
        encoding="utf-8",
    )
    at = AppTest.from_file(str(wrapper), default_timeout=90)
    at.run()
    return at


def test_app_without_a_file_shows_the_prompt():
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    assert not at.exception
    assert any("Drop a PDF" in i.value for i in at.info)


def test_app_with_a_single_page_file(tmp_path):
    at = run_app_with_upload(tmp_path, CORRECTED_PDF)
    assert not at.exception, at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert int(metrics["Tables found"]) == 1
    assert int(metrics["Checks failed"]) == 0


@pytest.mark.skipif(not COMPLETE_PDF.exists(), reason="complete_pdf.pdf not present")
def test_app_with_a_full_filing_defaults_to_the_balance_sheet(tmp_path):
    at = run_app_with_upload(tmp_path, COMPLETE_PDF)
    assert not at.exception, at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert int(metrics["Tables found"]) == 2  # the two balance-sheet pages
    assert int(metrics["Checks failed"]) == 0


def test_only_real_statement_pages_get_a_green_tick(complete_pdf):
    """No cover-page or notes table may look verified: a tick needs a passed accounting check."""
    from fin_table_parser.ui_model import group_health

    found = [r for r in parse_document(complete_pdf) if r.table is not None]
    states = group_health([r.table for r in found])
    ok_pages = {r.page_no + 1 for r, (state, _) in zip(found, states, strict=True) if state == "ok"}
    assert ok_pages == {8, 9, 10, 11, 14, 15}


def test_a_table_with_no_applicable_check_is_unverified():
    from fin_table_parser.labels import classify_row
    from fin_table_parser.models import Row, Table
    from fin_table_parser.normalize import parse_value
    from fin_table_parser.ui_model import table_health

    rows = [
        Row(i, f"line {i}", 0, (f"line {i}",), [parse_value(str(100 + i))], classify_row("x", True))
        for i in range(6)
    ]
    table = Table("連結貸借対照表", "千円", ["cur"], [None], rows, kind="balance_sheet")
    assert table_health(table)[0] == "unverified"
    from fin_table_parser.ui_model import group_health

    assert group_health([table])[0][0] == "unverified"
