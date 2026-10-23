# Layout variants beyond the sample company

The corpus is one company, so these layouts never appeared in it. Each is reproduced as a synthetic page
(`tests/synth.py`) and tested in `tests/integration/test_layouts.py`. All thresholds stay relative to the measured page
(word height, row pitch); nothing refers to coordinates.

| Layout | What went wrong before | What the parser does now | Code |
|---|---|---|---|
| Note-number column (注記) | the note numbers (5, 12) became a bogus value column and a bogus header | a leftmost column of bare 1-3 digit integers, while another column has thousands separators, is a note column: kept in `Row.note_ref`, shown as a "Note" column in the UI, written to the sheet's last column | `textgeom.find_note_column` |
| Label wrapped over two lines, amounts level with the first line | the second line became its own row with no amounts | a label-only line under an amount line (gap < 0.9 pitch, same indent) is the tail of that label | `textgeom._row_blocks` |
| Account form (勘定式): assets left, liabilities right | labels of both panels glued together, numbers in the wrong rows, still shown as checked | a label right of the first amount column that is followed by an amount starts a second panel; the page is split, each panel read, rows joined; title and unit come from the whole page | `textgeom.panel_boundary`, `_extract_panels` |
| IFRS statement of financial position | identity check skipped (liabilities-and-equity total not recognised) | 負債及び資本合計 and variants recognised | `labels.LIABILITIES_EQUITY_TOTALS` |
| Minus signs `−1,234`, `‐`, dashes | read as text, flagged unreadable | any of the minus/dash characters before digits is a negative sign (a lone dash is still "nil") | `normalize._MINUS_SIGNS` |
| Unit line forms `(単位 千円)`, `（千円）`, English | unit None | `find_unit` accepts these | `strategies/common.find_unit` |
| Grid lines, 1 or 3 value columns | (checked: already fine) | regression tests added | |

## Still not supported

* Statements printed as images inside an otherwise text page are only read through OCR if the text layer fails.
* Account form with more than two panels, or panels with different column counts (the page is rejected, not guessed).
* Parenthesised negatives with a sign inside, `(△1,234)`.
* Layouts I have not seen: only what a synthetic page can reproduce was tested. Real filings from other companies are
  the next test.
