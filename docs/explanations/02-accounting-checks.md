# Accounting checks (how we know whether the parse is right)

Code: [validate.py](../../src/fin_table_parser/validate.py). Tests: `tests/unit/test_validate.py`.

## Why

A balance sheet is self-checking. If a digit is mis-read, a total stops adding up. The checks use
only the numbers in the table, never the PDF, so they are an **independent** signal about parser errors.

They run on a `Table`, which can come from the parser or from an **Excel file** (`xlsx_reader`), so the
same checks validate the output workbook, including after someone edits it by hand:

```
python -m fin_table_parser check output/balance_sheet_after_correction.xlsx
```

## The checks

| Check | Rule | Tolerance |
|---|---|---|
| `numeric_matches_raw` | numeric cell equals the number parsed from the printed text | exact |
| `total_equals_components` | every `...合計` row equals the sum of its components | number of figures involved |
| `gross_less_accum_equals_net` | gross + (negative) accumulated depreciation = net | number of figures involved |
| `assets_equal_liabilities_equity` | 資産合計 = 負債純資産合計 across the pages of the balance sheet | exact |

How components are found (from the indent tree): a valued sibling contributes its value (or its `（純額）`
child's value if it has one); a section header (no values) contributes its closing `合計` child. Example
for `固定資産合計`: 有形固定資産合計 + 無形固定資産合計 + 投資その他の資産合計.

## Why there is a tolerance (this was measured, not assumed)

Every printed figure is rounded to 千円 on its own. On the sample page:

```
流動資産 items sum to 5,863,681; printed total 5,863,684   (diff 3, 10 items)
1,880,082 - 1,640,253 = 239,829; printed net 239,828        (diff -1)
```

Both are correct readings of the page. Exact equality would raise false alarms on a correct parse.
Statuses: `PASS` (exact), `PASS_ROUNDING` (differs, within tolerance), `FAIL`, `SKIP` (cannot evaluate,
reason given). The balance identity is exact because both sides are printed totals of the same quantity.

## What a PASS does not prove (fault injection)

[evaluate.py](../../src/fin_table_parser/evaluate.py) `mutation_test` corrupts one numeric cell at a time and
checks whether a new FAIL appears. On the sample page: errors in the middle or leading digit, transposed
digits, sign flips and dropped digits are caught 97-100% of the time, but **a +1 error in the last digit is
caught only 14% of the time**, because it hides inside the rounding tolerance. One cell (貸倒引当金, `△0`)
is not caught for any error: it is covered by the 流動資産合計 check, but its value is 0, so every
possible change is +-1 and falls inside the tolerance. So the checks are strong against gross mistakes and weak against tiny ones.
Details: [docs/reports/phase1-metrics.md](../reports/phase1-metrics.md).

## Using it across pages

Parse both halves of the balance sheet into one workbook and run `check`; the identity check then runs
instead of being skipped. Verified on the original filing's pages 8 and 9:
7,534,110 = 7,534,110 (prior year) and 5,135,249 = 5,135,249 (current year).

## Ideas not yet implemented

- Use the sign of the rounding difference. On the sample page every total is >= the sum of its parts,
  which suggests the filer truncates; a negative difference would then be suspicious. This would tighten the
  tolerance but rests on one page.
- Income-statement and cash-flow identities (Phase 2).

---

# Update (Phase 2): statement-specific rules, and what a tick means

## Rules per statement type

The first version had one generic rule (a 合計 row equals the sum of its siblings). It is right for a balance
sheet, and wrong for a flat income statement, where it produced false FAILs. Rules now come in three layers:

| Layer | Where | Example |
|---|---|---|
| Structural, from the indent tree | `validate.check_totals`, `check_net_rows` | 流動資産合計 = its items; gross + accumulated depreciation = net |
| Formulas per statement type | `rules/statement_rules.yaml` | `営業利益 = 売上総利益 - 販売費及び一般管理費合計` |
| Ties between statements | same file, `ties:` | cash-flow pre-tax profit = income-statement pre-tax profit |

A formula is one readable line (`"A = B + C - D"`, `|` for alternative labels, trailing `?` for optional terms), so a
new rule is a data change, not code. A rule whose target row is absent produces no finding (a page is never blamed
for a row it does not contain). Tolerance is the number of printed figures involved.

Advisory ties (cash-flow ending cash = balance-sheet cash) produce `WARN`, not `FAIL`, because restricted or
time deposits can make the two legitimately differ.

On the full filing (6 statement pages) this gives 80 checks with no failure, including the cross-page balance
identity and the cash-flow formulas that span two pages.

## Details learned from the corpus

* **Closing stock is subtracted.** In a cost-of-goods-sold build-up, `期末棚卸高` and transfers to other accounts are
  printed positive but deducted (`labels.component_sign`). Found on the standalone P&L of the annual report.
* **A loss line printed positive** (`営業損失 50`) is negative; `特別損失合計` is an ordinary positive total
  (`rules.engine.signed_value` only flips profit-line labels).
* **`unparsed_cell`.** A number column cell that cannot be read as a number is a FAIL (WARN if it has no digit).
  Before this check a footnote marker glued to a number turned the cell into text, and the sums quietly treated it as 0.

## What a green tick means in the UI

A table is ticked only if (a) its statement type is supported, (b) it has no unreadable cell, and (c) its group of
pages of the same type passed **at least one real accounting check** and failed none (`ui_model.group_health`).
"No check could run" is shown as *unverified*, never as a tick. Pages of one statement are judged together
because their checks use rows from several pages (a cash-flow statement's formulas span both of its pages).
Regression test: on the full filing, exactly pages 8, 9, 10, 11, 14 and 15 get a tick; the cover-page and
equity-statement tables do not.
