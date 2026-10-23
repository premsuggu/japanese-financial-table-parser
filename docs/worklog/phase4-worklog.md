# Phase 4 work log: layouts beyond the sample company (offline work only)

Plan: [../plans/phase4-plan.md](../plans/phase4-plan.md). On the user's instruction, steps that need downloads or
external APIs (other companies' filings, EDINET XBRL truth) were **not done**; everything below uses synthetic pages and
the existing corpus. Explanation: [../explanations/06-layout-variants.md](../explanations/06-layout-variants.md).

## Built and tested (184 tests pass, ruff and mypy clean)

* `tests/synth.py`: synthetic statement pages (note column, IFRS names, wrapped labels, grid, 1 or 3 columns, account form).
  `tests/integration/test_layouts.py`: 14 tests.
* Note-number column support (`Row.note_ref`, Excel "Note ref" column, UI "Note" column).
* Top-aligned wrapped labels; two-panel account form (勘定式); IFRS liabilities-and-equity totals; minus-sign variants;
  more unit-line forms.
* Realistic scan degradation (blur, noise, uneven light, 0.5 degree skew, JPEG q60): `pdf_io.degrade_image`, new
  condition in `ocr_eval.CONDITIONS` (needs numpy, used only for evaluation).

## Measured

Safety net on the 22 corpus pages, now with the harder "photo-like" condition
([../reports/phase4-safety-with-photo-condition.md](../reports/phase4-safety-with-photo-condition.md)):

| Condition (YomiToku) | Cells right (parsed value) | Wrong pages | Caught by accounting checks | Caught with read agreement + label check |
|---|---|---|---|---|
| clean 300 dpi | 98.6% | 7 / 22 | 3 | 7 |
| scan-like 150 dpi JPEG q40 | 98.8% | 4 / 22 | 4 | 4 |
| skewed 1 degree | 99.1% | 4 / 22 | 3 | 4 |
| photo-like (new) | 92.9% | 22 / 22 | 21 | 21 |

On photo-like scans every page has at least one error, and one page (`S100X0Y3:p11`, one wrong item) is not flagged by
any check: the safety net is not complete.

Real OCR (YomiToku) on the synthetic layouts: rows are right for note column, IFRS, wrapped labels, grid and account
form, but:
* two-line column headers come out merged or with dropped characters (`(2025 年3 月31 日) 2026 年3 月3 日)`), so periods
  are wrong on 4 of 5 synthetic pages. A split heuristic was tried and reverted: it did not fix it reliably. **Known gap.**
* grid-ruled pages read through OCR give wrong cells (`1,000` read as `1`), with no check failing (health "unverified").
* a wrapped label's amount went missing once; a check flagged it.

## Not done

Other companies' real filings; independent (XBRL) ground truth; real scanned PDFs. The synthetic pages show the code
handles each layout feature in isolation, not that real filings from other companies will parse.
