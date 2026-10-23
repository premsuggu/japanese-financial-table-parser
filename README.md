# Japanese financial-statement table parser

Takes a PDF page that holds a Japanese consolidated balance sheet (layout may vary, may be a scan) and produces a
structured table: row labels, values, columns, hierarchy, units and accounting signs. No coordinates are
hard-coded; every tolerance is a fraction of a length measured on the page. Personal, non-commercial project.

Output is Excel: one workbook per PDF, one sheet per statement, plus a Validation sheet (accounting checks) and a
Metadata sheet.

## Status

| Area | State |
|---|---|
| Text-layer PDFs (balance sheet, income statement, cash flow, comprehensive income) | working; whole sample filing: 80 checks, 0 failures |
| Accounting checks (balance identity, totals, statement formulas) | working; rules live in `src/fin_table_parser/rules/statement_rules.yaml` |
| Scanned pages (OCR route, YomiToku) | working on simulated scans; about 93-97% of cells right, not every page exact |
| Upload UI | working, localhost only |
| Grid-ruled pages (equity statement, notes), note-number columns | not supported |
| Other companies, real scans | not yet tested |

Details and numbers: [docs/worklog/phase2-worklog.md](docs/worklog/phase2-worklog.md).

## Install

Python 3.12. From the project root:

```
pip install -e .                  # pymupdf, openpyxl, pyyaml
pip install streamlit pandas      # only for the UI
pip install pytest ruff mypy      # only for development
```

OCR (optional, only for scanned pages) lives in its own virtual environment so it cannot disturb the main one:
`.venv-yomitoku/` with `yomitoku` installed. Every install is recorded in
[docs/worklog/installed-packages.md](docs/worklog/installed-packages.md).

## Use

```
python -m fin_table_parser ui                                   # upload page at http://localhost:8501
python -m fin_table_parser parse in.pdf -o output/in.xlsx --page 0   # one page (0-based) to Excel
python -m fin_table_parser check output/in.xlsx                 # re-run the accounting checks on a workbook
python -m fin_table_parser evaluate in.pdf truth.json -o docs/reports/metrics.md
python -m fin_table_parser ocr-eval --engines yomitoku --limit 6     # OCR comparison on the corpus
```

In the UI each table gets a health state: **ok** (a real accounting check passed), **check** (a check failed),
**unverified** (no check applies) or **unsupported** (layout not handled). Pages read by OCR deserve a human look.

## How it works (one paragraph)

`pdf_io` reads the text layer. `pipeline` decides: healthy text layer -> use it; unusable, or no table found on a
mostly-image page -> render and OCR it, de-skew the words. A words-only extractor finds rows by line spacing, columns
by right-aligned number edges and the header above the first amount; a band-based extractor is used when coloured
row bands exist. Labels become a hierarchy by indent. `validate` classifies the statement and runs the checks.
`export` writes the workbook. Full explanation: [docs/explanations/](docs/explanations/).

## Layout

```
src/fin_table_parser/   the package (pdf_io, strategies/, pipeline, ocr, validate, rules/, export, app, cli, ...)
tests/                  unit + integration tests (pytest); ground truth in tests/fixtures/
tools/ocr/              worker scripts run inside the OCR virtual environment
docs/                   explanations, plans, work logs, reports, review (index: docs/README.md)
data/corpus/            public test PDFs (untrusted input; see data/corpus/README.md)
AGENT.md                working rules for the coding agent (binding)
```

## Quality gates

```
python -m pytest -q      # 156 tests with the sample PDFs; 78 are skipped without them (see data/README.md)
ruff check src tests && ruff format --check src tests
mypy
```

## Caveats

* The ground truth for the sample page was written by the agent, not a human; review it in
  [docs/review/ground-truth-review.md](docs/review/ground-truth-review.md).
* "Silver" references used for OCR scoring are text-layer parses that pass the accounting checks, not gold.
* All test documents come from one company.
* A passing accounting check does not prove an OCR page is right: a misread label does not change a total.
* Corpus PDFs are untrusted: open them only through the parser, and run ad-hoc Python on them with `python -I`.
