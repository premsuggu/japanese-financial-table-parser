# Documentation index

Goal: given a PDF page with a Japanese consolidated balance sheet (layout may vary, may be scanned), extract the
table with row labels, values, columns, hierarchy, units and accounting signs, with no hard-coded coordinates.

Start with the top-level [../README.md](../README.md), then the project status in [worklog/phase3-worklog.md](worklog/phase3-worklog.md), then the explanation
documents in the order below.

## Explanations (how it works, for a new developer)

| # | Document | Topic |
|---|---|---|
| 1 | [explanations/01-how-the-parser-works.md](explanations/01-how-the-parser-works.md) | the row-band strategy, hierarchy, value conventions |
| 2 | [explanations/02-accounting-checks.md](explanations/02-accounting-checks.md) | why checks exist, rounding tolerance, fault injection |
| 3 | [explanations/03-band-free-core-and-ocr-route.md](explanations/03-band-free-core-and-ocr-route.md) | words-only strategy, footnote markers, hybrid OCR routing |
| 4 | [explanations/04-the-ui.md](explanations/04-the-ui.md) | the upload page |
| 5 | [explanations/05-read-quality-checks.md](explanations/05-read-quality-checks.md) | read agreement and label vocabulary for OCR pages |
| 6 | [explanations/06-layout-variants.md](explanations/06-layout-variants.md) | note-number column, wrapped labels, account form, IFRS, units |

## Research and plans

| Document | Topic |
|---|---|
| [research/01-table-parser-landscape.md](research/01-table-parser-landscape.md) | survey of industry table parsers and recommendation |
| [plans/phase1-implementation-plan.md](plans/phase1-implementation-plan.md) | original Phase 1 proposal (scope later narrowed) |
| [plans/phase2-plan.md](plans/phase2-plan.md) | validation, band-free core, hybrid OCR, evaluation |
| [plans/phase3-plan.md](plans/phase3-plan.md) | read agreement, label vocabulary, OCR state in the UI (approved) |
| [plans/phase4-plan.md](plans/phase4-plan.md) | other companies and layouts (the download and API parts were dropped) |

## Work logs and reports (what happened, measured)

| Document | Topic |
|---|---|
| [worklog/phase1-worklog.md](worklog/phase1-worklog.md) | Phase 1: problems found and fixed |
| [worklog/phase2-worklog.md](worklog/phase2-worklog.md) | Phase 2: same, plus current status |
| [worklog/phase3-worklog.md](worklog/phase3-worklog.md) | Phase 3: read agreement, label vocabulary, UI review state, measured effect |
| [worklog/phase4-worklog.md](worklog/phase4-worklog.md) | Phase 4: new layouts (synthetic), harder scan condition, known gaps |
| [worklog/installed-packages.md](worklog/installed-packages.md) | every install, its reason, and what can be removed |
| [reports/phase1-metrics.md](reports/phase1-metrics.md) | metrics of the sample page against the ground truth |
| [reports/phase3-metrics.md](reports/phase3-metrics.md) | how many wrong OCR pages the new checks catch (22 pages) |
| [reports/phase4-safety-with-photo-condition.md](reports/phase4-safety-with-photo-condition.md) | same, with the harder photo-like scan condition |
| [reports/ocr-comparison.md](reports/ocr-comparison.md) | OCR engine bake-off (YomiToku vs PaddleOCR) |
| [review/ground-truth-review.md](review/ground-truth-review.md) | the ground truth laid out for human review |

## Code map

`src/fin_table_parser/`: `pdf_io` (only module touching PyMuPDF) -> `strategies/{banded,textgeom}` -> `models` ->
`validate` + `rules/` -> `export` / `xlsx_reader`; `pipeline` chooses text layer or OCR (`ocr`); `document` and
`ui_model` / `app` serve the UI; `evaluate`, `report`, `ocr_eval` measure quality. Tests mirror this under `tests/`.
