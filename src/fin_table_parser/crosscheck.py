"""Read agreement: compare two independent reads of the same page and flag every difference.

The accounting checks cannot see a misread label, or a digit error that keeps the totals consistent.
Two reads of one page (text layer vs OCR, or OCR of the same picture at two pixel sizes) rarely make
the same mistake in the same cell, so a cell where they differ is where to look.

Rows are paired without trusting either label: first by identical amounts (then a label difference is
a label misread), then by identical label (then an amount difference is a number misread).
Whatever is left has no partner and is reported as a row seen by one read only.
"""

from __future__ import annotations

from collections import Counter

from .labels import label_key
from .models import Finding, Row, Table, Value

CHECK = "read_agreement"


def _amounts(row: Row) -> tuple[str, ...]:
    """What each cell means (kind, number, sign of zero), not how it is printed: ``204, 257`` equals ``204,257``."""
    return tuple(_meaning(v) for v in row.values)


def _meaning(v: Value | None) -> str:
    return f"{v.kind}:{v.number}:{v.negative_zero}" if v else ""


def _has_amounts(row: Row) -> bool:
    return any(_amounts(row))


def _unique(rows: list[Row], key: object) -> dict[object, Row]:
    """Rows whose key occurs exactly once (a repeated key cannot be paired safely)."""
    keyed = [(key(r), r) for r in rows]  # type: ignore[operator]
    counts = Counter(k for k, _ in keyed)
    return {k: r for k, r in keyed if counts[k] == 1}


def compare_reads(first: Table, second: Table) -> list[Finding]:
    """One WARN per disagreement; empty when the two reads agree."""
    findings: list[Finding] = []
    name = first.statement or first.source
    rows_a = [r for r in first.rows if _has_amounts(r)]
    rows_b = [r for r in second.rows if _has_amounts(r)]
    paired_a: set[int] = set()
    paired_b: set[int] = set()

    by_amounts_a = _unique(rows_a, _amounts)
    by_amounts_b = _unique(rows_b, _amounts)
    for ra in rows_a:
        rb = by_amounts_b.get(_amounts(ra))
        if rb is None or by_amounts_a.get(_amounts(ra)) is not ra:
            continue
        paired_a.add(ra.index)
        paired_b.add(rb.index)
        if label_key(ra.label) != label_key(rb.label):
            findings.append(
                Finding(
                    CHECK,
                    "WARN",
                    name,
                    "",
                    ra.label,
                    detail=f"label read two ways: '{ra.label}' / '{rb.label}'",
                )
            )

    by_label_b = _unique(
        [r for r in rows_b if r.index not in paired_b], lambda r: label_key(r.label)
    )
    unpaired_a = [r for r in rows_a if r.index not in paired_a]
    by_label_a = _unique(unpaired_a, lambda r: label_key(r.label))
    for key, ra in by_label_a.items():
        rb = by_label_b.get(key)
        if rb is None:
            continue
        paired_a.add(ra.index)
        paired_b.add(rb.index)
        for col, (va, vb) in enumerate(zip(ra.values, rb.values, strict=False)):
            if _meaning(va) != _meaning(vb):
                header = first.headers[col] if col < len(first.headers) else str(col)
                findings.append(
                    Finding(
                        CHECK,
                        "WARN",
                        name,
                        header,
                        ra.label,
                        expected=vb.number if vb else None,
                        actual=va.number if va else None,
                        detail=f"amount read two ways: '{va.raw if va else ''}' / '{vb.raw if vb else ''}'",
                    )
                )

    for ra in rows_a:
        if ra.index not in paired_a:
            findings.append(
                Finding(
                    CHECK, "WARN", name, "", ra.label, detail="row not found by the second read"
                )
            )
    for rb in rows_b:
        if rb.index not in paired_b:
            findings.append(
                Finding(
                    CHECK, "WARN", name, "", rb.label, detail="row found only by the second read"
                )
            )
    return findings
