"""Validator tests on small synthetic tables (no PDF needed)."""

from fin_table_parser.labels import classify_row
from fin_table_parser.models import Row, Table
from fin_table_parser.normalize import parse_value
from fin_table_parser.validate import check_balance_identity, summarize, validate_tables


def make_table(spec, statement="BS"):
    """spec: list of (level, label, raw values...) with raw=None for an empty cell."""
    rows = []
    for i, (level, label, *raws) in enumerate(spec):
        values = [parse_value(r) if r is not None else None for r in raws]
        rows.append(
            Row(
                i,
                label,
                level,
                (label,),
                values,
                classify_row(label, any(v is not None for v in values)),
            )
        )
    return Table(statement, "千円", ["cur"], [None], rows)


GOOD = [
    (0, "資産の部", None),
    (1, "流動資産", None),
    (2, "現金", "100"),
    (2, "貸倒引当金", "△10"),
    (2, "流動資産合計", "90"),
    (1, "固定資産", None),
    (2, "土地", "50"),
    (2, "固定資産合計", "50"),
    (1, "資産合計", "140"),
]


def statuses(findings, check):
    return [f.status for f in findings if f.check == check]


def test_good_table_passes():
    findings = validate_tables([make_table(GOOD)])
    assert summarize(findings)["FAIL"] == 0
    assert statuses(findings, "total_equals_components") == ["PASS"] * 3


def test_wrong_digit_in_a_component_is_caught():
    bad = list(GOOD)
    bad[2] = (2, "現金", "900")  # 100 -> 900
    findings = validate_tables([make_table(bad)])
    assert "流動資産合計" in {f.row for f in findings if f.status == "FAIL"}


def test_small_rounding_difference_is_tolerated_not_failed():
    spec = list(GOOD)
    spec[4] = (2, "流動資産合計", "91")  # off by 1 with 2 components
    spec[8] = (1, "資産合計", "141")
    findings = validate_tables([make_table(spec)])
    assert "PASS_ROUNDING" in statuses(findings, "total_equals_components")
    assert summarize(findings)["FAIL"] == 0


def test_net_row_check_uses_section_children():
    spec = [
        (0, "資産の部", None),
        (1, "有形固定資産", None),
        (2, "建物", "1,000"),
        (3, "減価償却累計額", "△400"),
        (3, "建物（純額）", "600"),
        (2, "有形固定資産合計", "600"),
    ]
    findings = validate_tables([make_table(spec)])
    assert statuses(findings, "gross_less_accum_equals_net") == ["PASS"]
    assert summarize(findings)["FAIL"] == 0


def test_nil_counts_as_zero_in_sums():
    spec = [
        (0, "資産の部", None),
        (1, "流動資産", None),
        (2, "a", "－"),
        (2, "b", "5"),
        (2, "流動資産合計", "5"),
    ]
    assert summarize(validate_tables([make_table(spec)]))["FAIL"] == 0


def test_balance_identity_skipped_when_other_half_missing():
    assert [f.status for f in check_balance_identity([make_table(GOOD)])] == ["SKIP"]


def test_balance_identity_pass_and_fail():
    assets = make_table(GOOD)
    ok = make_table([(0, "負債純資産合計", "140")], "BS2")
    assert [f.status for f in check_balance_identity([assets, ok])] == ["PASS"]
    bad = make_table([(0, "負債純資産合計", "141")], "BS2")
    assert [f.status for f in check_balance_identity([assets, bad])] == ["FAIL"]


def test_closing_stock_is_subtracted_inside_a_cost_of_goods_total():
    spec = [
        (0, "売上原価", None),
        (1, "商品及び製品期首棚卸高", "100"),
        (1, "当期商品及び製品仕入高", "500"),
        (1, "当期製品製造原価", "300"),
        (1, "商品及び製品期末棚卸高", "200"),
        (1, "売上原価合計", "700"),
    ]
    findings = validate_tables([make_table(spec)])
    assert summarize(findings)["FAIL"] == 0
    wrong = list(spec)
    wrong[-1] = (1, "売上原価合計", "1,100")  # what you get by adding the closing stock
    assert summarize(validate_tables([make_table(wrong)]))["FAIL"] == 1
