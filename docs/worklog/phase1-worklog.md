# Phase 1 work log

Scope (agreed): parse `balance_sheet_after_correction.pdf` as well as possible; Excel output, one workbook
per PDF, one sheet per statement; evaluate with metrics.

## What was built

`src/fin_table_parser/`: models, pdf_io, triage, strategies/banded, hierarchy, normalize, labels,
validate, export, xlsx_reader, evaluate, report, pipeline, cli. Tests in `tests/unit` and `tests/integration`
(47 tests). Ground truth in `tests/fixtures/ground_truth/`.

## Packages installed (with permission)

openpyxl (Excel), pytest, ruff, mypy. The project itself was installed in editable mode (`pip install -e .`).
PyMuPDF, pandas, PyYAML were already present (pandas / PyYAML turned out to be unused).

## Problems found and how they were resolved

| # | Problem | How found | Fix |
|---|---|---|---|
| 1 | 60 "rows" instead of 43; every indent level off by one | first run of the extractor | 0.7 pt white slivers hidden behind rules were treated as bands; bands thinner than half the typical band are dropped |
| 2 | "Exact" net-value check failed by 1 on 3 cells | first validator run | not a parser bug (verified against the text layer): figures are rounded independently; net check now has a tolerance |
| 3 | Original page 8 (same layout family) gave duplicated rows and an empty header | stress test on `complete_pdf.pdf` | that PDF draws rules as strokes (not filled rectangles) and total-row bands overlap; `pdf_io` now normalises strokes, `find_bands` drops overlapping duplicates |
| 4 | Continuation page (p. 9) took the running page header as the statement name | stress test | a title line must contain a statement keyword |
| 5 | Earlier claim that underlines mark corrections was wrong | original filing has 12 word-width underlines | underline is a low-trust flag only; corrections found by diffing versions |
| 6 | Several tolerances were absolute points (rule height 1.5 pt, line gap 3 pt, underline offsets): headers broke when the same page was rendered at 0.5x or 3x | scale/offset experiment (user asked to confirm nothing is hard-coded) | every geometric tolerance is now a fraction of the page's own median row height (`row_height`, constants at top of `banded.py`); `tests/integration/test_layout_invariance.py` re-renders the page at 0.4x-3x with offsets and requires an exact match |

Audit result for "is anything hard-coded": no page coordinates and no PDF-specific strings anywhere in `src/`
(grep-verified). What *is* fixed: relative tolerances (now scale-free), the domain vocabulary in `labels.py`
(合計, 純額, 資産合計, 負債純資産合計, statement keywords), and structural assumptions (rows are drawn as coloured
bands; a total sits at the same indent as its components).

Problems 3-4 were found only because of the stress tests; a single-page score of 100% did not reveal them.

## Results (details: docs/reports/phase1-metrics.md)

- Ground truth: 43/43 rows, 86/86 cells, hierarchy, row types, headers, unit, period dates all correct; page exact match.
- Baseline `find_tables()`: ties on labels (43/43) and cell text, but produces no header, period dates, hierarchy,
  row types, unit or flags. Everything this parser adds is structure. (An earlier report showed the baseline at
  42/43 because the evaluation wrongly dropped its first row; fixed.)
- Ground-truth caveat: written by Claude after the parser's rows were on screen, values from the same text layer;
  not blind to the parser and not re-read from the pixels.
- Accounting checks on the page: 0 FAIL (8 PASS, 13 PASS_ROUNDING, 1 SKIP: balance identity needs the other page).
- Original vs corrected page: differ in exactly the 3 corrected cells.
- Assets = liabilities + net assets verified on the original filing's pages 8 + 9.

## Caveats

- The ground truth was written by Claude from the text dump and the page image, not by a human and not from
  the parser output. It is not yet reviewed by you. The text-layer digits were not compared with an
  independent OCR of the image.
- One page, developed against: 100% here is an upper bound for unseen pages, not an expected score.
- Static analysis: ruff and mypy (strict) clean; 47 tests pass.

## Known gap found after Phase 1 (evidence, not yet fixed)

With all graphics removed from the page (text layer untouched: 132 words), the parser raises `UnsupportedPage`.
It needs the coloured row bands. A balance sheet without bands, or the output of an OCR engine (words with boxes,
no drawings), cannot be parsed yet, although labels, numbers, indents and headers are all present in the words.
The band-stripped page is a ready test case: same ground truth, no graphics.

## Not done / next

- Phase 2: grid-ruled pages (equity statement, segment notes), multi-line labels, title inheritance across pages.
- Fallback routing (OCR / Docling) behind `UnsupportedPage`.
- Human review of the ground-truth file; XBRL ground truth for more filings.
- Nothing has been committed or pushed (this directory is not a git repository).
