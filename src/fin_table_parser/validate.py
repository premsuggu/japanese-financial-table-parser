"""Accounting-identity checks on parsed tables.

These checks use only the numbers in the table, never the PDF, so they are an independent signal
about parser errors. They run on ``Table`` objects, which can come from the parser directly or
from an Excel workbook (``xlsx_reader``), so the same checks validate a hand-edited file too.

Checks
------
``numeric_matches_raw``  the numeric cell equals the printed text (catches export bugs / edits)
``total_equals_components``  every 合計 row equals the sum of its components (rounding tolerated)
``gross_less_accum_equals_net``  gross + accumulated depreciation = net (rounding tolerated)
``assets_equal_liabilities_equity``  資産合計 = 負債純資産合計 across the statement's pages

How a total's components are found (from the indent tree; in these statements a 合計 row sits at
the same indent as the rows it adds up):
* a valued sibling contributes its value, or its （純額） child's value if it has one;
* a section header (no values) contributes its closing 合計 child.

Rounding: every printed figure is rounded to the unit separately (error < 1 unit each), so a total
can differ from the sum of its lines by up to the number of figures involved. Such differences are
reported as ``PASS_ROUNDING``; anything larger is ``FAIL``. Only the balance identity is exact
(both sides are printed totals of the same quantity).

Limit: the tolerance also hides real errors no larger than the tolerance (see the mutation test
in ``evaluate``).
"""

from __future__ import annotations

from collections.abc import Sequence

from .hierarchy import parent_indices
from .labelcheck import check_labels, load_lexicon
from .labels import ASSETS_TOTAL, LIABILITIES_EQUITY_TOTALS, component_sign, label_key
from .models import Finding, Row, Status, Table
from .normalize import nfkc
from .rules import check_formulas, check_ties

PATH_SEP = " > "


def validate_tables(tables: Sequence[Table]) -> list[Finding]:
    """Run every check that applies. Statement-specific rules come from ``rules/statement_rules.yaml``."""
    findings: list[Finding] = []
    for table in tables:
        findings += check_numeric_matches_raw(table)
        findings += check_unparsed_cells(table)
        findings += check_totals(table)
        findings += check_net_rows(table)
        findings += check_read_quality(table)
    findings += check_formulas(tables)
    findings += check_ties(tables)
    if any(t.kind == "balance_sheet" for t in tables):
        findings += check_balance_identity(tables)
    return findings


def check_read_quality(table: Table) -> list[Finding]:
    """Checks that only apply to OCR pages: a misspelt label, and disagreement between two reads."""
    findings: list[Finding] = []
    if str(table.meta.get("route", "")).startswith("ocr"):
        findings += check_labels(table, load_lexicon())
    read_findings = table.meta.get("read_findings")
    if isinstance(read_findings, list):
        findings += read_findings
        if not read_findings:
            name = table.statement or table.source
            findings.append(
                Finding("read_agreement", "PASS", name, "", "", detail="two reads agree")
            )
    return findings


