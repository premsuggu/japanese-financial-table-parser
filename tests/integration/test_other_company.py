"""A filing of a different company (IFRS, first-time adoption, three balance-sheet columns)."""

import pytest

from fin_table_parser.pipeline import parse_page
from fin_table_parser.validate import summarize, validate_tables

from ..conftest import ROOT

PDF = ROOT / "data" / "corpus" / "others" / "jpx_44460" / "jpx_44460.pdf"
pytestmark = pytest.mark.skipif(not PDF.exists(), reason="other-company PDF not present")


def test_income_statement_header_years_and_periods_are_read():
    table = parse_page(PDF, 8)
    assert table.kind == "income_statement" and table.unit == "千円"
    assert table.periods == ["2024-07-31", "2025-07-31"]
    assert [r.label for r in table.rows[:3]] == ["売上収益", "売上原価", "売上総利益"]
    assert summarize(validate_tables([table]))["FAIL"] == 0


def test_balance_sheet_with_three_columns_has_no_page_number_row():
    table = parse_page(PDF, 6)
    assert len(table.headers) == 3
    assert not any(r.label == "" and any(v for v in r.values) for r in table.rows)
    counts = summarize(validate_tables([table]))
    assert counts["FAIL"] == 0 and counts["PASS"] + counts["PASS_ROUNDING"] > 0


def test_comprehensive_income_has_two_columns_not_four_and_the_whole_filing_has_no_failed_check():
    from fin_table_parser.document import parse_document
    from fin_table_parser.ui_model import select_results

    assert len(parse_page(PDF, 9).headers) == 2
    tables = [
        r.table for r in select_results(parse_document(PDF), "All financial statements") if r.table
    ]
    counts = summarize(validate_tables(tables))
    assert counts["FAIL"] == 0 and counts["PASS"] + counts["PASS_ROUNDING"] > 20
