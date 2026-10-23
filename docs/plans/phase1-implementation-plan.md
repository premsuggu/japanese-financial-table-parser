# Phase 1 Implementation Plan: Financial-Statement Table Parser

> Status: **APPROVED with a narrower scope** (user decision): Phase 1 targets `balance_sheet_after_correction.pdf`
> only, Excel output, one workbook per PDF. Implemented; see [../worklog/phase1-worklog.md](../worklog/phase1-worklog.md).
> The text below is the original proposal and still describes Classes B/C and later phases as future work.
> Test corpus: `complete_pdf.pdf` (19 pages, original) + `balance_sheet_after_correction.pdf` (1 page, corrected).
> Background: [../research/01-table-parser-landscape.md](../research/01-table-parser-landscape.md)

---

## 1. Layout survey of `complete_pdf.pdf` (basis for the scope)

The PDF does **not** have one layout. The 12 table pages fall into three classes (measured with PyMuPDF):

| Class | Pages | Content | Visual structure | Vertical lines | `find_tables()` result |
|---|---|---|---|---|---|
| **A. Banded statement** | 8, 9, 10, 11, 14, 15 | Balance sheet (assets / liabilities+equity), income statement, comprehensive income, cash flow | Alternating blue/white row bands, black rules above totals, 3 logical columns (label, prior, current), indent hierarchy | 0 | 1 table, correct body, header lost |
| **B. Ruled matrix** | 12, 13 | Statement of changes in equity (prior year p12, current year p13) | Full grid, two stacked blocks per page (6-col and 9-col), 2-level spanning headers, 2-line row labels | 162-179 | 2 tables (10x6, 10x9) |
| **C. Ruled notes tables** | 17, 18, 19 | Segment information, per-share information | Full grid, spanning headers ("報告セグメント"), multi-line cells, prose cells, footnotes under the table, table continues across pages | 20-117 | 1-3 tables per page, 7 or 3 cols |

Class A is highly regular: the 6 pages share the same page furniture, band colours, column x-positions and indent
step (≈13 pt). Classes B and C need a different engine because their structure comes from the ruling grid.

**Answer to "one rule-based parser for all pages":** one *package* with a shared core (word/drawing extraction,
normalisation, validation, export) and **two extraction strategies** (banded-statement and ruled-grid), chosen per
page by a classifier. A single heuristic that handles all three classes would be brittle.
Phase 1 builds the core and strategy A; strategy B/C is Phase 2.

---

## 2. Objectives and scope

**Phase 1 objective:** convert every Class A page (pp. 8, 9, 10, 11, 14, 15 and the corrected page) into a correct,
validated table exported as Excel and CSV.

"Correct" means for every cell:
- exact numeric value (△ → negative, － → nil, `△0` and `0` kept distinct, full-width digits normalised),
- correct row label and **parent path** (hierarchy),
- correct column header (period label, unit 千円),
- an accounting self-check passes or the discrepancy is reported.

**In scope (Phase 1)**
- Page triage (text layer present and healthy, or flag the page for the future fallback)
- Class A extraction, header reconstruction, hierarchy, value normalisation
- Accounting validation with rounding tolerance
- Excel (one sheet per table, indented labels) and CSV export
- Evaluation harness and tests (including the 訂正前/訂正後 diff test)
- Documentation in `docs/`

**Out of scope (Phase 1):** Class B/C pages, OCR/VLM fallback implementation (only the routing hook and the
triage test), stitching of multi-page tables beyond BS pages 8+9, other companies' filings, XBRL ground truth.

**Proposed phases**

| Phase | Deliverable |
|---|---|
| 1 (this plan) | Core + Class A (6 pages) + validation + export + eval |
| 2 | Ruled-grid strategy: equity statement (matrix with spans), segment and per-share tables |
| 3 | Hybrid routing: triage to OCR/Docling fallback, optional VLM cross-check |
| 4 | More filings, XBRL ground truth, full benchmark |

---

## 3. Architecture

