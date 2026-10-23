"""Rule parsing, kind detection and formula/tie evaluation on small synthetic tables."""

import pytest

from fin_table_parser.labels import classify_row, detect_kind
from fin_table_parser.models import Row, Table
from fin_table_parser.normalize import parse_value, strip_section_number
from fin_table_parser.rules import check_formulas, check_ties, load_rules
from fin_table_parser.rules.engine import parse_expr, signed_value
from fin_table_parser.validate import check_unparsed_cells, summarize, validate_tables


def make_table(kind, spec, statement="x", period="2026-03-31"):
    rows = []
    for i, (level, label, raw) in enumerate(spec):
        value = parse_value(raw) if raw is not None else None
        rows.append(Row(i, label, level, (label,), [value], classify_row(label, value is not None)))
    return Table(statement, "千円", ["cur"], [period], rows, kind=kind)


def test_parse_expr_signs_alternatives_and_optional():
    target, terms = parse_expr("営業利益|営業損失 = 売上総利益 - 販売費 + 雑収入?")
    assert target == ("営業利益", "営業損失")
    assert [(t.sign, t.labels, t.optional) for t in terms] == [
        (1, ("売上総利益",), False),
        (-1, ("販売費",), False),
        (1, ("雑収入",), True),
    ]


def test_shipped_rules_load():
    rules = load_rules()
    assert {f.id for f in rules.formulas} >= {"gross_profit", "net_income", "cash_end"}
    assert {t.id for t in rules.ties} >= {"cashflow_cash_equals_balance_sheet_cash"}


@pytest.mark.parametrize(
    ("title", "labels", "kind"),
    [
        ("連結貸借対照表", [], "balance_sheet"),
        ("連結損益計算書", [], "income_statement"),
        ("連結損益及び包括利益計算書", [], "income_statement"),
        ("連結包括利益計算書", [], "comprehensive_income"),
        ("連結キャッシュ・フロー計算書", [], "cash_flow"),
        ("", ["負債の部", "流動負債", "純資産の部"], "balance_sheet"),
        ("", ["財務活動によるキャッシュ・フロー", "現金及び現金同等物の期末残高"], "cash_flow"),
        # one statement word on its own is not enough evidence
        ("", ["営業利益の概況", "その他"], "unknown"),
        ("", ["資産合計"], "unknown"),
        ("", ["その他"], "unknown"),
        ("連結株主資本等変動計算書", [], "equity_statement"),
        ("", ["当期首残高", "当期末残高"], "equity_statement"),
        ("中間連結貸借対照表", [], "balance_sheet"),
        # a note whose title merely mentions a statement is not that statement
        ("連結損益計算書関係", [], "other"),
        ("市場価格のない株式等の貸借対照表計上額", [], "other"),
    ],
)
def test_detect_kind(title, labels, kind):
    assert detect_kind(title, labels) == kind


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("（１）連結貸借対照表", "連結貸借対照表"),
        ("1【連結貸借対照表】", "連結貸借対照表"),
        ("(連結損益計算書)", "連結損益計算書"),
        ("【中間連結貸借対照表】", "中間連結貸借対照表"),
    ],
)
def test_statement_names_lose_brackets_and_numbers(raw, expected):
    assert strip_section_number(raw) == expected


PL = [
    (0, "売上高", "1,000"),
    (0, "売上原価", "600"),
    (0, "売上総利益", "400"),
]


def test_formula_passes_and_detects_a_wrong_figure():
    assert [f.status for f in check_formulas([make_table("income_statement", PL)])] == ["PASS"]
    bad = [*PL[:2], (0, "売上総利益", "900")]
    assert [f.status for f in check_formulas([make_table("income_statement", bad)])] == ["FAIL"]


def test_formula_not_applicable_when_target_row_absent():
    assert check_formulas([make_table("income_statement", PL[:2])]) == []


def test_formula_reports_missing_terms_instead_of_guessing():
    only_profit = [(0, "売上総利益", "400"), (0, "売上高", "1,000")]
    findings = check_formulas([make_table("income_statement", only_profit)])
    assert [f.status for f in findings] == ["SKIP"]


def test_flat_statement_total_is_not_checked_against_unrelated_siblings():
    """Regression: 法人税等合計 used to be compared with the sum of every row above it."""
    spec = [
        (0, "売上高", "1,000"),
        (0, "法人税、住民税及び事業税", "30"),
        (0, "法人税等調整額", "5"),
        (0, "法人税等合計", "35"),
    ]
    findings = validate_tables([make_table("income_statement", spec)])
    assert summarize(findings)["FAIL"] == 0


def test_loss_line_printed_positive_is_negative():
    loss = make_table("income_statement", [(0, "営業損失", "50")]).rows[0]
    assert signed_value(loss, 0) == -50
    expense_total = make_table("income_statement", [(0, "特別損失合計", "50")]).rows[0]
    assert signed_value(expense_total, 0) == 50  # an ordinary expense total stays positive


def test_tie_exact_and_advisory():
    cf = make_table("cash_flow", [(0, "現金及び現金同等物の期末残高", "608")])
    bs = make_table("balance_sheet", [(0, "現金及び預金", "608")])
    assert [f.status for f in check_ties([cf, bs])] == ["PASS"]
    bs_off = make_table("balance_sheet", [(0, "現金及び預金", "700")])
    assert [f.status for f in check_ties([cf, bs_off])] == ["WARN"]  # advisory: WARN, not FAIL


def test_tie_not_applicable_when_other_statement_absent():
    cf = make_table("cash_flow", [(0, "現金及び現金同等物の期末残高", "608")])
    assert check_ties([cf]) == []


def test_unreadable_number_is_a_failure_not_a_silent_zero():
    table = make_table("balance_sheet", [(0, "現金", "※12,121,360"), (0, "注", "あり")])
    statuses = [f.status for f in check_unparsed_cells(table)]
    assert statuses == ["FAIL", "WARN"]  # digits present -> FAIL; plain text -> WARN
