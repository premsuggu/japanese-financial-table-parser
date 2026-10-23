"""Evaluation: parser output vs ground truth, a baseline, and a fault-injection test of the checks.

Three independent questions:

1. ``score_against_truth``  Is the parsed table equal to the hand-made ground truth?
2. ``score_baseline``       How does PyMuPDF's built-in ``find_tables`` do on the same truth?
3. ``mutation_test``        If a single cell were wrong, would the accounting checks notice?
   (This measures the validator, not the parser: it answers "how much can we trust a PASS".)
"""

from __future__ import annotations

import copy
import difflib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .labels import label_key
from .models import Row, Table, Value
from .normalize import nfkc, parse_value
from .validate import validate_tables

# ---------------------------------------------------------------- ground truth


@dataclass
class TruthRow:
    level: int
    row_type: str
    label: str
    values: list[str | None]


@dataclass
class GroundTruth:
    statement: str
    unit: str
    headers: list[str]
    periods: list[str]
    revision: str | None
    rows: list[TruthRow]
    underlined: set[tuple[int, int]]
    annotation_method: str = ""


def load_truth(path: str | Path) -> GroundTruth:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return GroundTruth(
        statement=data["statement"],
        unit=data["unit"],
        headers=data["headers"],
        periods=data["periods"],
        revision=data.get("revision"),
        rows=[TruthRow(r[0], r[1], r[2], r[3:]) for r in data["rows"]],
        underlined={(r, c) for r, c in data.get("underlined_cells", [])},
        annotation_method=data.get("annotation_method", ""),
    )


def truth_from_table(table: Table) -> GroundTruth:
    """Use a trusted parse as the reference for another route (a *silver* standard, not gold)."""
    return GroundTruth(
        statement=table.statement,
        unit=table.unit or "",
        headers=list(table.headers),
        periods=[p or "" for p in table.periods],
        revision=table.meta.get("revision") or None,  # type: ignore[arg-type]
        rows=[
            TruthRow(r.level, r.row_type, r.label, [v.raw if v else None for v in r.values])
            for r in table.rows
        ],
        underlined=set(),
        annotation_method="silver: text-layer parse that passed all accounting checks",
    )


# ---------------------------------------------------------------- metrics


@dataclass
class Ratio:
    correct: int
    total: int

    @property
    def value(self) -> float:
        return self.correct / self.total if self.total else 1.0

    def __str__(self) -> str:
        return f"{self.value:6.1%}  ({self.correct}/{self.total})"


@dataclass
class PRF:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


@dataclass
class Scores:
    rows_truth: int
    rows_pred: int
    metrics: dict[str, Ratio] = field(default_factory=dict)
    cells: PRF = field(default_factory=lambda: PRF(0, 0, 0))
    underline: PRF = field(default_factory=lambda: PRF(0, 0, 0))
    errors: list[str] = field(default_factory=list)

    @property
    def page_exact(self) -> bool:
        return (
            self.rows_truth == self.rows_pred
            and all(r.correct == r.total for r in self.metrics.values())
            and self.cells.fp == 0
            and self.cells.fn == 0
            and self.underline.fp == 0
            and self.underline.fn == 0
        )


def align(truth_labels: Sequence[str], pred_labels: Sequence[str]) -> dict[int, int]:
    """Map truth row index -> predicted row index (equal-length lists align by position)."""
    if len(truth_labels) == len(pred_labels):
        return {i: i for i in range(len(truth_labels))}
    matcher = difflib.SequenceMatcher(a=truth_labels, b=pred_labels, autojunk=False)
    mapping: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            mapping[block.a + k] = block.b + k
    return mapping


def _value_signature(v: Value | None) -> tuple[Any, ...] | None:
    return None if v is None else (v.kind, v.number, v.negative_zero)