```
src/fin_table_parser/
  models.py        dataclasses: Word, Rule, Row, Cell, Table, ParsedPage
  pdf_io.py        PyMuPDF wrapper -> words + drawings (the only module importing pymupdf)
  triage.py        text-layer health check, page-class detection (A / B / C / unknown)
  furniture.py     remove running header, page number, section titles -> metadata
  normalize.py     NFKC, △/▲ -> '-', －/―/— -> nil, comma removal, Value dataclass
  strategies/
    banded.py      Class A extractor
    grid.py        (Phase 2)
  hierarchy.py     indent clustering -> level -> parent path
  validate.py      accounting checks with tolerance
  export.py        Excel + CSV writers
  pipeline.py      parse(pdf_path) -> list[Table]; picks strategy per page
  cli.py           python -m fin_table_parser input.pdf -o out/
tests/
  unit/            normalize, hierarchy, banded helpers, validate
  integration/     whole-page tests on the sample PDFs + diff test
  fixtures/        small golden JSON per page (reviewed by you)
```

Design rules: only `pdf_io.py` knows about PyMuPDF (swap to pdfplumber is a one-file change); every stage
takes and returns plain dataclasses (easy to test); no hard-coded row names. Statement-specific knowledge lives
in a small config (`config/statements.yaml`) that PyYAML (already installed) loads.

---

## 4. Algorithm for Class A (banded statement)

**Step 1: words and rules.** `page.get_text("words")` plus `page.get_drawings()`. Drawings split into
band fills (`fill=(0.8,0.93,1.0)` blue, `(1,1,1)` white) and thin black rules (`height < 1.5`).

**Step 2: furniture and table region.** The table starts at the `（単位：千円）` line / heavy top rule and ends at the
last band. Words above are titles (kept as metadata: statement name, section number). The running header and
`- N -` footer are dropped by position (outermost y-bands, repeated across pages).

**Step 3: rows from bands.** Each band rectangle is exactly one table row, which is more reliable than clustering
words by y. Assign a word to the band with the greatest y-overlap. Fallback if a page has no bands: cluster by
y-centre with a tolerance of half the median line height.

**Step 4: columns.** The label zone is everything left of the first numeric token. Value columns come from the
header words: group header words by x-overlap, giving N value columns, then assign numeric tokens by their **right
edge** (numbers are right-aligned) to the nearest column right edge.

**Step 5: header.** Header words (between the unit line and the first black rule) are joined per column, in
reading order, e.g. `前連結会計年度 (2025年3月31日)`. This is the row `find_tables()` dropped.

**Step 6: hierarchy.** Cluster label `x0` values per page (tolerance 2 pt) and rank them: level = rank of the cluster.
A stack gives the parent path, so `その他` becomes `資産の部 > 固定資産 > 有形固定資産 > その他`.

```python
def assign_levels(rows, tol=2.0):
    xs = sorted({r.label_x0 for r in rows})
    clusters = []
    for x in xs:                                   # 1-D clustering
        if clusters and x - clusters[-1][-1] <= tol:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    level_of = {x: i for i, c in enumerate(clusters) for x in c}
    stack = []                                     # (level, label)
    for r in rows:
        r.level = level_of[r.label_x0]
        while stack and stack[-1][0] >= r.level:
            stack.pop()
        r.path = tuple(l for _, l in stack) + (r.label,)
        stack.append((r.level, r.label))
```

**Step 7: value normalisation.**

```python
import unicodedata, re
NIL = {"－", "―", "—", "-", "ー"}

def parse_value(raw: str) -> Value:
    s = unicodedata.normalize("NFKC", raw).strip()
    if s in {unicodedata.normalize("NFKC", n) for n in NIL}:
        return Value(raw=raw, number=None, is_nil=True)
    neg = s.startswith(("△", "▲", "-"))
    s = re.sub(r"[△▲\-,]", "", s)
    return Value(raw=raw, number=-int(s) if neg else int(s), is_nil=False)   # △0 -> -0 == 0, raw preserved
```

Careful: NFKC maps `－` (U+FF0D) to ASCII `-`, so the nil check must run before the negative check. A unit test covers this.
`△0` is kept as `number=0, raw="△0"` so the information that the source printed a negative zero is not lost.

**Step 8: row typing.** `section` (no values), `item`, `subtotal/total` (label ends in 合計/計, or a full-column black rule
sits directly above), `net` (純額). The rule geometry is a secondary signal; the label is primary.

**Step 9: validation (`validate.py`).**
- Parent total vs sum of its direct children: `abs(total - sum) <= len(children)` (each item is rounded to 千円 separately; measured diffs on
  this PDF are 3 and 2 over 10 items).
