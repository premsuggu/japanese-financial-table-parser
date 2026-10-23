import pytest

from fin_table_parser.normalize import parse_value, period_end, strip_section_number


def test_plain_number():
    v = parse_value("2,002,429")
    assert v is not None and v.number == 2002429 and v.kind == "number"


def test_triangle_is_negative():
    v = parse_value("△2,979")
    assert v is not None and v.number == -2979 and v.raw == "△2,979"


def test_negative_zero_keeps_printed_form():
    v = parse_value("△0")
    assert v is not None and v.number == 0 and v.negative_zero and v.raw == "△0"


def test_plain_zero_is_not_negative_zero():
    v = parse_value("0")
    assert v is not None and v.number == 0 and not v.negative_zero


@pytest.mark.parametrize("dash", ["－", "―", "—", "-"])
def test_lone_dash_is_nil_not_zero(dash):
    # NFKC turns the full-width dash into "-": nil must be decided before the sign handling.
    v = parse_value(dash)
    assert v is not None and v.kind == "nil" and v.number is None


def test_full_width_digits():
    v = parse_value("１，２３４")
    assert v is not None and v.number == 1234


def test_empty_cell_is_none():
    assert parse_value("") is None and parse_value("  ") is None


def test_bad_grouping_is_text_not_a_guess():
    v = parse_value("1,12")
    assert v is not None and v.kind == "text" and v.number is None


def test_parenthesised_negative():
    v = parse_value("(1,500)")
    assert v is not None and v.number == -1500


def test_period_end_takes_last_date():
    assert period_end("前連結会計年度 (2025年３月31日)") == "2025-03-31"
    assert period_end("(自 2024年4月1日 至 2025年3月31日)") == "2025-03-31"
    assert period_end("資産の部") is None


def test_strip_section_number():
    assert strip_section_number("（１）連結貸借対照表") == "連結貸借対照表"


@pytest.mark.parametrize(
    ("raw", "number", "notes"),
    [
        ("※１2,121,360", 2121360, ("※1",)),
        ("※４△1,923,585", -1923585, ("※4",)),
        ("※ 1 2,121,360", 2121360, ("※1",)),
        ("※１－", None, ("※1",)),
        ("2,121,360", 2121360, ()),
    ],
)
def test_footnote_marker_is_split_from_the_amount(raw, number, notes):
    v = parse_value(raw)
    assert v is not None and v.number == number and v.notes == notes
    assert v.raw == raw  # the printed form is preserved


def test_ambiguous_ascii_marker_is_not_guessed():
    # "※12,121,360" could be note 1 + 2,121,360 or note 12 + ...: report it, do not guess
    v = parse_value("※12,121,360")
    assert v is not None and v.kind == "text"


def test_several_footnote_markers_before_one_amount():
    v = parse_value("※１,※２162,303")
    assert v is not None and v.number == 162303 and v.notes == ("※1", "※2")
    v = parse_value("※１,※２△366,165")
    assert v is not None and v.number == -366165 and v.notes == ("※1", "※2")


def test_period_end_ignores_spaces_between_numbers_and_units():
    # OCR engines and some PDFs print "(2025 年3月31 日)" with stray spaces
    assert period_end("前連結会計年度 (2025 年3月31 日)") == "2025-03-31"
    assert period_end("(自 2024 年 4 月 1 日 至 2025 年 3 月 31 日)") == "2025-03-31"
