# The band-free core and the OCR route

Audience: a developer new to the project. Code: [strategies/textgeom.py](../../src/fin_table_parser/strategies/textgeom.py),
[ocr.py](../../src/fin_table_parser/ocr.py), [pipeline.py](../../src/fin_table_parser/pipeline.py).

## Why it exists

The first parser (`strategies/banded.py`) reads rows and columns from the shaded row bands a page draws. Two
facts made that insufficient:

* with the graphics removed (text layer untouched) it refused the page, although every label, amount, indent and
  header is still in the words;
* OCR output is *words with boxes and nothing else*: no bands, no rules.

So the second strategy works from words alone. Because OCR gives exactly that input, the same code is the
extractor for scanned pages: the hybrid is "change where the words come from", not "write a second parser".

## How it finds the table (words only)

```
words ──► text lines            centres closer than 0.4 x word height are one line
      ──► rejoin split signs    "△" + "2,979" -> "△2,979" (OCR engines often split them)
      ──► value columns         amounts are right-aligned: their right edges pile up at a few x positions
      ──► amount lines          a token counts only if it sits over a column (a page number does not)
      ──► header                the contiguous text block directly above the first amount, below the unit line
      ──► row blocks            lines closer than 0.75 x row pitch are one row (a label wrapped over two lines)
      ──► hierarchy             label indent clusters -> level -> parent path   (same code as the band strategy)
```

Every tolerance is a fraction of a length measured on the page itself (word height or row pitch). No absolute
points, so zoom, page size and font size do not matter (tested at 0.4x-3x).

Choosing a strategy (`pipeline.parse_geometry`): `auto` uses row bands when the page has at least 8, otherwise the
words alone. Both produce the same `Table`.

## Evidence that the two agree

On all 28 statement pages that both strategies can read (6 pages of the full filing, plus 22 pages from 10 company
documents) the band-free result equals the band-based result in rows, labels, indent levels, row types and every
printed value (`tests/integration/test_text_strategy.py`). Differences that remain by design: underline flags need
drawings, so the words-only route cannot set them.

## Footnote markers

An annual report prints markers next to amounts: `※１2,121,360` is note 1 and the amount 2,121,360. The marker is
removed *before* NFKC folding (`normalize.split_note_marker`), because after folding it would read as 12,121,360.
It is kept in `Value.notes` and the printed form stays in `Value.raw`. The ambiguous all-ASCII form
`※12,121,360` is reported by the `unparsed_cell` check rather than guessed.

## The OCR route

```
page ──► text layer healthy? ──yes──► banded or words-only strategy        route = "text-layer"
            │ no (too few words / garbled)
            ▼
        render at 300 dpi ─► OCR engine ─► words in pixels ─► points ─► words-only strategy   route = "ocr:<engine>"
```

* `parse_source(pdf, page, ocr=engine)` in `pipeline.py` makes the decision. OCR is used only when the text layer is
  unusable. A healthy page with "no table" is *not* sent to OCR (that would only waste time).
* Engines live in their own virtual environments (`.venv-paddle/`, `.venv-yomitoku/`). `ocr.SubprocessEngine` runs a
  worker script from `tools/ocr/` there and reads JSON back. The main environment stays light and an engine is
  removed by deleting one folder.
* OCR cleanup (`ocr.clean_text`): a bare dash-like token becomes the nil mark `－`; `Δ` / `▲` before digits become
  `△`. The long-vowel mark `ー` inside a word (リース資産) is never touched.
* The accounting checks arbitrate: the same `validate_tables` runs on OCR output, and `ocr_eval` measures how often
  they catch an OCR mistake.

## Robustness tested without a real engine

`tests/ocr_sim.py` replays the page's own words as OCR would return them: random box error and split signs. The
band-free strategy stays exact up to about 2 pt of random box error and with split signs
(`tests/integration/test_ocr_route.py`). At 3 pt the indent clustering starts to slip. Real engines at 300 dpi are
usually well inside 1 pt, but that is for the bake-off to confirm.

## Limits

* A label wrapped over two lines is one row only when the lines are closer than 0.75 row pitch (the amounts
  centred between them). A top-aligned wrap with normal line spacing still produces a separate label-only row.
* A column of small integers (a 注記番号 note-number column) would be taken as a value column.
* Grid-ruled pages (equity statement, notes) are not supported; the `unparsed_cell` check flags them.
