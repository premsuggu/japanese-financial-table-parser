"""Data shaping for the UI (no Streamlit import, so it can be unit-tested)."""

from __future__ import annotations

import re
from collections.abc import Sequence

import pandas as pd

from .document import PageResult
from .models import Finding, Table
from .validate import summarize, validate_tables

INDENT = "　"  # ideographic space: visible indentation that survives any table widget

SUPPORTED_KINDS = ("balance_sheet", "income_statement", "comprehensive_income", "cash_flow")
KIND_LABELS = {
    "balance_sheet": "Balance sheet",
    "income_statement": "Income statement",
    "comprehensive_income": "Comprehensive income",
    "cash_flow": "Cash flow",
    "equity_statement": "Changes in equity",
    "other": "Other table",
    "unknown": "Table",
}

SCOPES = {
    "Balance sheet": ("balance_sheet",),
    "All financial statements": SUPPORTED_KINDS,
    "Every table found": None,  # no filter
}


def parse_page_spec(spec: str, total: int) -> list[int] | None:
    """``"all"`` / ``""`` -> None (all pages); ``"1-3, 8"`` -> [0, 1, 2, 7] (0-based, validated)."""
    spec = spec.strip().lower()
    if spec in ("", "all", "*"):
        return None
    pages: set[int] = set()
    for part in re.split(r"[,\s]+", spec):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if m is None:
            raise ValueError(f"cannot read page range {part!r} (use e.g. 1-3, 8)")
        lo = int(m.group(1))
        hi = int(m.group(2) or lo)
        if lo < 1 or hi < lo or hi > total:
            raise ValueError(f"page range {part!r} is outside 1-{total}")
        pages.update(range(lo - 1, hi))
    return sorted(pages)


def select_results(results: Sequence[PageResult], scope: str) -> list[PageResult]:
    kinds = SCOPES[scope]
    return [r for r in results if r.table is not None and (kinds is None or r.table.kind in kinds)]


def table_title(result: PageResult) -> str:
    """Short tab name: page and statement type in one language; the printed title goes in the caption."""
    t = result.table
    assert t is not None
    return f"p{result.page_no + 1} {KIND_LABELS.get(t.kind, 'Table')}"


def number_text(n: int | None) -> str:
    """12345 -> '12,345', -2979 -> '-2,979', None -> ''."""
    return "" if n is None else f"{n:,}"


def table_frame(table: Table, numeric: bool = False) -> pd.DataFrame:
    """The table as shown on screen.

    Default is the printed text (△, －, ※ kept). ``numeric`` gives signed numbers with thousands
    separators (-2,979) and "nil" for an empty dash. Blank cells are empty strings, never "None".
    """
    data: dict[str, list[str]] = {"Label": [INDENT * r.level + r.label for r in table.rows]}
    if any(r.note_ref for r in table.rows):
        data["Note"] = [r.note_ref for r in table.rows]
    for c, header in enumerate(table.headers):
        col: list[str] = []
        for r in table.rows:
            v = r.values[c] if c < len(r.values) else None
            if v is None:
                col.append("")
            elif numeric:
                col.append("nil" if v.kind == "nil" else number_text(v.number) or v.raw)
            else:
                col.append(v.raw)
        data[header or f"column {c + 1}"] = col
    return pd.DataFrame(data)


def row_styles(table: Table) -> list[str]:
    """CSS per row for the Styler: headings tinted, totals bold."""
    styles = []
    for r in table.rows:
        if r.row_type == "section":
            styles.append("background-color: rgba(120,160,200,0.18); font-weight: 600")
        elif r.row_type == "total":
            styles.append("font-weight: 700")
        else:
            styles.append("")
    return styles


def findings_frame(findings: Sequence[Finding]) -> pd.DataFrame:
    order = {"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS_ROUNDING": 3, "PASS": 4}
    rows = [
        {
            "Status": f.status,
            "Check": f.check,
            "Statement": f.table,
            "Column": f.column,
            "Row": f.row.split(" > ")[-1],
            "Expected": number_text(f.expected),
            "Printed": number_text(f.actual),
            "Difference": number_text(f.diff),
            "Allowed": str(f.tolerance) if f.expected is not None else "",
            "Detail": f.detail,
        }
        for f in sorted(findings, key=lambda f: order[f.status])
    ]
    return pd.DataFrame(rows)


def table_health(table: Table) -> tuple[str, dict[str, int]]:
    """('ok' | 'review' | 'check' | 'unsupported' | 'unverified', counts) for one table.

    'ok' needs positive evidence: at least one accounting check that passed (the numbers hang
    together). A table on which no check could run is 'unverified', never 'ok'.
    """
    findings = validate_tables([table])
    counts = summarize(findings)
    unparsed = any(f.check == "unparsed_cell" and f.status == "FAIL" for f in findings)
    if table.kind not in SUPPORTED_KINDS or unparsed:
        return "unsupported", counts
    if counts["FAIL"] or counts["WARN"]:
        return "check", counts
    # numeric_matches_raw passes for any table with numbers, so it says nothing about accounting
    evidence = sum(
        1
        for f in findings
        if f.status in ("PASS", "PASS_ROUNDING") and f.check != "numeric_matches_raw"
    )
    if not evidence:
        return "unverified", counts
    return ("review" if needs_review(table) else "ok"), counts


def needs_review(table: Table) -> bool:
    """An OCR-read table whose reads were not compared (or never compared) has not earned a tick.

    The accounting checks cannot see a misread label, so a person should look at such a page.
    """
    return str(table.meta.get("route", "")).startswith("ocr") and table.meta.get("reads") != 2


def group_health(tables: Sequence[Table]) -> list[tuple[str, dict[str, int]]]:
    """Health of each table, judged together with the other pages of the same statement type.

    A statement can span pages (a cash-flow statement, a balance sheet's two halves) and its checks
    use rows from several pages, so verification is per group of tables of the same kind. A table
    is 'ok' only if its group passed at least one real accounting check and failed none; a table
    with an unreadable cell or an unsupported kind is 'unsupported' regardless of its group.
    """
    from collections import defaultdict

    from .validate import check_unparsed_cells

    groups: dict[str, list[Table]] = defaultdict(list)
    for t in tables:
        groups[t.kind].append(t)
    group_state: dict[str, tuple[str, dict[str, int]]] = {}
    for kind, members in groups.items():
        findings = validate_tables(members)
        counts = summarize(findings)
        evidence = any(
            f.status in ("PASS", "PASS_ROUNDING") and f.check != "numeric_matches_raw"
            for f in findings
        )
        verified = "ok" if evidence else "unverified"
        group_state[kind] = ("check" if counts["FAIL"] or counts["WARN"] else verified, counts)
    out: list[tuple[str, dict[str, int]]] = []
    for t in tables:
        state, counts = group_state[t.kind]
        if state == "ok" and needs_review(t):
            state = "review"
        own_unparsed = any(f.status == "FAIL" for f in check_unparsed_cells(t))
        if t.kind not in SUPPORTED_KINDS or own_unparsed:
            state = "unsupported"
        out.append((state, counts))
    return out


def skipped_pages(results: Sequence[PageResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"Page": r.page_no + 1, "Reason": r.reason} for r in results if r.table is None]
    )
