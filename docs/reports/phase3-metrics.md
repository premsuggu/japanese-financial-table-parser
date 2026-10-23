# Safety-net evaluation (YomiToku reads)

22 silver pages x 3 conditions. A page is *wrong* when the OCR table differs from the silver reference. *Accounting checks* = a check failed (what existed before this phase). *Label* = vocabulary check flagged a label. *Reads* = read agreement flagged a difference. *Any new* = label or reads. *False alarms* = right pages flagged.

Caveats: silver is not gold; one company; label list built from the same company's filings.

## second read at 0.75x pixels, label list = shipped list

| Condition | Pages | Wrong | Accounting checks | Label | Reads | Checks + new | False alarms (right pages) | Finding precision |
|---|---|---|---|---|---|---|---|---|
| clean (300 dpi) | 22 | 7 | 3 | 4 | 5 | 7 | 4/15 | 27/35 |
| scan-like (150 dpi, JPEG q40) | 22 | 4 | 4 | 1 | 4 | 4 | 3/18 | 37/43 |
| skewed (1 degree) | 22 | 4 | 3 | 1 | 4 | 4 | 1/18 | 17/19 |
| all | 66 | 15 | 10 | 6 | 13 | 15 | 8/51 | 81/97 |

## second read at 0.75x pixels, label list without the page's own document

| Condition | Pages | Wrong | Accounting checks | Label | Reads | Checks + new | False alarms (right pages) | Finding precision |
|---|---|---|---|---|---|---|---|---|
| clean (300 dpi) | 22 | 7 | 3 | 3 | 5 | 7 | 4/15 | 25/33 |
| scan-like (150 dpi, JPEG q40) | 22 | 4 | 4 | 0 | 4 | 4 | 3/18 | 36/42 |
| skewed (1 degree) | 22 | 4 | 3 | 0 | 4 | 4 | 1/18 | 15/17 |
| all | 66 | 15 | 10 | 3 | 13 | 15 | 8/51 | 76/92 |
