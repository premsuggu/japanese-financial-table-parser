"""Render evaluation results as a Markdown report."""

from __future__ import annotations

from collections.abc import Sequence

from .evaluate import PRF, GroundTruth, MutationResult, Ratio, Scores
from .models import Finding
from .validate import summarize


def _prf(p: PRF) -> str:
    return (
        f"P {p.precision:.1%} / R {p.recall:.1%} / F1 {p.f1:.1%}  (TP {p.tp}, FP {p.fp}, FN {p.fn})"
    )


def render_report(
    pdf_name: str,
    truth: GroundTruth,
    scores: Scores,
    baseline: dict[str, Ratio | PRF],
    findings: Sequence[Finding],
    mutation: MutationResult,
) -> str:
    lines = [f"# Parser evaluation: {pdf_name}", ""]
    lines += [
        "## Ground truth",
        "",
        f"- {truth.annotation_method}",
        f"- {len(truth.rows)} rows x {len(truth.headers)} value columns",
        "",
    ]

    lines += ["## 1. Parser vs ground truth (measured on the Excel file, i.e. end to end)", ""]
    lines += ["| Metric | Result |", "|---|---|"]
    lines.append(f"| Row count (truth / parsed) | {scores.rows_truth} / {scores.rows_pred} |")
    for name, r in scores.metrics.items():
        lines.append(f"| {name} | {r} |")
    lines.append(f"| Cell text (printed form, non-empty cells) | {_prf(scores.cells)} |")
    lines.append(f"| Underline flags | {_prf(scores.underline)} |")
    lines.append(f"| **Page exact match** | **{'YES' if scores.page_exact else 'NO'}** |")
    lines.append("")
    if scores.errors:
        lines += ["Errors:", ""] + [f"- {e}" for e in scores.errors[:30]] + [""]

    base_cells = baseline["cells"]
    base_labels = baseline["row.label"]
    assert isinstance(base_cells, PRF) and isinstance(base_labels, Ratio)
    lines += ["## 2. Baseline: PyMuPDF `find_tables()` on the same page", ""]
    lines += ["| Metric | Baseline | This parser |", "|---|---|---|"]
    lines.append(f"| Row labels | {base_labels} | {scores.metrics['row.label']} |")
    lines.append(f"| Cell text | F1 {base_cells.f1:.1%} | F1 {scores.cells.f1:.1%} |")
    lines.append(
        "| Column headers / period dates | not produced | "
        + f"{scores.metrics['table.headers']} / {scores.metrics['table.periods']} |"
    )
    lines.append(
        f"| Hierarchy (level, parent path) | not produced | {scores.metrics['row.level']} / {scores.metrics['row.path']} |"
    )
    lines.append(
        f"| Row type (section/item/total/net) | not produced | {scores.metrics['row.type']} |"
    )
    lines.append(
        "| Unit, 訂正後 marker | not produced | "
        + f"{scores.metrics['table.unit']} / {scores.metrics['table.revision']} |"
    )
    lines.append("")

    counts = summarize(findings)
    lines += ["## 3. Accounting checks on the parsed workbook", ""]
    lines += [
        f"PASS {counts['PASS']}, PASS_ROUNDING {counts['PASS_ROUNDING']}, FAIL {counts['FAIL']}, SKIP {counts['SKIP']}",
        "",
    ]
    lines += [
        "| Status | Check | Column | Row | Expected | Actual | Diff | Tolerance |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in findings:
        if f.check == "numeric_matches_raw":
            continue
        lines.append(
            f"| {f.status} | {f.check} | {f.column[:6]} | {f.row.split(' > ')[-1]} | {f.expected} | {f.actual} | {f.diff} | {f.tolerance} |"
        )
    lines.append("")

    lines += ["## 4. How much can a PASS be trusted? (fault injection)", ""]
    lines += [
        "Each numeric cell was corrupted one at a time (printed text and number together) and the "
        "accounting checks re-run. 'Detected' means at least one new FAIL.",
        "",
        "| Injected error | Detected |",
        "|---|---|",
    ]
    for kind, r in mutation.by_kind.items():
        lines.append(f"| {kind} | {r} |")
    lines.append(f"| **All** | **{mutation.total}** |")
    lines.append("")
    if mutation.never_detected:
        lines += [
            "Cells where *no* injected error was ever caught: either no check covers the cell, or "
            "every injected change stayed within the rounding tolerance (a value of 0, for "
            "example, can only change by +-1):",
            "",
        ]
        lines += [f"- {c}" for c in mutation.never_detected]
        lines.append("")
    return "\n".join(lines)
