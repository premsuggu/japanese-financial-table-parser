"""Write one Excel workbook per test PDF into output/ (all financial statements found, with their checks).

python -X utf8 tools/make_outputs.py
"""

from __future__ import annotations

from pathlib import Path

from fin_table_parser.document import parse_document
from fin_table_parser.export import write_workbook
from fin_table_parser.ui_model import SCOPES, select_results
from fin_table_parser.validate import summarize, validate_tables

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    pdfs = sorted(ROOT.glob("*.pdf")) + sorted((ROOT / "data" / "corpus").glob("*/*/*.pdf"))
    summary = [
        "| PDF | Statement tables | Checks passed | Failed | Warnings |",
        "|---|---|---|---|---|",
    ]
    for pdf in pdfs:
        results = select_results(parse_document(pdf), "All financial statements")
        tables = [r.table for r in results if r.table is not None]
        if not tables:
            summary.append(f"| {pdf.name} | 0 | | | |")
            continue
        findings = validate_tables(tables)
        counts = summarize(findings)
        name = pdf.stem if pdf.parent == ROOT else f"{pdf.parent.name}"
        write_workbook(tables, findings, ROOT / "output" / f"{name}.xlsx")
        passed = counts["PASS"] + counts["PASS_ROUNDING"]
        summary.append(
            f"| {pdf.relative_to(ROOT).as_posix()} | {len(tables)} | {passed} | {counts['FAIL']} | {counts['WARN']} |"
        )
    text = (
        "# Parser output\n\nOne workbook per test PDF (all financial statements found; sheets: one per statement, "
        'Validation, Metadata). Written by `tools/make_outputs.py`; scope "'
        + list(SCOPES)[1]
        + '".\n\n'
        + "\n".join(summary)
        + "\n"
    )
    (ROOT / "output" / "README.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
