# OCR engine comparison

Reference ('silver'): 6 balance-sheet pages, one per company document, whose text-layer parse passes every accounting check (20260626b:p3, 20260626d:p3, ir202603q2:p6, ir202603q3:p6, ir202703q1:p6, S100YMK7:p43).
Each page is rendered as an image, read by the engine, and the words go through the production OCR function (`pipeline.parse_ocr_words`: de-skew + words-only extractor).

Caveats: silver is not gold (a mistake the text layer and the extractor share is invisible), and every page comes from the same company, so layout variety is small.

## clean (300 dpi)

| Engine | Cell F1 | Pages exact | Label acc. | Indent acc. | Char error rate | s/page | model load (s) | Wrong pages caught by checks | Failed runs |
|---|---|---|---|---|---|---|---|---|---|
| paddle | 83.7% | 0/6 | 69.0% | 100.0% | 5.67% | 73.3 | 4.5 | 1/6 | 0 |
| yomitoku | 97.2% | 4/6 | 98.7% | 100.0% | 1.30% | 11.5 | 2.5 | 1/2 | 0 |

## scan-like (150 dpi, JPEG q40)

| Engine | Cell F1 | Pages exact | Label acc. | Indent acc. | Char error rate | s/page | model load (s) | Wrong pages caught by checks | Failed runs |
|---|---|---|---|---|---|---|---|---|---|
| paddle | 90.7% | 0/6 | 64.8% | 100.0% | 4.57% | 68.9 | 1.8 | 1/6 | 0 |
| yomitoku | 92.8% | 3/6 | 98.4% | 100.0% | 3.64% | 11.4 | 12.1 | 1/3 | 0 |

## skewed (1 degree)

| Engine | Cell F1 | Pages exact | Label acc. | Indent acc. | Char error rate | s/page | model load (s) | Wrong pages caught by checks | Failed runs |
|---|---|---|---|---|---|---|---|---|---|
| paddle | 84.1% | 0/6 | 69.1% | 100.0% | 5.27% | 73.0 | 1.9 | 1/6 | 0 |
| yomitoku | 97.3% | 5/6 | 99.2% | 100.0% | 1.23% | 13.0 | 2.9 | 1/1 | 0 |
