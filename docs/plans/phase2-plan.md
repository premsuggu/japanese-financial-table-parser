# Phase 2 plan: layout-independent core, hybrid (OCR) routing, statement-aware validation

> Status: **PROPOSED, awaiting approval.** No code for this phase has been written. (AGENT.md: plan first.)
> Goal (from the user): given a PDF page with a Japanese consolidated balance sheet, possibly with slight
> layout variation and possibly scanned, extract the table preserving row labels, values, columns, hierarchy,
> units and accounting signs. No hard-coded coordinates.

## 1. Evidence that shapes the plan

| Finding | Source | Consequence |
|---|---|---|
| Parser needs coloured row bands; with graphics removed (text intact) it refuses | strip test | rows/columns/hierarchy must be derivable from words alone |
| OCR output = words + boxes, no drawings | design reasoning | the same band-free core serves scans: this is the hybrid |
| 23 balance-sheet pages in 10 company PDFs; 9 of 10 documents parse with 0 FAIL (決算短信, 中間, 訂正, 半期) | corpus survey | real test data exists now; 3 documents contain before/after correction pages |
| 有価証券報告書 pages: 11 FAIL on one page. Cause: footnote markers (`※1 2,121,360`) glued into the cell, cell read as text, silently counted as 0 | annual report p. 42 | parser needs marker handling and a loud warning for unreadable numeric cells; the checks caught it |
| Generic "total = sum of siblings" gives 2 false FAILs on the income statement (flat layout) | P&L probe | validation rules must be per statement type, not one generic rule |
| 20 statement-specific identities (P&L chain, comprehensive income, cash-flow ties) hold within +-1 on parsed numbers, incl. cross-statement ties (CF ending cash = BS cash; CF pre-tax profit = P&L pre-tax profit) | rules probe | other statements are usable as an automatic oracle, as the user proposed |

## 2. Steps (in this order)

### A. Statement-aware validation (about 1 day, no new packages)
- Declarative rule sets per statement type (`rules/balance_sheet.yaml`, `income_statement.yaml`, ...), e.g.
  `営業利益 = 売上総利益 - 販売費及び一般管理費合計`, tolerance = number of terms. PyYAML is already installed.
- Cross-statement ties: CF 期末残高 = BS 現金及び預金; CF 税金等調整前利益 = P&L; 包括利益 = 純利益 + その他の包括利益.
- Statement type detected from the title keyword, else from the row labels; unknown type -> only the safe checks.
- Loud finding `unparsed_cell` when a cell that looks numeric is not parsed (fixes the silent-zero hazard).
- Why first: it is the oracle for everything after it, and it fixes a false-positive bug that exists today.

### B. Band-free core (about 2 days, no new packages)
Input: `list[Word]` (+ optional drawings as hints). Output: the same `Table`.

```python
rows    = cluster_by_y(words, tol=0.25 * median_line_height)          # text lines
numbers = [w for w in words if looks_numeric(w.text)]
cols    = cluster_by_right_edge(numbers, tol=0.5 * median_char_width)  # right-aligned amount columns
label_x = leftmost word per row  -> cluster_levels(...)                # unchanged
header  = words above the first numeric row, grouped under each column by x-overlap
note_refs = strip ※N / (注N) tokens from value cells into Row.note_refs
```
All tolerances relative to measured text size (same rule as today: no absolute points).
Tests: (1) band-stripped page equals the ground truth; (2) on all corpus pages that parse today the band-free result equals the
band-based result; (3) existing scale/offset invariance test; (4) annual-report pages with ※ markers pass the checks.

### C. Hybrid routing (about 2-3 days; needs the OCR packages below)
- `WordSource` interface: `TextLayerSource` (today's PyMuPDF) and `OcrSource` (rasterise at ~300 dpi, OCR, return Words
  with boxes in the same coordinate space).
- Triage (exists) decides: healthy text layer -> text layer; otherwise OCR. Both can run; **the accounting checks
  arbitrate** and disagreement is reported, not hidden.
- Simulated scans for testing: rasterise corpus pages, then add noise, slight rotation/skew, lower dpi, JPEG artefacts.
- OCR bake-off on the rasterised sample page, scored with the same metrics (cell exact match, digit-level errors):
  candidates below. Keep the winner, uninstall the rest and report freed space.

### D. Evaluation on the corpus (about 1 day)
- Silver labels: text-layer parses that pass all checks (about 18-20 of the 23 pages). They score the OCR route automatically.
  Honest label: *silver*, not gold; a human review of a sample (the sheet in `docs/review/`) calibrates it.
- Pairs: 3 correction notices give 訂正前/訂正後 diffs as extra tests.
- Report: per-document cell F1, digit error rate, check pass rate, and the fault-injection detection rates.

## 3. Packages (all need your approval; large downloads were approved, deletion later)

| Candidate | Why | Notes |
|---|---|---|
| PaddleOCR (+ paddlepaddle) | strong general OCR with Japanese models, CPU capable | Apache-2.0 |
| YomiToku (+ torch) | built for Japanese documents, has table and layout models | open-source licence reported non-commercial: fine for personal use, to be verified in its repo |
| Tesseract (jpn) | classic baseline | needs a Windows binary installer = needs elevated rights; I would give you the manual steps, or skip |
| opencv-python-headless | rasterised-page preprocessing (deskew) | small |

Every install goes in a ledger (`docs/worklog/installed-packages.md`: package, size, reason, status). After the
bake-off I propose which to remove and wait for your OK before deleting anything. Expect torch-based installs of
several GB; I will report real sizes.

## 4. Risks

| Risk | Mitigation |
|---|---|
| OCR confuses `△` / `－` / `0` / `8` and breaks signs | these are the cases the checks and fault-injection test target; measure digit and sign errors separately |
| OCR splits or merges words, so columns misalign | cluster by right edge, not by word identity; report column-count disagreement |
| Silver labels share errors with the parser | human sample review; cross-check against XBRL where available (none offered by this IR page) |
| Same company only: layout variety limited | state it in every report; add other companies' filings when available |
| Heavy installs fail on Windows | one engine at a time, ledger, fall back to the other candidate |
| Scope creep to the grid-ruled pages (equity statement, notes) | stays Phase 3; balance sheet first |

## 5. Decisions needed

1. Approve the order A -> B -> C -> D (A and B need no new packages and can start immediately).
2. Approve the OCR candidates in section 3 (and say whether to skip Tesseract).
3. Review `docs/review/ground-truth-review.md` (10 minutes) so the metrics rest on a human-checked answer.