def score_against_truth(table: Table, truth: GroundTruth) -> Scores:
    s = Scores(rows_truth=len(truth.rows), rows_pred=len(table.rows))
    mapping = align(
        [label_key(r.label) for r in truth.rows], [label_key(r.label) for r in table.rows]
    )
    truth_paths = _truth_paths(truth.rows)

    def ratio(name: str) -> Ratio:
        return s.metrics.setdefault(name, Ratio(0, 0))

    # Table-level fields.
    for name, ok in {
        "statement": nfkc(table.statement) == nfkc(truth.statement),
        "unit": (table.unit or "") == truth.unit,
        "revision": (table.meta.get("revision") or None) == truth.revision,
        "headers": [label_key(h) for h in table.headers] == [label_key(h) for h in truth.headers],
        "periods": list(table.periods) == list(truth.periods),
    }.items():
        r = ratio(f"table.{name}")
        r.total += 1
        r.correct += int(ok)
        if not ok:
            s.errors.append(f"table.{name} mismatch")

    n_cols = len(truth.headers)
    for ti, trow in enumerate(truth.rows):
        pi = mapping.get(ti)
        prow: Row | None = table.rows[pi] if pi is not None else None
        for name, ok in {
            "row.label": prow is not None and label_key(prow.label) == label_key(trow.label),
            "row.level": prow is not None and prow.level == trow.level,
            "row.path": prow is not None
            and [label_key(p) for p in prow.path] == [label_key(p) for p in truth_paths[ti]],
            "row.type": prow is not None and prow.row_type == trow.row_type,
        }.items():
            r = ratio(name)
            r.total += 1
            r.correct += int(ok)
            if not ok:
                s.errors.append(f"row {ti} {trow.label!r}: {name} wrong")
        for c in range(n_cols):
            t_raw = trow.values[c] if c < len(trow.values) else None
            p_val = prow.values[c] if prow is not None and c < len(prow.values) else None
            p_raw = p_val.raw if p_val is not None else None
            if t_raw is not None and p_raw == t_raw:
                s.cells.tp += 1
            else:
                if p_raw is not None:
                    s.cells.fp += 1
                    s.errors.append(
                        f"cell ({ti},{c}) {trow.label!r}: got {p_raw!r}, expected {t_raw!r}"
                    )
                if t_raw is not None:
                    s.cells.fn += 1
            # Strictly typed comparison (number / nil / negative zero) incl. empty cells.
            t_val = parse_value(t_raw) if t_raw else None
            ok = _value_signature(t_val) == _value_signature(p_val)
            r = ratio("cell.parsed_value")
            r.total += 1
            r.correct += int(ok)
            if t_val is not None and (t_val.kind == "nil" or t_val.number == 0):
                rr = ratio("cell.nil_vs_zero")
                rr.total += 1
                rr.correct += int(ok)
            pred_under = prow is not None and c < len(prow.underlined) and prow.underlined[c]
            true_under = (ti, c) in truth.underlined
            if pred_under and true_under:
                s.underline.tp += 1
            elif pred_under:
                s.underline.fp += 1
            elif true_under:
                s.underline.fn += 1
    return s


def _truth_paths(rows: Sequence[TruthRow]) -> list[tuple[str, ...]]:
    from .hierarchy import build_paths

    return build_paths([r.label for r in rows], [r.level for r in rows])


# ---------------------------------------------------------------- baseline


def score_baseline(
    baseline_rows: Sequence[Sequence[str]], truth: GroundTruth
) -> dict[str, Ratio | PRF]:
    """Score PyMuPDF ``find_tables`` rows (label, v1, v2): text only, no header/level/type/flags."""
    body = [list(r) for r in baseline_rows]
    t_labels = [label_key(r.label) for r in truth.rows]
    p_labels = [label_key(r[0]) for r in body]
    mapping = align(t_labels, p_labels)
    label_ok = Ratio(0, len(truth.rows))
    cells = PRF(0, 0, 0)
    for ti, trow in enumerate(truth.rows):
        pi = mapping.get(ti)
        if pi is not None and p_labels[pi] == t_labels[ti]:
            label_ok.correct += 1
        for c in range(len(truth.headers)):
            t_raw = trow.values[c]
            p_raw = (body[pi][c + 1] or None) if pi is not None and c + 1 < len(body[pi]) else None
            if t_raw is not None and p_raw == t_raw:
                cells.tp += 1
            else:
                cells.fp += int(p_raw is not None)
                cells.fn += int(t_raw is not None)
    return {"row.label": label_ok, "cells": cells}


# ---------------------------------------------------------------- mutation test

MUTATIONS = (
    "last_digit_plus1",
    "middle_digit",
    "leading_digit",
    "transpose",
    "sign_flip",
    "drop_digit",
)


