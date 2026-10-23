# Safety-net evaluation (YomiToku reads)

6 silver pages x 3 conditions. A page is *wrong* when the OCR table differs from the silver reference. *Accounting checks* = a check failed (what existed before this phase). *Label* = vocabulary check flagged a label. *Reads* = read agreement flagged a difference. *Any new* = label or reads. *False alarms* = right pages flagged.

Caveats: silver is not gold; one company; label list built from the same company's filings.

## second read at 0.75x pixels, label list = shipped list

| Condition | Pages | Wrong | Accounting checks | Label | Reads | Checks + new | False alarms (right pages) | Finding precision |
|---|---|---|---|---|---|---|---|---|
| clean (300 dpi) | 6 | 2 | 1 | 1 | 2 | 2 | 1/4 | 5/7 |
| scan-like (150 dpi, JPEG q40) | 6 | 1 | 1 | 0 | 1 | 1 | 0/5 | 8/8 |
| skewed (1 degree) | 6 | 1 | 1 | 0 | 1 | 1 | 0/5 | 2/2 |
| all | 18 | 4 | 3 | 1 | 4 | 4 | 1/14 | 15/17 |

## second read at 0.75x pixels, label list without the page's own document

| Condition | Pages | Wrong | Accounting checks | Label | Reads | Checks + new | False alarms (right pages) | Finding precision |
|---|---|---|---|---|---|---|---|---|
| clean (300 dpi) | 6 | 2 | 1 | 1 | 2 | 2 | 1/4 | 5/7 |
| scan-like (150 dpi, JPEG q40) | 6 | 1 | 1 | 0 | 1 | 1 | 0/5 | 8/8 |
| skewed (1 degree) | 6 | 1 | 1 | 0 | 1 | 1 | 0/5 | 2/2 |
| all | 18 | 4 | 3 | 1 | 4 | 4 | 1/14 | 15/17 |

## second read at 1.33x pixels, label list = shipped list

| Condition | Pages | Wrong | Accounting checks | Label | Reads | Checks + new | False alarms (right pages) | Finding precision |
|---|---|---|---|---|---|---|---|---|
| clean (300 dpi) | 6 | 2 | 1 | 1 | 1 | 2 | 1/4 | 4/6 |
| scan-like (150 dpi, JPEG q40) | 6 | 1 | 1 | 0 | 1 | 1 | 0/5 | 8/8 |
| skewed (1 degree) | 6 | 1 | 1 | 0 | 0 | 1 | 1/5 | 0/2 |
| all | 18 | 4 | 3 | 1 | 2 | 4 | 2/14 | 12/16 |

## second read at 1.33x pixels, label list without the page's own document

| Condition | Pages | Wrong | Accounting checks | Label | Reads | Checks + new | False alarms (right pages) | Finding precision |
|---|---|---|---|---|---|---|---|---|
| clean (300 dpi) | 6 | 2 | 1 | 1 | 1 | 2 | 1/4 | 4/6 |
| scan-like (150 dpi, JPEG q40) | 6 | 1 | 1 | 0 | 1 | 1 | 0/5 | 8/8 |
| skewed (1 degree) | 6 | 1 | 1 | 0 | 0 | 1 | 1/5 | 0/2 |
| all | 18 | 4 | 3 | 1 | 2 | 4 | 2/14 | 12/16 |
