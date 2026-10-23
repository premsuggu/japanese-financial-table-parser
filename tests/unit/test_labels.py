import pytest

from fin_table_parser.labels import classify_row


@pytest.mark.parametrize(
    ("label", "has_values", "expected"),
    [
        ("資産の部", False, "section"),
        ("流動資産合計", True, "total"),
        ("建物及び構築物（純額）", True, "net"),
        ("建物及び構築物 (純額)", True, "net"),
        ("現金及び預金", True, "item"),
        ("貸倒引当金", True, "item"),
    ],
)
def test_classify_row(label, has_values, expected):
    assert classify_row(label, has_values) == expected