def _mutate(n: int, kind: str) -> int | None:
    sign, digits = (-1 if n < 0 else 1), str(abs(n))
    if kind == "sign_flip":
        return -n if n else None
    if kind == "drop_digit":
        return sign * int(digits[:-1]) if len(digits) > 1 else None
    pos = {
        "last_digit_plus1": len(digits) - 1,
        "middle_digit": len(digits) // 2,
        "leading_digit": 0,
    }.get(kind)
    if pos is not None:
        d = list(digits)
        d[pos] = str((int(d[pos]) + 1) % 10)
        return sign * int("".join(d))
    if kind == "transpose":
        for i in range(len(digits) - 1):
            if digits[i] != digits[i + 1]:
                d = list(digits)
                d[i], d[i + 1] = d[i + 1], d[i]
                return sign * int("".join(d))
        return None
    raise ValueError(kind)


def _format(n: int) -> str:
    return ("△" if n < 0 else "") + f"{abs(n):,}"


@dataclass
class MutationResult:
    by_kind: dict[str, Ratio]
    total: Ratio
    never_detected: list[str]  # cells no mutation kind was ever caught on
    baseline_fails: int


def mutation_test(table: Table) -> MutationResult:
    """Corrupt one numeric cell at a time and count how often the checks raise a FAIL."""
    baseline_fails = sum(f.status == "FAIL" for f in validate_tables([table]))
    by_kind = {k: Ratio(0, 0) for k in MUTATIONS}
    caught_cells: dict[tuple[int, int], int] = {}
    for row in table.rows:
        for col, v in enumerate(row.values):
            if v is None or v.kind != "number" or v.number is None:
                continue
            for kind in MUTATIONS:
                new = _mutate(v.number, kind)
                if new is None or new == v.number:
                    continue
                mutated = copy.deepcopy(table)
                mutated.rows[row.index].values[col] = Value(_format(new), new, "number")
                detected = (
                    sum(f.status == "FAIL" for f in validate_tables([mutated])) > baseline_fails
                )
                by_kind[kind].total += 1
                by_kind[kind].correct += int(detected)
                caught_cells[(row.index, col)] = caught_cells.get((row.index, col), 0) + int(
                    detected
                )
    total = Ratio(sum(r.correct for r in by_kind.values()), sum(r.total for r in by_kind.values()))
    never = [
        f"{table.rows[r].label} [col {c}]" for (r, c), n in sorted(caught_cells.items()) if n == 0
    ]
    return MutationResult(by_kind, total, never, baseline_fails)


# ---------------------------------------------------------------- table vs table


def _raw_at(row: Row, col: int) -> str | None:
    value = row.values[col] if col < len(row.values) else None
    return value.raw if value is not None else None


def table_diff(a: Table, b: Table, *, compare_flags: bool = False) -> list[str]:
    """Differences between two parses of the same page (empty list = identical).

    Compares statement fields, row labels, levels, row types and printed cell text. Underline /
    rule flags are ignored unless ``compare_flags`` (they need drawings that OCR does not have).
    """
    diffs: list[str] = []
    for name in ("statement", "unit", "kind"):
        if getattr(a, name) != getattr(b, name):
            diffs.append(f"{name}: {getattr(a, name)!r} != {getattr(b, name)!r}")
    if [label_key(h) for h in a.headers] != [label_key(h) for h in b.headers]:
        diffs.append(f"headers: {a.headers} != {b.headers}")
    if a.periods != b.periods:
        diffs.append(f"periods: {a.periods} != {b.periods}")
    mapping = align([label_key(r.label) for r in a.rows], [label_key(r.label) for r in b.rows])
    if len(a.rows) != len(b.rows) or len(mapping) != len(a.rows):
        diffs.append(f"rows: {len(a.rows)} != {len(b.rows)} (aligned {len(mapping)})")
    for i, ra in enumerate(a.rows):
        j = mapping.get(i)
        if j is None:
            diffs.append(f"row {i} {ra.label!r}: missing in second")
            continue
        rb = b.rows[j]
        if (ra.level, ra.row_type) != (rb.level, rb.row_type):
            diffs.append(
                f"row {i} {ra.label!r}: level/type {(ra.level, ra.row_type)} != {(rb.level, rb.row_type)}"
            )
        for c in range(max(len(ra.values), len(rb.values))):
            va = _raw_at(ra, c)
            vb = _raw_at(rb, c)
            if va != vb:
                diffs.append(f"row {i} {ra.label!r} col {c}: {va!r} != {vb!r}")
        if compare_flags and ra.underlined != rb.underlined:
            diffs.append(f"row {i} {ra.label!r}: underline flags differ")
    return diffs
