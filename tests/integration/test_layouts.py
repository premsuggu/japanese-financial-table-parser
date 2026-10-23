"""Layouts the sample corpus does not contain, reproduced as synthetic pages (tests/synth.py)."""

import pytest

from fin_table_parser.export import write_workbook
from fin_table_parser.labels import label_key
from fin_table_parser.pipeline import parse_source
from fin_table_parser.ui_model import table_frame
from fin_table_parser.validate import summarize, validate_tables
from fin_table_parser.xlsx_reader import read_workbook

from ..synth import IFRS, J_GAAP, Layout, make_pdf


def parse(layout: Layout, lines=None):
    return parse_source(make_pdf(layout, lines))


def amounts(table, label):
    row = next(r for r in table.rows if label_key(r.label) == label_key(label))
    return [v.raw if v else None for v in row.values]


def no_failures(table):
    counts = summarize(validate_tables([table]))
    assert counts["FAIL"] == 0 and counts["WARN"] == 0
    assert counts["PASS"] > 5


def test_plain_page_is_a_balance_sheet_that_balances():
    table = parse(Layout())
    assert (
        table.kind == "balance_sheet" and table.unit == "百万円" and len(table.rows) == len(J_GAAP)
    )
    no_failures(table)


def test_note_number_column_is_not_a_value_column():
    table = parse(Layout(note_header="注記"))
    assert len(table.headers) == 2 and "注記" not in "".join(table.headers)
    assert amounts(table, "現金及び預金") == ["1,000", "1,200"]
    row = next(r for r in table.rows if r.label == "現金及び預金")
    assert row.note_ref == "5" and "5" not in row.label
    assert next(r for r in table.rows if r.label == "支払手形及び買掛金").note_ref == "12"
    no_failures(table)


def test_note_numbers_survive_excel_and_show_in_the_ui_frame(tmp_path):
    table = parse(Layout(note_header="注記"))
    path = write_workbook([table], validate_tables([table]), tmp_path / "n.xlsx")
    again = read_workbook(path)[0]
    assert [r.note_ref for r in again.rows] == [r.note_ref for r in table.rows]
    assert list(table_frame(table).columns)[:2] == ["Label", "Note"]


def test_one_value_column_beside_a_note_column_keeps_its_amounts():
    table = parse(Layout(headers=("当期\n(2026年3月31日)",), note_header="注記"))
    assert len(table.headers) == 1 and amounts(table, "現金及び預金") == ["1,000"]


def test_a_small_first_value_column_is_not_a_note_column_without_thousands_elsewhere():
    small = [line for line in J_GAAP]
    from ..synth import Line

    tiny = [Line(x.label, tuple(v.replace(",", "")[-2:] for v in x.values), x.level) for x in small]
    table = parse(Layout(), tiny)
    assert len(table.headers) == 2  # no comma anywhere: nothing marks the first column as notes


def test_ifrs_statement_of_financial_position_balances_with_its_own_total_names():
    table = parse(Layout(title="連結財政状態計算書", note_header="注記"), IFRS)
    assert table.kind == "balance_sheet"
    checks = {f.check: f.status for f in validate_tables([table])}
    assert checks["assets_equal_liabilities_equity"] == "PASS"
    no_failures(table)


def test_label_wrapped_over_two_lines_with_amounts_level_with_the_first_line():
    table = parse(Layout(wrap_labels_top_aligned=True))
    assert len(table.rows) == len(J_GAAP)
    assert amounts(table, "受取手形及び売掛金") == ["2,000", "2,100"]
    no_failures(table)


def test_grid_lines_do_not_disturb_the_words_only_strategy():
    table = parse(Layout(grid=True))
    assert len(table.rows) == len(J_GAAP)
    no_failures(table)


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("（単位：百万円）", "百万円"),
        ("(単位 千円)", "千円"),
        ("（千円）", "千円"),
        ("（単位：円）", "円"),
    ],
)
def test_unit_line_forms(unit, expected):
    assert parse(Layout(unit=unit)).unit == expected


def test_three_columns_keep_their_headers():
    table = parse(Layout(headers=("前期\n(2025年3月31日)", "当期\n(2026年3月31日)", "増減")))
    assert len(table.headers) == 3 and table.headers[2] == "増減"


def test_account_form_with_two_panels_is_read_as_one_statement():
    from ..synth import make_account_form_pdf

    table = parse_source(make_account_form_pdf())
    assert table.meta["panels"] == 2 and table.kind == "balance_sheet" and table.unit == "百万円"
    assert [r.label for r in table.rows] == [line.label for line in J_GAAP]
    assert amounts(table, "資産合計") == ["3,800"] and amounts(table, "負債純資産合計") == ["3,800"]
    checks = {f.check: f.status for f in validate_tables([table])}
    assert checks["assets_equal_liabilities_equity"] == "PASS"
    assert summarize(validate_tables([table]))["FAIL"] == 0
