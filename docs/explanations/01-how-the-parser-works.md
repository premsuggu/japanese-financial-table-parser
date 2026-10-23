# How the parser works (concepts)

Audience: a developer new to the project. Code: [src/fin_table_parser/](../../src/fin_table_parser/).

## The one-paragraph version

The PDF page already contains the exact text and also draws one coloured 12 pt **band** per table row.
We read the words and the drawn rectangles with PyMuPDF, use the bands as rows and the band
rectangles as columns, put each word into the cell it falls in, then add the financial-statement
knowledge (indentation = account hierarchy, `△` = negative, `－` = nil) and export an Excel file.
Because the digits are copied from the text layer and never re-typed or "recognised", the parser
cannot invent a number.

## Data flow

```
PDF page
  │  pdf_io.load_page        words (text + box), filled rectangles, black rules
  ▼
PageGeometry
  │  triage.check_banded     enough text? not garbled? has row bands?  else UnsupportedPage
  ▼
  │  strategies/banded.py    bands -> rows, band rectangles -> columns, header, unit, title
  │  hierarchy.py            label indent -> level -> parent path
  │  normalize.py            "△2,979" -> -2979, "－" -> nil, "△0" -> 0 (negative_zero)
  │  labels.py               row type: section / item / total / net
  ▼
Table (models.py)
  │  validate.py             accounting checks -> Findings
  │  export.py               Excel: one sheet per statement + Validation + Metadata
  ▼
workbook.xlsx  ──xlsx_reader.py──►  Table  ──validate / evaluate──►  report
```

Only `pdf_io.py` imports PyMuPDF, so the PDF library can be swapped by rewriting one file.

## The page geometry the strategy relies on

For `balance_sheet_after_correction.pdf`:

| Fact | Value |
|---|---|
| Row bands | 43 rectangles, 12 pt high, alternating blue and white |
| Columns | label 54.7-274.7, prior year 274.7-399.7, current year 399.7-524.6 (from the band rectangles) |
| Indent levels | label x0 clusters at 62 / 75 / 88 / 101 / 114 pt |
| Heavy top rule | 2.16 pt black rule at y=115.4; the header sits between it and the first band |
| Slivers | 0.7 pt white rectangles hidden behind rules, no text; they are not rows |

## Key ideas, each with the code that does it

**1. Rows come from bands, not from guessing at text positions.**
`find_bands` in [banded.py](../../src/fin_table_parser/strategies/banded.py) collects the distinct (y0, y1)
bands, drops slivers thinner than half the typical band, and drops a band that overlaps the previous
one by more than half (some pages paint a total row's band slightly taller, so two bands cover one row).

**2. Columns come from the band rectangles.** Each band is split into one rectangle per column
(`find_columns`). A word belongs to the column whose x-interval contains its centre. No
alignment guessing, and a nil `－` that is not right-aligned still lands in the right column.

**3. Hierarchy comes from the label indent.** `cluster_levels` in
[hierarchy.py](../../src/fin_table_parser/hierarchy.py) ranks the indent clusters on the page, so levels
are ranks, never absolute positions (one page starts at 62 pt, another at 75 pt).

```python
cluster_levels([62.3, 75.2, 88.2, 75.1])      # -> [0, 1, 2, 1]
build_paths(["資産", "有形", "その他", "無形", "その他"], [0, 1, 2, 1, 2])
# the two その他 get different paths: 資産>有形>その他 and 資産>無形>その他
```

In these statements a total (`流動資産合計`) sits at the **same indent as the rows it adds up**, so it
becomes a sibling of its components. The validator relies on this.

**4. Values keep what was printed.** [normalize.py](../../src/fin_table_parser/normalize.py):

| Printed | number | kind | notes |
|---|---|---|---|
| `2,002,429` | 2002429 | number | |
| `△2,979` | -2979 | number | `△` = negative |
| `△0` | 0 | number | `negative_zero=True`: the printed form is kept |
| `0` | 0 | number | |
| `－` | None | nil | **not zero**; checked before the sign logic because NFKC turns `－` into `-` |

**5. Underlines are a flag, not a correction marker.** A rule narrower than its column directly under a
number is recorded in `Row.underlined`. In the corrected page two of the three corrected cells have one,
but the original filing also has such underlines where nothing was corrected, so never treat the flag as
proof of a correction. Detect corrections by diffing the 訂正前 and 訂正後 versions.

**6. Rules can be filled rectangles or stroked lines**, depending on the PDF producer.
`pdf_io.load_page` normalises both to the same `Rect` form.

## No absolute coordinates

Nothing in the code is a page coordinate. Every geometric tolerance is a fraction of the page's own median
row height (`row_height` in `banded.py`), so the result does not depend on page size, zoom or font size.
`tests/integration/test_layout_invariance.py` proves it by re-rendering the sample page at 0.4x-3x with offsets.
What *is* assumed: the vocabulary in `labels.py`, and that rows are drawn as coloured bands.

## What happens on a page this parser cannot read

`triage.check_banded` raises `UnsupportedPage` with a reason (scanned page, garbled text layer, no row
bands). Nothing is guessed. This is the hook where an OCR/Docling fallback attaches in a later phase.

## Excel layout

One workbook per PDF, one sheet per statement, plus `Validation` and `Metadata`.
Columns: `Row | Level | Row type | Label (indented) | Path | numeric columns | Raw: columns | Underlined: columns | Rule above`.
Nil cells are empty in the numeric columns; the `Raw:` columns keep the printed text, so nil, `0` and `△0`
stay distinguishable. [xlsx_reader.py](../../src/fin_table_parser/xlsx_reader.py) reads this layout back.

## Known limits (Phase 1)

- Only banded statements (rows drawn as alternating bands). Grid-ruled tables (equity statement, segment
  notes) are Phase 2.
- Single-line labels. A label wrapped over two lines in one band is not handled yet.
- A continuation page without a title gets an empty statement name (it is not inherited from the previous page).
- Tested on one page plus its sibling pages from the same filing. Other companies' layouts are untested.
