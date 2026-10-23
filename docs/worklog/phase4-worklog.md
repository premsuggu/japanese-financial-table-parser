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

## Addendum: one real filing of another company

A command that was meant to be a download attempt (the user declined it) had in fact already saved four PDFs to
`data/corpus/others/`. Three held only cover pages and were deleted; the fourth, Link-U Group's IFRS 決算短信 (26 pages,
see `data/corpus/README.md`), is a real unseen-company test. The unchanged parser gave 7 statement tables and **9 false
FAILs**. The causes and fixes:

| Cause | Fix |
|---|---|
| page numbers (`-4-`, `14-`) read as an amount row, "cannot read '-4-' as a number" | an end line whose cells do not read as numbers, or that holds only a dash, is not part of the table (`textgeom._reads_as_amounts`) |
| the J-GAAP rule 営業利益 = 売上総利益 - 販管費 failed on an IFRS income statement (other income / expenses are inside operating profit) | formulas can now say `requires` / `excludes`; IFRS formulas added for operating, pre-tax and net profit (`rules/statement_rules.yaml`) |
| header "(自 2023年8月1日 至 2024年7月31日)" with the years on their own line became a data row and the columns had no period | a line that says 自/至 or 年/月 and whose only numbers are years is header text (`textgeom.is_period_line`) |

Two further causes surfaced when the tables were checked together: the year tokens of that header line also created
two empty phantom columns on the comprehensive-income page (years are now ignored when finding columns), and a formula
looked up its terms in another table (a reconciliation page repeating the labels), so formulas now prefer the target's
own table and the gross-profit rule accepts 売上収益 as well as 売上高.

After the fixes: 0 FAIL on all 7 tables (34 checks passed); the income statement has periods 2024-07-31 / 2025-07-31 and 17 rows. Regression
tests: `tests/integration/test_other_company.py`, `test_layouts.py::test_a_page_number_under_the_table_is_not_a_row`,
`test_rules.py::test_ifrs_income_statement_uses_its_own_operating_profit_formula`. Only the accounting checks verify
this filing (no ground truth), and it is one filing, so this is evidence of progress, not proof of generality.
Pages 17 and 19 (IFRS transition reconciliations with four columns) are read as balance sheets and pass the column
totals, but the reconciliation identity (IFRS = Japanese GAAP + reclassification + difference) is not checked.

## Not done

Other companies' real filings; independent (XBRL) ground truth; real scanned PDFs. The synthetic pages show the code
handles each layout feature in isolation, not that real filings from other companies will parse.
