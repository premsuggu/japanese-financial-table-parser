"""Label conventions of Japanese financial statements (the only account-name knowledge we use)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from .models import RowType
from .normalize import nfkc

_TOTAL = re.compile(r"(合計|総計)$")
_NET = re.compile(r"[（(]純額[）)]")

# A title line must contain one of these to be taken as the statement name.
STATEMENT_KEYWORDS = (
    "貸借対照表",
    "損益計算書",
    "包括利益計算書",
    "キャッシュ・フロー計算書",
    "株主資本等変動計算書",
)

# Lines printed as positive amounts that are SUBTRACTED inside the total they belong to, e.g. in a
# cost-of-goods-sold build-up: opening stock + purchases + production cost - closing stock.
SUBTRACTED_COMPONENTS = ("期末棚卸高", "他勘定振替高", "他勘定へ振替", "他勘定への振替")


def component_sign(label: str) -> int:
    """-1 for a line that is deducted within its total, else +1."""
    key = label_key(label)
    return -1 if any(s in key for s in SUBTRACTED_COMPONENTS) else 1


ASSETS_TOTAL = "資産合計"
LIABILITIES_EQUITY_TOTALS = {
    "負債純資産合計",
    "負債及び純資産合計",
    "負債・純資産合計",
}


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def label_key(label: str) -> str:
    """Comparison key: NFKC with all whitespace removed."""
    return re.sub(r"\s+", "", nfkc(label))


def classify_row(label: str, has_values: bool) -> RowType:
    key = label_key(label)
    if not has_values:
        return "section"
    if _TOTAL.search(key):
        return "total"
    if _NET.search(key):
        return "net"
    return "item"


def detect_kind(statement: str, labels: Sequence[str]) -> str:
    """Statement type from its title; for untitled continuation pages, from the row labels.

    A title counts only if it *ends with* the statement name (``中間連結貸借対照表``). Titles such as
    ``連結損益計算書関係`` (a note) or ``...貸借対照表計上額`` merely mention a statement and give ``other``.
    """
    title = label_key(statement)
    if title:
        for noun, kind in _TITLE_KINDS:
            if title.endswith(noun):
                return kind
        return "other"
    keys = [label_key(x) for x in labels]
    for needles, kind in _LABEL_KINDS:
        # Without a title, trust the labels only if at least two different statement terms each
        # START a row label. A single word somewhere in running text (a cover page, a summary
        # table) must not turn that page into a "statement".
        hits = {n for n in needles if any(k.startswith(n) for k in keys)}
        if len(hits) >= MIN_LABEL_EVIDENCE:
            return kind
    return "unknown"


MIN_LABEL_EVIDENCE = 2

# The combined 損益及び包括利益計算書 is an income statement that also holds the comprehensive-income
# rows. Order matters for the label fallback: the equity statement also contains 純資産 wording.
_TITLE_KINDS = (
    ("貸借対照表", "balance_sheet"),
    ("損益及び包括利益計算書", "income_statement"),
    ("包括利益計算書", "comprehensive_income"),
    ("損益計算書", "income_statement"),
    ("キャッシュ・フロー計算書", "cash_flow"),
    ("株主資本等変動計算書", "equity_statement"),
    ("純資産変動計算書", "equity_statement"),
)
_LABEL_KINDS = (
    (("当期首残高", "当期末残高"), "equity_statement"),
    (("資産合計", "負債の部", "純資産の部", "流動資産合計"), "balance_sheet"),
    (
        (
            "営業活動によるキャッシュ",
            "投資活動によるキャッシュ",
            "財務活動によるキャッシュ",
            "現金及び現金同等物の期末残高",
        ),
        "cash_flow",
    ),
    (("売上総利益", "営業利益", "経常利益"), "income_statement"),
    (("その他の包括利益", "包括利益"), "comprehensive_income"),
)