- Gross + accumulated depreciation (negative) = net, expected exact.
- Cross-page: 資産合計 (p. 8) = 負債純資産合計 (p. 9).
- Income-statement chain and cash-flow reconciliation defined declaratively in `statements.yaml`.
- Output is a list of `Finding(severity, row path, expected, actual, tolerance)`, never an exception.

**Step 10: export.** Excel: one sheet per table with indented labels, a `Level` column, red negatives, a validation sheet and a metadata
sheet. CSV: one file per table with a `path` column. Word-width underlines are recorded as a low-trust `underlined` flag (they are *not*
a reliable correction marker; see research doc).

---

## 5. Dependencies

| Package | Status | Use |
|---|---|---|
| PyMuPDF 1.28.2 | installed | words, drawings (AGPL is fine for personal use) |
| PyYAML 6.0.2 | installed | statement config |
| pandas 2.2.3 | installed | optional DataFrame view, CSV |
| **openpyxl** | **not installed, needs your permission** | write `.xlsx` with formatting |
| **pytest** | **not installed, needs your permission** | unit and integration tests |
| **ruff, mypy** | **not installed, needs your permission** | lint and type check (AGENT.md: static analysis) |

Nothing will be installed until you approve. Python 3.12.

---

## 6. Testing and evaluation

All tests live under `tests/` (never the root).

1. **Unit tests:** `parse_value` (△, －, `△0`, full-width, commas), level clustering, row typing, tolerance logic.
2. **Integration tests:** each Class A page parses to the expected number of rows, columns and header text.
3. **Diff test (free ground truth):** parse the corrected page and the original p. 8, and diff the tables. Expected result is *exactly* these 3 cells:
   `投資有価証券` (current year) 53,925 -> 218,836; `関係会社株式` (current year) 166,033 -> 1,123; `貸倒引当金` (current year) 0 -> △0.
   Both versions also pass the 投資その他の資産合計 sum check within rounding (369,360 and 369,361 vs stated 369,362), so the oracle works on both.
4. **Accounting checks** as a correctness oracle on all 6 pages.
5. **Golden files:** one reviewed JSON per page. You review one page by hand, then these stay as regression tests. Golden files made by the parser alone would be circular, so the
   independent signals are the accounting checks, the diff test, and your spot check.
6. **Visual overlay:** a debug image per page (bands, columns, words coloured by cell) generated into a scratch/`tests/artifacts/` folder to make errors visible.

Metrics reported: cell exact-match precision/recall/F1, page exact-match rate, hierarchy (parent path) accuracy, validation pass rate.

---

## 7. Timeline (estimate, single developer)

| Step | Effort |
|---|---|
| Models, pdf_io, normalize + unit tests | 0.5 day |
| Banded strategy: rows, columns, header | 1 day |
| Hierarchy, row typing | 0.5 day |
| Validation + statements config | 1 day |
| Export (xlsx, csv) | 0.5 day |
| Integration/diff tests, golden review, overlay debug | 1 day |
| Docs (concept docs, work log) | 0.5 day |
| **Total** | **about 5 days** |

I will give a summary and snippets after each step, per AGENT.md, and wait for your confirmation at milestones.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Other pages differ subtly (e.g. p. 11, 15 are short; rows with no values) | Strategy is data-driven; verified on all 6 pages before sign-off |
| Indent levels differ per page (BS clusters 75/88/101/114; PL 62/75) | Rank clusters per page, no absolute x |
| Multi-line labels in some statements | Row-from-band handles it; word-cluster fallback tested |
| Rounding makes checks noisy | Tolerance = number of summands; report, don't fail |
| Golden files are circular | Independent oracles (see section 6) plus your manual review |
| Scope creep into Class B/C | Explicitly Phase 2 |
| Generalisation to other companies is unproven | Phase 4 corpus; only claim this filing family until tested |
| PyMuPDF AGPL if you ever distribute | Isolated in `pdf_io.py`; swap to pdfplumber if needed |

---

## 9. Decisions needed from you

1. Approve **Phase 1 scope** (Class A only, 6 pages), or include Class B/C now.
2. Approve installing **openpyxl, pytest, ruff, mypy** (or tell me which to skip).
3. Package layout under `src/` and tests under `tests/` as above, OK?
4. Excel layout: one workbook per PDF with one sheet per statement, OK?
