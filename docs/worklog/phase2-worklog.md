# Phase 2 work log

Approved plan: [../plans/phase2-plan.md](../plans/phase2-plan.md). Order: A (statement-aware validation), B (band-free
core), C (hybrid with OCR), D (evaluation), plus an upload UI built alongside. Status at the end of this entry:
A, B, UI done and tested; C wired and measured (see "OCR bake-off"); D partly done (silver references, bake-off).

## What was built

| Step | Deliverable | Evidence |
|---|---|---|
| A | `rules/statement_rules.yaml` + `rules/engine.py`; statement kinds; `unparsed_cell`; closing-stock sign | whole filing: 80 checks, 0 FAIL / WARN / SKIP |
| B | `strategies/textgeom.py` (words only), `strategies/common.py`, footnote markers | identical to the band-based parse on all 28 comparable corpus pages |
| UI | `app.py`, `ui_model.py`, `document.py`; Excel download; localhost only | driven in a headless browser on a 19-page and a 109-page file |
| C | `ocr.py` (engine interface, worker protocol), `strategies/deskew.py`, `pipeline.parse_source`, workers in `tools/ocr/` | simulated-OCR tests; real engines in the bake-off |
| D | `ocr_eval.py`, silver pages, `docs/reports/ocr-comparison.md` | 22 silver pages found; bake-off on 6 |

Test suite: 156 tests, ruff and mypy (strict) clean.

## Problems found, and how each was resolved

| # | Problem | Found by | Resolution |
|---|---|---|---|
| 1 | Generic "total = sum of siblings" gave false FAILs on the flat income statement | probe on the other statements | totals need a parent section; flat statements use formulas from the rules file |
| 2 | Equity-statement pages classified as balance sheets (spurious FAILs); note tables named after a statement classified as that statement | document scan | a title counts only if it *ends with* the statement name; the equity statement is its own kind; label-based detection needs two distinct row labels that *start* with statement vocabulary |
| 3 | Footnote markers `※１2,121,360` glued into amounts: cell read as text, silently counted as 0 | annual report (11 FAILs on one page) | marker split off before NFKC; `unparsed_cell` makes any unreadable number cell loud |
| 4 | Several markers `※１,※２162,303` | annual report, comprehensive income | marker pattern repeats |
| 5 | Cost of goods sold: closing stock is subtracted, not added | standalone P&L of the annual report | `labels.component_sign` |
| 6 | Wrapped label (two lines, amounts centred between) became 3 rows | cash-flow page | lines closer than 0.75 row pitch form one row |
| 7 | Running page header (company name) taken as column header | band vs band-free comparison | header = contiguous block above the first amount, cut at the unit line |
| 8 | OCR cleanup changed `ー` inside リース資産 | simulated OCR at zero noise | dash look-alikes only mapped when the whole token is a dash |
| 9 | De-skew "corrected" noise at +-2 pt box error | simulated OCR sweep | angles under 0.3 degree ignored; plateau centre instead of first maximum |
| 10 | Dates with stray spaces `(2025 年3月31 日)` lost their period | first real OCR output | date regex allows spaces; headers compared without whitespace |
| 11 | UI: empty cells showed "None", floats with 6 decimals, Deploy button, mixed-language tab names | looked at screenshots | fixed; checked again in the browser |
| 12 | Cover-page tables got a green tick | looked at screenshots | a tick needs a passed accounting check ("unverified" otherwise); regression test on the full filing |
| 13 | A scripted `str.replace` edit silently did not apply (file had been reformatted) | a test that should have failed passed | edits now made with a tool that errors on no match; earlier scripted edits re-verified |
| 14 | A server I thought had picked up new code was stale | screenshot disagreed with the test suite | restarted; trust the test suite and restart before judging a screenshot |

## Reviewer-driven changes (before the OCR comparison)

Worker output is a JSON file (never parsed from stdout); one batch call per engine so model load time is reported
separately; the bake-off calls the same `parse_ocr_words` as production; one page per document (spread across the
corpus); de-skew added because real scans are rotated; "no table found on a page that is mostly a picture" now
triggers OCR; the UI is started with explicit localhost flags so the working directory cannot widen it.

## Caveats that apply to every number in this phase

* Silver references are text-layer parses that pass all accounting checks. A mistake shared by the text layer and the
  extractor would be invisible. They are not human-made.
* Every document comes from one company, so layout variety is small.
* The sample-page ground truth was written by Claude and has not been reviewed by a human yet.
* Skew in the bake-off is simulated by rotating the page when rendering; real scans also have uneven lighting,
  bleed-through and compression that are only partly simulated (JPEG at quality 40, 150 dpi).

## Not done

* Grid-ruled pages (equity statement, notes) and statements with a note-number column.
* Top-aligned wrapped labels (normal line spacing).
* XBRL ground truth; other companies' filings.
* Arbitration between text layer and OCR when both are available but disagree (the checks run on both, but no
  automatic choice is made).

## OCR bake-off result (6 silver pages x 3 conditions, CPU only)

Full tables: [../reports/ocr-comparison.md](../reports/ocr-comparison.md).

| Engine | Cell F1 (clean / scan-like / skewed) | Pages exact (of 6) | Label accuracy | Char error | s/page |
|---|---|---|---|---|---|
| YomiToku | 97.2% / 92.8% / 97.3% | 4 / 3 / 5 | 98-99% | 1.2-3.6% | about 12 |
| PaddleOCR | 83.7% / 90.7% / 84.1% | 0 / 0 / 0 | 65-69% | 4.6-5.7% | about 72 |

Decision: YomiToku is the OCR engine (more accurate on Japanese labels, about 6x faster). PaddleOCR is not needed.

Caveats: silver references, one company, simulated scan conditions. The accounting checks flagged only some of the
wrong YomiToku pages (1 of 2 clean, 1 of 3 scan-like), so an OCR page that passes the checks is not proof it is
right. (The UI does not yet mark OCR-read pages specially; a possible follow-up.) Label errors are mostly kanji misreads, which a
total-based check cannot see.
