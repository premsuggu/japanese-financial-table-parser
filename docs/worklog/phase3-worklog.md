# Phase 3 work log: trustworthy OCR pages

Plan (approved): [../plans/phase3-plan.md](../plans/phase3-plan.md). Explanation: [../explanations/05-read-quality-checks.md](../explanations/05-read-quality-checks.md).
Numbers: [../reports/phase3-metrics.md](../reports/phase3-metrics.md) (22 pages) and
[../reports/phase3-second-read-size.md](../reports/phase3-second-read-size.md) (choice of second-read size, 6 pages).

## Built

| Upgrade | Where | Notes |
|---|---|---|
| U1 read agreement | `crosscheck.py`, `pipeline._second_read`, `parse_source(verify=True)`, `pdf_io.rescale_image`, `ocr.ocr_geometry(rescale=)` | scan: second read at 0.75x pixels; text-layer page: second read by OCR. Opt-in |
| U2 label vocabulary | `labelcheck.py`, `data/labels_ja.txt` (236 labels), `tools/build_label_list.py` | warns only, never corrects |
| U3 UI | `ui_model.needs_review`, `app.py` ("Read twice and compare", state "review"), Excel Metadata "Read via / Reads" | OCR page without a compared second read shows "review", not a tick |
| Evaluation | `ocr_eval.collect_reads` (cached reads), `safety_runs`, `render_safety`, CLI `safety-eval` | |

Other fix found on the way: `pipeline.parse_geometry` let a banded-layout `ValueError` escape; it is now `UnsupportedPage`.
Tests: 170 pass (11 new unit tests, 3 new integration tests with a simulated engine that gets a digit wrong on its second read).

## Result (YomiToku, 22 silver pages x 3 conditions = 66 reads; 15 of them differ in meaning from the reference)

| Safety net | Wrong pages caught |
|---|---|
| accounting checks alone (before) | 10 / 15 |
| + label vocabulary | 3 to 6 of the 15 flagged by it alone (3 with the label list built without the page's own document) |
| + read agreement (0.75x) | 13 / 15 alone; all 15 together with the checks |
| False alarms | 8 of 51 right pages (16%) flagged by the new checks |
| Findings that point at a real error | 81 / 97 (84%) |

So the safety net goes from catching two thirds of wrong OCR pages to catching all of them in this sample, and one
right page in six is flagged for a look. Cost: reading twice doubles OCR time (about 12 s to 24 s a page), so it is opt-in.

Second-read size: 0.75x caught 4 of 4 wrong pages (6-page set), 1.33x only 2 of 4, so 0.75x was kept.

## Caveats (the numbers are indicative, not general)

* The 22 pages are 10 documents of one company, many near-identical, and the label list comes from the same company.
  The "without the page's own document" variant removes that overlap only partly, since quarterly filings share labels.
* A page counts as wrong when a value or a label differs in meaning from the silver reference; print-format differences
  (a space inside a number, full-width markers) do not count. Silver is not gold.
* Conditions are simulated (150 dpi JPEG q40, 1 degree rotation), not real scans.
* A disagreement between reads says where to look, not which read is right. Nothing is auto-corrected.
* Earlier OCR bake-off tables (Phase 2) counted print-format differences as wrong cells, so "pages exact" there is stricter
  than the value-level view used here.

## Not done from the upgrade list

Per-cell review with the page image, grid-ruled pages, note-number columns, other companies, real scans, independent
(XBRL) ground truth, speed.
