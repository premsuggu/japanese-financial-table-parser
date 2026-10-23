# Phase 3 plan: make scanned pages trustworthy (proposal, awaiting approval)

## Problem

On OCR pages the accounting checks catch only some wrong pages (bake-off: 1 of 2 clean, 1 of 3 scan-like). A misread
label (kanji) or a digit error that keeps the totals consistent passes silently. Goal: raise the share of wrong OCR
pages that get flagged, without flooding right pages with false alarms, and make OCR pages visible in the UI.

## Scope (three upgrades, in this order)

### U1. Multi-read agreement
Read the same page more than once and compare; disagreement marks the exact cell.
* Born-digital page + OCR engine available (opt-in, "Verify with OCR"): compare text-layer table with OCR table.
* Scan (no text layer): read twice at two render resolutions (for example 300 and 200 dpi) and compare.
* Rows are aligned by (parent path, label key) then by order; cells compared by column. New module `crosscheck.py`:
  ```python
  def compare_reads(a: Table, b: Table) -> list[Finding]   # check="read_agreement", WARN per differing cell/label
  ```
* Costs 2x OCR time (about 12 s a page becomes about 24 s); off by default for text-layer pages.
* Limit, stated up front: two reads of the same engine can make the *same* mistake. It reduces, not removes, risk.

### U2. Label vocabulary check
* Known-label list built from the corpus parses plus the labels in `rules/statement_rules.yaml`, stored as a data file
  (`src/fin_table_parser/data/labels_ja.txt`), not in code.
* A label not in the list but within edit distance 1 of a known one (length at least 4) gets a WARN with the suggestion.
  Never auto-corrected. Unknown and far from everything: no finding (companies have their own account names).
* Limit: the list comes from one company, so it can only flag near-misses of common accounts.

### U3. UI: show how each page was read
* Per page: "text layer" or "OCR (engine)". OCR tables get health "review" (new state) unless every check passed
  and read agreement found no differences. The Pages tab shows the source; the Excel Metadata sheet records it.
* Not in this phase: click-to-correct cells with the page image (listed as a later upgrade).

## Evaluation (how we find out whether it works)

Re-run the bake-off (YomiToku only; 6 silver pages x 3 conditions) with U1+U2 enabled and report:
* wrong pages flagged / wrong pages (recall of the safety net), before vs after;
* right pages flagged (false-alarm rate);
* cells flagged that were actually wrong (precision).
Plus fault-injection unit tests (a swapped kanji, a changed digit) and tests on the label list. Results go to
`docs/reports/phase3-metrics.md`. If recall barely improves, I will say so and not claim the upgrade.

## Technical details

* Files: `crosscheck.py`, `labelcheck.py`, data file, edits to `pipeline.py` (second read), `validate.py` (include new
  findings), `ui_model.py` / `app.py` (states, source column), `export.py` (Metadata), `ocr_eval.py` (new metrics).
* Tests under `tests/unit` and `tests/integration` (simulated OCR with injected errors, as in `tests/ocr_sim.py`).
* Dependencies: none new. Distance function already exists in `ocr_eval.edit_distance`.
* Quality gates: pytest, ruff, mypy strict, all green before done.

## Risks

* False alarms from harmless differences (spacing, full/half width): compare on normalised text/numbers.
* OCR time doubling: opt-in and per-page.
* Evaluation uses only 6 pages of one company, so the numbers are indicative, not general.

## Estimate

U2 and U3 are small; U1 is the largest. About one session each, evaluation last.

## Decisions needed from you

1. Approve this plan (or change it).
2. U1 default: opt-in only (my recommendation), or always on for scans?
3. May I build the label list from the corpus filings (one company), or do you have another source?