def summarize(findings: Sequence[Finding]) -> dict[str, int]:
    out = {"PASS": 0, "PASS_ROUNDING": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
    for f in findings:
        out[f.status] += 1
    return out


# ---------------------------------------------------------------- helpers


def _number(row: Row, col: int) -> int:
    """Numeric value of a cell, with empty / nil counted as 0."""
    v = row.values[col]
    return v.number if v is not None and v.number is not None else 0


def _has_value(row: Row, col: int) -> bool:
    v = row.values[col]
    return v is not None and v.number is not None


def _children(rows: Sequence[Row], parents: Sequence[int | None], parent: int | None) -> list[int]:
    return [i for i, p in enumerate(parents) if p == parent]


def _closing_total(rows: Sequence[Row], parents: Sequence[int | None], section: int) -> int | None:
    totals = [c for c in _children(rows, parents, section) if rows[c].row_type == "total"]
    return totals[-1] if totals else None


def _contribution(
    rows: Sequence[Row], parents: Sequence[int | None], sibling: int
) -> tuple[int | None, str]:
    """Row index whose value this sibling adds into its parent's total (None if unknown)."""
    row = rows[sibling]
    if row.row_type == "section":
        return _closing_total(rows, parents, sibling), "section closing total"
    nets = [c for c in _children(rows, parents, sibling) if rows[c].row_type == "net"]
    if nets:
        return nets[-1], "net child"
    return sibling, "item"


def _fmt(row: Row) -> str:
    return PATH_SEP.join(row.path)


# ---------------------------------------------------------------- checks


def check_numeric_matches_raw(table: Table) -> list[Finding]:
    """The numeric cell must equal the number parsed from the printed text."""
    from .normalize import parse_value

    findings = []
    for row in table.rows:
        for col, v in enumerate(row.values):
            if v is None or v.kind != "number":
                continue
            parsed = parse_value(v.raw)
            if parsed is None or parsed.number != v.number:
                findings.append(
                    Finding(
                        "numeric_matches_raw",
                        "FAIL",
                        table.statement,
                        table.headers[col],
                        _fmt(row),
                        expected=parsed.number if parsed else None,
                        actual=v.number,
                        detail=f"printed {v.raw!r}",
                    )
                )
    if not findings:
        findings.append(
            Finding(
                "numeric_matches_raw",
                "PASS",
                table.statement,
                "*",
                "*",
                detail="all numeric cells match their printed text",
            )
        )
    return findings


def check_unparsed_cells(table: Table) -> list[Finding]:
    """A cell in a number column that could not be read as a number must never pass silently.

    (Before this check, a footnote marker glued to a number turned the cell into text and the
    sums quietly treated it as 0.)
    """
    findings = []
    for row in table.rows:
        for col, v in enumerate(row.values):
            if v is None or v.kind != "text":
                continue
            has_digit = any(c.isdigit() for c in nfkc(v.raw))
            findings.append(
                Finding(
                    "unparsed_cell",
                    "FAIL" if has_digit else "WARN",
                    table.statement,
                    table.headers[col],
                    _fmt(row),
                    detail=f"cannot read {v.raw!r} as a number",
                )
            )
    return findings


def check_totals(table: Table) -> list[Finding]:
    rows = table.rows
    parents = parent_indices([r.level for r in rows])
    findings: list[Finding] = []
    for t_idx, total in enumerate(rows):
        if total.row_type != "total":
            continue
        siblings = [s for s in _children(rows, parents, parents[t_idx]) if s < t_idx]
        if parents[t_idx] is None and any(rows[s].row_type != "section" for s in siblings):
            # A flat statement (e.g. an income statement) has no section to add up: its totals
            # are covered by the formulas in statement_rules.yaml instead.
            continue
        if any(rows[s].row_type == "total" for s in siblings):
            for header in table.headers:
                findings.append(
                    Finding(
                        "total_equals_components",
                        "SKIP",
                        table.statement,
                        header,
                        _fmt(total),
                        detail="earlier subtotal among siblings: ambiguous composition",
                    )
                )
            continue
        parts: list[int] = []
        unresolved = ""
        for s in siblings:
            idx, _how = _contribution(rows, parents, s)
            if idx is None:
                unresolved = f"section {rows[s].label!r} has no closing total"
                break
            parts.append(idx)
        for col, header in enumerate(table.headers):
            if unresolved or not parts:
                findings.append(
                    Finding(
                        "total_equals_components",
                        "SKIP",
                        table.statement,
                        header,
                        _fmt(total),
                        detail=unresolved or "no components found",
                    )
                )
                continue
            if not _has_value(total, col):
                continue
            expected = sum(component_sign(rows[p].label) * _number(rows[p], col) for p in parts)
            n_terms = sum(1 for p in parts if _has_value(rows[p], col))
            findings.append(
                _compare(
                    "total_equals_components",
                    table,
                    header,
                    total,
                    col,
                    expected,
                    tolerance=n_terms,
                    detail=f"{n_terms} components: " + ", ".join(rows[p].label for p in parts),
                )
            )
    return findings


def check_net_rows(table: Table) -> list[Finding]:
    rows = table.rows
    parents = parent_indices([r.level for r in rows])
    findings: list[Finding] = []
    for g_idx, gross in enumerate(rows):
        kids = _children(rows, parents, g_idx)
        nets = [k for k in kids if rows[k].row_type == "net"]
        if not nets or gross.row_type == "section":
            continue
        net = rows[nets[-1]]
        deductions = [k for k in kids if k != nets[-1] and rows[k].row_type == "item"]
        for col, header in enumerate(table.headers):
            if not _has_value(net, col):
                continue
            expected = _number(gross, col) + sum(_number(rows[k], col) for k in deductions)
            # Gross and accumulated depreciation are each rounded on their own, and the net is
            # rounded from the unrounded difference, so +-1 per figure is normal (seen on this page).
            n_terms = 1 + len(deductions)
            findings.append(
                _compare(
                    "gross_less_accum_equals_net",
                    table,
                    header,
                    net,
                    col,
                    expected,
                    tolerance=n_terms,
                    detail=f"{gross.label} + " + ", ".join(rows[k].label for k in deductions),
                )
            )
    return findings


def check_balance_identity(tables: Sequence[Table]) -> list[Finding]:
    assets = _find_total(tables, {label_key(ASSETS_TOTAL)})
    liab_eq = _find_total(tables, {label_key(x) for x in LIABILITIES_EQUITY_TOTALS})
    if assets is None or liab_eq is None:
        missing = "資産合計" if assets is None else "負債純資産合計"
        return [
            Finding(
                "assets_equal_liabilities_equity",
                "SKIP",
                "*",
                "*",
                "*",
                detail=f"{missing} not found in this workbook (other half of the balance sheet not parsed)",
            )
        ]
    (ta, ra), (tl, rl) = assets, liab_eq
    findings = []
    for col, header in enumerate(ta.headers):
        # Match columns by period end when possible, else by position.
        other = tl.periods.index(ta.periods[col]) if ta.periods[col] in tl.periods else col
        if not (_has_value(ra, col) and other < len(rl.values) and _has_value(rl, other)):
            continue
        findings.append(
            Finding(
                "assets_equal_liabilities_equity",
                _status(_number(ra, col), _number(rl, other), 0),
                ta.statement,
                header,
                f"{ra.label} vs {rl.label}",
                expected=_number(rl, other),
                actual=_number(ra, col),
                tolerance=0,
            )
        )
    return findings


def _find_total(tables: Sequence[Table], keys: set[str]) -> tuple[Table, Row] | None:
    for table in tables:
        for row in table.rows:
            if label_key(row.label) in keys and row.row_type == "total":
                return table, row
    return None


def _status(actual: int, expected: int, tolerance: int) -> Status:
    diff = abs(actual - expected)
    if diff == 0:
        return "PASS"
    return "PASS_ROUNDING" if diff <= tolerance else "FAIL"


def _compare(
    check: str,
    table: Table,
    header: str,
    row: Row,
    col: int,
    expected: int,
    tolerance: int,
    detail: str,
) -> Finding:
    actual = _number(row, col)
    return Finding(
        check,
        _status(actual, expected, tolerance),
        table.statement,
        header,
        _fmt(row),
        expected=expected,
        actual=actual,
        tolerance=tolerance,
        detail=detail,
    )
