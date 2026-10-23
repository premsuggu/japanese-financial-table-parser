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
| OCR safety net (read twice and compare, label vocabulary) | on 22 test pages, caught all 15 wrong OCR pages (accounting checks alone: 10); 8 of 51 right pages flagged. Opt-in, doubles OCR time |
| Upload UI | working, localhost only |
| Note-number column, wrapped labels, two-panel account form, IFRS totals | supported (tested on synthetic pages only) |
| Grid-ruled pages (equity statement, notes) | not supported; OCR on grid pages gives wrong cells |
| Other companies | one extra real filing tested (IFRS, 26 pages): 0 failed checks after fixes; no ground truth for it. OCR merges two-line column headers on tight layouts (periods can be wrong) |
| Real scanned PDFs | not tested (none available); scans are simulated |

Details and numbers: [docs/worklog/phase4-worklog.md](docs/worklog/phase4-worklog.md) (latest), [phase3](docs/worklog/phase3-worklog.md), [phase2](docs/worklog/phase2-worklog.md).

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
python -m fin_table_parser safety-eval --every-page --limit 100 --cache data/cache/reads.json   # how well the OCR safety net works
```

In the UI each table gets a health state: **ok** (a real accounting check passed), **check** (a check failed),
**review** (read by OCR and not double-checked), **unverified** (no check applies) or **unsupported** (layout not handled). Tick "Read twice and compare" to double-check OCR pages.

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
data/corpus/            public test PDFs, included (untrusted input; see data/README.md and data/corpus/README.md)
output/                 parser output for every test PDF (Excel) + summary table
report.pdf, chat.pdf    one-page project report; the conversation the project was built in (tools/make_report.py, tools/text_to_pdf.py)
AGENT.md                working rules for the coding agent (binding)
```

## Quality gates

```
python -m pytest -q      # 189 tests (the PDFs are in the repository; tests skip cleanly if they are removed)
ruff check src tests && ruff format --check src tests
mypy
```

## Caveats

* The ground truth for the sample page was written by the agent and then checked by the user against the PDF (all 43
  rows correct); see [docs/review/ground-truth-review.md](docs/review/ground-truth-review.md).
* "Silver" references used for OCR scoring are text-layer parses that pass the accounting checks, not gold.
* Test documents: twelve PDFs of one company and one IFRS filing of another (accounting checks only, no ground truth). They are public filings of third parties, included for testing; treat them as untrusted input and run ad-hoc Python on them with `python -I`.
* A passing accounting check does not prove an OCR page is right: a misread label does not change a total.