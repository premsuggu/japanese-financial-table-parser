# Read-quality checks for OCR pages

Why: the accounting checks (balance identity, totals, formulas) only see numbers that break arithmetic. On OCR pages two
kinds of mistake pass them: a misread label (`繰延税金資産` read as `繰延税全資産`) and a digit error that keeps a total
consistent. Phase 3 adds two checks and a UI state for this. Plan: [../plans/phase3-plan.md](../plans/phase3-plan.md).
Measured effect: [../reports/phase3-metrics.md](../reports/phase3-metrics.md).

## 1. Read agreement (`crosscheck.py`)

Read the page twice and compare. Two reads rarely make the same mistake in the same cell, so a difference marks the cell.

* Text-layer page + OCR engine (option "Read twice and compare"): the second read is OCR.
* Scan: the second read is the same picture at 0.75x pixel size (`pipeline.SECOND_READ_SCALE`), which is a different
  input for the engine. The boxes are mapped back to the first read's frame (`ocr.ocr_geometry(rescale=...)`).
* `compare_reads(first, second)` pairs rows without trusting labels: first by identical amounts (a label difference is
  then a label misread), then by identical label (an amount difference is then a number misread). Unpaired rows are
  reported as seen by one read only. Amounts are compared by meaning (kind, number, sign of zero), so `204, 257` equals
  `204,257`.

```python
table = parse_source("scan.pdf", ocr=engine, verify=True)
table.meta["read_findings"]     # list[Finding], check="read_agreement", status WARN
```

Limit: a disagreement does not say which read is right, only where to look. Two reads of the same engine can also make
the same mistake.

## 2. Label vocabulary (`labelcheck.py`)

`data/labels_ja.txt` lists known account labels, built by `tools/build_label_list.py` from statement pages that pass all
their checks. A label that is not in the list but exactly one character away from a listed one (length at least 4) gets a
WARN naming the likely intended label. It is not flagged when the intended label is itself printed on the same page
(then it is a different line, as in 短期借入金 / 長期借入金). Nothing is corrected automatically. Labels far from every
known one are left alone because companies have their own account names.

Limit: the list comes from one company's filings, so it covers common accounts only.

## 3. UI and Excel

`ui_model.needs_review`: an OCR-read table that passes its checks is shown as **review** (not ok) unless two reads were
compared and agreed. A WARN from either check makes the table **check**. The Excel Metadata sheet records "Read via" and
"Reads".

## Where it runs

`validate.check_read_quality(table)` is called from `validate_tables`. The label check applies to tables whose
`meta["route"]` starts with `ocr`; read agreement applies when `meta["read_findings"]` exists. These metadata are not
stored in the Excel file, so `check` on a saved workbook re-runs the accounting checks but not these two (the findings
are in the workbook's Validation sheet).
