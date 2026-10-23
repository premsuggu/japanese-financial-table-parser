"""End-to-end tests on the real sample pages."""

import pytest
from openpyxl import load_workbook

from fin_table_parser.evaluate import load_truth, mutation_test, score_against_truth
from fin_table_parser.export import HEADER_ROW, write_workbook
from fin_table_parser.pipeline import parse_page
from fin_table_parser.triage import UnsupportedPage
from fin_table_parser.validate import summarize, validate_tables
from fin_table_parser.xlsx_reader import read_workbook

from ..conftest import TRUTH_JSON


@pytest.fixture(scope="module")
def table(corrected_pdf):
    return parse_page(corrected_pdf)


@pytest.fixture(scope="module")
def workbook(table, tmp_path_factory):
    path = tmp_path_factory.mktemp("xlsx") / "bs.xlsx"
    write_workbook([table], validate_tables([table]), path)
    return path


def test_table_metadata(table):
    assert table.statement == "連結貸借対照表"
    assert table.unit == "千円"
    assert table.periods == ["2025-03-31", "2026-03-31"]
    assert table.meta["revision"] == "訂正後"
    assert len(table.rows) == 43


def test_page_furniture_is_not_in_the_table(table):
    labels = [r.label for r in table.rows]
    assert not any("- 4 -" in x or "訂正後" in x or "連結財務諸表" in x for x in labels)


def test_nil_and_negative_zero_are_preserved(table):
    nil_row = next(r for r in table.rows if r.label == "建設仮勘定")
    assert nil_row.values[0].kind == "nil" and nil_row.values[1].number == 4553
    neg_zero = next(r for r in table.rows if r.label == "貸倒引当金").values[1]
    assert neg_zero.number == 0 and neg_zero.negative_zero


def test_repeated_labels_have_distinct_paths(table):
    paths = [r.path for r in table.rows if r.label == "その他"]
    assert len(paths) == 4 and len(set(paths)) == 4


def test_matches_ground_truth_through_the_excel_file(workbook):
    scores = score_against_truth(read_workbook(workbook)[0], load_truth(TRUTH_JSON))
    assert scores.errors == []
    assert scores.page_exact


def test_accounting_checks_pass_on_the_parsed_page(workbook):
    counts = summarize(validate_tables(read_workbook(workbook)))
    assert counts["FAIL"] == 0
    assert counts["PASS"] + counts["PASS_ROUNDING"] >= 20


def test_checker_catches_a_cell_edited_in_the_excel_file(workbook, tmp_path):
    """Someone (or a bug) changes one number in the sheet: the checker must notice."""
    wb = load_workbook(workbook)
    ws = wb["連結貸借対照表"]
    row = next(r for r in range(HEADER_ROW + 1, ws.max_row + 1) if ws.cell(r, 4).value == "売掛金")
    ws.cell(row, 6).value = 2_919_476  # was 2,019,476; column F = prior-year values
    edited = tmp_path / "edited.xlsx"
    wb.save(edited)
    findings = validate_tables(read_workbook(edited))
    assert "流動資産合計" in {f.row.split(" > ")[-1] for f in findings if f.status == "FAIL"}
    assert any(f.check == "numeric_matches_raw" and f.status == "FAIL" for f in findings)


def test_mutation_test_reports_coverage_and_its_limit(table):
    result = mutation_test(table)
    assert result.baseline_fails == 0
    assert result.by_kind["leading_digit"].value > 0.9
    # Honest limit: a +1 change in the last digit hides inside the rounding tolerance.
    assert result.by_kind["last_digit_plus1"].value < 0.5


def test_unsupported_page_is_reported_not_guessed(complete_pdf):
    with pytest.raises(UnsupportedPage):
        parse_page(complete_pdf, 4)  # prose page: no row bands


def test_original_vs_corrected_differ_in_exactly_the_three_corrected_cells(
    corrected_pdf, complete_pdf
):
    corrected, original = parse_page(corrected_pdf), parse_page(complete_pdf, 7)
    assert [(a.label, a.level) for a in original.rows] == [
        (b.label, b.level) for b in corrected.rows
    ]

    def raw(v):
        return v.raw if v else None

    diffs = [
        (a.label, c, raw(a.values[c]), raw(b.values[c]))
        for a, b in zip(original.rows, corrected.rows, strict=True)
        for c in range(2)
        if raw(a.values[c]) != raw(b.values[c])
    ]
    assert diffs == [
        ("貸倒引当金", 1, "0", "△0"),
        ("投資有価証券", 1, "53,925", "218,836"),
        ("関係会社株式", 1, "166,033", "1,123"),
    ]


def test_assets_equal_liabilities_plus_equity_across_pages(complete_pdf, tmp_path):
    assets, liabilities = parse_page(complete_pdf, 7), parse_page(complete_pdf, 8)
    only_assets = [
        f for f in validate_tables([assets]) if f.check == "assets_equal_liabilities_equity"
    ]
    assert [f.status for f in only_assets] == ["SKIP"]
    path = write_workbook([assets, liabilities], [], tmp_path / "both.xlsx")
    identity = [
        f
        for f in validate_tables(read_workbook(path))
        if f.check == "assets_equal_liabilities_equity"
    ]
    assert [f.status for f in identity] == ["PASS", "PASS"]


def test_whole_filing_passes_every_applicable_check(complete_pdf):
    """Balance sheet (2 pages), P&L, comprehensive income, cash flow (2 pages): no FAIL/WARN/SKIP."""
    pages = [7, 8, 9, 10, 13, 14]
    tables = [parse_page(complete_pdf, p) for p in pages]
    assert [t.kind for t in tables] == [
        "balance_sheet",
        "balance_sheet",
        "income_statement",
        "comprehensive_income",
        "cash_flow",
        "cash_flow",
    ]
    counts = summarize(validate_tables(tables))
    assert counts["FAIL"] == counts["WARN"] == counts["SKIP"] == 0
    assert counts["PASS"] + counts["PASS_ROUNDING"] >= 70
