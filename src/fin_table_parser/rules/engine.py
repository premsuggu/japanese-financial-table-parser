"""Evaluate the formulas and cross-statement ties of ``statement_rules.yaml``.

A formula is looked up in *all* tables of the right statement kind (a cash-flow statement spans two
pages), and columns of different tables are paired by period end date, falling back to position.
A rule that does not apply (its target row is absent) produces no finding, so a page is never
blamed for a rule about a row it does not contain.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from importlib import resources

import yaml

from ..labels import label_key
from ..models import Finding, Row, Status, Table

_OPERATOR = re.compile(r"\s([+-])\s")
# A loss line such as "営業損失" is printed as a positive amount; "特別損失合計" is an ordinary expense total.
_PROFIT_LOSS_LABEL = re.compile(
    r"^(売上総|営業|経常|税金等調整前当期純|税引前当期純|当期純|親会社株主に帰属する当期純)損失$"
)


@dataclass(frozen=True)
class Term:
    sign: int
    labels: tuple[str, ...]
    optional: bool = False


@dataclass(frozen=True)
class Formula:
    id: str
    kinds: tuple[str, ...]
    target: tuple[str, ...]
    terms: tuple[Term, ...]


@dataclass(frozen=True)
class Side:
    kind: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class Tie:
    id: str
    left: Side
    right: Side
    advisory: bool = False


@dataclass(frozen=True)
class Rules:
    formulas: tuple[Formula, ...]
    ties: tuple[Tie, ...]


def _labels(text: str) -> tuple[str, ...]:
    return tuple(label_key(part) for part in text.split("|") if part.strip())


def parse_expr(expr: str) -> tuple[tuple[str, ...], tuple[Term, ...]]:
    """``"A = B + C - D?"`` -> target labels and signed terms."""
    target_text, _, rhs = expr.partition("=")
    pieces = _OPERATOR.split(" " + rhs.strip())  # leading space so the first term has a sign slot
    terms: list[Term] = []
    sign = 1
    for piece in pieces:
        piece = piece.strip()
        if piece in ("+", "-"):
            sign = 1 if piece == "+" else -1
        elif piece:
            optional = piece.endswith("?")
            terms.append(Term(sign, _labels(piece.rstrip("?")), optional))
            sign = 1
    return _labels(target_text), tuple(terms)


@cache
def load_rules() -> Rules:
    raw = yaml.safe_load(
        resources.files("fin_table_parser.rules")
        .joinpath("statement_rules.yaml")
        .read_text(encoding="utf-8")
    )
    formulas = []
    for item in raw["formulas"]:
        target, terms = parse_expr(item["expr"])
        formulas.append(Formula(item["id"], tuple(item["kinds"]), target, terms))
    ties = [
        Tie(
            item["id"],
            Side(item["left"]["kind"], _labels(item["left"]["label"])),
            Side(item["right"]["kind"], _labels(item["right"]["label"])),
            bool(item.get("advisory", False)),
        )
        for item in raw["ties"]
    ]
    return Rules(tuple(formulas), tuple(ties))


# ---------------------------------------------------------------- lookup helpers


def _valued(row: Row) -> bool:
    return any(v is not None and v.number is not None for v in row.values)


def find_row(
    tables: Sequence[Table], kinds: Sequence[str], labels: Sequence[str]
) -> tuple[Table, Row] | None:
    """First row with a value whose label starts with one of ``labels`` (in the given kinds)."""
    for table in tables:
        if table.kind not in kinds:
            continue
        for row in table.rows:
            key = label_key(row.label)
            if _valued(row) and any(key.startswith(lab) for lab in labels):
                return table, row
    return None


def signed_value(row: Row, col: int) -> int | None:
    """Cell value as a signed number: a bare ``営業損失`` row printed positive is a negative profit."""
    v = row.values[col] if col < len(row.values) else None
    if v is None or v.number is None:
        return None
    if _PROFIT_LOSS_LABEL.match(label_key(row.label)) and v.number > 0:
        return -v.number
    return v.number


def _column_in(table: Table, period: str | None, fallback: int) -> int | None:
    if period is not None and period in table.periods:
        return table.periods.index(period)
    return fallback if fallback < len(table.headers) else None


def _status(actual: int, expected: int, tolerance: int) -> Status:
    diff = abs(actual - expected)
    if diff == 0:
        return "PASS"
    return "PASS_ROUNDING" if diff <= tolerance else "FAIL"


# ---------------------------------------------------------------- formulas


def check_formulas(tables: Sequence[Table]) -> list[Finding]:
    findings: list[Finding] = []
    for formula in load_rules().formulas:
        found = find_row(tables, formula.kinds, formula.target)
        if found is None:
            continue  # rule does not apply to these tables
        t_table, t_row = found
        for col, header in enumerate(t_table.headers):
            actual = signed_value(t_row, col)
            if actual is None:
                continue
            period = t_table.periods[col]
            total, used, missing = 0, [], []
            for term in formula.terms:
                hit = find_row(tables, formula.kinds, term.labels)
                tcol = _column_in(hit[0], period, col) if hit else None
                value = signed_value(hit[1], tcol) if hit and tcol is not None else None
                if value is None:
                    if not term.optional:
                        missing.append(term.labels[0])
                    continue
                total += term.sign * value
                used.append(hit[1].label if hit else "")
            if missing:
                findings.append(
                    Finding(
                        formula.id,
                        "SKIP",
                        t_table.statement,
                        header,
                        t_row.label,
                        detail="missing terms: " + ", ".join(missing),
                    )
                )
                continue
            tolerance = len(used)
            findings.append(
                Finding(
                    formula.id,
                    _status(actual, total, tolerance),
                    t_table.statement,
                    header,
                    t_row.label,
                    expected=total,
                    actual=actual,
                    tolerance=tolerance,
                    detail=f"{t_row.label} = " + " , ".join(used),
                )
            )
    return findings


# ---------------------------------------------------------------- cross-statement ties


def check_ties(tables: Sequence[Table]) -> list[Finding]:
    findings: list[Finding] = []
    kinds_present = {t.kind for t in tables}
    for tie in load_rules().ties:
        if tie.left.kind not in kinds_present or tie.right.kind not in kinds_present:
            continue  # the other statement is not part of this workbook: not applicable
        left = find_row(tables, [tie.left.kind], tie.left.labels)
        right = find_row(tables, [tie.right.kind], tie.right.labels)
        if left is None or right is None:
            findings.append(
                Finding(tie.id, "SKIP", "*", "*", "*", detail="a row of the tie was not found")
            )
            continue
        (lt, lr), (rt, rr) = left, right
        for col, header in enumerate(lt.headers):
            rcol = _column_in(rt, lt.periods[col], col)
            a = signed_value(lr, col)
            e = signed_value(rr, rcol) if rcol is not None else None
            if a is None or e is None:
                continue
            status = _status(a, e, 0)
            if status == "FAIL" and tie.advisory:
                status = "WARN"
            findings.append(
                Finding(
                    tie.id,
                    status,
                    f"{lt.statement} vs {rt.statement}",
                    header,
                    f"{lr.label} vs {rr.label}",
                    expected=e,
                    actual=a,
                )
            )
    return findings
