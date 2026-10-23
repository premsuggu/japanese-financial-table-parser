# The upload UI

Code: [app.py](../../src/fin_table_parser/app.py) (layout only), [ui_model.py](../../src/fin_table_parser/ui_model.py)
(data shaping, unit-tested), [document.py](../../src/fin_table_parser/document.py) (whole-document parsing).

## Start it

```
python -m fin_table_parser ui            # opens http://localhost:8501
python -m fin_table_parser ui --port 8765
```

The server is bound to `localhost` only (`.streamlit/config.toml`), because the page handles financial documents.
Usage statistics are switched off.

## What you see

1. Drop a PDF. Every page is read (a 109-page annual report takes under a second).
2. Sidebar: **Extract** chooses what to show (balance sheet / all financial statements / every table found),
   **Pages** limits the range (`all`, `1-5`, `8, 10-12`), **Advanced** picks the method and switches the table
   between printed text (`△2,979`, `－`, `※1`) and signed numbers.
3. Three numbers: tables found, checks passed, checks failed. A total that differs from the sum of its lines by
   rounding counts as passed.
4. One tab per table: the table with indentation, headings tinted and totals bold, a CSV button, and the page image
   beside it so the result can be compared with the source at a glance.
5. Tab icons: ✅ all checks hold, ⚠️ some check does not hold, 🚧 this layout is not fully supported yet.
6. **Checks** tab: every accounting check with expected vs printed value, worst first.
7. **Pages** tab: why each page without a table was skipped.
8. **Download Excel**: one workbook, one sheet per table, plus Validation and Metadata sheets.

## What counts as a table

`document.looks_like_statement`: at least 4 amount rows and most of them labelled. This keeps prose pages from
turning into fake tables (checked on a 19-page and a 109-page document).

## Honest limits

* Equity statements and note tables (grid-ruled) are shown with the 🚧 icon and a warning; their numbers can be
  incomplete. The default scope hides them.
* Scanned PDFs need an OCR engine (see the OCR route document); the page reports "text layer too small" otherwise.
