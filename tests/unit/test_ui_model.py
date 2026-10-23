import pytest

from fin_table_parser.document import PageResult
from fin_table_parser.pipeline import parse_page
from fin_table_parser.ui_model import (
    INDENT,
    findings_frame,
    parse_page_spec,
    select_results,
    skipped_pages,
    table_frame,
    table_health,
)
from fin_table_parser.validate import validate_tables

from ..conftest import CORRECTED_PDF


@pytest.mark.parametrize(
    ("spec", "total", "expected"),
    [
        ("all", 10, None),
        ("", 10, None),
        ("1-3, 8", 10, [0, 1, 2, 7]),
        ("5", 10, [4]),
        ("3 4,4", 10, [2, 3]),
    ],
)
def test_page_spec(spec, total, expected):
    assert parse_page_spec(spec, total) == expected


@pytest.mark.parametrize("bad", ["0", "11", "3-1", "abc", "1-x"])
def test_page_spec_rejects_nonsense(bad):
    with pytest.raises(ValueError, match="page range|cannot read"):
        parse_page_spec(bad, 10)


@pytest.fixture(scope="module")
def table():
    return parse_page(CORRECTED_PDF)


def test_table_frame_shows_printed_text_and_indentation(table):
    frame = table_frame(table)
    assert list(frame.columns)[0] == "Label"
    assert frame.shape == (43, 3)
    row = frame[frame["Label"].str.strip(INDENT) == "貸倒引当金"].iloc[0]
    assert row["Label"].startswith(INDENT * 2)
    assert row.iloc[2] == "△0"  # printed form kept
    nil = frame[frame["Label"].str.strip(INDENT) == "建設仮勘定"].iloc[0]
    assert nil.iloc[1] == "－"


def test_table_frame_numeric_mode_gives_signed_numbers(table):
    frame = table_frame(table, numeric=True)
    row = frame[frame["Label"].str.strip(INDENT) == "貸倒引当金"].iloc[0]
    assert row.iloc[1] == "-2,979"
    nil = frame[frame["Label"].str.strip(INDENT) == "建設仮勘定"].iloc[0]
    assert nil.iloc[1] == "nil"


def test_blank_cells_are_empty_not_the_word_none(table):
    frame = table_frame(table)
    section = frame[frame["Label"].str.strip(INDENT) == "資産の部"].iloc[0]
    assert section.iloc[1] == "" and section.iloc[2] == ""
    assert "None" not in frame.to_csv()


def test_findings_numbers_are_whole_numbers_with_separators(table):
    frame = findings_frame(validate_tables([table]))
    row = frame[frame["Row"] == "流動資産合計"].iloc[0]
    assert row["Expected"] == "5,863,681" and row["Printed"] == "5,863,684"
    assert row["Difference"] == "3"


def test_health_and_findings_frame(table):
    state, counts = table_health(table)
    assert state == "ok" and counts["FAIL"] == 0
    frame = findings_frame(validate_tables([table]))
    assert "FAIL" not in set(frame["Status"])
    assert frame.iloc[0]["Status"] in {"SKIP", "PASS_ROUNDING", "PASS"}  # worst first


def test_scope_filter_and_skipped_pages(table):
    results = [PageResult(0, table), PageResult(1, None, "no statement table on this page")]
    assert len(select_results(results, "Balance sheet")) == 1
    assert len(select_results(results, "Every table found")) == 1
    assert skipped_pages(results).to_dict("records") == [
        {"Page": 2, "Reason": "no statement table on this page"}
    ]
