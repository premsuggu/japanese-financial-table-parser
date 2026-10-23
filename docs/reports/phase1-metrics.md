# Parser evaluation: balance_sheet_after_correction.pdf

## Ground truth

- Written by Claude: values from the PDF plain-text dump (the same text layer the parser reads), indent level / row type / underlines from the rendered page image. Written after the parser's rows had been displayed, so it is not blind to the parser output. Values were not re-read from the pixels. Not yet reviewed by a human.
- 43 rows x 2 value columns

## 1. Parser vs ground truth (measured on the Excel file, i.e. end to end)

| Metric | Result |
|---|---|
| Row count (truth / parsed) | 43 / 43 |
| table.statement | 100.0%  (1/1) |
| table.unit | 100.0%  (1/1) |
| table.revision | 100.0%  (1/1) |
| table.headers | 100.0%  (1/1) |
| table.periods | 100.0%  (1/1) |
| row.label | 100.0%  (43/43) |
| row.level | 100.0%  (43/43) |
| row.path | 100.0%  (43/43) |
| row.type | 100.0%  (43/43) |
| cell.parsed_value | 100.0%  (86/86) |
| cell.nil_vs_zero | 100.0%  (3/3) |
| Cell text (printed form, non-empty cells) | P 100.0% / R 100.0% / F1 100.0%  (TP 74, FP 0, FN 0) |
| Underline flags | P 100.0% / R 100.0% / F1 100.0%  (TP 2, FP 0, FN 0) |
| **Page exact match** | **YES** |

## 2. Baseline: PyMuPDF `find_tables()` on the same page

| Metric | Baseline | This parser |
|---|---|---|
| Row labels | 100.0%  (43/43) | 100.0%  (43/43) |
| Cell text | F1 100.0% | F1 100.0% |
| Column headers / period dates | not produced | 100.0%  (1/1) / 100.0%  (1/1) |
| Hierarchy (level, parent path) | not produced | 100.0%  (43/43) / 100.0%  (43/43) |
| Row type (section/item/total/net) | not produced | 100.0%  (43/43) |
| Unit, 訂正後 marker | not produced | 100.0%  (1/1) / 100.0%  (1/1) |

## 3. Accounting checks on the parsed workbook

PASS 8, PASS_ROUNDING 13, FAIL 0, SKIP 1

| Status | Check | Column | Row | Expected | Actual | Diff | Tolerance |
|---|---|---|---|---|---|---|---|
| PASS_ROUNDING | total_equals_components | 前連結会計年 | 流動資産合計 | 5863681 | 5863684 | 3 | 10 |
| PASS_ROUNDING | total_equals_components | 当連結会計年 | 流動資産合計 | 3377405 | 3377407 | 2 | 10 |
| PASS_ROUNDING | total_equals_components | 前連結会計年 | 有形固定資産合計 | 1429093 | 1429094 | 1 | 5 |
| PASS_ROUNDING | total_equals_components | 当連結会計年 | 有形固定資産合計 | 1352607 | 1352610 | 3 | 6 |
| PASS_ROUNDING | total_equals_components | 前連結会計年 | 無形固定資産合計 | 44260 | 44261 | 1 | 2 |
| PASS_ROUNDING | total_equals_components | 当連結会計年 | 無形固定資産合計 | 35868 | 35869 | 1 | 2 |
| PASS_ROUNDING | total_equals_components | 前連結会計年 | 投資その他の資産合計 | 197068 | 197069 | 1 | 4 |
| PASS_ROUNDING | total_equals_components | 当連結会計年 | 投資その他の資産合計 | 369361 | 369362 | 1 | 5 |
| PASS_ROUNDING | total_equals_components | 前連結会計年 | 固定資産合計 | 1670424 | 1670426 | 2 | 3 |
| PASS | total_equals_components | 当連結会計年 | 固定資産合計 | 1757841 | 1757841 | 0 | 3 |
| PASS | total_equals_components | 前連結会計年 | 資産合計 | 7534110 | 7534110 | 0 | 2 |
| PASS_ROUNDING | total_equals_components | 当連結会計年 | 資産合計 | 5135248 | 5135249 | 1 | 2 |
| PASS | gross_less_accum_equals_net | 前連結会計年 | 建物及び構築物（純額） | 197775 | 197775 | 0 | 2 |
| PASS_ROUNDING | gross_less_accum_equals_net | 当連結会計年 | 建物及び構築物（純額） | 239829 | 239828 | -1 | 2 |
| PASS | gross_less_accum_equals_net | 前連結会計年 | 機械装置及び運搬具（純額） | 390757 | 390757 | 0 | 2 |
| PASS | gross_less_accum_equals_net | 当連結会計年 | 機械装置及び運搬具（純額） | 336708 | 336708 | 0 | 2 |
| PASS_ROUNDING | gross_less_accum_equals_net | 前連結会計年 | リース資産（純額） | 63147 | 63146 | -1 | 2 |
| PASS_ROUNDING | gross_less_accum_equals_net | 当連結会計年 | リース資産（純額） | 41873 | 41872 | -1 | 2 |
| PASS | gross_less_accum_equals_net | 前連結会計年 | その他（純額） | 8439 | 8439 | 0 | 2 |
| PASS | gross_less_accum_equals_net | 当連結会計年 | その他（純額） | 24243 | 24243 | 0 | 2 |
| SKIP | assets_equal_liabilities_equity | * | * | None | None | None | 0 |

## 4. How much can a PASS be trusted? (fault injection)

Each numeric cell was corrupted one at a time (printed text and number together) and the accounting checks re-run. 'Detected' means at least one new FAIL.

| Injected error | Detected |
|---|---|
| last_digit_plus1 |  13.9%  (10/72) |
| middle_digit |  97.2%  (70/72) |
| leading_digit |  98.6%  (71/72) |
| transpose | 100.0%  (71/71) |
| sign_flip | 100.0%  (71/71) |
| drop_digit | 100.0%  (71/71) |
| **All** | ** 84.8%  (364/429)** |

Cells where *no* injected error was ever caught: either no check covers the cell, or every injected change stayed within the rounding tolerance (a value of 0, for example, can only change by +-1):

- 貸倒引当金 [col 1]
